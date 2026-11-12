import QtQuick 2.15
import QtQuick.Controls 2.15
import Qt.labs.platform 1.1

import gui 1.0

import "../../style"
import "../../components"

Rectangle {
    id: slot
    property string key: ""
    property string title: ""
    property string path: ""

    function tr(str, file = "FrameSlot.qml") {
        return TRANSLATOR.instance.translate(str, file)
    }

    color: COMMON.bg00
    border.color: slotDrop.containsDrag ? COMMON.fg2 : COMMON.bg4

    function sync() {
        var p = VIDEO.values.get(slot.key)
        slot.path = p ? p : ""
    }

    Component.onCompleted: sync()

    Connections {
        target: VIDEO.values
        function onUpdated(k) {
            if(k == slot.key) {
                slot.sync()
            }
        }
    }

    Image {
        anchors.fill: parent
        anchors.margins: 2
        fillMode: Image.PreserveAspectFit
        source: slot.path != "" ? "file:///" + slot.path.replace(/\\/g, "/") : ""
        asynchronous: true
    }

    SText {
        visible: slot.path == ""
        anchors.centerIn: parent
        horizontalAlignment: Text.AlignHCenter
        text: slot.title + "\n" + slot.tr("(optional)")
        color: COMMON.bg7
        pointSize: 9.5
    }

    MouseArea {
        anchors.fill: parent
        acceptedButtons: Qt.LeftButton | Qt.RightButton
        onPressed: {
            if(mouse.button == Qt.RightButton) {
                VIDEO.setFrame(slot.key, "")
            } else {
                frameDialog.open()
            }
        }
    }

    AdvancedDropArea {
        id: slotDrop
        anchors.fill: parent
        onDropped: {
            var file = VIDEO.pathDrop(mimeData)
            if(file != "") {
                VIDEO.setFrame(slot.key, file)
            }
        }
    }

    FileDialog {
        id: frameDialog
        nameFilters: [slot.tr("Images") + " (*.png *.jpg *.jpeg *.webp *.bmp)"]
        onAccepted: {
            VIDEO.setFrame(slot.key, SETTINGS.toLocal(frameDialog.file))
        }
    }
}
