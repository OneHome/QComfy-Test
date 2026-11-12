import QtQuick 2.15
import QtQuick.Controls 2.15

import gui 1.0

import "../../style"

Rectangle {
    id: box
    property alias text: area.text
    property string placeholder: ""
    property string bindKey: ""      // key of VIDEO.values this box shows: changes made elsewhere (Use prompts / Use settings) show up here
    signal edited()

    color: COMMON.bg00

    Connections {
        target: VIDEO.values
        function onUpdated(key) {
            if(box.bindKey != "" && key == box.bindKey) {
                var v = VIDEO.values.get(key)
                if(v === undefined || v === null) {
                    v = ""
                }
                if(v != area.text) {
                    area.text = v
                }
            }
        }
    }
    border.color: COMMON.bg4
    border.width: 1

    Flickable {
        anchors.fill: parent
        anchors.margins: 2
        clip: true
        contentHeight: area.height
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: SScrollBarV {}

        TextArea {
            id: area
            width: parent.width
            wrapMode: TextArea.Wrap
            color: COMMON.fg1
            placeholderText: box.placeholder
            placeholderTextColor: COMMON.bg6
            selectByMouse: true
            persistentSelection: true
            font.pointSize: 10.5
            background: null
            SInputMenu { anchors.fill: parent; target: parent }
            onTextChanged: {
                if(activeFocus) {
                    box.edited()
                }
            }
        }
    }
}
