import QtQuick 2.15
import QtQuick.Controls 2.15

import gui 1.0

// Right click menu (Cut / Copy / Paste) for a TextInput or TextArea. Put it inside the text item or next to it.
// Left clicks are not taken, so selecting and typing keep working.
MouseArea {
    id: root
    property var target: null
    property string enhanceKey: ""      // set on prompt boxes: adds Enhance / Undo enhance to the menu
    property int selStart: 0
    property int selEnd: 0
    acceptedButtons: Qt.RightButton

    // the selection is remembered when the menu opens: the menu takes the focus and a text field may drop its selection
    function restoreSelection() {
        if(root.target && root.selEnd > root.selStart) {
            root.target.select(root.selStart, root.selEnd)
        }
    }

    onPressed: {
        if(root.target) {
            root.selStart = root.target.selectionStart
            root.selEnd = root.target.selectionEnd
            if(!root.target.activeFocus) {
                root.target.forceActiveFocus()
                root.restoreSelection()
            }
        }
        menu.popup()
    }

    SContextMenu {
        id: menu
        width: root.enhanceKey != "" ? 160 : 80
        SContextMenuItem {
            text: "Cut"
            onPressed: {
                root.restoreSelection()
                root.target.cut()
            }
        }
        SContextMenuItem {
            text: "Copy"
            onPressed: {
                root.restoreSelection()
                root.target.copy()
            }
        }
        SContextMenuItem {
            text: "Paste"
            onPressed: root.target.paste()
        }
        SContextMenuItem {
            text: "Select all"
            onPressed: root.target.selectAll()
        }
        SContextMenuItem {
            visible: root.enhanceKey != ""
            text: "Enhance"
            shortcut: "Ctrl+E"
            onPressed: VIDEO.enhance(root.enhanceKey)
        }
        SContextMenuItem {
            visible: root.enhanceKey != "" && VIDEO.undoFields.indexOf(root.enhanceKey) >= 0
            text: "Undo enhance"
            shortcut: "Ctrl+Shift+E"
            onPressed: VIDEO.undoEnhance(root.enhanceKey)
        }
    }
}
