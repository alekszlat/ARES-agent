import asyncio
from typing import Optional

from PySide6.QtCore import QObject, Signal, QThread

# --- your existing backend imports ---
from myagent import Agent, LlamaCPP, LlamaPrompt
from agentio import PiperConfig, PiperTTS

# -----------------------------
# Background thread that owns an asyncio loop + the Agent
# -----------------------------
class AgentBackend(QThread):
    # Signals emitted to the UI thread
    state_changed = Signal(str)            # "idle" | "thinking" | "speaking" | "error"
    assistant_text = Signal(str)           # final assistant text
    tool_event = Signal(str)               # tool-calling / tool-result text
    error = Signal(str)                    # error message

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._agent: Optional[Agent] = None
        self._tts: Optional[PiperTTS] = None
        self._shutdown_fut: Optional[asyncio.Future] = None

    def run(self) -> None:
        """Qt calls this in a separate OS thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        async def _startup() -> None:
            # Create and initialize your agent + TTS inside the backend thread
            model = LlamaCPP.from_path("./models/llama-3.2-3b-instruct-q4_k_m.gguf")
            prompt = LlamaPrompt()
            self._agent = Agent(name="Helper", model=model, prompt=prompt)

            # register MCP tools (server path as in your CLI script)
            self._agent.register_mcp(path="./run_server.py")

            self._tts = PiperTTS(PiperConfig(model_path="./models/en_GB-northern_english_male-medium.onnx"))

            # Keep the agent context open for the lifetime of the app
            await self._agent.__aenter__()

            self.state_changed.emit("idle")

        async def _shutdown() -> None:
            try:
                if self._agent is not None:
                    await self._agent.__aexit__(None, None, None)
            finally:
                self.state_changed.emit("idle")
                # Stop the event loop from inside itself
                self._loop.stop()

        # start up
        try:
            self._loop.run_until_complete(_startup())
        except Exception as e:
            self.error.emit(f"Backend startup failed: {e}")
            return

        # keep references so UI can ask us to stop
        self._shutdown_fut = asyncio.ensure_future(asyncio.sleep(10**9), loop=self._loop)  # placeholder

        # run event loop until stopped
        try:
            self._loop.run_forever()
        finally:
            # cleanup loop
            pending = asyncio.all_tasks(loop=self._loop)
            for t in pending:
                t.cancel()
            try:
                self._loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
            except Exception:
                pass
            self._loop.close()

    def submit_user_message(self, text: str) -> None:
        """Called from UI thread. Schedules work on the backend asyncio loop."""
        if not self._loop or not self._agent:
            self.error.emit("Backend not ready yet.")
            return

        asyncio.run_coroutine_threadsafe(self._handle_message(text), self._loop)

    async def _handle_message(self, text: str) -> None:
        try:
            self.state_changed.emit("thinking")

            # Call the agent
            response_parts = await self._agent.chat(text)

            final_text_chunks: list[str] = []

            for r in response_parts:
                if getattr(r, "type", None) == "text":
                    final_text_chunks.append(str(getattr(r, "data", "")))
                elif getattr(r, "type", None) == "tool-calling":
                    self.tool_event.emit(f"tool calling: {getattr(r, 'data', '')}")
                elif getattr(r, "type", None) == "tool-result":
                    self.tool_event.emit(f"tool result: {getattr(r, 'data', '')}")

            final_text = "\n".join([t for t in final_text_chunks if t.strip()]) or "(no text response)"
            self.assistant_text.emit(final_text)

            # Speak (run blocking TTS in a thread executor so asyncio loop stays responsive)
            if self._tts is not None and final_text.strip():
                self.state_changed.emit("speaking")
                loop = asyncio.get_running_loop()
                await loop.run_in_executor(None, self._tts.speak, final_text)

            self.state_changed.emit("idle")

        except Exception as e:
            self.state_changed.emit("error")
            self.error.emit(str(e))
            self.state_changed.emit("idle")

    def shutdown(self) -> None:
        """Called from UI thread on app exit."""
        if not self._loop:
            return
        asyncio.run_coroutine_threadsafe(self._shutdown_async(), self._loop)

    async def _shutdown_async(self) -> None:
        try:
            if self._agent is not None:
                await self._agent.__aexit__(None, None, None)
        finally:
            # stop the loop
            asyncio.get_running_loop().stop()