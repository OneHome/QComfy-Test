import QtQuick 2.15
import QtQuick.Controls 2.15

import gui 1.0

import "../../style"

Rectangle {
    id: root
    color: COMMON.bg00

    signal deleteRequested()
    signal playRequested()
    signal fullscreenRequested()

    Item {
        id: header
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.top: parent.top
        height: 30

        Rectangle {
            anchors.left: parent.left
            anchors.right: filterBox.left
            anchors.rightMargin: 2
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            color: COMMON.bg1
            border.color: search.activeFocus ? COMMON.fg3 : COMMON.bg3

            TextInput {
                id: search
                anchors.fill: parent
                anchors.margins: 7
                verticalAlignment: TextInput.AlignVCenter
                color: COMMON.fg1
                font.pointSize: 10
                clip: true
                selectByMouse: true
                persistentSelection: true
                onTextChanged: VIDEO.setSearch(text)
                SInputMenu { anchors.fill: parent; target: parent }
            }

            SText {
                visible: search.text == "" && !search.activeFocus
                anchors.left: parent.left
                anchors.leftMargin: 7
                anchors.verticalCenter: parent.verticalCenter
                text: "Search..."
                color: COMMON.bg6
                pointSize: 10
            }
        }

        SComboBox {
            id: sortBox
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: 84
            model: ["Newest", "Oldest"]
            onActivated: VIDEO.setSort(model[index])
        }

        SComboBox {
            id: dateBox
            anchors.right: sortBox.left
            anchors.rightMargin: 2
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: 100
            model: ["Any date", "Today", "Last 7 days", "Last 30 days"]
            onActivated: VIDEO.setDateFilter(model[index])
        }

        SComboBox {
            id: filterBox
            anchors.right: dateBox.left
            anchors.rightMargin: 2
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: 92
            model: ["All", "Previews", "Upscaled"]
            onActivated: VIDEO.setFilter(model[index])
        }
    }

    GridView {
        id: grid
        anchors.top: header.bottom
        anchors.topMargin: 4
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.leftMargin: 4
        anchors.rightMargin: 4
        anchors.bottomMargin: 20
        clip: true
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: SScrollBarV {}
        Keys.onDeletePressed: root.deleteRequested()
        Keys.onSpacePressed: root.playRequested()
        Keys.onLeftPressed: grid.move(-1)
        Keys.onRightPressed: grid.move(1)
        Keys.onUpPressed: grid.move(-grid.columns)
        Keys.onDownPressed: grid.move(grid.columns)
        Keys.onReturnPressed: root.fullscreenRequested()
        Keys.onEnterPressed: root.fullscreenRequested()
        Keys.onPressed: {
            if(event.key === Qt.Key_F) {
                root.fullscreenRequested()
            } else if(event.key === Qt.Key_Home) {
                grid.moveTo(0)
            } else if(event.key === Qt.Key_End) {
                grid.moveTo(VIDEO.library.length - 1)
            } else if(event.key === Qt.Key_PageUp) {
                grid.move(-grid.columns * Math.max(1, Math.floor(grid.height / grid.cellHeight)))
            } else if(event.key === Qt.Key_PageDown) {
                grid.move(grid.columns * Math.max(1, Math.floor(grid.height / grid.cellHeight)))
            } else {
                return
            }
            event.accepted = true
        }

        function currentIndex_() {
            var items = VIDEO.library
            for(var i = 0; i < items.length; i++) {
                if(items[i].path === VIDEO.selectedPath) {
                    return i
                }
            }
            return -1
        }

        function moveTo(index) {
            var items = VIDEO.library
            if(items.length === 0) {
                return
            }
            index = Math.max(0, Math.min(items.length - 1, index))
            VIDEO.select(items[index].path)
            grid.positionViewAtIndex(index, GridView.Contain)
        }

        function move(delta) {
            var cur = grid.currentIndex_()
            grid.moveTo(cur < 0 ? 0 : cur + delta)
        }

        property int columns: Math.max(1, Math.floor(width / 150))
        cellWidth: Math.floor(width / columns)
        cellHeight: Math.round(cellWidth * 0.75) + 66

        model: VIDEO.library

        delegate: Item {
            id: cell
            width: grid.cellWidth
            height: grid.cellHeight
            property bool selected: VIDEO.selectedPath == modelData.path

            Rectangle {
                anchors.fill: parent
                anchors.margins: 4
                color: COMMON.bg1
                border.color: "#cc2f00"
                border.width: cell.selected ? 2 : 0

                Rectangle {
                    id: frame
                    anchors.top: parent.top
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.margins: 2
                    height: width * 0.75
                    color: "black"

                    Image {
                        anchors.fill: parent
                        source: modelData.thumb
                        fillMode: Image.PreserveAspectCrop
                        asynchronous: true
                        visible: modelData.thumb != ""
                    }

                    SText {
                        visible: modelData.thumb == ""
                        anchors.centerIn: parent
                        text: "\u25b6"
                        color: COMMON.bg6
                        pointSize: 16
                    }
                }

                SText {
                    id: titleText
                    anchors.top: frame.bottom
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.topMargin: 3
                    anchors.leftMargin: 4
                    anchors.rightMargin: 4
                    height: 34
                    text: modelData.title
                    wrapMode: Text.Wrap
                    maximumLineCount: 2
                    elide: Text.ElideRight
                    color: cell.selected ? COMMON.fg1 : COMMON.fg2
                    pointSize: 8.8
                    verticalAlignment: Text.AlignTop
                }

                SText {
                    anchors.top: titleText.bottom
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.leftMargin: 4
                    anchors.rightMargin: 4
                    height: 16
                    text: modelData.sub
                    elide: Text.ElideRight
                    color: COMMON.fg3
                    pointSize: 7.8
                    verticalAlignment: Text.AlignVCenter
                }
            }

            MouseArea {
                id: cellMouse
                anchors.fill: parent
                hoverEnabled: true
                onPressed: {
                    grid.forceActiveFocus()
                    VIDEO.select(modelData.path)
                }
                onDoubleClicked: VIDEO.openSelected()

                SToolTip {
                    visible: cellMouse.containsMouse && modelData.tooltip != ""
                    delay: 600
                    text: modelData.tooltip
                }
            }
        }
    }

    SText {
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        anchors.margins: 4
        text: VIDEO.libraryText
        color: COMMON.fg3
        pointSize: 8.8
    }
}
