import QtQuick
import QtQuick.Window
import QtQuick.Controls
import QtQuick.Layouts

Window {
    id: window
    width: 900
    height: 700
    visible: true
    title: "ARES"
    color: "#202020"

    ColumnLayout {
        id: rootLayout
        anchors.fill: parent
        anchors.margins: 16
        spacing: 12

        // Orb (top)
        Item {
            Layout.fillWidth: true
            Layout.preferredHeight: 260

            Orb {
                id: orb
                anchors.centerIn: parent
                state: bridge.state

                // Reasonable responsive sizing based on window size
                baseSize: Math.min(window.width, window.height) * 0.28
            }
        }

        // Output (middle, takes most space)
        ScrollView {
            id: outputScroll
            Layout.fillWidth: true
            Layout.fillHeight: true

            TextArea {
                id: output
                readOnly: true
                wrapMode: TextArea.Wrap
                text: bridge.outputText
            }
        }

        // Input row (bottom)
        RowLayout {
            Layout.fillWidth: true
            spacing: 8

            TextField {
                id: input
                Layout.fillWidth: true
                placeholderText: qsTr("Enter a prompt")
                onAccepted: {
                    bridge.sendUserMessage(text)
                    text = ""
                }
            }

            Button {
                text: qsTr("Send")
                onClicked: {
                    bridge.sendUserMessage(input.text)
                    input.text = ""
                }
            }
        }
    }
}
