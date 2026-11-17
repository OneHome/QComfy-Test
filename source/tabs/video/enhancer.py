"""Prompt enhancer: sends the text of one prompt box to a language model API and returns the improved text.
No Qt in here, so it can be tested on its own. Uses only the standard library (urllib)."""
import json
import re
import socket
import urllib.error
import urllib.request


class EnhancerError(Exception):
    def __init__(self, message, status=None):
        super().__init__(message)
        self.status = status      # HTTP status when the service answered with an error


# kind "openai": POST {url}/chat/completions (OpenAI, Gemini, OpenRouter, Ollama, LM Studio, ...)
# kind "anthropic": POST {url}/messages
PROVIDERS = {
    "OpenAI": {"kind": "openai", "url": "https://api.openai.com/v1", "model": "", "key": True},
    "Anthropic": {"kind": "anthropic", "url": "https://api.anthropic.com/v1", "model": "claude-haiku-5-5", "key": True},
    "Google Gemini": {"kind": "openai", "url": "https://generativelanguage.googleapis.com/v1beta/openai", "model": "", "key": True},
    "OpenRouter": {"kind": "openai", "url": "https://openrouter.ai/api/v1", "model": "openrouter/auto", "key": True},
    "Ollama (local)": {"kind": "openai", "url": "http://localhost:11434/v1", "model": "", "key": False},
    "Custom (OpenAI-compatible)": {"kind": "openai", "url": "", "model": "", "key": False},
}
PROVIDER_NAMES = list(PROVIDERS)

FIELD_LABELS = {
    "prompt": "Scene / action",
    "dialogue": "Spoken line",
    "sound": "Sound effects / ambience",
    "music": "Music",
}

# Duckyshell H3 Prompt Writer / official MiniMax H3 prompt-writing contract.
# QComfy deliberately reuses its existing provider/API settings; only the writing
# contract is shared with the upstream Writer. No Lightx2v prompt is downloaded.
H3_STYLE = "Duckyshell H3 Writer"
STANDARD_STYLE = H3_STYLE  # migrate old saved "Standard" settings to the unified H3 writer
STYLES = [H3_STYLE]

BASE_GUIDE = r"""You are the H3 Prompt Writer. Rewrite the user's Creative Brief into a complete MiniMax H3 audiovisual prompt. Follow the official MiniMax H3 Base guide for T2VA, I2VA, FL2VA, and L2VA.

OUTPUT FORMAT (exact field names and order):
integrated_multimodal_description: [Shot 1] ...

overall_soundscape: ...

non_diegetic_music: ...

KEYFRAME INSTRUCTIONS:
- T2VA: no alignment preamble; start directly with the three fields.
- I2VA: the FIRST line must be: For the target video, at 0.00 seconds into the target video, <Picture 1> (from [Shot 1]) is fully referenced.
- FL2VA: the first line must be: How the reference pictures align with the target video — Picture 1 (from Shot 1) aligns with the 0.00-second mark of the target video; Picture 2 (from Shot 1) aligns with the DURATION-second mark of the target video.
- L2VA: the first line must be: How the reference pictures align with the target video — <Picture 1> (from [Shot N]) aligns with the DURATION-second mark of the target video. N is the actual final shot number.
For I2VA/FL2VA/L2VA, put one blank line between the alignment instruction and the three core fields. Format DURATION to exactly two decimal places.

VISUAL TIMELINE:
- integrated_multimodal_description is the main audiovisual timeline. Begin with [Shot 1], with no timestamp on that first shot. Later shots use sequential numbering and start with a strictly increasing cut timestamp in the exact form [Shot 2] At 00:03.500, ...; timestamps must fall within the requested duration.
- For each shot describe concrete composition, subjects and their positions/appearance, environment, action and reaction, camera framing/movement, lighting/color, and synchronized diegetic sound where relevant. Avoid abstract plot summaries.
- Use a continuous shot when that best serves the request; do not add cuts merely to create activity. Camera movement should be expressed naturally and specify movement type, amplitude and speed when meaningful.
- I2VA starts from the supplied first frame and develops forward while preserving identity, clothing, objects, spatial relationships and scene anchors.
- FL2VA describes a continuous, plausible motion path from the first frame to the last frame; the final shot must land on the supplied last frame.
- L2VA infers a plausible preceding state and converges naturally to the supplied last frame in the final shot.
- Do not contradict attached frames. If frames are not actually attached to the model request, do not invent or describe their visual contents.

DIALOGUE AND SOUND:
- Give each speaking/singing voice a stable ID (S1), (S2), etc. Describe the voice and delivery outside the dialogue tag. Wrap only the exact spoken words in <d>[Language] ...</d>. Preserve supplied dialogue, lyrics, language and punctuation verbatim; do not translate or paraphrase.
- Voiceover must say "says in an off-screen voiceover" and immediately state that the corresponding on-screen character's lips remain completely closed.
- Use <scenetrans> for dialogue continuing across a cut and <cutoff> for speech truncated by the video ending; state audio continuity explicitly.
- Put visible signs, subtitles and other on-screen text in English double quotation marks, preserving their exact original text.
- overall_soundscape: 1–4 English sentences in one paragraph covering ambience, physical action sounds and non-verbal human sounds across the whole clip. Do not repeat dialogue, singing or diegetic music. Use N/A only if complete silence is explicitly requested.
- non_diegetic_music: 1–3 English sentences describing audience-only background music through instruments, tempo, rhythm and dynamic changes. Use N/A if no background score is requested. Music audible to characters belongs in the shot description instead.

Write the descriptive sections in English, but preserve dialogue, lyrics and visible text in their original language. Output only the complete prompt, without markdown fences, commentary or explanations."""

