import QtQuick 2.15
import QtQuick.Controls 2.15

import gui 1.0

import "../../style"

Rectangle {
    id: box
    property alias text: area.text
    property string placeholder: ""
    signal edited()

    color: COMMON.bg00
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
            font.pointSize: 10.5
            background: null
            onTextChanged: {
                if(activeFocus) {
                    box.edited()
                }
            }
        }
    }
}
