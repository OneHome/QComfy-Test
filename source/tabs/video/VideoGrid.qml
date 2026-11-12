import QtQuick 2.15
import QtQuick.Controls 2.15

import gui 1.0

import "../../style"

Rectangle {
    id: root
    color: COMMON.bg00

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
                onTextChanged: VIDEO.setSearch(text)
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
            id: filterBox
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: 110
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

        property int columns: Math.max(1, Math.floor(width / 150))
        cellWidth: Math.floor(width / columns)
        cellHeight: Math.round(cellWidth * 0.75) + 34

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
                    anchors.top: frame.bottom
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.margins: 4
                    height: 28
                    text: modelData.sub != "" ? modelData.sub : modelData.name
                    elide: Text.ElideRight
                    color: cell.selected ? COMMON.fg1 : COMMON.fg3
                    pointSize: 8.8
                    verticalAlignment: Text.AlignVCenter
                }
            }

            MouseArea {
                anchors.fill: parent
                onPressed: VIDEO.select(modelData.path)
                onDoubleClicked: VIDEO.openSelected()
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
