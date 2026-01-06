import QtQuick

Item {
    id: root

    // Inputs from Main.qml / bridge
    property string state: "idle"
    property real level: 0.0      // later

    // A base size you can tweak
    property real baseSize: 120

    width: baseSize
    height: baseSize

    // The circle
    Rectangle {
        id: circle
        anchors.centerIn: parent

        width: root.baseSize
        height: root.baseSize
        radius: width / 2
        border.color: "#3498db"
        border.width: 3
        color: "transparent"

        // Smoothly animate size changes
        Behavior on width { NumberAnimation { duration: 120 } }
        Behavior on height { NumberAnimation { duration: 120 } }

        // Example: change size based on state
        // (You can later make this depend on level too)
        Component.onCompleted: {
            // initial setup if needed
        }
    }

    // Example animation patterns (conceptual)
    // - idle: slow pulse
    // - thinking: faster pulse
    // - speaking: strong pulse (later driven by level)
    // - error: steady + different look
}
