import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import Qt.labs.platform 1.1

import gui 1.0

import "../../style"
import "../../components"

Item {
    id: root
    clip: true

    function tr(str, file = "Video.qml") {
        return TRANSLATOR.instance.translate(str, file)
    }

    function releaseFocus() {
        parent.releaseFocus()
    }

    property var swap: GUI.config.get("swap")
    property var rightWidth: 300

    // ---------------------------------------------------------------- main area (left)
    Item {
        id: mainArea
        anchors.left: parent.left
        anchors.right: settingsArea.left
        anchors.top: parent.top
        anchors.bottom: parent.bottom

        // Player + parameters (left), gallery (right)
        Item {
            id: topArea
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            anchors.bottom: promptRow.top
            anchors.margins: 4

            Item {
                id: viewerColumn
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: Math.max(320, parent.width * 0.52)

                // last message of the server / the app; click to see the whole log
                Rectangle {
                    id: logStrip
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: parent.top
                    height: 20
                    color: COMMON.bg00

                    SText {
                        anchors.fill: parent
                        anchors.leftMargin: 6
                        anchors.rightMargin: 6
                        text: VIDEO.lastLog != "" ? VIDEO.lastLog : root.tr("Videos are saved to the output folder")
                        elide: Text.ElideRight
                        color: VIDEO.lastLog != "" ? COMMON.fg2 : COMMON.bg6
                        pointSize: 8.8
                        verticalAlignment: Text.AlignVCenter
                    }

                    MouseArea {
                        anchors.fill: parent
                        onPressed: logOverlay.visible = !logOverlay.visible
                    }
                }

                Loader {
                    id: playerLoader
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.top: logStrip.bottom
                    anchors.topMargin: 2
                    anchors.bottom: metaBox.top
                    anchors.bottomMargin: 2
                    source: "VideoPlayer.qml"
                }

                // QtMultimedia is not available: everything else keeps working
                Rectangle {
                    visible: playerLoader.status == Loader.Error
                    anchors.fill: playerLoader
                    color: "black"

                    SText {
                        anchors.centerIn: parent
                        width: parent.width - 40
                        horizontalAlignment: Text.AlignHCenter
                        wrapMode: Text.Wrap
                        text: root.tr("The built-in player is not available on this install (QtMultimedia). Double-click a video to open it with your player.")
                        color: "#e08060"
                        pointSize: 10
                    }
                }

                MetaBox {
                    id: metaBox
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.bottom: parent.bottom
                    height: 150
                    onDeleteRequested: {
                        if(VIDEO.selectedPath != "") {
                            deleteDialog.open()
                        }
                    }
                }

                Rectangle {
                    id: logOverlay
                    visible: false
                    anchors.fill: playerLoader
                    color: "#ee111111"

                    Flickable {
                        id: logFlick
                        anchors.fill: parent
                        anchors.margins: 6
                        clip: true
                        contentHeight: logText.height
                        boundsBehavior: Flickable.StopAtBounds
                        ScrollBar.vertical: SScrollBarV {}

                        SText {
                            id: logText
                            width: logFlick.width - 14
                            text: VIDEO.log
                            wrapMode: Text.Wrap
                            color: COMMON.fg2
                            pointSize: 9.5
                            onTextChanged: logFlick.contentY = Math.max(0, logText.height - logFlick.height)
                        }
                    }
                }
            }

            VideoGrid {
                anchors.left: viewerColumn.right
                anchors.leftMargin: 4
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.bottom: parent.bottom
            }
        }

        // Prompts
        Item {
            id: promptRow
            height: 170
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom

            PromptBox {
                id: scenePrompt
                anchors.left: parent.left
                anchors.top: parent.top
                anchors.bottom: parent.bottom
                width: parent.width * 0.5
                placeholder: root.tr("Scene / action")
                text: VIDEO.values.get("prompt")
                onEdited: VIDEO.values.set("prompt", text)
            }

            Column {
                anchors.left: scenePrompt.right
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.bottom: parent.bottom

                PromptBox {
                    width: parent.width
                    height: parent.height / 3
                    placeholder: root.tr("Spoken line (optional)")
                    text: VIDEO.values.get("dialogue")
                    onEdited: VIDEO.values.set("dialogue", text)
                }
                PromptBox {
                    width: parent.width
                    height: parent.height / 3
                    placeholder: root.tr("Sound effects / ambience (optional)")
                    text: VIDEO.values.get("sound")
                    onEdited: VIDEO.values.set("sound", text)
                }
                PromptBox {
                    width: parent.width
                    height: parent.height / 3
                    placeholder: root.tr("Music (optional)")
                    text: VIDEO.values.get("music")
                    onEdited: VIDEO.values.set("music", text)
                }
            }
        }
    }

    // ---------------------------------------------------------------- settings (right)
    Rectangle {
        id: settingsArea
        color: COMMON.bg0
        width: root.rightWidth
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: status.top

        GenerateButton {
            id: genButton
            anchors.top: parent.top
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.margins: 2
            height: 40

            progress: GUI.statusProgress
            working: VIDEO.busy
            info: GUI.statusInfo

            onPressed: {
                if(VIDEO.busy) {
                    VIDEO.cancel()
                } else {
                    VIDEO.generate()
                }
            }
        }

        Flickable {
            id: flick
            anchors.top: genButton.bottom
            anchors.topMargin: 2
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.bottom: parent.bottom
            clip: true
            contentHeight: sections.height
            boundsBehavior: Flickable.StopAtBounds
            ScrollBar.vertical: SScrollBarV {}

            Column {
                id: sections
                width: flick.width - 8

                // ---- Server
                OColumn {
                    text: root.tr("Server")
                    width: parent.width
                    Column {
                        width: parent.width
                        OTextInput {
                            width: parent.width
                            height: 30
                            label: ""
                            placeholder: root.tr("Endpoint")
                            bindMap: GUI.config
                            bindKey: "endpoint"
                        }
                        OTextInput {
                            width: parent.width
                            height: 30
                            label: ""
                            placeholder: root.tr("Password")
                            bindMap: GUI.config
                            bindKey: "password"
                        }
                        SButton {
                            width: parent.width
                            height: 30
                            label: GUI.remoteInfoMode == "Remote" ? root.tr("Reconnect") : root.tr("Connect")
                            onPressed: SETTINGS.restart()
                        }
                        SText {
                            width: parent.width
                            height: 24
                            leftPadding: 4
                            text: GUI.statusText
                            color: COMMON.fg2
                            pointSize: 9.5
                            verticalAlignment: Text.AlignVCenter
                        }
                    }
                }

                // ---- Start / end frame
                OColumn {
                    text: root.tr("Start / end frame")
                    width: parent.width
                    Row {
                        width: parent.width
                        height: 96
                        spacing: 4
                        topPadding: 4
                        FrameSlot { width: (parent.width - 4) / 2; height: 92; key: "start_frame"; title: root.tr("Start frame") }
                        FrameSlot { width: (parent.width - 4) / 2; height: 92; key: "end_frame"; title: root.tr("End frame") }
                    }
                }

                // ---- Options
                OColumn {
                    text: root.tr("Options")
                    width: parent.width
                    Column {
                        width: parent.width
                        OSlider {
                            width: parent.width
                            label: root.tr("Seconds")
                            bindMap: VIDEO.values
                            bindKey: "seconds"
                            minValue: 3
                            maxValue: 15
                            precValue: 1
                            incValue: 0.5
                        }
                        SText {
                            width: parent.width
                            height: 22
                            leftPadding: 4
                            text: VIDEO.frameInfo
                            color: COMMON.fg3
                            pointSize: 9.2
                            verticalAlignment: Text.AlignVCenter
                        }
                        OChoice {
                            width: parent.width; height: 30
                            label: root.tr("Aspect")
                            bindMap: VIDEO.values
                            bindKeyCurrent: "aspect"
                            bindKeyModel: "aspects"
                        }
                        OChoice {
                            width: parent.width; height: 30
                            label: root.tr("Resolution")
                            bindMap: VIDEO.values
                            bindKeyCurrent: "resolution"
                            bindKeyModel: "resolutions"
                        }
                        OChoice {
                            width: parent.width; height: 30
                            label: root.tr("Output")
                            bindMap: VIDEO.values
                            bindKeyCurrent: "output"
                            bindKeyModel: "outputs"
                        }
                        OChoice {
                            width: parent.width; height: 30
                            label: root.tr("Upscale")
                            bindMap: VIDEO.values
                            bindKeyCurrent: "preset"
                            bindKeyModel: "presets"
                        }
                        SText {
                            visible: !VIDEO.upscaleAvailable
                            width: parent.width
                            height: visible ? 22 : 0
                            leftPadding: 4
                            text: root.tr("Upscale needs the 384p resolution")
                            color: COMMON.fg3
                            pointSize: 9
                            verticalAlignment: Text.AlignVCenter
                        }
                        CheckOption {
                            width: parent.width
                            height: 44
                            label: root.tr("Notify me when it finishes")
                            hint: root.tr("Sound, plus taskbar flash and a popup while qComfy is in the background")
                            configKey: "notify"
                        }
                        OSlider {
                            width: parent.width
                            label: root.tr("Seed")
                            bindMap: VIDEO.values
                            bindKey: "seed"
                            minValue: -1
                            maxValue: 2147483647
                            precValue: 0
                            incValue: 1
                            bounded: false
                        }
                        OSlider {
                            width: parent.width
                            label: root.tr("Upscale seed")
                            bindMap: VIDEO.values
                            bindKey: "refine_seed"
                            minValue: -1
                            maxValue: 2147483647
                            precValue: 0
                            incValue: 1
                            bounded: false
                        }
                    }
                }

                // ---- Advanced
                OColumn {
                    text: root.tr("Advanced")
                    width: parent.width
                    isCollapsed: true
                    Column {
                        width: parent.width
                        OChoice {
                            width: parent.width; height: 30
                            label: root.tr("Sampler")
                            tooltip: root.tr("euler: what PDMD was trained for")
                            bindMap: VIDEO.values
                            bindKeyCurrent: "sampler"
                            bindKeyModel: "samplers"
                        }
                        OSlider {
                            width: parent.width
                            label: root.tr("Flow shift")
                            tooltip: root.tr("Preview flow shift (video)")
                            bindMap: VIDEO.values
                            bindKey: "shift"
                            defaultValue: 12
                            minValue: 1
                            maxValue: 16
                            precValue: 0
                            incValue: 1
                        }
                        OSlider {
                            width: parent.width
                            label: root.tr("Steps")
                            tooltip: root.tr("Preview steps (0 = PDMD's 4)")
                            bindMap: VIDEO.values
                            bindKey: "steps"
                            defaultValue: 0
                            minValue: 0
                            maxValue: 12
                            precValue: 0
                            incValue: 1
                        }
                        CheckOption {
                            width: parent.width
                            height: 44
                            label: root.tr("Re-anchor the start / end image at the output resolution")
                            hint: root.tr("Keeps an Image \u2192 Video upscale faithful to your picture")
                            configKey: "anchor"
                        }
                    }
                }

                // ---- Sound
                OColumn {
                    text: root.tr("Sound")
                    width: parent.width
                    isCollapsed: true
                    Column {
                        width: parent.width
                        OChoice {
                            width: parent.width; height: 30
                            label: root.tr("Language")
                            bindMap: VIDEO.values
                            bindKeyCurrent: "language"
                            bindKeyModel: "languages"
                        }
                    }
                }

                // ---- LoRA
                OColumn {
                    text: root.tr("LoRA")
                    width: parent.width
                    Column {
                        width: parent.width
                        OChoice {
                            width: parent.width; height: 30
                            label: root.tr("LoRA 1")
                            bindMap: VIDEO.values
                            bindKeyCurrent: "lora1"
                            bindKeyModel: "loras"
                        }
                        OSlider {
                            width: parent.width
                            label: root.tr("Strength 1")
                            bindMap: VIDEO.values
                            bindKey: "strength1"
                            minValue: 0
                            maxValue: 1.5
                            precValue: 2
                            incValue: 0.05
                        }
                        OChoice {
                            width: parent.width; height: 30
                            label: root.tr("LoRA 2")
                            bindMap: VIDEO.values
                            bindKeyCurrent: "lora2"
                            bindKeyModel: "loras"
                        }
                        OSlider {
                            width: parent.width
                            label: root.tr("Strength 2")
                            bindMap: VIDEO.values
                            bindKey: "strength2"
                            minValue: 0
                            maxValue: 1.5
                            precValue: 2
                            incValue: 0.05
                        }
                        SText {
                            width: parent.width
                            height: 24
                            leftPadding: 4
                            text: root.tr("My LoRAs") + (VIDEO.myLoras.length ? " (" + VIDEO.myLoras.length + ")" : "")
                            color: COMMON.fg3
                            pointSize: 9.2
                            verticalAlignment: Text.AlignVCenter
                        }
                        Repeater {
                            model: 8
                            LoraRow {
                                width: sections.width
                                index: model.index
                            }
                        }
                        SButton {
                            width: parent.width; height: 30
                            label: root.tr("Upload LoRA files (.safetensors)")
                            onPressed: loraDialog.open()
                        }
                        LinkInput {
                            width: parent.width
                            height: 30
                            placeholder: root.tr("Hugging Face link, then Add")
                            onSubmitted: VIDEO.addLoraLink(text)
                        }
                    }
                }

                // ---- Files
                OColumn {
                    text: root.tr("Files")
                    width: parent.width
                    isCollapsed: true
                    Column {
                        width: parent.width
                        SButton {
                            width: parent.width; height: 30
                            label: root.tr("Open last video")
                            disabled: VIDEO.lastFile == ""
                            onPressed: VIDEO.openLast()
                        }
                        SButton {
                            width: parent.width; height: 30
                            label: root.tr("Open output folder")
                            onPressed: VIDEO.openOutputFolder()
                        }
                    }
                }
            }
        }
    }

    Status {
        id: status
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        width: root.rightWidth
    }

    Timer {
        id: deleteTimer
        interval: 200
        onTriggered: VIDEO.deleteSelected()
    }

    MessageDialog {
        id: deleteDialog
        title: root.tr("Delete video")
        text: root.tr("Move the selected video, its parameters and its poster to the recycle bin?")
        buttons: MessageDialog.Yes | MessageDialog.No
        onYesClicked: {
            if(playerLoader.item) {
                playerLoader.item.release()   // the player must let go of the file first
            }
            deleteTimer.start()
        }
    }

    FileDialog {
        id: loraDialog
        title: root.tr("Upload LoRA")
        nameFilters: ["LoRA (*.safetensors)"]
        fileMode: FileDialog.OpenFiles
        onAccepted: {
            for(var i = 0; i < loraDialog.files.length; i++) {
                VIDEO.uploadLora(SETTINGS.toLocal(loraDialog.files[i]))
            }
        }
    }
}
