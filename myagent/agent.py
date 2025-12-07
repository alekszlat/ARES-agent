"""Agent orchestration logic.

This module defines the `Agent` class, which is responsible for:
- Managing the lifecycle of MCP (Model Context Protocol) clients.
- Building prompts using a `BasePrompt` implementation.
- Calling an underlying LLM (`BaseModel`) to:
  - decide whether tools should be called,
  - generate tool call signatures,
  - incorporate tool outputs into a final user-facing answer.
- Returning structured `AgentResponse` objects that describe what happened
  (tool calls, tool results, final text answer).

In the overall system:
- The Agent is the main entry point for "ask a question and get an answer".
- It orchestrates interplay between:
  - prompt builder (`BasePrompt`)
  - LLM backend (`BaseModel`)
  - MCP tools/resources (`MCPClientMaanger`)
"""

from .prompt import BasePrompt
from .model import BaseModel
from .client import MCPClientManager
from .basetypes import AgentResponse
from . import utils
import json
import re
import logging


# High-level, system-level instruction. This gets injected into the prompt
# to define the assistant's behavior in general (without tools).
SYSTEM_PROMPT = """You are a helpful assistant"""

# Template used when we want the model to decide which tools to call.
# The `{function_scheme}` placeholder is later filled with a JSON description
# of the available MCP tools. The agent uses this to "bootstrap" tool calling:
# the model is instructed to return only a tool call signature (no prose).
TOOL_CALL_PROMPT = """You are an expert in composing functions. You are given a question and a set of possible functions. 
Based on the question, you will need to make one or more function/tool calls to achieve the purpose. 
If none of the function can be used, point it out. If the given question lacks the parameters required by the function,
also point it out. You should only return the function call in tools call sections.

If you decide to invoke any of the function(s), you MUST put it in the format of [func_name1(), func_name2(params_name1=params_value1, params_name2=params_value2...), func_name3(params)]
You SHOULD NOT include any other text in the response.

Here is a list of functions in JSON format that you can invoke.

{function_scheme}
"""

# -------------------------------------------------------------------------
# Logging setup
# -------------------------------------------------------------------------

logger = logging.getLogger("agent")
logger.setLevel(logging.DEBUG)

handler = logging.StreamHandler()

formatter = logging.Formatter("[%(asctime)s] [%(levelname)s] %(message)s")
handler.setFormatter(formatter)

logger.addHandler(handler)


# -------------------------------------------------------------------------
# Agent
# -------------------------------------------------------------------------

