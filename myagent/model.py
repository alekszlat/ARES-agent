"""LLM backend implementation for the agent.

This module exposes a concrete `LlamaCPP` backend that adapts the
`llama_cpp.Llama` client to the internal `BaseModel` interface used
by the rest of the agent system.

High-level responsibilities:
- Own the lifecycle of a single Llama model (weights + config).
- Hide llama-cpp-specific parameters (n_ctx, n_gpu_layers, n_threads).
- Provide a simple `generate(prompt: str) -> str` API to the Agent.
"""

from typing_extensions import Self
from llama_cpp import Llama
from .basetypes import BaseModel
import os


class LlamaCPP(BaseModel):
    """Concrete `BaseModel` implementation backed by `llama_cpp.Llama`.

    This class is the glue between:
    - the generic model interface (`BaseModel`) that the Agent depends on, and
    - the llama-cpp Python bindings (`llama_cpp.Llama`).

    It encapsulates:
    - how the model is loaded (file path, context size, GPU settings),
    - how text generation is invoked,
    - and default decoding parameters (e.g. `max_tokens`).

    In the overall system:
    - The Agent should depend only on `BaseModel`.
    - `LlamaCPP` is one possible backend; others (e.g. OpenAI, Gemma) can
      implement the same interface and be swapped without changing Agent code.
    """

    def __init__(self, name: str, model: Llama) -> None:
        """Initialize a `LlamaCPP` instance.

        Args:
            name: Human-friendly identifier for this model instance,
                usually derived from the model filename (e.g. "llama-3.2-3b...").
            model: An already-initialized `llama_cpp.Llama` client.

        Note:
            This constructor expects a fully-constructed `Llama` object.
            Prefer using `LlamaCPP.from_path(...)` in normal codepaths,
            which knows how to construct `Llama` with sensible defaults.
        """
        self.name = name
        self.model = model

        # Default maximum number of tokens to generate when the caller
        # does not override it. This keeps `generate()` calls predictable.
        self.max_tokens = 1024

    # -------------------------------------------------------------------------
    # Construction helpers
    # -------------------------------------------------------------------------

    @classmethod
    def from_path(
        cls,
        model_path: str,
        n_ctx: int = 10_000,
        n_gpu_layers: int = 50,
        n_threads: int = 16,
        **kwargs,
    ) -> Self:
        """Create a `LlamaCPP` instance from a GGUF model file.

        This is the main entry point used by the rest of the system.

        Args:
            model_path: Filesystem path to a GGUF model file.
            n_ctx: Context window (in tokens). Larger values increase memory
                usage (especially on GPU) but allow longer prompts.
            n_gpu_layers: Number of transformer layers to offload to the GPU.
                Higher values push more work to the GPU at the cost of VRAM.
            n_threads: Number of CPU threads to use for non-GPU work.
            **kwargs: Additional keyword arguments forwarded to `llama_cpp.Llama`.
                Use this to tweak sampling params, flash-attn, etc.

        Returns:
            A fully initialized `LlamaCPP` instance, ready to call `.generate()`.

        In the overall system:
            This method is typically called once at startup to construct the
            model backend from configuration (env vars, CLI args, or a config
            file). The resulting instance is then passed into the Agent.
        """
        model = Llama(
            model_path=model_path,
            n_ctx=n_ctx,
            n_gpu_layers=n_gpu_layers,  # offload these layers to GPU
            n_threads=n_threads,        # CPU threads for remaining work
            verbose=False,              # set to True when debugging model init
            **kwargs,
        )

        # Use the basename of the path as a human-readable identifier.
        name = os.path.basename(model_path)
        return cls(name=name, model=model)

    # -------------------------------------------------------------------------
    # Inference API
    # -------------------------------------------------------------------------

    def generate(self, prompt: str, **kwargs) -> str:
        """Generate a single text completion for the given prompt.

        Args:
            prompt: The full text prompt to send to the model. In this project,
                this is typically the result of `LlamaPrompt.get_generation_prompt()`.
            **kwargs: Optional generation parameters forwarded to `self.model`,
                such as `max_tokens`, `temperature`, `top_p`, etc.

        Returns:
            The model's first completion as a stripped string.

        Behavior:
            - If `max_tokens` is not provided, it falls back to the instance's
              default `self.max_tokens`.
            - Only the first choice from the underlying llama-cpp response is
              returned. If you need multiple candidates, extend this method or
              add a dedicated API.
        """
        if "max_tokens" not in kwargs:
            kwargs["max_tokens"] = self.max_tokens

        # Call into the underlying llama-cpp client. This returns a dict with a
        # `choices` list; each element represents one completion candidate.
        output = self.model(prompt, **kwargs)

        choices = output["choices"]
        # We currently only care about the first completion. If we later want
        # n-best outputs, this is the place to extend.
        response = choices[0]["text"].strip()
        return response
