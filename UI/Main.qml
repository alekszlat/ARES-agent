import QtQuick
import QtQuick.Window

Window {
    width: 400
    height: 400
    visible: true
    title: "Agent UI"
    

    Orb {
        anchors.centerIn: parent

        // Bind orb inputs to Python bridge
        state: bridge.state
        // speaking: bridge.state === "speaking"   // optional
        // level: bridge.level                    // later
    }
}
