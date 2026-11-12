import QtQuick 2.15
import QtMultimedia 5.15
import QtQuick.Window 2.15

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

    function togglePlay() {
        if(VIDEO.selectedUrl == "") {
            return
        }
        if(media.playbackState === MediaPlayer.PlayingState) {
            media.pause()
        } else {
            media.play()
        }
    }

    function openFullscreen() {
        if(VIDEO.selectedUrl == "" || root.errorText != "") {
            return
        }
        fullscreen.startPosition = media.position
        fullscreen.startPlaying = media.playbackState === MediaPlayer.PlayingState
        media.pause()
        fullscreen.visibility = Window.FullScreen
    }

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
            if(status === MediaPlayer.InvalidMedia && root.errorText == "") {
                root.errorText = "invalid media or unsupported codec"
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
        onDoubleClicked: root.openFullscreen()      // the two presses of the double click cancel each other: play / pause stays as it was
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
            onPressed: root.togglePlay()
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
            id: fullButton
            anchors.right: externalButton.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: 46
            label: "Full"
            disabled: VIDEO.selectedUrl == ""
            onPressed: root.openFullscreen()
        }

        SButton {
            id: loopButton
            anchors.right: fullButton.left
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

    // Full screen: its own window with its own player, started where the main one was and handing the position back on exit.
    Window {
        id: fullscreen
        color: "black"
        title: "qComfy"
        visibility: Window.Hidden
        transientParent: null

        property int startPosition: 0
        property bool startPlaying: true
        property int lastPosition: 0
        property bool playing: true
        property bool controlsVisible: true

        function toggle() {
            if(fsMedia.playbackState === MediaPlayer.PlayingState) {
                fsMedia.pause()
            } else {
                fsMedia.play()
            }
        }

        function seekBy(ms) {
            if(fsMedia.duration > 0) {
                fsMedia.seek(Math.max(0, Math.min(fsMedia.duration, fsMedia.position + ms)))
            }
            fullscreen.showControls()
        }

        function showControls() {
            fullscreen.controlsVisible = true
            hideTimer.restart()
        }

        property bool shown: false      // so that only a real exit from full screen touches the main player

        onVisibilityChanged: {
            if(visibility === Window.Hidden) {
                if(fullscreen.shown) {
                    fullscreen.shown = false
                    media.seek(fullscreen.lastPosition)
                    if(fullscreen.playing) {
                        media.play()
                    }
                }
            } else {
                fullscreen.shown = true
                fullscreen.showControls()
                keys.forceActiveFocus()
            }
        }

        MediaPlayer {
            id: fsMedia
            source: fullscreen.visible ? root.videoSource : ""
            autoPlay: false
            muted: root.muted
            loops: root.loop ? MediaPlayer.Infinite : 1
            onStatusChanged: {
                if(status === MediaPlayer.Loaded && fullscreen.visible) {
                    fsMedia.seek(fullscreen.startPosition)
                    if(fullscreen.startPlaying) {
                        fsMedia.play()
                    } else {
                        fsMedia.pause()
                    }
                }
            }
            onPositionChanged: {
                if(fullscreen.visible) {
                    fullscreen.lastPosition = position
                }
            }
            onPlaybackStateChanged: {
                if(fullscreen.visible && playbackState !== MediaPlayer.StoppedState) {
                    fullscreen.playing = playbackState === MediaPlayer.PlayingState
                }
            }
        }

        Timer {
            id: hideTimer
            interval: 2500
            onTriggered: fullscreen.controlsVisible = false
        }

        VideoOutput {
            anchors.fill: parent
            source: fsMedia
            fillMode: VideoOutput.PreserveAspectFit
        }

        Item {
            id: keys
            anchors.fill: parent
            focus: true
            Keys.onPressed: {
                if(event.key === Qt.Key_Escape || event.key === Qt.Key_F || event.key === Qt.Key_F11
                        || event.key === Qt.Key_Return || event.key === Qt.Key_Enter) {
                    fullscreen.visibility = Window.Hidden
                } else if(event.key === Qt.Key_Space) {
                    fullscreen.toggle()
                    fullscreen.showControls()
                } else if(event.key === Qt.Key_Left) {
                    fullscreen.seekBy(-5000)
                } else if(event.key === Qt.Key_Right) {
                    fullscreen.seekBy(5000)
                } else if(event.key === Qt.Key_M) {
                    root.muted = !root.muted
                } else {
                    return
                }
                event.accepted = true
            }
        }

        MouseArea {
            anchors.fill: parent
            hoverEnabled: true
            cursorShape: fullscreen.controlsVisible ? Qt.ArrowCursor : Qt.BlankCursor
            onPositionChanged: fullscreen.showControls()
            onPressed: fullscreen.toggle()
            onDoubleClicked: fullscreen.visibility = Window.Hidden
        }

        Rectangle {
            visible: fullscreen.controlsVisible
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            height: 44
            color: "#cc000000"

            SText {
                id: fsPosition
                anchors.left: parent.left
                anchors.leftMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                text: root.fmt(fsMedia.position)
                color: COMMON.fg1
                pointSize: 10
            }

            Rectangle {
                id: fsBar
                anchors.left: fsPosition.right
                anchors.leftMargin: 12
                anchors.right: fsDuration.left
                anchors.rightMargin: 12
                anchors.verticalCenter: parent.verticalCenter
                height: 8
                color: COMMON.bg3

                Rectangle {
                    anchors.left: parent.left
                    anchors.top: parent.top
                    anchors.bottom: parent.bottom
                    width: fsMedia.duration > 0 ? parent.width * Math.min(1, fsMedia.position / fsMedia.duration) : 0
                    color: "#cc2f00"
                }

                MouseArea {
                    anchors.fill: parent
                    anchors.topMargin: -12
                    anchors.bottomMargin: -12
                    onPressed: seek(mouse.x)
                    onPositionChanged: if(pressed) seek(mouse.x)
                    function seek(x) {
                        if(fsMedia.duration > 0) {
                            fsMedia.seek(Math.max(0, Math.min(1, x / fsBar.width)) * fsMedia.duration)
                        }
                    }
                }
            }

            SText {
                id: fsDuration
                anchors.right: fsHint.left
                anchors.rightMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                text: root.fmt(fsMedia.duration)
                color: COMMON.fg1
                pointSize: 10
            }

            SText {
                id: fsHint
                anchors.right: parent.right
                anchors.rightMargin: 14
                anchors.verticalCenter: parent.verticalCenter
                text: "Esc: exit   Space: play/pause   \u2190 \u2192: \u00b15 s"
                color: COMMON.fg3
                pointSize: 9
            }
        }
    }
}