REFERENCE_GUIDE = r"""You are the H3 Prompt Writer in full-reference (Ref2VA) mode. Rewrite the Creative Brief and reference manifest into a complete MiniMax H3 full-reference prompt. Follow the official MiniMax H3 Reference guide.

OUTPUT EXACTLY SIX SECTIONS IN THIS ORDER:
subject_definitions: ...

summary: ...

retention_analysis: ...

detailed_description: ...

overall_soundscape: ...

non_diegetic_music: ...

REFERENCE LABELS:
- <Subject N> identifies reusable visible content (person, animal, object, environment, clothing, prop, style, action, expression or pose), not the source file itself. Define each distinct reusable content unit and cite its source assets.
- <Picture N> is a concrete frame/keyframe/storyboard/composition anchor. If an image only defines a subject, cite it in that subject's definition instead of creating a separate Picture entry.
- <Video N> identifies a whole-video source used for editing, continuation, camera/cut/rhythm or temporal structure. Reused visible content from it still gets a <Subject N> label.
- <Audio N> identifies a standalone audio reference. Audio labels are independent of Video numbering. Do not infer an audio reference merely because a video file has an audio track.
- Keep every label's meaning and numbering consistent in all six sections. Do not invent missing assets or labels.

SECTION RULES:
1. subject_definitions: one line per tracked item, defining what the label denotes, its role and key features; name source assets where useful.
2. summary: one short English paragraph beginning with a square-bracketed task prefix assembled from the actual relationships: [keyframe completion], [reference generation], [video editing], [video continuation], [audio reuse], and/or [audio reference], joined by " + ". Mere presence of an asset does not imply editing, continuation or audio reuse.
3. retention_analysis: one line for each defined reference label. For Subject/Picture/Video use only fully_preserved, partially_preserved, attribute_transfer or weak_reference. For Audio use only fully_copy, partially_copy, reference or weak_reference. Explain where/how it is retained.
4. detailed_description: main body, in playback order, with concrete shot composition, subject appearance/position, environment, lighting, actions/state changes, camera movement, sound and the exact points where references appear or take effect. Establish overall style in one or two English sentences before [Shot 1]. [Shot 1] has no timestamp; later shots use [Shot N] At MM:SS.mmm, ... with increasing in-range cut times. Use reference labels where relevant; do not reduce this section to a plot summary or list of relationships.
5. overall_soundscape: 1–4 English sentences for ambience, physical sounds and non-verbal human sounds; do not repeat dialogue or music.
6. non_diegetic_music: 1–3 English sentences for audience-only background score, or N/A when none is requested.

DIALOGUE: assign stable speaker IDs (S1), (S2), etc.; describe voice and delivery outside <d>; preserve exact user-provided words, language and punctuation inside <d>[Language] ...</d>. Preserve visible text verbatim in double quotes. Describe camera motion naturally, with type/amplitude/speed when meaningful. Write all rewrite sections in English except dialogue, lyrics and visible text, which retain their original language.

Do not claim to analyze audio bytes: use only the written brief and manifest roles supplied to you. Output only the six-section prompt, without markdown fences, commentary or explanations."""


def h3_system_prompt(mode="T2VA"):
    return REFERENCE_GUIDE if str(mode).lower() in ("reference", "ref2va") else BASE_GUIDE


