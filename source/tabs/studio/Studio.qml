import QtQuick 2.15
import QtQuick.Controls 2.15
import QtQuick.Layouts 1.15
import QtQuick.Dialogs 1.3
import gui 1.0
import "../../style"
import "../../components"

Item {
    id: root
    property string mode: "T2VA"
    property string brief: ""
    property string extra: ""
    property string refineText: ""
    property int sequenceCount: 3
    property real duration: 6.5
    property string aspect: "Auto (match image)"
    property string dialogue: ""
    property string soundEffects: ""
    property string music: ""
    property var contextTarget: null

    function addUrls(kind, urls) {
        var list = []
        for (var i = 0; i < urls.length; i++) list.push(urls[i].toString())
        if (kind === "image") H3STUDIO.addImages(list)
        else if (kind === "video") H3STUDIO.addVideos(list)
        else H3STUDIO.addAudios(list)
    }

    function removeMedia(kind, index) { H3STUDIO.removeMedia(kind, index) }

    FileDialog { id: imageDialog; title: "Add picture references"; selectMultiple: true; nameFilters: ["Images (*.png *.jpg *.jpeg *.webp *.bmp)"]; onAccepted: root.addUrls("image", fileUrls) }
    FileDialog { id: videoDialog; title: "Add video references"; selectMultiple: true; nameFilters: ["Videos (*.mp4 *.mov *.mkv *.webm *.avi)"]; onAccepted: root.addUrls("video", fileUrls) }
    FileDialog { id: audioDialog; title: "Add audio references"; selectMultiple: true; nameFilters: ["Audio (*.wav *.mp3 *.m4a *.aac *.ogg *.flac)"]; onAccepted: root.addUrls("audio", fileUrls) }



    Rectangle { anchors.fill: parent; color: COMMON.bg0 }

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 8

        RowLayout {
            Layout.fillWidth: true
            ColumnLayout {
                Layout.fillWidth: true
                spacing: 1
                SText { text: "MINIMAX H3 PROMPT STUDIO"; pointSize: 15; color: COMMON.fg1 }
                SText { text: "Multimodal prompt workspace · uses the AI provider configured in Settings → Enhancer"; pointSize: 9; color: COMMON.fg3 }
            }
            SText { text: H3STUDIO.status; pointSize: 9; color: H3STUDIO.busy ? "#e6b45c" : COMMON.fg3 }
        }
        Rectangle { Layout.fillWidth: true; height: 1; color: COMMON.bg4 }

        RowLayout {
            Layout.fillWidth: true
            Layout.fillHeight: true
            spacing: 10

            // Input workspace: media composer above the original creative brief controls.
            Rectangle {
                Layout.preferredWidth: Math.max(570, parent.width * 0.49)
                Layout.minimumWidth: 500
                Layout.fillHeight: true
                color: COMMON.bg00
                border.color: COMMON.bg4

                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 10
                    spacing: 8

                    RowLayout {
                        Layout.fillWidth: true
                        SText { text: "MEDIA"; pointSize: 9; color: COMMON.fg3 }
                        Item { Layout.fillWidth: true }
                        SText { text: H3STUDIO.media.length + "/15"; pointSize: 9; color: COMMON.fg3 }
                        SButton { height: 25; label: "Clear"; onPressed: H3STUDIO.clearMedia() }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        SText { text: "Images, video & audio"; pointSize: 11; color: COMMON.fg1 }
                        Item { Layout.fillWidth: true }
                        SButton { height: 26; label: "+ Images"; onPressed: imageDialog.open() }
                        SButton { height: 26; label: "+ Video"; onPressed: videoDialog.open() }
                        SButton { height: 26; label: "+ Audio"; onPressed: audioDialog.open() }
                    }

                    GridView {
                        id: mediaGrid
                        Layout.fillWidth: true
                        Layout.preferredHeight: 286
                        clip: true
                        cellWidth: Math.floor(width / 4)
                        cellHeight: 138
                        model: H3STUDIO.media
                        delegate: Rectangle {
                            width: mediaGrid.cellWidth - 7
                            height: mediaGrid.cellHeight - 7
                            radius: 6
                            color: COMMON.bg0
                            border.color: COMMON.bg4
                            clip: true

                            Column {
                                anchors.fill: parent
                                spacing: 2
                                Item {
                                    width: parent.width
                                    height: 68
                                    Image {
                                        anchors.fill: parent
                                        source: modelData.thumbnail
                                        visible: modelData.thumbnail !== ""
                                        fillMode: Image.PreserveAspectCrop
                                        asynchronous: true
                                        cache: true
                                    }
                                    Rectangle {
                                        anchors.fill: parent
                                        color: modelData.thumbnail === "" ? COMMON.bg2 : "transparent"
                                        visible: modelData.kind === "audio" || modelData.thumbnail === ""
                                        Text {
                                            anchors.centerIn: parent
                                            text: modelData.kind === "audio" ? "♫" : (modelData.kind === "video" ? "▶" : "▧")
                                            color: COMMON.fg2
                                            font.pixelSize: 26
                                        }
                                    }
                                    Rectangle {
                                        anchors.centerIn: parent
                                        visible: modelData.kind === "video" && modelData.thumbnail !== ""
                                        width: 25; height: 25; radius: 13
                                        color: "#99000000"
                                        Text { anchors.centerIn: parent; text: "▶"; color: "white"; font.pixelSize: 12 }
                                    }
                                }
                                Row {
                                    width: parent.width
                                    height: 25
                                    leftPadding: 5
                                    rightPadding: 3
                                    spacing: 2
                                    Text {
                                        width: parent.width - 25
                                        anchors.verticalCenter: parent.verticalCenter
                                        text: "<" + (index + 1) + "> " + modelData.name
                                        color: COMMON.fg2
                                        font.pixelSize: 9
                                        elide: Text.ElideMiddle
                                    }
                                    ToolButton {
                                        width: 20; height: 22
                                        text: "×"
                                        onClicked: root.removeMedia(modelData.kind, modelData.index)
                                    }
                                }
                                TextField {
                                    visible: modelData.kind === "image"
                                    width: parent.width - 10
                                    height: 27
                                    leftPadding: 6
                                    rightPadding: 6
                                    text: modelData.identity || ""
                                    placeholderText: "Identity name (e.g. Mira, Robot)"
                                    selectByMouse: true
                                    color: COMMON.fg1
                                    font.pixelSize: 9
                                    background: Rectangle { color: COMMON.bg1; border.color: COMMON.bg4; radius: 3 }
                                    onEditingFinished: H3STUDIO.setImageIdentity(modelData.index, text)
                                }
                            }
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 5
                        OSlider {
                            id: durationSlider
                            Layout.fillWidth: true
                            height: 30
                            label: "Seconds"
                            labelWidth: 64
                            value: root.duration
                            minValue: 2
                            maxValue: 15
                            precValue: 1
                            incValue: 0.5
                            snapValue: 0.5
                            onValueChanged: if (Math.abs(root.duration - value) > 0.001) root.duration = value
                        }
                        SText { text: "Aspect"; pointSize: 9; color: COMMON.fg3 }
                        SComboBox {
                            id: aspectCombo
                            Layout.preferredWidth: 205
                            Layout.minimumWidth: 180
                            height: 30
                            model: ["Auto (match image)", "16:9 Landscape", "9:16 Portrait", "1:1 Square", "4:3 Classic", "3:4 Portrait", "21:9 Cinema"]
                            currentIndex: Math.max(0, model.indexOf(root.aspect))
                            onActivated: root.aspect = model[index]
                        }
                    }

                    RowLayout {
                        Layout.fillWidth: true
                        SText { text: "CREATIVE BRIEF"; pointSize: 9; color: COMMON.fg3 }
                        Item { Layout.fillWidth: true }
                        SText { text: "Describe what should happen in the video"; pointSize: 8; color: COMMON.fg3 }
                    }
                    SComboBox {
                        id: modeCombo
                        Layout.fillWidth: true
                        height: 30
                        model: H3STUDIO.modes
                        currentIndex: Math.max(0, model.indexOf(root.mode))
                        onActivated: root.mode = model[index]
                    }
                    TextArea {
                        id: briefArea
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        Layout.minimumHeight: 100
                        text: root.brief
                        onTextChanged: root.brief = text
                        wrapMode: TextEdit.Wrap
                        selectByMouse: true
                        persistentSelection: true
                        color: COMMON.fg1
                        placeholderText: "Describe the scene, subject, action, camera movement, atmosphere, and what should happen over time…"
                        background: Rectangle { color: COMMON.bg0; border.color: COMMON.bg4; radius: 4 }
                    }
                    SInputMenu { anchors.fill: briefArea; target: briefArea }
                    RowLayout {
                        Layout.fillWidth: true
                        SText { text: "Additional direction"; pointSize: 9; color: COMMON.fg2 }
                        Item { Layout.fillWidth: true }
                    }
                    TextField {
                        id: extraField
                        Layout.fillWidth: true
                        text: root.extra
                        onTextChanged: root.extra = text
                        selectByMouse: true
                        persistentSelection: true
                        placeholderText: "e.g. slow cinematic pacing, realistic physics"
                        color: COMMON.fg1
                        background: Rectangle { color: COMMON.bg0; border.color: COMMON.bg4; radius: 3 }
                    }
                    SInputMenu { anchors.fill: extraField; target: extraField }
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: 6
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 3
                            SText { text: "Spoken line"; pointSize: 9; color: COMMON.fg2 }
                            TextArea {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 52
                                text: root.dialogue
                                onTextChanged: root.dialogue = text
                                selectByMouse: true
                                persistentSelection: true
                                wrapMode: TextEdit.Wrap
                                placeholderText: "Dialogue (optional)"
                                color: COMMON.fg1
                                background: Rectangle { color: COMMON.bg0; border.color: COMMON.bg4 }
                                SInputMenu { anchors.fill: parent; target: parent }
                            }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 3
                            SText { text: "Sound effects"; pointSize: 9; color: COMMON.fg2 }
                            TextArea {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 52
                                text: root.soundEffects
                                onTextChanged: root.soundEffects = text
                                selectByMouse: true
                                persistentSelection: true
                                wrapMode: TextEdit.Wrap
                                placeholderText: "Effects / ambience"
                                color: COMMON.fg1
                                background: Rectangle { color: COMMON.bg0; border.color: COMMON.bg4 }
                                SInputMenu { anchors.fill: parent; target: parent }
                            }
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 3
                            SText { text: "Music"; pointSize: 9; color: COMMON.fg2 }
                            TextArea {
                                Layout.fillWidth: true
                                Layout.preferredHeight: 52
                                text: root.music
                                onTextChanged: root.music = text
                                selectByMouse: true
                                persistentSelection: true
                                wrapMode: TextEdit.Wrap
                                placeholderText: "Background music"
                                color: COMMON.fg1
                                background: Rectangle { color: COMMON.bg0; border.color: COMMON.bg4 }
                                SInputMenu { anchors.fill: parent; target: parent }
                            }
                        }
                    }
                    RowLayout {
                        visible: root.mode === "Sequence"
                        Layout.fillWidth: true
                        SText { text: "Clips"; color: COMMON.fg3; pointSize: 9 }
                        SpinBox { from: 2; to: 8; value: root.sequenceCount; onValueChanged: root.sequenceCount = value }
                    }
                    SButton {
                        Layout.fillWidth: true
                        height: 34
                        label: H3STUDIO.busy ? "Working…" : "Generate H3 prompt"
                        disabled: H3STUDIO.busy
                        onPressed: H3STUDIO.generate(root.mode, root.brief, root.duration.toFixed(1), root.aspect, root.extra, root.sequenceCount, root.dialogue, root.soundEffects, root.music)
                    }
                }
            }

            // Keep the generated prompt editor in its established right-hand position.
            Rectangle {
                Layout.fillWidth: true
                Layout.fillHeight: true
                color: COMMON.bg00
                border.color: COMMON.bg4
                ColumnLayout {
                    anchors.fill: parent
                    anchors.margins: 9
                    spacing: 7
                    SText { text: "GENERATED H3 PROMPT"; pointSize: 10; color: COMMON.fg2 }
                    TextArea {
                        id: outputArea
                        Layout.fillWidth: true
                        Layout.fillHeight: true
                        text: H3STUDIO.result
                        onTextChanged: { if (activeFocus) H3STUDIO.setResult(text) }
                        wrapMode: TextEdit.Wrap
                        selectByMouse: true
                        persistentSelection: true
                        color: COMMON.fg1
                        placeholderText: "Your generated prompt will appear here. You can edit it before sending it to Video."
                        background: Rectangle { color: COMMON.bg0; border.color: COMMON.bg4 }
                    }
                    SInputMenu { anchors.fill: outputArea; target: outputArea }
                    RowLayout {
                        Layout.fillWidth: true
                        SButton { Layout.fillWidth: true; height: 30; label: "Refine"; disabled: H3STUDIO.busy || outputArea.text.length === 0; onPressed: H3STUDIO.refine(outputArea.text, root.refineText) }
                        SButton { Layout.fillWidth: true; height: 30; label: "Copy"; disabled: outputArea.text.length === 0; onPressed: outputArea.copy() }
                        SButton { Layout.fillWidth: true; height: 30; label: "Send to Video"; disabled: outputArea.text.length === 0 || H3STUDIO.busy; onPressed: { H3STUDIO.setResult(outputArea.text); H3STUDIO.sendToVideo(root.duration.toFixed(1), root.aspect, root.mode, root.dialogue, root.soundEffects, root.music) } }
                    }
                    TextField {
                        id: refineField
                        Layout.fillWidth: true
                        text: root.refineText
                        onTextChanged: root.refineText = text
                        selectByMouse: true
                        persistentSelection: true
                        placeholderText: "Refine instruction (optional): make camera movement smoother…"
                        color: COMMON.fg1
                        background: Rectangle { color: COMMON.bg0; border.color: COMMON.bg4 }
                    }
                    SInputMenu { anchors.fill: refineField; target: refineField }
                }
            }
        }

        SText {
            Layout.fillWidth: true
            text: "Privacy: local providers keep prepared media on this machine. Remote API providers receive the brief and prepared image/contact-sheet references. Audio content is not analyzed by the prompt model."
            pointSize: 8
            color: COMMON.fg3
            wrapMode: Text.Wrap
        }
    }
}
