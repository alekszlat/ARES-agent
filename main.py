# app/main.py
import sys
from PySide6.QtGui import QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from backend import AgentBackend
from bridge import Bridge

def main() -> None:
    app = QGuiApplication(sys.argv)
    engine = QQmlApplicationEngine()

    # 1) Create long-lived objects
    bridge = Bridge()
    backend = AgentBackend()

    # 2) Backend -> Bridge (UI state)
    backend.state_changed.connect(bridge.setState)
    backend.assistant_text.connect(bridge.setLastAssistantText)
#    backend.tool_event.connect(bridge.addLogLine)                # optional
#    backend.error.connect(bridge.setLastError)                   # optional

    # 3) Bridge -> Backend (user intent)
    bridge.sendRequested.connect(backend.submit_user_message)

    # 4) Expose bridge to QML
    engine.rootContext().setContextProperty("bridge", bridge)


    # 5) Load QML
    engine.load("UI/Main.qml")
    if not engine.rootObjects():
        sys.exit(1)

    # 6) Start backend thread
    backend.start()

    # 7) Shutdown
    app.aboutToQuit.connect(backend.shutdown)

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