def h3_task(frames):
    """Choose the official H3 writing guide from the actual Video-tab inputs."""
    frames = frames or {}
    if int(frames.get("refs") or 0) > 0:
        return "Reference"
    start, end = bool(frames.get("start")), bool(frames.get("end"))
    return "FL2VA" if start and end else "I2VA" if start else "L2VA" if end else "T2VA"


def build_h3_user(boxes, task, seconds, language, frames, images_attached, aspect=""):
    frames = frames or {}
    duration = f"{float(seconds):.2f}"
    selected_aspect = str(aspect or "Auto (match image)")
    lines = [f"Input mode: {task}", f"Target video duration: {duration} seconds",
             f"Aspect ratio: {selected_aspect}"]

    # Frame/keyframe numbering follows the actual order sent to the vision model:
    # start frame, end frame, then the Ref2VA reference images.
    picture_index = 1
    if frames.get("start"):
        lines.append("<Picture 1> is the first frame at 0.00 seconds.")
        picture_index += 1
    if frames.get("end"):
        lines.append(f"<Picture {picture_index}> is the last frame at {duration} seconds.")
        picture_index += 1

    ref_count = int(frames.get("refs") or 0)
    ref_names = list(frames.get("ref_names") or [])
    if ref_count:
        lines += ["", "Ref2VA full-reference image manifest (the images are attached in this exact order):"]
        for i in range(ref_count):
            name = (str(ref_names[i]).strip() if i < len(ref_names) else "") or f"Reference subject {i + 1}"
            lines.append(f"<Picture {picture_index + i}>: {name} — reference image defining this named character/object's visual identity and appearance.")
        lines.append("Treat each named reference as a persistent identity/appearance source. Preserve its recognizable features when that character or object appears; do not rename or merge distinct references.")

    if (frames.get("start") or frames.get("end") or ref_count) and not images_attached:
        lines.append("The image files are not attached to this AI request. Respect the written asset roles and names, but do not claim to see or invent visual details from the images.")

    lines += ["", "Creative Brief / scene and action:",
              (boxes.get("prompt") or "").strip() or "(Use the supplied reference assets and infer a coherent, visually clear action.)"]
    if (boxes.get("dialogue") or "").strip():
        lines += ["", f"Exact dialogue to preserve (language: {language}):", boxes["dialogue"].strip()]
    if (boxes.get("sound") or "").strip():
        lines += ["", "Requested sound effects and ambience:", boxes["sound"].strip()]
    if (boxes.get("music") or "").strip():
        lines += ["", "Requested non-diegetic background music:", boxes["music"].strip()]
    return "\n".join(lines)


def enhance_h3(settings, boxes, frames, images, seconds, language="English", extra="", notes=None, timeout=120, aspect=""):
    """Generate one complete Duckyshell-style MiniMax H3 prompt.

    Ref2VA references use the Reference guide and include their names/manifest;
    ordinary text, first/last-frame modes use the Base guide.
    """
    task = h3_task(frames)
    system = h3_system_prompt(task)
    if (extra or "").strip():
        system += "\n\nAdditional user instructions (obey if compatible with the official format):\n" + extra.strip()
    user = build_h3_user(boxes, task, seconds, language, frames, bool(images), aspect=aspect)
    result = request(settings, system, user, timeout, images or None)
    expected = "subject_definitions" if task == "Reference" else "integrated_multimodal_description"
    if expected not in result and notes is not None:
        notes.append(f"The model did not return the expected official H3 field '{expected}'. Check whether the selected model follows long structured instructions.")
    return result

def build_system(field, extra="", mode="", frames=None):
    """Compatibility helper: the unified writer always uses the official H3 contract."""
    system = h3_system_prompt(h3_task(frames or {}))
    if (extra or "").strip():
        system += "\n\nAdditional user instructions (obey if compatible with the official format):\n" + extra.strip()
    return system


FIELD_LABELS = {"prompt": "Scene / action", "dialogue": "Spoken line", "sound": "Sound effects / ambience", "music": "Music"}

def build_user(field, text, context=None):
    boxes = dict(context or {})
    boxes[field if field in FIELD_LABELS else "prompt"] = text
    return build_h3_user(boxes, h3_task({}), 5.0, "English", {}, False)

