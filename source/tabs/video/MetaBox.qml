import QtQuick 2.15

import gui 1.0

import "../../style"

Rectangle {
    id: root
    color: COMMON.bg1

    signal deleteRequested()

    Item {
        id: header
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: 26

        SText {
            anchors.left: parent.left
            anchors.leftMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            text: "Parameters"
            color: COMMON.fg2
            pointSize: 9
        }

        Row {
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            spacing: 2

            SButton {
                width: 100
                height: parent.height
                label: "\u2190 Use settings"
                disabled: VIDEO.selectedPath == ""
                onPressed: VIDEO.reuseSelected()
            }
            SButton {
                width: 90
                height: parent.height
                label: "Use prompts"
                disabled: VIDEO.selectedPath == ""
                onPressed: VIDEO.reusePrompts()
            }
            SButton {
                width: 56
                height: parent.height
                label: "Folder"
                disabled: VIDEO.selectedPath == ""
                onPressed: VIDEO.showSelected()
            }
            SButton {
                width: 56
                height: parent.height
                label: "Delete"
                disabled: VIDEO.selectedPath == ""
                onPressed: root.deleteRequested()
            }
        }
    }

    Rectangle {
        id: titleRow
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: header.bottom
        anchors.leftMargin: 4
        anchors.rightMargin: 4
        height: 24
        color: COMMON.bg00
        border.color: titleInput.activeFocus ? COMMON.fg3 : COMMON.bg4

        TextInput {
            id: titleInput
            anchors.fill: parent
            anchors.margins: 5
            verticalAlignment: TextInput.AlignVCenter
            color: COMMON.fg1
            font.pointSize: 10
            clip: true
            selectByMouse: true
            persistentSelection: true
            maximumLength: 120
            enabled: VIDEO.selectedPath != ""
            text: VIDEO.selectedTitle
            onEditingFinished: VIDEO.setTitle(VIDEO.selectedPath, text)

            SInputMenu { anchors.fill: parent; target: parent }
        }

        SText {
            visible: VIDEO.selectedPath != "" && titleInput.text == "" && !titleInput.activeFocus
            anchors.left: parent.left
            anchors.leftMargin: 5
            anchors.verticalCenter: parent.verticalCenter
            text: "Title (optional): shown in the gallery and searchable"
            color: COMMON.bg6
            pointSize: 9.2
        }
    }

    STextArea {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: titleRow.bottom
        anchors.topMargin: 2
        anchors.bottom: parent.bottom
        anchors.margins: 1
        color: COMMON.bg1
        readOnly: true
        text: VIDEO.selectedMeta
    }
}
