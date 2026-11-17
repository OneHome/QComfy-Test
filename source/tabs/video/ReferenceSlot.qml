import QtQuick 2.15

import gui 1.0

import "../../style"

// One reference image of a Ref2VA server: the picture, its <Picture N> number, a name for the subject, and buttons to
// remove it or move it earlier / later (the order is the order of <Picture N>).
Item {
    id: slot
    property int index: 0
    property string path: ""
    property string name: ""
    property string label: ""
    property int count: 1

    width: 84
    height: 110

    function tr(str, file = "ReferenceSlot.qml") {
        return TRANSLATOR.instance.translate(str, file)
    }

    Rectangle {
        id: frame
        x: 0
        y: 0
        width: parent.width
        height: 84
        color: COMMON.bg00
        border.color: COMMON.bg4

        Image {
            anchors.fill: parent
            anchors.margins: 2
            fillMode: Image.PreserveAspectFit
            asynchronous: true
            source: slot.path != "" ? "file:///" + slot.path.replace(/\\/g, "/") : ""
        }

        Rectangle {
            anchors.left: parent.left
            anchors.top: parent.top
            width: badge.implicitWidth + 8
            height: 16
            color: "#cc000000"
            SText {
                id: badge
                anchors.centerIn: parent
                text: slot.label
                color: COMMON.fg1
                pointSize: 8.5
            }
        }

        Rectangle {
            anchors.right: parent.right
            anchors.top: parent.top
            width: 18
            height: 18
            color: removeMouse.containsMouse ? "#cc2f00" : "#cc000000"
            SText {
                anchors.centerIn: parent
                text: "\u00d7"
                color: COMMON.fg1
                pointSize: 11
            }
            MouseArea {
                id: removeMouse
                anchors.fill: parent
                hoverEnabled: true
                onPressed: VIDEO.removeReference(slot.index)
            }
        }

        Row {
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            visible: slot.count > 1
            Rectangle {
                width: 18
                height: 18
                visible: slot.index > 0
                color: leftMouse.containsMouse ? COMMON.bg5 : "#cc000000"
                SText {
                    anchors.centerIn: parent
                    text: "\u2039"
                    color: COMMON.fg1
                    pointSize: 11
                }
                MouseArea {
                    id: leftMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    onPressed: VIDEO.moveReference(slot.index, -1)
                }
            }
            Rectangle {
                width: 18
                height: 18
                visible: slot.index < slot.count - 1
                color: rightMouse.containsMouse ? COMMON.bg5 : "#cc000000"
                SText {
                    anchors.centerIn: parent
                    text: "\u203a"
                    color: COMMON.fg1
                    pointSize: 11
                }
                MouseArea {
                    id: rightMouse
                    anchors.fill: parent
                    hoverEnabled: true
                    onPressed: VIDEO.moveReference(slot.index, 1)
                }
            }
        }
    }

    Rectangle {
        x: 0
        y: 86
        width: parent.width
        height: 22
        color: COMMON.bg00
        border.color: nameInput.activeFocus ? COMMON.fg3 : COMMON.bg4

        TextInput {
            id: nameInput
            anchors.fill: parent
            anchors.margins: 4
            verticalAlignment: TextInput.AlignVCenter
            color: COMMON.fg1
            font.pointSize: 9
            clip: true
            selectByMouse: true
            persistentSelection: true
            maximumLength: 60
            text: slot.name
            onTextEdited: VIDEO.setReferenceName(slot.index, text)

            SInputMenu { anchors.fill: parent; target: parent }
        }

        SText {
            visible: nameInput.text == "" && !nameInput.activeFocus
            anchors.left: parent.left
            anchors.leftMargin: 4
            anchors.verticalCenter: parent.verticalCenter
            text: slot.tr("who / what is it?")
            color: COMMON.bg6
            pointSize: 8.5
        }
    }
}
