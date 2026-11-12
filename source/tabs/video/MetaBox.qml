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
                width: 50
                height: parent.height
                label: "Copy"
                disabled: VIDEO.selectedPath == ""
                onPressed: VIDEO.copyMeta()
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

    STextArea {
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: header.bottom
        anchors.bottom: parent.bottom
        anchors.margins: 1
        color: COMMON.bg1
        readOnly: true
        text: VIDEO.selectedMeta
    }
}
