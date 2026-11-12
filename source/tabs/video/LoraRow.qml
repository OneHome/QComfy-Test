import QtQuick 2.15

import gui 1.0

import "../../style"

Item {
    id: row
    property int index: 0
    visible: index < VIDEO.myLoras.length
    height: visible ? 52 : 0

    SText {
        id: name
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        height: 22
        leftPadding: 4
        rightPadding: 4
        elide: Text.ElideMiddle
        text: row.index < VIDEO.myLoras.length ? VIDEO.myLoras[row.index] : ""
        color: COMMON.fg2
        pointSize: 9.2
        verticalAlignment: Text.AlignVCenter
    }

    OSlider {
        anchors.top: name.bottom
        anchors.left: parent.left
        anchors.right: removeButton.left
        anchors.rightMargin: 2
        label: "Strength"
        bindMap: VIDEO.values
        bindKey: "mylora_s" + row.index
        defaultValue: 1
        minValue: 0
        maxValue: 2
        precValue: 2
        incValue: 0.05
    }

    SButton {
        id: removeButton
        anchors.top: name.bottom
        anchors.right: parent.right
        anchors.rightMargin: 8
        width: 26
        height: 26
        label: "\u2715"
        onPressed: VIDEO.removeLora(row.index)
    }
}
