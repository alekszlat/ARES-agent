from typing import Optional
from PySide6.QtCore import QObject, Signal, Property, Slot

class Bridge(QObject):
    # Notify signals (QML re-evaluates bindings when these emit)
    stateChanged = Signal()
    outputTextChanged = Signal()

    # UI -> backend intent
    sendRequested = Signal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._state = "idle"
        self._output_text = ""

    # ---------- QML-callable method ----------
    @Slot(str)
    def sendUserMessage(self, text: str) -> None:
        text = (text or "").strip()
        if not text:
            return

        # Optional: add the user's message to the visible log
        self.appendOutput(f"You: {text}\n")

        self.sendRequested.emit(text)

    # ---------- Properties exposed to QML ----------
    @Property(str, notify=stateChanged)
    def state(self) -> str:
        return self._state

    @Property(str, notify=outputTextChanged)
    def outputText(self) -> str:
        return self._output_text

    # ---------- Setters called from backend ----------
    @Slot(str)
    def setState(self, state: str) -> None:
        if state == self._state:
            return
        self._state = state
        self.stateChanged.emit()

    @Slot(str)
    def appendOutput(self, text: str) -> None:
        """Append text to the UI output log."""
        if not text:
            return
        self._output_text += text
        self.outputTextChanged.emit()

    @Slot(str)
    def setLastAssistantText(self, text: str) -> None:
        """Add the assistant response to the UI output log."""
        text = (text or "").strip()
        if not text:
            return
        self.appendOutput(f"Assistant: {text}\n")
