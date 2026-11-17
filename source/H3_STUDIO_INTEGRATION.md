# QComfy – H3 Prompt Studio integration

This build adds a native **H3 Studio** tab to QComfy. It reuses the existing Settings → Enhancer provider configuration (provider, API key, model, endpoint, and extra instructions) and the existing Video tab as the final MiniMax H3 generation destination.

## Included in this integration

- Native QML workspace with a media-card grid (image/video thumbnails and generic audio icons), Creative Brief, mode selector, generated prompt editor, Refine, Copy, and Send to Video.
- QComfy-native duration control (2–15 seconds in 0.5-second steps), QComfy-native aspect-ratio selector including “Auto (match image)”, persistent mouse text selection, and a right-click edit menu (Cut, Copy, Paste, Select all).
- Modes: T2VA, I2VA, FL2VA, L2VA, Reference, and Sequence.
- Up to 9 image references, 3 video references, and 3 audio references.
- Video references are sampled locally into contact sheets (up to six frames per video) and sent as image references to the configured vision-capable prompt model.
- Image and video reference tags are included in the brief so the model can assign them roles.
- Sequence mode requests multiple independently structured clip prompts, with consistent characters and continuity. Send to Video loads the first clip; subsequent clips are reviewed and submitted manually.
- Sending a prompt transfers the editable prompt to the existing Video tab and maps duration, aspect, spoken dialogue, sound effects, and music. For I2VA, FL2VA, and L2VA it also assigns the appropriate first/last frame image.
- Existing QComfy image-generation tabs and existing Video generation backend are left intact.

## Setup

1. Start QComfy as usual.
2. Open Settings → Enhancer and configure a provider/model. Use a vision-capable model for image/video-reference modes. T2VA and Refine can use text-only models.
3. Open the **H3 Studio** tab, write a brief, select a mode, and optionally add media.
4. Generate, edit/refine the result, then select **Send to Video**. Review the Video tab settings and press Generate when ready.

The existing enhancer key is reused; this integration does not create a second key store. The H3 Studio request is sent through `tabs.video.enhancer.request`, so the configured QComfy provider, endpoint, model, and API key remain authoritative. This build does not install or start a second provider runtime.

## Important limitations in this first integrated build

- Audio files are catalogued and their names/roles are passed as context, but audio bytes are not analyzed. Describe the desired soundtrack, dialogue, or ambience in the the dedicated Spoken line, Sound effects / ambience, and Background music fields. These text fields are included in the H3 prompt request; audio bytes themselves are not analyzed.
- Video understanding is based on sampled contact-sheet frames, not full temporal/audio decoding.
- The existing QComfy video engine exposes first/last-frame inputs, not a general multi-reference loader. Reference mode uses all selected media to write the prompt, but only the text and supported first/last frames are transferred to the Video tab.
- Sequence mode produces a set of prompts in one editable result. The first clip is sent automatically; later clips must be selected/copied and run manually in Video.
- The upstream Media Editor, drag-and-drop Media panel, and full collage composer have not been ported into this first integration. They remain follow-up work rather than being represented as implemented.
- Video reference processing requires PyAV (`av`). The app's existing requirements include `av>=10.0.0`; if it is missing in a portable environment, install it in QComfy's Python environment with `python -m pip install av`.

## Upstream project and license

This integration follows the feature concepts and modes of [ComfyUI-MiniMaxH3-Prompt-Writer](https://github.com/duckyshell/ComfyUI-MiniMaxH3-Prompt-Writer), by duckyshell. The upstream README describes its own provider options (Ollama, Direct GGUF, External llama.cpp, and API providers) and says it includes official MiniMax base and Reference guides. QComfy currently reuses its own Enhancer provider/API layer instead of bundling the upstream standalone runtime or provider manager. Both H3 Studio and Video now use one shared Duckyshell-style H3 writing contract, based on MiniMax's official Base and full-Reference prompt guides. Video Enhance combines Scene / action, Spoken line, Sound effects and Music into one complete H3 prompt and writes it into Scene / action; the previous per-box Standard enhancer and Lightx2v prompt download are no longer selectable. The existing QComfy provider/API layer remains unchanged. The port implements the official output structures and keyframe/reference rules, but does not port Duckyshell's separate provider manager, local model runtimes, sequence planner, or media editor. The upstream project is MIT-licensed. See `THIRD_PARTY_NOTICES.txt`.


## Unified Duckyshell H3 Writer update

- Video → Enhance now uses the same shared H3 writing contract as H3 Studio. Pressing Enhance in any Video prompt field generates one complete prompt and places it in Scene / action; the other fields are incorporated into their matching H3 sections. Undo restores the previous Scene / action text.
- The previous Standard per-field enhancer and Lightx2v MiniMax-H3-Prompt-Rewriter-LoRA-Omni system-prompt download have been removed from the selectable Video prompt systems. Existing saved `Standard` settings automatically fall back to the unified writer.
- Base/keyframe modes follow MiniMax's `base-en.txt` structure; full Reference mode follows `ref-en.txt` with six ordered sections. Duckyshell's upstream usage describes the same mode distinction and output structure.
- QComfy still uses the configured Enhancer provider/API. This is a port of the prompt-writing contract, not the upstream provider runtime or its full media/sequence toolset. Audio files remain manifest-only in QComfy and are not acoustically analyzed.

Prompt-guide sources: [MiniMax H3 Base guide](https://github.com/MiniMax-AI/MiniMax-H3/blob/main/skills/h3-prompt-writing/references/base-en.txt), [MiniMax H3 Reference guide](https://github.com/MiniMax-AI/MiniMax-H3/blob/main/skills/h3-prompt-writing/references/ref-en.txt), and [Duckyshell H3 Prompt Writer usage](https://github.com/duckyshell/ComfyUI-MiniMaxH3-Prompt-Writer/blob/main/docs/USAGE.md).
