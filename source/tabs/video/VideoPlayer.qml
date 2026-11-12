import QtQuick 2.15
import QtMultimedia 5.15

import gui 1.0

import "../../style"

// Loaded through a Loader (see Video.qml): if QtMultimedia is missing, only this player is lost, not the whole tab.
Rectangle {
    id: root
    color: "black"

    property url videoSource: VIDEO.selectedUrl
    property bool released: false     // set before deleting the file: Windows will not delete a video that is open
    property bool muted: false
    property bool loop: false
    property string errorText: ""

    function release() {
        media.stop()
        root.released = true
    }

    function fmt(ms) {
        var s = Math.floor(ms / 1000)
        var m = Math.floor(s / 60)
        s = s % 60
        return m + ":" + (s < 10 ? "0" : "") + s
    }

    onVideoSourceChanged: {
        root.released = false
        root.errorText = ""
    }

    MediaPlayer {
        id: media
        source: root.released ? "" : root.videoSource
        autoPlay: GUI.windowActive      // a clip that finishes while you are away waits, with its first frame, instead of talking
        muted: root.muted
        loops: root.loop ? MediaPlayer.Infinite : 1
        onError: root.errorText = errorString
        onStatusChanged: {
            if(status === MediaPlayer.Loaded || status === MediaPlayer.Buffered) {
                root.errorText = ""
            }
            if(status === MediaPlayer.Loaded && !media.autoPlay) {
                media.pause()           // shows the first frame
            }
        }
    }

    VideoOutput {
        id: output
        anchors.top: parent.top
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: controls.top
        source: media
        fillMode: VideoOutput.PreserveAspectFit
    }

    MouseArea {
        anchors.fill: output
        onPressed: {
            if(media.playbackState === MediaPlayer.PlayingState) {
                media.pause()
            } else {
                media.play()
            }
        }
    }

    SText {
        visible: VIDEO.selectedUrl == "" && root.errorText == ""
        anchors.centerIn: output
        text: "Select a video from the gallery"
        color: COMMON.bg6
        pointSize: 10
    }

    SText {
        visible: root.errorText != ""
        anchors.centerIn: output
        width: output.width - 40
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.Wrap
        text: "qComfy cannot play this video (" + root.errorText + "). Use Open externally."
        color: "#e08060"
        pointSize: 10
    }

    Rectangle {
        id: sizeLabel
        visible: sizeText.text != ""
        anchors.top: parent.top
        anchors.right: parent.right
        anchors.margins: 2
        width: sizeText.width + 10
        height: 18
        color: "#99000000"

        SText {
            id: sizeText
            anchors.centerIn: parent
            color: COMMON.fg1_5
            pointSize: 8.6
            text: output.sourceRect.width > 0 ? Math.round(output.sourceRect.width) + "x" + Math.round(output.sourceRect.height)
                                              : VIDEO.selectedResolution
        }
    }

    Rectangle {
        id: controls
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.bottom: parent.bottom
        height: 32
        color: COMMON.bg1

        SButton {
            id: playButton
            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: 36
            label: media.playbackState === MediaPlayer.PlayingState ? "\u275a\u275a" : "\u25b6"
            disabled: VIDEO.selectedUrl == ""
            onPressed: {
                if(media.playbackState === MediaPlayer.PlayingState) {
                    media.pause()
                } else {
                    media.play()
                }
            }
        }

        SText {
            id: positionText
            anchors.left: playButton.right
            anchors.leftMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            text: root.fmt(media.position)
            color: COMMON.fg2
            pointSize: 9
        }

        Rectangle {
            id: bar
            anchors.left: positionText.right
            anchors.leftMargin: 8
            anchors.right: durationText.left
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            height: 8
            color: COMMON.bg3

            Rectangle {
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: media.duration > 0 ? parent.width * Math.min(1, media.position / media.duration) : 0
                color: "#cc2f00"
            }

            MouseArea {
                anchors.fill: parent
                anchors.topMargin: -8
                anchors.bottomMargin: -8
                onPressed: seek(mouse.x)
                onPositionChanged: if(pressed) seek(mouse.x)
                function seek(x) {
                    if(media.duration > 0) {
                        media.seek(Math.max(0, Math.min(1, x / bar.width)) * media.duration)
                    }
                }
            }
        }

        SText {
            id: durationText
            anchors.right: muteButton.left
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            text: root.fmt(media.duration)
            color: COMMON.fg2
            pointSize: 9
        }

        SButton {
            id: muteButton
            anchors.right: loopButton.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: 56
            label: root.muted ? "Muted" : "Sound"
            onPressed: root.muted = !root.muted
        }

        SButton {
            id: loopButton
            anchors.right: externalButton.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: 70
            label: root.loop ? "Loop: on" : "Loop: off"
            onPressed: root.loop = !root.loop
        }

        SButton {
            id: externalButton
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: 110
            label: "Open externally"
            disabled: VIDEO.selectedUrl == ""
            onPressed: VIDEO.openSelected()
        }
    }
}
