import QtQuick 2.15

import gui 1.0

import "../../style"

// Check box bound to a GUI.config key
Item {
    id: option
    property string label: ""
    property string hint: ""
    property string configKey: ""
    property bool checked: false

    function sync() {
        option.checked = GUI.config.get(option.configKey) !== false
    }

    Component.onCompleted: sync()

    Connections {
        target: GUI.config
        function onUpdated(k) {
            if(k == option.configKey) {
                option.sync()
            }
        }
    }

    Rectangle {
        id: box
        anchors.left: parent.left
        anchors.leftMargin: 4
        anchors.top: parent.top
        anchors.topMargin: 6
        width: 16
        height: 16
        color: option.checked ? COMMON.fg3 : COMMON.bg00
        border.color: COMMON.bg4

        SText {
            anchors.centerIn: parent
            visible: option.checked
            text: "\u2713"
            color: COMMON.bg00
            pointSize: 10
        }
    }

    Column {
        anchors.left: box.right
        anchors.leftMargin: 8
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.topMargin: 3

        SText {
            width: parent.width
            wrapMode: Text.Wrap
            text: option.label
            color: COMMON.fg1
            pointSize: 9.6
        }
        SText {
            visible: option.hint != ""
            width: parent.width
            wrapMode: Text.Wrap
            text: option.hint
            color: COMMON.fg3
            pointSize: 8.8
        }
    }

    MouseArea {
        anchors.fill: parent
        onPressed: GUI.config.set(option.configKey, !option.checked)
    }
}
