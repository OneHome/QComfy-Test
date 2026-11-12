import QtQuick 2.15

import gui 1.0

import "../../style"

Item {
    id: box
    property string placeholder: ""
    signal submitted(string text)

    function submit() {
        if(input.text.trim() != "") {
            box.submitted(input.text)
            input.text = ""
        }
    }

    Rectangle {
        anchors.left: parent.left
        anchors.right: addButton.left
        anchors.rightMargin: 2
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        color: COMMON.bg00
        border.color: input.activeFocus ? COMMON.fg3 : COMMON.bg4

        TextInput {
            id: input
            anchors.fill: parent
            anchors.margins: 6
            verticalAlignment: TextInput.AlignVCenter
            color: COMMON.fg1
            font.pointSize: 10
            clip: true
            selectByMouse: true
            persistentSelection: true
            onAccepted: box.submit()
            SInputMenu { anchors.fill: parent; target: parent }
        }

        SText {
            visible: input.text == "" && !input.activeFocus
            anchors.left: parent.left
            anchors.leftMargin: 6
            anchors.verticalCenter: parent.verticalCenter
            width: parent.width - 12
            elide: Text.ElideRight
            text: box.placeholder
            color: COMMON.bg6
            pointSize: 9.5
        }
    }

    SButton {
        id: addButton
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
        width: 52
        label: "Add"
        onPressed: box.submit()
    }
}
