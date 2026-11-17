import QtQuick 2.15
import QtQuick.Controls 2.15

import gui 1.0

import "../../style"

Rectangle {
    id: box
    property alias text: area.text
    property string placeholder: ""
    property bool enhanceable: false      // Enhance / Undo live in the right click menu and on Ctrl+E / Ctrl+Shift+E (uses bindKey as the field)
    property bool enhancing: enhanceable && VIDEO.enhancingFields.indexOf(bindKey) >= 0
    property bool canUndo: enhanceable && VIDEO.undoFields.indexOf(bindKey) >= 0
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
            readOnly: box.enhancing
            opacity: box.enhancing ? 0.55 : 1.0
            SInputMenu { anchors.fill: parent; target: parent; enhanceKey: box.enhanceable ? box.bindKey : "" }
            onTextChanged: {
                if(activeFocus) {
                    box.edited()
                }
            }
        }
    }

    Shortcut {
        sequence: "Ctrl+E"
        enabled: box.enhanceable && area.activeFocus && !box.enhancing
        onActivated: VIDEO.enhance(box.bindKey)
    }

    Shortcut {
        sequence: "Ctrl+Shift+E"
        enabled: box.enhanceable && area.activeFocus && box.canUndo
        onActivated: VIDEO.undoEnhance(box.bindKey)
    }

    // while the language model works: a thin pulsing line on the bottom border (takes no space)
    Rectangle {
        visible: box.enhancing
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 2
        color: "#cc2f00"
        SequentialAnimation on opacity {
            running: box.enhancing
            loops: Animation.Infinite
            NumberAnimation { from: 0.25; to: 1.0; duration: 600 }
            NumberAnimation { from: 1.0; to: 0.25; duration: 600 }
        }
    }
}