class Agent:
    """Tool-using LLM agent.

    The Agent ties together:
    - `BaseModel`: the underlying LLM backend (e.g. `LlamaCPP`).
    - `BasePrompt`: the prompt manager, which builds model-ready text prompts.
    - `MCPClientMaanger`: the manager responsible for discovering and calling
      MCP tools and resources.

    Typical lifecycle:
        async with Agent(name, model, prompt) as agent:
            responses = await agent.chat("some question")

    The Agent:
    - Adds tool descriptions and resources into the prompt.
    - Asks the LLM whether to call tools and parses the returned tool signature.
    - Executes those tools via MCP.
    - Feeds the tool results back into the LLM to produce a final answer.
    - Returns a list of `AgentResponse` entries describing each step.
    """

    def __init__(self, name: str, model: BaseModel, prompt: BasePrompt) -> None:
        """Initialize the agent with its core dependencies.

        Args:
            name: Human-readable name for this agent instance.
            model: Concrete implementation of `BaseModel` (LLM backend).
            prompt: Concrete implementation of `BasePrompt` (prompt builder).
        """
        self.name: str = name

        # LLM backend (e.g. LlamaCPP). The Agent never depends on a specific
        # model implementation; it only calls the BaseModel interface.
        self.llm: BaseModel = model

        # Prompt builder responsible for constructing system/user/tool prompts
        # in the format expected by the underlying LLM.
        self.prompt: BasePrompt = prompt

        # Manages connections to MCP servers and exposes tool/resource APIs.
        self.mcp_manager = MCPClientManager()

        # Cached prompt fragments built from MCP tool schemas and resources.
        # These are injected into TOOL_CALL_PROMPT so the model knows which
        # functions/resources it can use.
        self.func_scheme_prompt = ""
        self.resource_prompt = ""

        # Regex pattern to detect whether the model response looks like a tool
        # call list in the required format:
        #   [func1(), func2(arg="value"), ...]
        self.tool_pattern = re.compile(
            r'\[([A-Za-z0-9\_]+\(([A-Za-z0-9\_]+=\"?.+\"?,?\s?)*\),?\s?)+\]'
        )

        # Regex pattern to extract individual function calls from the tool
        # call list, capturing:
        #   - function name
        #   - parameter string inside the parentheses
        self.func_pattern = re.compile(
            r'(?P<function>[A-Za-z0-9\_]+)\((?P<params>[A-Za-z0-9\_]+=\"?.+\"?,?\s?)*\)'
        )

    # ---------------------------------------------------------------------
    # Read-only properties
    # ---------------------------------------------------------------------

    @property
    def model_name(self) -> str:
        """Return the underlying model's name."""
        return self.llm.name

    @property
    def server_list(self) -> list[str]:
        """Return the list of MCP server names registered with this agent."""
        return self.mcp_manager.get_server_names()

    # ---------------------------------------------------------------------
    # MCP registration and lifecycle
    # ---------------------------------------------------------------------

    def register_mcp(self, path: str) -> None:
        """Register a new MCP server by path (e.g. config or executable path)."""
        self.mcp_manager.register_mcp(path)

    async def init_agent(self) -> None:
        """Initialize MCP clients and seed the prompt with system information.

        This method:
        - connects to MCP servers,
        - fetches the available tool schemas and resource list,
        - serializes them into JSON for use in TOOL_CALL_PROMPT,
        - and configures the base system prompt used by the LLM.
        """
        await self.mcp_manager.init_mcp_client()

        func_scheme_list = await self.mcp_manager.get_func_scheme()
        resource_list = await self.mcp_manager.get_resource_list()

        # Cache JSON-serialized tool and resource descriptions so we can
        # inject them into tool-calling instructions later.
        self.func_scheme_prompt = json.dumps(func_scheme_list)
        self.resource_prompt = json.dumps(resource_list)

        # Install the system prompt into the prompt builder so all future
        # generation prompts start from the same high-level instruction.
        p = self.prompt.get_system_prompt(SYSTEM_PROMPT)
        self.prompt.set_system_prompt(p)

    async def clean_agent(self) -> None:
        """Tear down MCP clients and release any external resources."""
        await self.mcp_manager.clean_mcp_client()

    # Async context manager support:
    #   async with Agent(...) as agent: ...
    async def __aenter__(self) -> "Agent":
        await self.init_agent()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.clean_agent()

    # ---------------------------------------------------------------------
    # Tool parsing and execution
    # ---------------------------------------------------------------------

    def _is_tool_required(self, response: str) -> bool:
        """Return True if the LLM response matches the expected tool-call format.

        The tool-call format is a bracketed list of function calls, e.g.:

            [func1(), func2(arg="value"), func3(...)]

        If the response matches this pattern, we treat it as a tool invocation
        request rather than a final answer.
        """
        return self.tool_pattern.match(response)

    def get_func_props(self, response: str):
        """Yield (function_name, params_dict) pairs parsed from a tool-call string.

        The input is expected to be a string like:

            [func1(), func2(arg1="value1", arg2="value2")]

        This method:
        - strips the outer brackets,
        - splits by commas to get individual signatures,
        - uses `self.func_pattern` to extract:
            - the function name
            - the raw parameter string
        - uses `utils.param2dict` to convert the parameter string into a dict.
        """
        for signature in response.strip("[]").split(","):
            signature = signature.strip()

            if res := self.func_pattern.findall(signature):
                name, param_string = res[0]
                yield name, utils.param2dict(param_string)

    async def get_result_tool(self, response: str) -> list[dict]:
        """Execute tools requested by the LLM and collect their outputs.

        Args:
            response: Raw tool call response from the LLM in the bracketed
                function-call format (e.g. `[func1(), func2(arg="x")]`).

        Returns:
            A list of dicts, each with:
              - "name": tool name
              - "output": list of text outputs from that tool
        """
        result_list: list[dict] = []

        for name, param in self.get_func_props(response):
            res = await self.mcp_manager.call_tool(name, param)
            is_err, content_list = res
            logger.debug(
                f"mcp function({name}) with param({param}) has results({content_list})"
            )

            # Extract plain text from MCP content objects.
            results = [c.text for c in content_list]

            result_list.append({"name": name, "output": results})

        return result_list

    # ---------------------------------------------------------------------
    # Main chat flow
    # ---------------------------------------------------------------------

    async def chat(self, question: str, **kwargs) -> list[AgentResponse]:
        """Run a full agent interaction for a single user question.

        High-level flow:
            1. Ask the LLM (with tool-calling instructions) whether tools
               should be called, and if so, which ones and with what params.
            2. If tools are requested:
                - execute them via MCP,
                - feed their results back into the conversation,
                - ask the LLM again for a final natural-language answer.
            3. Return a list of `AgentResponse` objects describing:
                - tool-calling request,
                - tool results,
                - final text answer.

        Args:
            question: The user's natural-language question.
            **kwargs: Extra generation parameters forwarded to the underlying
                `BaseModel.generate` (e.g. temperature, max_tokens).

        Returns:
            A list of `AgentResponse` entries in chronological order
            (tool-calling, tool-result, final text).
        """
        response_list: list[AgentResponse] = []

        logger.debug(f"agent got question({question})")

        # Build the tool-calling instruction prompt by injecting the function
        # schema JSON into the TOOL_CALL_PROMPT template.
        tool_scheme = TOOL_CALL_PROMPT.format(
            function_scheme=self.func_scheme_prompt
        )

        # Build the user message containing both the question and the tool
        # instructions, then append it to the conversational history.
        p = self.prompt.get_user_prompt(question=question, tool_scheme=tool_scheme)
        self.prompt.append_history(p)

        # Ask the LLM what to do next, with tools enabled. The prompt builder
        # will include system prompt + history + an empty assistant turn.
        response = self.llm.generate(
            self.prompt.get_generation_prompt(tool_enabled=True), **kwargs
        )

        # Strip noise that sometimes appears around tool call outputs
        # (angle brackets, braces, backticks, etc.). This is a temporary
        # heuristic and may be tightened later.
        response = response.strip().lstrip("()<>{}`")

        logger.debug(f"llm generated response ({response})")

        # If the LLM chose to make tool calls, handle the full tool-calling flow.
        if self._is_tool_required(response):
            logger.debug("agent tool required")
            response_list.append(
                AgentResponse(type="tool-calling", data=response)
            )

            # Store the tool-call message in history as an assistant message.
            p = self.prompt.get_assistant_prompt(answer=response)
            self.prompt.append_history(p)

            # Execute the tools and collect their outputs.
            result = await self.get_result_tool(response)
            result = json.dumps(result, ensure_ascii=False)

            response_list.append(
                AgentResponse(type="tool-result", data=result)
            )
            logger.debug(f"got result of each tool ({result})")

            # Add the tool results to the conversation so the LLM can
            # incorporate them into a final answer.
            p = self.prompt.get_tool_result_prompt(result=result)
            self.prompt.append_history(p)

            # Ask the LLM for a final natural-language answer, this time with
            # tools disabled and a shorter history window (last 3 messages).
            response = self.llm.generate(
                self.prompt.get_generation_prompt(
                    tool_enabled=False, last=3
                ),
                **kwargs,
            )

            logger.debug(f"llm generated final response({response})")

        # In all cases, append the final textual answer to the response list.
        response_list.append(AgentResponse(type="text", data=response))

        # Store the final assistant answer into the prompt history so it
        # contributes to future context.
        p = self.prompt.get_assistant_prompt(answer=response)
        self.prompt.append_history(p)

        return response_list
