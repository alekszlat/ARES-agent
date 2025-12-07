"""MCP client utilities.

This module provides:
- `MCPClient`: a single-client wrapper around an MCP stdio server.
- `MCPClientManager`: a small orchestrator that manages multiple MCP clients,
  aggregates their tools/resources, and routes tool calls to the right client.

The goal is to hide the low-level MCP session / stdio details and expose a
simple async API the rest of the agent can use.
"""
import os
import asyncio
from contextlib import AsyncExitStack
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp import types

from . import utils
from . import errors


class MCPClient:
    """Thin wrapper around a single MCP stdio server.

    Responsibilities:
        - Spawn a server process using stdio (via `stdio_client`).
        - Maintain an MCP `ClientSession` bound to that process.
        - Expose convenience methods for listing tools/resources and calling
          tools on that server.
        - Manage its own async cleanup via an `AsyncExitStack`.

    In the overall system:
        - `MCPClient` represents one MCP server instance (e.g. "docs server",
          "filesystem server", etc.).
        - `MCPClientManager` owns multiple `MCPClient` instances.
    """

    def __init__(self) -> None:
        # Will hold the active MCP session once connected.
        self.session: ClientSession | None = None

        # A human-readable name derived from server initialization response.
        self.name: str = ""

        # AsyncExitStack manages all async contexts (stdio client, session, etc.)
        # so we can cleanly tear everything down with a single `aclose()` call.
        self.exit_stack = AsyncExitStack()

        # Read/write endpoints returned by stdio_client once connected.
        self.read = None
        self.write = None

    async def connect_to_server(self, server_script_path: str) -> None:
        """Start an MCP stdio server and initialize a session.

        Args:
            server_script_path:
                The path to the Python script that implements the MCP server.
                It will be executed as `python <server_script_path>`.

        Flow:
            1. Spawn the server process via stdio.
            2. Wrap the stdio pipes in a `ClientSession`.
            3. Send `initialize` to the server and store its name/version.
        """

        abs_path = os.path.abspath(server_script_path)
        print("Starting MCP server at:", abs_path)
        print("Exists?", os.path.exists(abs_path))

        if not os.path.exists(abs_path):
            raise FileNotFoundError(f"MCP server script not found: {abs_path}")

        server_params = StdioServerParameters(
            command="python",
            args=[abs_path],
            env=None,
        )

        # Spawn a subprocess running the MCP server over stdio.
        # `stdio_client` returns a (read, write) pair for communicating with it.
        stdio_transport = await self.exit_stack.enter_async_context(
            stdio_client(server_params)
        )
        self.read, self.write = stdio_transport

        # Initialize the MCP client session on top of the stdio transport.
        self.session = await self.exit_stack.enter_async_context(
            ClientSession(self.read, self.write)
        )

        # Perform the MCP initialize handshake to get server metadata.
        init_result = await self.session.initialize()
        server_info = init_result.serverInfo
        self.name = f"{server_info.name}(v{server_info.version})"

    async def list_tools(self) -> list[types.Tool]:
        """Return the list of tools exposed by this MCP server."""
        assert self.session is not None, "Client not connected"
        response = await self.session.list_tools()
        return response.tools

    async def list_resources(self) -> list[types.Resource]:
        """Return the list of resources exposed by this MCP server."""
        assert self.session is not None, "Client not connected"
        response = await self.session.list_resources()
        return response.resources

    async def call_tool(
        self, name: str, args: dict
    ) -> tuple[bool, list[types.TextContent]]:
        """Invoke a tool on the server by name.

        Args:
            name: Name of the tool to call (as exposed by `list_tools()`).
            args: JSON-serializable arguments for the tool.

        Returns:
            A tuple `(is_error, content)` where:
                - is_error: True if the server reported an error.
                - content: List of `TextContent` items returned by the tool.

        Note:
            The underlying MCP API may contain richer error information; this
            method keeps a simplified `(ok, content)` contract for now.
        """
        assert self.session is not None, "Client not connected"
        response = await self.session.call_tool(name, args)
        return response.isError, response.content

    async def cleanup(self) -> None:
        """Close all async resources (session, stdio transport, etc.)."""
        await self.exit_stack.aclose()


