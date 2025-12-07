"""Abstact Base Classes module.
This module defines the abstract base classes (ABCs) that outline
the core interfaces for models, prompts, and messages used in the agent system.
These ABCs serve as contracts that concrete implementations must adhere to,
ensuring consistency and interoperability across different components.

They help with modularity by allowing different implementations (e.g., various LLM backends,
prompt formats) to be swapped in and out without changing the overall system architecture.

"""
import abc
from typing import Optional, Literal
import pydantic

# -------------------------------------------------------------------------
# Abstract Base Classes
# -------------------------------------------------------------------------

class BaseModel:
    @abc.abstractmethod
    def generate(self, prompt: str, **kwargs) -> str:
        ...

class BaseMessage:
    @abc.abstractmethod
    def template(self, tool_enabled: bool = False) -> str:
        ...
    
class BasePrompt:
    @abc.abstractmethod
    def append_history(self, message:BaseMessage):
        ...
    
    @abc.abstractmethod
    def set_system_prompt(self, system_prompt:BaseMessage):
        ...

    @abc.abstractmethod
    def get_system_prompt(self, system_prompt:str):
        ...

    @abc.abstractmethod
    def get_user_prompt(self, question:str, tool_scheme:str='') -> BaseMessage:
        ...

    @abc.abstractmethod
    def get_assistant_prompt(self, answer:Optional[str]="") -> BaseMessage:
        ...
    
    @abc.abstractmethod
    def get_tool_result_prompt(self, result:str) -> BaseMessage:
        ...
    
    @abc.abstractmethod
    def get_generation_prompt(self, tool_enabled:bool=False, last:int=50) -> str:
        ...

class BaseModel:
    @abc.abstractmethod
    def generate(self, prompt: BasePrompt, **kwargs) -> str:
        ...


class AgentResponse(pydantic.BaseModel):
    type: Literal["text", "tool-calling", "tool-result"]
    data: str