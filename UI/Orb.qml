import QtQuick

Item {
    id: root

    // Inputs from Main.qml / bridge
    property string state: "idle"

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

        // Visible defaults
        color: "transparent"
        border.width: 3
        border.color: "#3498db"

        // One knob we animate per-state
        property real pulseScale: 1.0
        scale: pulseScale
    }

    // IDLE: slow pulse
    SequentialAnimation {
        running: root.state === "idle"
        loops: Animation.Infinite
        NumberAnimation { target: circle; property: "pulseScale"; from: 1.00; to: 1.06; duration: 1400; easing.type: Easing.InOutSine }
        NumberAnimation { target: circle; property: "pulseScale"; from: 1.06; to: 1.00; duration: 1400; easing.type: Easing.InOutSine }
    }

    // THINKING: faster pulse
    SequentialAnimation {
        running: root.state === "thinking"
        loops: Animation.Infinite
        NumberAnimation { target: circle; property: "pulseScale"; from: 1.00; to: 1.10; duration: 550; easing.type: Easing.InOutSine }
        NumberAnimation { target: circle; property: "pulseScale"; from: 1.10; to: 1.00; duration: 550; easing.type: Easing.InOutSine }
    }

    // SPEAKING: strong pulse (later you can replace pulseScale with level-driven scale)
    SequentialAnimation {
        running: root.state === "speaking"
        loops: Animation.Infinite
        NumberAnimation { target: circle; property: "pulseScale"; from: 1.00; to: 1.18; duration: 320; easing.type: Easing.InOutSine }
        NumberAnimation { target: circle; property: "pulseScale"; from: 1.18; to: 1.00; duration: 320; easing.type: Easing.InOutSine }
    }

    // ERROR: steady + different look
    // Use a binding so it switches instantly when state changes.
    // Also stop pulsing by forcing scale to 1.0.
    states: [
        State {
            name: "error"
            when: root.state === "error"
            PropertyChanges { target: circle; border.color: "#ff4d4d"; pulseScale: 1.0 }
        }
    ]

}
