import QtQuick 2.15
import QtQuick.Controls 2.15

import gui 1.0

import "../../style"
import "../../components"

Item {
    id: root

    function tr(str, file = "EnhancerSettings.qml") {
        return TRANSLATOR.instance.translate(str, file)
    }

    Connections {
        target: VIDEO
        function onEnhancePresetsUpdated() {
            presetChoice.ready = false
            Qt.callLater(function() {
                presetChoice.sync()
                presetChoice.ready = true
            })
        }
    }

    // a loaded preset changes the provider in the config: the selector follows
    Connections {
        target: GUI.config
        function onUpdated(key) {
            if(key == "enhancer_style") {
                var j = Math.max(0, VIDEO.enhancerStyles.indexOf(GUI.config.get("enhancer_style")))
                if(styleChoice.currentIndex !== j) {
                    styleChoice.currentIndex = j
                }
            }
            if(key == "enhancer_provider") {
                var i = Math.max(0, VIDEO.enhancerProviders.indexOf(GUI.config.get("enhancer_provider")))
                if(providerChoice.currentIndex !== i) {
                    providerChoice.currentIndex = i
                }
            }
        }
    }

    Column {
        anchors.centerIn: parent
        width: parent.width / 2

        SText {
            width: parent.width
            height: 40
            wrapMode: Text.Wrap
            verticalAlignment: Text.AlignVCenter
            horizontalAlignment: Text.AlignHCenter
            pointSize: 9.8
            color: COMMON.fg2
            text: root.tr("H3 Prompt Writer: Enhance combines the Video tab fields into one complete official MiniMax H3 prompt and writes it into Scene / action.")
        }

        OChoice {
            id: presetChoice
            x: -2
            width: parent.width + 2
            height: 30
            label: root.tr("Preset")
            entries: VIDEO.enhancerPresetEntries

            // the preset in use is shown once the list is filled in, and only a choice made afterwards loads one
            property bool ready: false
            function sync() {
                var i = VIDEO.enhancerPresetEntries.indexOf(VIDEO.enhancerPreset)
                presetChoice.currentIndex = i < 0 ? 0 : i
            }
            Component.onCompleted: Qt.callLater(function() {
                presetChoice.sync()
                presetChoice.ready = true
            })
            onCurrentIndexChanged: {
                if(ready && currentIndex > 0) {
                    VIDEO.applyPreset(VIDEO.enhancerPresetEntries[currentIndex])
                }
            }
        }

        OTextInput {
            width: parent.width
            height: 30
            label: root.tr("Preset name")
            placeholder: root.tr("e.g. Claude Haiku")
            bindMap: GUI.config
            plain: true
            bindKey: "enhancer_preset_name"
        }

        Row {
            width: parent.width
            height: 30
            spacing: 4
            SButton {
                width: (parent.width - 4) / 2
                height: parent.height
                label: root.tr("Save preset")
                onPressed: VIDEO.savePreset()
            }
            SButton {
                width: (parent.width - 4) / 2
                height: parent.height
                label: root.tr("Delete preset")
                onPressed: VIDEO.deletePreset()
            }
        }

        Item {
            width: parent.width
            height: 10
        }

        OChoice {
            id: providerChoice
            x: -2
            width: parent.width + 2
            height: 30
            label: root.tr("Provider")
            entries: VIDEO.enhancerProviders

            // the saved provider is put back once the list is filled in, and only a change made afterwards is saved
            property bool ready: false
            Component.onCompleted: Qt.callLater(function() {
                providerChoice.currentIndex = Math.max(0, VIDEO.enhancerProviders.indexOf(GUI.config.get("enhancer_provider")))
                providerChoice.ready = true
            })
            onCurrentIndexChanged: {
                if(ready && currentIndex >= 0) {
                    GUI.config.set("enhancer_provider", VIDEO.enhancerProviders[currentIndex])
                }
            }
        }

        OTextInput {
            width: parent.width
            height: 30
            label: root.tr("API key")
            placeholder: providerChoice.value == "Ollama (local)" ? root.tr("Not needed") : root.tr("None")
            password: true
            bindMap: GUI.config
            plain: true
            bindKey: "enhancer_key"
        }

        OTextInput {
            width: parent.width
            height: 30
            label: root.tr("Model")
            placeholder: providerChoice.value == "Anthropic" ? "claude-haiku-5-5" : (providerChoice.value == "OpenRouter" ? "openrouter/auto" : root.tr("Model name"))
            bindMap: GUI.config
            plain: true
            bindKey: "enhancer_model"
        }

        OTextInput {
            width: parent.width
            height: 30
            label: root.tr("Address")
            placeholder: root.tr("Default of the provider")
            bindMap: GUI.config
            plain: true
            bindKey: "enhancer_url"
        }

        OChoice {
            id: styleChoice
            x: -2
            width: parent.width + 2
            height: 30
            label: root.tr("Prompt system")
            entries: VIDEO.enhancerStyles

            property bool ready: false
            function sync() {
                styleChoice.currentIndex = Math.max(0, VIDEO.enhancerStyles.indexOf(GUI.config.get("enhancer_style")))
            }
            Component.onCompleted: Qt.callLater(function() {
                styleChoice.sync()
                styleChoice.ready = true
            })
            onCurrentIndexChanged: {
                if(ready && currentIndex >= 0) {
                    GUI.config.set("enhancer_style", VIDEO.enhancerStyles[currentIndex])
                }
            }
        }

        OTextInput {
            width: parent.width
            height: 30
            label: root.tr("Additional H3 instructions")
            placeholder: root.tr("Optional, e.g. keep it short")
            bindMap: GUI.config
            plain: true
            bindKey: "enhancer_instructions"
        }

        EnhancerCheck {
            width: parent.width
            height: 58
            label: root.tr("Send frame and Ref2VA reference images to the model")
            hint: root.tr("Attach start / end frames and named Ref2VA images so the H3 Writer can inspect them. Requires a vision-capable model.")
            configKey: "enhancer_send_images"
        }

        Item {
            width: parent.width
            height: 10
        }

        SButton {
            width: parent.width
            height: 30
            label: root.tr("Test connection")
            onPressed: VIDEO.testEnhancer()
        }

        SText {
            width: parent.width
            height: 50
            wrapMode: Text.Wrap
            verticalAlignment: Text.AlignVCenter
            horizontalAlignment: Text.AlignHCenter
            pointSize: 9.5
            color: VIDEO.enhancerStatus.indexOf("Failed") === 0 ? COMMON.accent(0) : COMMON.fg2
            text: VIDEO.enhancerStatus
        }

        SText {
            width: parent.width
            height: 40
            wrapMode: Text.Wrap
            verticalAlignment: Text.AlignVCenter
            horizontalAlignment: Text.AlignHCenter
            pointSize: 8.8
            color: COMMON.fg3
            text: root.tr("The key is saved in config.json next to the program. The text of the box (and the other prompt boxes, as context) is sent to the provider, and the attached start / end and Ref2VA reference images too if that option is on.")
        }
    }
}
