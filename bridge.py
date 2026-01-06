from typing import Optional
from PySide6.QtCore import QObject, Signal, Property

class Bridge(QObject):
    # Notify signal: tells QML that the 'state' property changed
    stateChanged = Signal()
    
    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._state = "idle"  # internal storage

    # Qt Property exposed to QML
    @Property(str, notify=stateChanged)
    def state(self) -> str:
        """Getter: QML reads bridge.state through this."""
        return self._state

    def setState(self, state: str) -> None:
        """
        Setter called from Python backend.
        Updates internal value and notifies QML.
        """
        if state == self._state:
            return  # avoid unnecessary updates/animations
        self._state = state
        self.stateChanged.emit()