class MCPClientManager:
    """Coordinator for multiple MCP clients.

    Responsibilities:
        - Track multiple MCP server script paths.
        - Create and initialize corresponding `MCPClient` instances.
        - Aggregate tool/resource metadata across all servers.
        - Route tool calls to the owning client based on tool name.

    In the overall system:
        - This is the layer the Agent or higher-level orchestration code uses
          when it wants "all tools from all MCP servers" without manually
          managing individual clients.
    """

    def __init__(self) -> None:
        # Paths to server scripts that should be launched.
        self.server_path: list[str] = []

        # One `MCPClient` per server path, created during `init_mcp_client()`.
        self.clients: list[MCPClient] = []

        # Map: tool_name -> index into `self.clients`.
        # Used to route MCP tool calls to the correct server.
        self.tool_map: dict[str, int] = {}

        # Map: server_name -> {tool_name -> description}
        # Aggregated tool documentation for user-facing UIs or logging.
        self.tool_info: dict[str, dict[str, str]] = {}

        # Map: normalized_resource_uri -> index into `self.clients`.
        self.resource_map: dict[str, int] = {}

    def register_mcp(self, server_path: str) -> None:
        """Register an MCP server script path to be managed.

        This does *not* start the server yet; it only records the path.
        Actual connections are established in `init_mcp_client()`.

        Note:
            Currently only stdio-based MCP servers are supported.
        """
        self.server_path.append(server_path)

    async def init_mcp_client(self) -> None:
        """Instantiate and connect an `MCPClient` per registered server path."""
        for path in self.server_path:
            client = MCPClient()
            await client.connect_to_server(path)
            self.clients.append(client)

    async def clean_mcp_client(self) -> None:
        """Cleanly shut down all managed MCP clients."""
        for client in self.clients:
            await client.cleanup()

    def get_server_names(self) -> list[str]:
        """Return a list of non-empty server display names."""
        return list(filter(lambda x: x, (c.name for c in self.clients)))

    async def get_func_scheme(self) -> list[dict[str, str]]:
        """Collect and return a combined tool schema list from all servers.

        Returns:
            A list of tool schema dicts, one entry per tool across all clients.

        Side effects:
            - Populates `self.tool_map` so we can later route tool calls.
            - Populates `self.tool_info` with per-server tool descriptions.
        """
        func_scheme_list: list[dict[str, str]] = []

        for idx, client in enumerate(self.clients):
            tools = await client.list_tools()

            for tool in tools:
                # Tool schema normalized to a JSON-friendly shape.
                func_scheme_list.append(utils.tool2dict(tool))

                # Remember which client owns this tool name.
                self.tool_map[tool.name] = idx

                # Cache tool descriptions grouped by server name.
                server_name = self.clients[idx].name
                func_info = self.tool_info.get(server_name, {})
                func_info[tool.name] = tool.description
                self.tool_info[server_name] = func_info

        return func_scheme_list

    async def get_resource_list(self) -> list[dict[str, str]]:
        """Collect and return a combined resource list from all servers.

        Returns:
            A list of resource dicts (JSON-friendly) across all clients.

        Side effects:
            - Populates `self.resource_map` to map resource URIs to clients.
        """
        resource_list: list[dict[str, str]] = []

        for idx, client in enumerate(self.clients):
            resources = await client.list_resources()

            for rsrc in resources:
                resource_list.append(utils.resource2dict(rsrc))

                # Normalized URI is used as a key to find which client to ask.
                normalized_uri = utils.uri2path(rsrc.uri)
                self.resource_map[normalized_uri] = idx

        return resource_list

    async def call_tool(
        self, name: str, param: dict
    ) -> tuple[bool, list[types.TextContent]]:
        """Route a tool call to the correct MCP client by tool name.

        Args:
            name: Name of the tool to call.
            param: Arguments dict passed through to the underlying MCP server.

        Returns:
            `(is_error, content)` as returned by the underlying `MCPClient`.

        Raises:
            MCPException: If the tool name is unknown.
        """
        idx = self.tool_map.get(name, -1)

        if idx < 0:
            raise errors.MCPException(f"Unknown tool name {name!r}")

        client = self.clients[idx]
        return await client.call_tool(name, param)


# ---------------------------------------------------------------------------
# Manual test harness
# ---------------------------------------------------------------------------

async def test():
    client = MCPClient()
    path = 'myagent/test_server.py'

    try:
        await client.connect_to_server(path)

        tools = await client.list_tools()
        print("Tools:", [t.name for t in tools])

        # Call echo_tool
        ok, content = await client.call_tool("echo_tool", {"text": "Hello MCP"})
        print("echo_tool ->", ok, [c.text for c in content])

        # Call reverse_tool
        ok, content = await client.call_tool("reverse_tool", {"text": "Hello MCP"})
        print("reverse_tool ->", ok, [c.text for c in content])

    finally:
        await client.cleanup()


if __name__ == "__main__":
    asyncio.run(test())