def clean(text):
    text = (text or "").strip()
    text = re.sub(r"^```[a-zA-Z]*\s*|\s*```$", "", text).strip()
    text = re.sub(r"^(enhanced|improved|rewritten|revised)?\s*(prompt|text|version)\s*:\s*", "", text, flags=re.IGNORECASE)
    if len(text) >= 2 and text[0] == text[-1] and text[0] in "\"'\u201c\u201d":
        text = text[1:-1].strip()
    if len(text) >= 2 and text[0] == "\u201c" and text[-1] == "\u201d":
        text = text[1:-1].strip()
    return text


def resolve(settings):
    """settings: {"provider", "url", "model", "key"} -> (kind, url, model, key)"""
    spec = PROVIDERS.get(settings.get("provider") or "")
    if spec is None:
        raise EnhancerError("Choose a provider in Settings > Enhancer.")
    base = (settings.get("url") or "").strip().rstrip("/") or spec["url"]
    if not base:
        raise EnhancerError("Set the API address in Settings > Enhancer.")
    model = (settings.get("model") or "").strip() or spec["model"]
    if not model:
        raise EnhancerError("Set a model name in Settings > Enhancer.")
    key = (settings.get("key") or "").strip()
    if spec["key"] and not key:
        raise EnhancerError("Set the API key in Settings > Enhancer.")
    suffix = "/chat/completions" if spec["kind"] == "openai" else "/messages"
    url = base if base.endswith(suffix) else base + suffix
    return spec["kind"], url, model, key


def _error_text(body):
    try:
        data = json.loads(body)
        err = data.get("error", data) if isinstance(data, dict) else data
        if isinstance(err, dict):
            return str(err.get("message") or err.get("detail") or err)
        return str(err)
    except Exception:
        return (body or "").strip()[:300]


def request(settings, system, user, timeout=90, images=None):
    """images: [(mime, base64 text)] attached to the user message."""
    kind, url, model, key = resolve(settings)
    headers = {"Content-Type": "application/json", "User-Agent": "qComfy-prompt-enhancer"}
    if kind == "anthropic":
        headers["x-api-key"] = key
        headers["anthropic-version"] = "2023-06-01"
        content = user
        if images:
            content = [{"type": "image", "source": {"type": "base64", "media_type": m, "data": d}} for m, d in images]
            content.append({"type": "text", "text": user})
        payload = {"model": model, "max_tokens": 4096, "system": system, "messages": [{"role": "user", "content": content}]}
    else:
        if key:
            headers["Authorization"] = "Bearer " + key
        # no temperature / max_tokens on purpose: some models refuse them and the instructions already limit the length
        content = user
        if images:
            content = [{"type": "text", "text": user}]
            content += [{"type": "image_url", "image_url": {"url": f"data:{m};base64,{d}"}} for m, d in images]
        payload = {"model": model, "messages": [{"role": "system", "content": system}, {"role": "user", "content": content}]}

    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            body = response.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        detail = _error_text(e.read().decode("utf-8", errors="replace"))
        hint = " (check the API key)" if e.code in (401, 403) else (" (check the model name)" if e.code == 404 else "")
        raise EnhancerError(f"The service answered {e.code}{hint}: {detail}", e.code)
    except (socket.timeout, TimeoutError):
        raise EnhancerError("The service took too long to answer.")
    except urllib.error.URLError as e:
        if isinstance(e.reason, (socket.timeout, TimeoutError)):
            raise EnhancerError("The service took too long to answer.")
        raise EnhancerError(f"Could not connect to {url}: {e.reason}")
    except OSError as e:
        raise EnhancerError(f"Connection problem: {e}")

    try:
        data = json.loads(body)
        if kind == "anthropic":
            text = "".join(b.get("text", "") for b in data.get("content", []) if b.get("type") == "text")
        else:
            content = data["choices"][0]["message"]["content"]
            if isinstance(content, list):
                content = "".join(p.get("text", "") for p in content if isinstance(p, dict))
            text = content
    except Exception:
        raise EnhancerError("The answer of the service could not be understood: " + body[:200])
    text = clean(text)
    if not text:
        raise EnhancerError("The service returned an empty answer.")
    return text


def enhance(settings, field, text, context=None, extra="", images=None, frames=None, notes=None, timeout=90):
    """Backward-compatible entry point; every field now produces one complete H3 prompt."""
    boxes = dict(context or {})
    boxes[field if field in FIELD_LABELS else "prompt"] = text
    frames = frames or {}
    seconds = float((context or {}).get("seconds", 5.0)) if isinstance(context, dict) else 5.0
    return enhance_h3(settings, boxes, frames, images or [], seconds, "English", extra, notes, timeout)
