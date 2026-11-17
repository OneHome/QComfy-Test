import QtQuick 2.15

import gui 1.0

import "../../style"

// One prompt template button. Pressing it adds its phrase to the box it belongs to, pressing it again removes it.
Rectangle {
    id: chip
    property string label: ""
    property string phrase: ""
    property string field: "prompt"      // key of VIDEO.values: prompt / sound / music / dialogue
    property bool active: false

    width: chipText.implicitWidth + 14
    height: 22
    color: active ? COMMON.bg5 : (mouse.containsMouse ? COMMON.bg3 : COMMON.bg2)
    border.width: 1
    border.color: active ? "#cc2f00" : COMMON.bg4

    function refresh() {
        var v = VIDEO.values.get(chip.field)
        chip.active = (typeof v === "string") && chip.phrase != "" && v.toLowerCase().indexOf(chip.phrase.toLowerCase()) >= 0
    }

    Component.onCompleted: refresh()

    Connections {
        target: VIDEO.values
        function onUpdated(key) {
            if(key === chip.field) {
                chip.refresh()
            }
        }
    }

    SText {
        id: chipText
        anchors.centerIn: parent
        text: chip.label
        color: chip.active ? COMMON.fg1 : COMMON.fg2
        pointSize: 8.8
    }

    MouseArea {
        id: mouse
        anchors.fill: parent
        hoverEnabled: true
        onPressed: VIDEO.applyTemplate(chip.field, chip.phrase)

        SToolTip {
            visible: mouse.containsMouse && chip.phrase != chip.label
            delay: 500
            text: chip.phrase
        }
    }
}
