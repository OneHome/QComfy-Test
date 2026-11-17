"""Video tab: sends video requests to video_server.py (MiniMax H3 engine) and saves the MP4 it returns.

Protocol (see comfy-inference-server/video_server.py):
  options        -> {"type": "options", "data": {"video": {aspects, durations, outputs, preview_only, presets,
                     languages, loras, no_lora, ...}}}
  video          -> video_progress {fraction, text, elapsed} ... video_chunk {id, index, total, data} ...
                    video {id, name, kind, status, size, duration, aspect, eta}      (the 384p preview)
  video_upscale  -> same replies, kind "upscale"                                     (720p / 1080p / 2K)
  video_discard  -> video_discarded {name, files}                                    (frees the preview)
Cancelling goes through the usual {"type": "cancel"} request.
"""
import os
import re
import math
import glob
import json
import time
import datetime
import threading

from PyQt5.QtCore import Qt, pyqtProperty, pyqtSlot, pyqtSignal, QObject, QUrl, QTimer, QFileSystemWatcher
from PyQt5.QtQml import qmlRegisterSingletonType
from PyQt5.QtGui import QImage, QDesktopServices, QGuiApplication
from PyQt5.QtWidgets import QApplication, QSystemTrayIcon

import parameters
from tabs.video import enhancer
from misc import MimeData, encodeImage

try:
    import send2trash
except ImportError:      # deleting still works, just without the recycle bin
    send2trash = None

# ---------------------------------------------------------------- protocol names
REQ_GENERATE = "video"
REQ_UPSCALE = "video_upscale"
REQ_DISCARD = "video_discard"
RES_PROGRESS = "video_progress"
RES_CHUNK = "video_chunk"
RES_VIDEO = "video"
# ------------------------------------------------------------------------------

FPS = 24
MAX_MY_LORAS = 8
DEFAULT_RESOLUTION = "384p (default)"
PREVIEW_ONLY = "384p preview only"
NO_LORA = "None"

VIDEO_INSTANCE = None

# shown until the server sends its own tables (they are replaced by the "options" reply)
FALLBACK = {
    "aspects": ["16:9 Landscape", "9:16 Portrait", "1:1 Square", "4:3 Classic", "3:4 Portrait", "21:9 Cinema",
                "Auto (match image)"],
    "durations": {"3 s": 73, "4.5 s": 107, "5 s": 124, "6.5 s": 158, "8 s": 192, "10 s": 243, "12 s": 294, "15 s": 362},
    "outputs": ["720p", "1080p", "2K (1440p)"],
    "presets": ["\u26a1 Fast - 2 steps, slim overlaps", "\u2696\ufe0f Balanced - 3 steps",
                "\U0001f48e Quality - 3 steps, bigger tiles"],
    "languages": ["English", "Chinese", "Spanish", "French", "German", "Japanese", "Korean", "Hindi", "Urdu",
                  "Arabic", "Portuguese", "Russian", "Italian", "Turkish", "Indonesian"],
}

DEFAULTS = {
    "prompt": "", "dialogue": "", "sound": "", "music": "",
    "language": "English", "seconds": 5.0, "aspect": "Auto (match image)", "output": PREVIEW_ONLY,
    "preset": FALLBACK["presets"][1], "seed": -1, "refine_seed": -1,
    "lora1": NO_LORA, "strength1": 1.0, "lora2": NO_LORA, "strength2": 1.0,
    "sampler": "euler", "samplers": ["euler", "res_multistep"], "shift": 12.0, "steps": 0, "anchor": True,
    "resolution": DEFAULT_RESOLUTION, "resolutions": [DEFAULT_RESOLUTION],
    "start_frame": "", "end_frame": "", "notify": True, "title": "", "ref_size": 70,
    **{f"mylora_s{i}": 1.0 for i in range(MAX_MY_LORAS)},
    "aspects": FALLBACK["aspects"], "outputs": [PREVIEW_ONLY] + FALLBACK["outputs"],
    "presets": FALLBACK["presets"], "languages": FALLBACK["languages"], "loras": [NO_LORA],
}


def label_seconds(label, frames=None):
    try:
        return float(str(label).split()[0])
    except Exception:
        return (frames or 0) / FPS


DEFAULT_REF_NAMES = ("the main subject", "the subject")   # the labels the server uses for a reference without a name


def clean_ref_name(name):
    """A name for <Subject N>: one short line, no commas (the server splits the names on commas)."""
    return " ".join(str(name or "").replace(",", " ").split())[:60]


def ref_names_for_request(names):
    """One name per reference, in order. A blank one gets the generic label, so the position of the other names
    (<Subject N> follows the order of the references) cannot shift."""
    return [clean_ref_name(n) or DEFAULT_REF_NAMES[0 if i == 0 else 1] for i, n in enumerate(names)]


def nearest_duration(seconds, durations):
    """The server only knows a few clip lengths (label -> frames): use the closest one."""
    return min(durations, key=lambda k: abs(label_seconds(k, durations[k]) - float(seconds)))


def fmt_secs(s):
    s = int(round(s))
    return f"{s // 60}m{s % 60:02d}s" if s >= 60 else f"{s}s"


def short_side(resolution):
    m = re.match(r"\s*(\d+)p", str(resolution))
    return int(m.group(1)) if m else 384


def preview_size(aspect, ratio_img=None, short=384):
    ratios = {"16:9 Landscape": 16 / 9, "9:16 Portrait": 9 / 16, "1:1 Square": 1.0, "4:3 Classic": 4 / 3,
              "3:4 Portrait": 3 / 4, "21:9 Cinema": 21 / 9}
    ratio = ratios.get(aspect) or ratio_img or 16 / 9
    area = max(1, round(short * 16 / 9 / 32)) * 32 * short   # 384p -> 672x384, 480p -> 864x480 ...
    w = max(256, round(math.sqrt(area * ratio) / 32) * 32)
    h = max(256, round(area / w / 32) * 32)
    return w, h


def preview_eta(frames, aspect, ratio_img=None, short=384):
    """Rough local estimate of the 4-step preview time (T4 x2). Only a hint."""
    w, h = preview_size(aspect, ratio_img, short)
    latent_t = (frames - 1) // 4 + 1
    rows = latent_t * (h // 32) * (w // 32) + round(frames / FPS * 40) * 2 + 600
    x = rows / 16384
    step = 24.0 * x * x + 7.0 * x + 6.0
    return 12 + 4 * step + 0.6e-6 * w * h * frames + 5.0


def parse_lora_link(text):
    """(ok, link_or_message, label). Accepts Hugging Face / mirror / direct .safetensors links and user/repo/file."""
    text = str(text).strip().strip('"')
    if not text:
        return False, "Paste a link first.", ""
    if "://" not in text:
        m = re.match(r"^([\w.-]+/[\w.-]+)/(.+\.safetensors)$", text)
        if not m:
            return False, "Use a https:// link or user/repo/file.safetensors.", ""
        return True, text, os.path.basename(m.group(2))
    if not re.match(r"^https?://", text):
        return False, "A LoRA link must start with https://", ""
    host = re.match(r"^https?://([^/]+)", text).group(1).lower()
    path = text.split("?")[0]
    if host.endswith("huggingface.co") and not re.search(r"/(resolve|blob)/", path):
        return False, "Link the .safetensors file itself (the page of the file, with /blob/ or /resolve/), not the repo.", ""
    label = os.path.basename(path.rstrip("/")) or host
    return True, text, label


def clip_kind(name, meta):
    kind = (meta or {}).get("kind")
    if kind in ("preview", "final"):
        return kind
    if name.endswith("_final.mp4"):
        return "final"
    if name.endswith("_preview.mp4"):
        return "preview"
    return "other"


def fmt_bytes(n):
    return f"{n / 1024 ** 2:.1f} MB" if n >= 1024 ** 2 else f"{n / 1024:.0f} KB"


def clip_dims(meta):
    if meta.get("width") and meta.get("height"):
        return f"{meta['width']}x{meta['height']}"
    return ""


def format_meta(item):
    """The text of the Parameters box for one clip."""
    meta = item.get("meta") or {}
    lines = []
    if meta:
        lines.append(str(meta.get("prompt") or "").strip() or "(no scene prompt)")
        for key, label in (("dialogue", "Spoken line"), ("sound", "Sound effects"), ("music", "Music")):
            if str(meta.get(key) or "").strip():
                lines.append(f"{label}: {meta[key]}")
        frames = []
        if meta.get("start_frame"):
            frames.append("start frame")
        if meta.get("end_frame"):
            frames.append("end frame")
        if frames:
            lines.append("Used a " + " and ".join(frames) + " (the images are not stored)")
        lines.append("")
        clip = [f"Clip: {meta.get('duration', '?')}" + (f" ({meta['frames']} frames)" if meta.get("frames") else "")]
        if clip_dims(meta):
            clip.append(f"Size: {clip_dims(meta)}")
        clip += [f"Resolution: {meta.get('resolution', '?')}", f"Aspect: {meta.get('aspect', '?')}",
                 f"Language: {meta.get('language', '?')}"]
        lines.append(", ".join(clip))
        lines.append(f"Seed: {meta.get('seed', '?')}, Sampler: {meta.get('sampler', '?')}, "
                     f"Flow shift: {meta.get('shift', '?')}, Steps: {meta.get('steps') or '0 (PDMD 4)'}")
        if meta.get("loras"):
            lines.append("LoRA: " + ", ".join(f"{x['name']}:{x['strength']:.2f}" for x in meta["loras"]))
        up = meta.get("upscale")
        if up:
            lines.append(f"Upscale: {up.get('output')}, {up.get('preset')}, refine seed {up.get('seed')}, "
                         f"re-anchor {'on' if up.get('anchor') else 'off'}")
        took = meta.get("took_seconds")
        lines.append(f"Generated: {str(meta.get('created', '')).replace('T', ' ')}"
                     + (f", took {fmt_secs(took)}" if took else "") + f", {fmt_bytes(item['size'])}")
    else:
        lines.append("No parameters were saved for this video (it was made before the gallery existed).")
        lines.append("")
        lines.append(f"{item['name']}, {fmt_bytes(item['size'])}")
        lines.append(datetime.datetime.fromtimestamp(item["mtime"]).strftime("%Y-%m-%d %H:%M"))
    return "\n".join(lines)


TEMPLATES_FILE = "video_templates.json"
TEMPLATE_FIELDS = ("prompt", "dialogue", "sound", "music")

LEGACY_DEFAULTS = [
    {"name": "Camera", "field": "prompt", "items": [
        "static shot", "slow push-in", "slow pull-out", "tracking shot", "handheld camera", "pan left", "pan right",
        "orbit around the subject", "low angle", "aerial view", "close-up", "wide shot"]},
    {"name": "Lighting", "field": "prompt", "items": [
        "golden hour light", "soft diffused light", "dramatic side lighting", "neon lighting", "moody low-key lighting",
        "natural daylight", "backlit silhouette", "candlelight"]},
    {"name": "Style", "field": "prompt", "items": [
        "cinematic", "photorealistic", "35mm film look", "shallow depth of field", "documentary style", "anime style",
        "claymation", "vintage VHS look"]},
    {"name": "Motion", "field": "prompt", "items": [
        "slow motion", "smooth motion", "dynamic action", "subtle motion", "gentle breeze moving hair and clothes", "time-lapse"]},
    {"name": "Sound effects", "field": "sound", "items": [
        "gentle wind", "city traffic", "rain on a window", "footsteps", "crowd murmur", "birds chirping", "ocean waves", "quiet room tone"]},
    {"name": "Music", "field": "music", "items": [
        "soft ambient piano", "tense orchestral strings", "upbeat electronic", "lo-fi beat", "epic cinematic drums", "melancholic guitar"]},
]



DEFAULT_TEMPLATES = [
    {"name": "Shot size / framing", "field": "prompt", "items": [
        "extreme close-up", "close-up", "medium close-up", "medium shot", "cowboy shot", "full body shot", "wide shot",
        "extreme wide establishing shot", "over-the-shoulder shot", "two-shot", "point-of-view shot", "eye-level",
        "low angle", "high angle", "bird's-eye view", "worm's-eye view", "dutch angle", "centered symmetrical composition",
        "rule of thirds composition", "foreground framing"]},
    {"name": "Camera movement", "field": "prompt", "items": [
        "static locked-off shot", "slow push-in", "slow pull-out", "dolly in", "dolly out", "tracking shot", "side tracking shot",
        "handheld camera", "steadicam follow shot", "pan left", "pan right", "tilt up", "tilt down", "crane up", "crane down",
        "orbit around the subject", "slow zoom in", "slow zoom out", "drone flyover", "aerial view descending", "whip pan",
        "rack focus", "smooth gimbal movement"]},
    {"name": "Lens / focus", "field": "prompt", "items": [
        "shallow depth of field", "deep focus", "creamy bokeh background", "85mm portrait lens", "35mm lens", "24mm wide-angle lens",
        "telephoto lens compression", "macro lens", "anamorphic lens", "fisheye lens", "tilt-shift lens", "soft focus",
        "sharp focus on the subject", "lens flare"]},
    {"name": "Lighting", "field": "prompt", "items": [
        "golden hour light", "blue hour light", "soft diffused light", "natural daylight", "hard sunlight with long shadows",
        "overcast soft light", "dramatic side lighting", "rim light", "backlit silhouette", "volumetric light rays",
        "light through window blinds", "neon lighting", "moody low-key lighting", "bright high-key lighting", "chiaroscuro lighting",
        "candlelight", "firelight glow", "moonlight", "practical lights in the scene", "studio three-point lighting",
        "harsh fluorescent light", "warm lamp light"]},
    {"name": "Time / weather", "field": "prompt", "items": [
        "dawn", "sunrise", "midday sun", "late afternoon", "sunset", "twilight", "night", "clear sky", "overcast sky",
        "light rain", "heavy rain", "wet streets reflecting lights", "fog", "morning mist", "snowfall", "thunderstorm",
        "windy day", "dust in the air", "falling autumn leaves"]},
    {"name": "Environment", "field": "prompt", "items": [
        "busy city street at night", "quiet forest at dawn", "foggy mountain valley", "sunlit kitchen", "rainy neon alley",
        "empty desert road", "cozy cabin interior", "beach at sunset", "futuristic laboratory", "old library", "modern apartment",
        "crowded market", "rooftop overlooking the city", "snowy landscape", "tropical jungle", "underground subway station",
        "small caf\u00e9", "open countryside", "spaceship interior", "abandoned building"]},
    {"name": "Style", "field": "prompt", "items": [
        "cinematic", "photorealistic", "hyperrealistic", "35mm film look", "16mm film grain", "documentary style",
        "professional cinematography", "film noir black and white", "vintage 1970s film", "retro 80s look", "vintage VHS look",
        "cyberpunk", "anime style", "hand-drawn 2D animation", "3D animation", "stop-motion", "claymation", "low-poly 3D",
        "watercolor painting", "oil painting", "comic book style", "surreal dreamlike", "found footage"]},
    {"name": "Color / grading", "field": "prompt", "items": [
        "natural colors", "warm color grade", "cool color grade", "teal and orange color grade", "desaturated muted tones",
        "vibrant saturated colors", "pastel color palette", "monochrome", "high contrast", "soft film colors", "rich deep blacks",
        "earthy tones", "neon color palette", "golden warm tones"]},
    {"name": "Mood", "field": "prompt", "items": [
        "calm and peaceful", "tense and suspenseful", "melancholic", "joyful and warm", "mysterious", "epic and grand", "intimate",
        "eerie", "nostalgic", "energetic", "dreamy", "romantic", "lonely", "hopeful", "dramatic", "playful", "serene"]},
    {"name": "Subject / character", "field": "prompt", "items": [
        "natural skin texture", "expressive face", "detailed eyes", "natural blinking", "subtle facial expressions",
        "realistic hands", "detailed clothing fabric", "natural hair strands", "lifelike body language", "consistent appearance",
        "natural proportions", "detailed textures"]},
    {"name": "Action", "field": "prompt", "items": [
        "walks toward the camera", "walks away from the camera", "turns and looks at the camera", "looks away thoughtfully",
        "smiles softly", "laughs", "talks to the camera", "talks with another person", "runs", "dances", "sits quietly",
        "takes a deep breath", "picks up an object", "opens a door", "looks out of a window", "reaches toward the camera",
        "nods slowly", "sips a drink"]},
    {"name": "Motion", "field": "prompt", "items": [
        "slow motion", "smooth motion", "fluid natural movement", "dynamic action", "fast-paced motion", "subtle motion",
        "time-lapse", "hyperlapse", "gentle breeze moving hair and clothes", "fabric fluttering in the wind", "hair flowing",
        "leaves swaying", "water rippling", "smoke drifting", "dust particles floating", "rain falling", "steam rising",
        "realistic physics", "stable consistent motion", "natural pacing"]},
    {"name": "Quality / details", "field": "prompt", "items": [
        "highly detailed", "sharp focus", "crisp textures", "high resolution", "clean image", "coherent details",
        "stable background", "consistent lighting", "natural look", "professional quality", "realistic reflections",
        "fine details"]},
    {"name": "Sound effects", "field": "sound", "items": [
        "gentle wind", "wind through the trees", "city traffic", "distant traffic", "rain on a window", "rain on a roof",
        "distant thunder", "footsteps", "footsteps on gravel", "echoing footsteps", "crowd murmur", "crowd chatter", "birds chirping",
        "ocean waves", "crackling fire", "door creaking", "clock ticking", "keyboard typing", "cutlery clinking",
        "car engine", "machinery hum", "heartbeat", "forest ambience", "quiet room tone"]},
    {"name": "Music", "field": "music", "items": [
        "soft ambient piano", "minimal piano", "classical piano", "tense orchestral strings", "emotional string quartet",
        "slow cello solo", "uplifting orchestral", "epic cinematic drums", "heroic brass fanfare", "dark ambient drone",
        "dreamy synth pad", "80s synthwave", "upbeat electronic", "lo-fi beat", "deep bass pulse", "trap beat",
        "melancholic guitar", "gentle acoustic guitar", "jazz trio with soft brushes", "playful pizzicato strings",
        "ethereal choir", "tribal percussion", "funky bass groove", "music box lullaby", "no music"]},
]


def normalize_templates(data):
    """Accepts [{"name", "field", "items": ["text", {"label", "text"}]}] and returns the clean version (or raises)."""
    groups = []
    for g in data:
        field = g.get("field", "prompt")
        if field not in TEMPLATE_FIELDS:
            field = "prompt"
        items = []
        for it in g.get("items", []):
            if isinstance(it, str):
                it = {"label": it, "text": it}
            text = " ".join(str(it.get("text") or it.get("label") or "").split())
            if text:
                items.append({"label": str(it.get("label") or text), "text": text})
        if items:
            groups.append({"name": str(g.get("name") or ""), "field": field, "items": items})
    if not groups:
        raise ValueError("no templates")
    return groups


def load_templates():
    """Reads video_templates.json (created with the defaults the first time, so you can edit it). Returns (templates, note)."""
    defaults = normalize_templates(DEFAULT_TEMPLATES)
    if not os.path.isfile(TEMPLATES_FILE):
        try:
            with open(TEMPLATES_FILE, "w", encoding="utf-8") as f:
                json.dump(DEFAULT_TEMPLATES, f, ensure_ascii=False, indent=2)
        except OSError:
            pass
        return defaults, ""
    try:
        with open(TEMPLATES_FILE, encoding="utf-8") as f:
            data = json.load(f)
        if data == LEGACY_DEFAULTS:
            # still the first, short list (never edited): upgrade it to the current one
            try:
                with open(TEMPLATES_FILE, "w", encoding="utf-8") as f:
                    json.dump(DEFAULT_TEMPLATES, f, ensure_ascii=False, indent=2)
            except OSError:
                pass
            return defaults, ""
        return normalize_templates(data), ""
    except Exception as ex:
        return defaults, f"{TEMPLATES_FILE} could not be read ({ex}); using the built-in templates."


PRESETS_FILE = "video_enhancer_presets.json"
# preset field -> key of GUI.config
PRESET_KEYS = {"provider": "enhancer_provider", "url": "enhancer_url", "model": "enhancer_model", "key": "enhancer_key",
               "instructions": "enhancer_instructions", "send_images": "enhancer_send_images", "style": "enhancer_style"}


def load_presets():
    """Enhancer presets (provider, key, model, ...) from video_enhancer_presets.json -> (list, name of the last one used)."""
    try:
        with open(PRESETS_FILE, encoding="utf-8") as f:
            data = json.load(f)
        presets = [p for p in data.get("presets", []) if isinstance(p, dict) and str(p.get("name") or "").strip()]
        return presets, str(data.get("current") or "")
    except Exception:
        return [], ""


def make_poster(path, out):
    """First frame of an mp4 as a small jpg (needs the 'av' package; without it the gallery just shows the play icon)."""
    import av
    with av.open(path) as container:
        for frame in container.decode(video=0):
            img = frame.to_image()
            img.thumbnail((384, 384))
            img.convert("RGB").save(out, "JPEG", quality=85)
            return True
    return False


class Video(QObject):
    updated = pyqtSignal()
    logUpdated = pyqtSignal()
    libraryUpdated = pyqtSignal()
    selectionUpdated = pyqtSignal()
    postersUpdated = pyqtSignal()
    referencesUpdated = pyqtSignal()
    deleted = pyqtSignal()
    enhanceUpdated = pyqtSignal()
    _enhanced = pyqtSignal(str, str, str, str)
    _enhancerTested = pyqtSignal(str)
    _enhancerNote = pyqtSignal(str)
    enhancePresetsUpdated = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.gui = parent
        self.priority = 2
        self.name = "Video"

        self._values = parameters.VariantMap(self, {k: (list(v) if isinstance(v, list) else v)
                                                   for k, v in DEFAULTS.items()})
        self._values.updated.connect(self.onValue)

        self._durations = dict(FALLBACK["durations"])
        self._preview_only = PREVIEW_ONLY
        self._log = []
        self._templates, note = load_templates()
        if note:
            self._addLog(note)
        self._lastFile = ""
        self._requestId = None
        self._stage = None          # "preview" | "upscale" while a job runs
        self._previewName = None
        self._chunks = {}
        self._frameImages = {}
        self._refs = []             # reference images of a Ref2VA server: [{"path", "image" (QImage), "name"}], in <Picture N> order
        self._refCfg = {"enabled": False, "max": 0, "min": 50, "top": 200, "default": 70}
        self._serverUpscale = True  # False on a Ref2VA server: previews only
        self._serverMode = "fl2va"
        self._upscale = False
        self._default_resolution = DEFAULT_RESOLUTION
        self._uploads = {}
        self._myLoras = []          # [{"kind": "file"|"url", "ref": ..., "label": ...}], strengths in mylora_s<i>
        self._maxLoras = MAX_MY_LORAS
        self._started = 0.0
        self._tray = None
        self._job = {}
        self._upscaleJob = {}
        self._uploadedKnown = []
        self._library = []          # every clip found in outputs/video
        self._shownView = []        # what the grid shows (search + filter applied)
        self._search = ""
        self._filter = "All"
        self._sort = "Newest"
        self._dateFilter = "Any date"
        self._selected = ""

        qmlRegisterSingletonType(Video, "gui", 1, 0, "VIDEO", lambda qml, js: self)
        global VIDEO_INSTANCE
        VIDEO_INSTANCE = self
        self.gui.response.connect(self.onResponse)

        # gui.windowActive is never updated by anything else, so it always said "active": follow the real state
        self._trackWindowState()

        self._presets, self._presetCurrent = load_presets()
        self._enhancing = set()
        self._undo = {}
        self._enhancerStatus = ""
        self._enhanced.connect(self._onEnhanced)
        self._enhancerTested.connect(self._onEnhancerTested)
        self._enhancerNote.connect(self._addLog)

        self._posterTried = set()
        self._posterBusy = False
        self.postersUpdated.connect(self.refreshLibrary)

        # gallery: keep outputs/video in sync with the folder
        self._watcher = QFileSystemWatcher(self)
        self._reload = QTimer(self)
        self._reload.setSingleShot(True)
        self._reload.setInterval(400)
        self._reload.timeout.connect(self.refreshLibrary)
        try:
            os.makedirs(self._videoFolder(), exist_ok=True)
            self._watcher.addPath(self._videoFolder())
            self._watcher.directoryChanged.connect(lambda _path: self._reload.start())
        except Exception:
            pass
        self.refreshLibrary()

    # ------------------------------------------------------------ properties for QML
    @pyqtProperty(QObject, constant=True)
    def values(self):
        return self._values

    @pyqtProperty(str, notify=updated)
    def frameInfo(self):
        label = nearest_duration(self._values.get("seconds", 5.0), self._durations)
        frames = self._durations[label]
        text = f"{frames / FPS:.2f} s ({frames} frames)"
        if abs(label_seconds(label, frames) - float(self._values.get("seconds", 5.0))) > 0.01:
            text += f" \u00b7 clip length {label}"
        if self._values.get("output") == self._preview_only:
            short = short_side(self._values.get("resolution"))
            text += (f" \u00b7 preview \u2248 "
                     f"{fmt_secs(preview_eta(frames, self._values.get('aspect'), self._ratio(), short))}")
        return text

    @pyqtProperty('QVariantList', notify=updated)
    def myLoras(self):
        return [("\u2601 " if x["kind"] == "url" else "") + x["label"] for x in self._myLoras]

    @pyqtProperty(bool, notify=updated)
    def upscaleAvailable(self):
        """The refine stage was built for the 384p preview: a different native resolution skips it."""
        return self._values.get("resolution") == self._default_resolution

    @pyqtProperty(str, notify=logUpdated)
    def log(self):
        return "\n".join(self._log[-200:])

    @pyqtProperty(str, notify=updated)
    def lastFile(self):
        return self._lastFile

    @pyqtProperty(bool, notify=updated)
    def busy(self):
        return self._requestId is not None

    @pyqtProperty(str, notify=logUpdated)
    def lastLog(self):
        return self._log[-1] if self._log else ""

    @pyqtProperty('QVariantList', notify=libraryUpdated)
    def library(self):
        return self._shownView

    @pyqtProperty(str, notify=libraryUpdated)
    def libraryText(self):
        n = len(self._shownView)
        return f"{n} video{'s' if n != 1 else ''}"

    @pyqtProperty(str, notify=selectionUpdated)
    def selectedPath(self):
        return self._selected

    @pyqtProperty(str, notify=selectionUpdated)
    def selectedUrl(self):
        return QUrl.fromLocalFile(self._selected).toString() if self._selected and os.path.isfile(self._selected) else ""

    def _selectedItem(self):
        return next((x for x in self._library if x["path"] == self._selected), None)

    @pyqtProperty(str, notify=selectionUpdated)
    def selectedMeta(self):
        item = self._selectedItem()
        return format_meta(item) if item else ""

    @pyqtProperty(str, notify=selectionUpdated)
    def selectedResolution(self):
        item = self._selectedItem()
        return clip_dims(item["meta"]) if item else ""

    # ------------------------------------------------------------ gallery
    def _videoFolder(self):
        return os.path.join(self.gui.outputDirectory(), "video")

    @pyqtSlot()
    def refreshLibrary(self):
        items = []
        for path in glob.glob(os.path.join(self._videoFolder(), "*.mp4")):
            stem = path[:-4]
            raw = {}
            try:
                with open(stem + ".json", encoding="utf-8") as f:
                    raw = json.load(f)
            except Exception:
                pass
            if not isinstance(raw, dict):
                raw = {}
            custom = " ".join(str(raw.get("custom_title") or "").split())
            meta = {k: v for k, v in raw.items() if k != "custom_title"}   # "no parameters" must stay true for a clip that only has a title
            try:
                st = os.stat(path)
            except OSError:
                continue
            name = os.path.basename(path)
            poster = stem + ".jpg"
            dims = clip_dims(meta)
            seconds = meta.get("seconds")
            kind = clip_kind(name, meta)
            when = datetime.datetime.fromtimestamp(st.st_mtime)
            prompt = " ".join(str(meta.get("prompt") or "").split())
            refs_n = int(meta.get("references") or 0)
            sub = " \u00b7 ".join(x for x in (when.strftime("%d %b %H:%M"), f"{seconds:g} s" if seconds else "", dims,
                                              f"{refs_n} ref" if refs_n else "",
                                              {"final": "upscaled", "preview": "preview"}.get(kind, "")) if x)
            tip = []
            if custom:
                tip.append(custom)
            if prompt:
                tip.append(prompt[:600])
            for key, label in (("dialogue", "Spoken line"), ("sound", "Sound"), ("music", "Music")):
                if str(meta.get(key) or "").strip():
                    tip.append(f"{label}: {str(meta[key]).strip()[:200]}")
            tip.append(name)
            words = [custom, prompt, name, when.strftime("%Y-%m-%d %d/%m/%Y %B %b"), str(meta.get("seed", "")),
                     str(meta.get("aspect") or ""), str(meta.get("resolution") or ""), dims, str(meta.get("language") or ""),
                     kind, str(meta.get("sampler") or "")]
            words += [str(meta.get(k) or "") for k in ("dialogue", "sound", "music")]
            words += [str(n) for n in (meta.get("ref_names") or [])]
            items.append({
                "path": path, "name": name, "meta": meta, "mtime": st.st_mtime, "size": st.st_size, "kind": kind,
                "custom_title": custom,
                "thumb": QUrl.fromLocalFile(poster).toString() if os.path.isfile(poster) else "",
                "title": custom or prompt or name, "sub": sub, "tooltip": "\n\n".join(tip),
                "haystack": " ".join(words).lower(),
            })
        items.sort(key=lambda x: -x["mtime"])
        self._library = items
        self._makePosters([x["path"] for x in items if not x["thumb"]])
        if self._selected and not any(x["path"] == self._selected for x in items):
            self._selected = ""
            self.selectionUpdated.emit()
        self._applyFilter()

    def _makePosters(self, missing):
        """Creates the missing <clip>.jpg thumbnails in the background (clips made before the server sent posters)."""
        todo = [p for p in missing if p not in self._posterTried]
        if not todo or self._posterBusy:
            return
        self._posterBusy = True
        self._posterTried.update(todo)

        def work():
            made = False
            try:
                for path in todo:
                    try:
                        if make_poster(path, path[:-4] + ".jpg"):
                            made = True
                    except ImportError:
                        break
                    except Exception:
                        pass
            finally:
                self._posterBusy = False
                if made:
                    self.postersUpdated.emit()

        threading.Thread(target=work, daemon=True).start()

    def _applyFilter(self):
        tokens = self._search.lower().split()      # every word has to match (prompt, title, seed, date, size, ...)
        mode = self._filter
        now = time.time()
        since = {"Today": datetime.datetime.combine(datetime.date.today(), datetime.time.min).timestamp(),
                 "Last 7 days": now - 7 * 86400, "Last 30 days": now - 30 * 86400}.get(self._dateFilter, 0)
        shown = []
        for x in self._library:
            if (mode == "Previews" and x["kind"] != "preview") or (mode == "Upscaled" and x["kind"] != "final"):
                continue
            if x["mtime"] < since:
                continue
            if tokens and not all(t in x["haystack"] for t in tokens):
                continue
            shown.append(x)
        shown.sort(key=lambda x: x["mtime"], reverse=(self._sort != "Oldest"))
        self._shownView = [{k: x[k] for k in ("path", "name", "thumb", "title", "sub", "tooltip")} for x in shown]
        self.libraryUpdated.emit()

    @pyqtSlot(str)
    def setSearch(self, text):
        self._search = text
        self._applyFilter()

    @pyqtSlot(str)
    def setFilter(self, mode):
        self._filter = mode
        self._applyFilter()

    @pyqtSlot(str)
    def setSort(self, mode):
        self._sort = mode
        self._applyFilter()

    @pyqtSlot(str)
    def setDateFilter(self, mode):
        self._dateFilter = mode
        self._applyFilter()

    @pyqtProperty(str, notify=selectionUpdated)
    def selectedTitle(self):
        item = self._selectedItem()
        return item["custom_title"] if item else ""

    @pyqtSlot(str, str)
    def setTitle(self, path, title):
        """Your own name for a clip: kept in its .json, shown in the gallery and found by the search."""
        item = next((x for x in self._library if x["path"] == path), None)
        if not item:
            return
        title = " ".join(title.split())[:120]
        if title == item["custom_title"]:
            return
        json_path = path[:-4] + ".json"
        raw = {}
        try:
            with open(json_path, encoding="utf-8") as f:
                raw = json.load(f)
        except Exception:
            pass
        if not isinstance(raw, dict):
            raw = {}
        if title:
            raw["custom_title"] = title
        else:
            raw.pop("custom_title", None)
        try:
            if raw:
                with open(json_path, "w", encoding="utf-8") as f:
                    json.dump(raw, f, ensure_ascii=False, indent=2)
            elif os.path.isfile(json_path):
                os.remove(json_path)
        except OSError as ex:
            self._addLog(f"Could not save the title: {ex}")
        self.refreshLibrary()
        self.selectionUpdated.emit()

    @pyqtSlot(str)
    def select(self, path):
        self._selected = path
        self.selectionUpdated.emit()

    @pyqtSlot()
    def openSelected(self):
        if self._selected and os.path.isfile(self._selected):
            self.gui.openFiles([os.path.abspath(self._selected)])

    @pyqtSlot()
    def showSelected(self):
        if self._selected and os.path.isfile(self._selected):
            self.gui.visitFiles([os.path.abspath(self._selected)])

    def _removeFile(self, path):
        """Recycle bin first, plain delete as a fallback. False if the file is still there (e.g. still open)."""
        if not os.path.isfile(path):
            return True
        try:
            if send2trash is None:
                raise OSError("no recycle bin")
            send2trash.send2trash(path)
        except Exception:
            try:
                os.remove(path)
            except OSError:
                pass
        return not os.path.exists(path)

    @pyqtSlot()
    def deleteSelected(self):
        item = self._selectedItem()
        if not item:
            self.deleted.emit()
            return
        self._deleteItem = item
        self._deleteTries = 0
        self._tryDelete()

    def _tryDelete(self):
        item = self._deleteItem
        path = item["path"]
        stem = path[:-4]
        # the video goes first: while it cannot be deleted (the player may still be letting go of it) the
        # parameters and the poster are kept, so the clip is never left half deleted
        if self._removeFile(path):
            for f in (stem + ".json", stem + ".jpg"):
                self._removeFile(f)
            self._addLog(f"Deleted {item['name']}.")
            if self._selected == path:
                self._selected = ""
                self.selectionUpdated.emit()
            self.refreshLibrary()
            self.deleted.emit()
        elif self._deleteTries < 15:
            self._deleteTries += 1
            QTimer.singleShot(300, self._tryDelete)
        else:
            self._addLog(f"Could not delete {item['name']}: it is still open in another program.")
            self.refreshLibrary()
            self.deleted.emit()

    @pyqtProperty('QVariantList', constant=True)
    def templates(self):
        return self._templates

    @pyqtSlot(str, str)
    def applyTemplate(self, field, phrase):
        """Adds the phrase to the end of that box, or takes it out again if it is already there."""
        phrase = " ".join(phrase.split())
        if field not in TEMPLATE_FIELDS or not phrase:
            return
        current = self._values.get(field)
        current = current if isinstance(current, str) else ""
        if phrase.lower() in current.lower():
            def gone(m):
                return ", " if (m.group(1) and m.group(2)) else ""
            new = re.sub(r"(,\s*)?" + re.escape(phrase) + r"(\s*,\s*)?", gone, current, count=1, flags=re.IGNORECASE)
            new = new.strip(" ,\n")
        else:
            base = current.rstrip()
            if not base:
                new = phrase
            elif base[-1] in ".!?":
                new = base + " " + phrase
            else:
                new = base.rstrip(",;") + ", " + phrase
        self._values.set(field, new)

    # ---- prompt enhancer (language model API, set up in Settings > Enhancer)
    def _text(self, key):
        v = self._values.get(key)
        return v if isinstance(v, str) else ""

    def _enhancerSettings(self):
        def cfg(key):
            v = self.gui.config.get(key)
            return v if isinstance(v, str) else ""
        return {"provider": cfg("enhancer_provider") or "OpenAI", "url": cfg("enhancer_url"),
                "model": cfg("enhancer_model"), "key": cfg("enhancer_key")}

    def _enhancerExtra(self):
        v = self.gui.config.get("enhancer_instructions")
        return v if isinstance(v, str) else ""

    def _enhancerStyle(self):
        style = self.gui.config.get("enhancer_style")
        return style if style in enhancer.STYLES else enhancer.STANDARD_STYLE

    @pyqtProperty('QStringList', constant=True)
    def enhancerStyles(self):
        return enhancer.STYLES

    @pyqtProperty('QStringList', notify=enhanceUpdated)
    def enhancingFields(self):
        return sorted(self._enhancing)

    @pyqtProperty('QStringList', notify=enhanceUpdated)
    def undoFields(self):
        return sorted(self._undo)

    @pyqtProperty(str, notify=enhanceUpdated)
    def enhancerStatus(self):
        return self._enhancerStatus

    def _enhancerImages(self, frames):
        """The start / end frames as base64 JPEGs, unless the user turned that off in Settings > Enhancer."""
        images = []
        if (frames["start"] or frames["end"] or frames["refs"]) and self.gui.config.get("enhancer_send_images") is not False:
            pictures = [self._frameImages.get(key) for key in ("start_frame", "end_frame")]
            pictures += [r["image"] for r in self._refs] if self._usingReferences() else []
            for img in pictures:
                data = self._frameJpeg(img)
                if data:
                    images.append(("image/jpeg", data))
        return images

    @pyqtSlot(str)
    def enhance(self, field):
        """Rewrites one prompt box with the language model. The previous text is kept for Undo.
        With the H3 Rewriter style every box asks for the same thing: one complete H3 prompt, written into Scene / action."""
        if field not in enhancer.FIELD_LABELS:
            return
        style = self._enhancerStyle()
        if style == enhancer.H3_STYLE:
            field = "prompt"
        if field in self._enhancing:
            return
        values = {k: self._text(k) for k in enhancer.FIELD_LABELS}
        text = values[field]
        using = self._usingReferences()
        frames = {"start": self._hasFrame("start_frame"), "end": self._hasFrame("end_frame"),
                  "refs": len(self._refs) if using else 0,
                  "ref_names": ref_names_for_request([r["name"] for r in self._refs]) if using else []}
        if style == enhancer.H3_STYLE:
            if not text.strip() and not (frames["start"] or frames["end"] or frames["refs"]):
                self._addLog("Write the idea in Scene / action first (or set a start / end frame or a reference image), then press Enhance.")
                return
        elif not text.strip() and (field == "prompt" or not values["prompt"].strip()):
            self._addLog("Write something in the box first, then press Enhance.")
            return
        settings = self._enhancerSettings()
        extra = self._enhancerExtra()
        images = self._enhancerImages(frames)
        # effective length: the closest clip length the server offers (frames / 24 fps), the same one the options panel shows
        clip = self._durations[nearest_duration(self._values.get("seconds", 5.0), self._durations)] / FPS
        language = self._text("language") or "English"
        aspect = str(self._values.get("aspect") or "")
        self._enhancing.add(field)
        self.enhanceUpdated.emit()

        def work():
            notes = []
            try:
                if style == enhancer.H3_STYLE:
                    result = enhancer.enhance_h3(settings, values, frames, images, clip, language, extra, notes, aspect=aspect)
                else:
                    result = enhancer.enhance(settings, field, text, values, extra, images, frames, notes)
                error = ""
            except enhancer.EnhancerError as ex:
                result, error = "", str(ex)
            except Exception as ex:
                result, error = "", f"Unexpected error: {ex}"
            for note in notes:
                self._enhancerNote.emit(note)
            self._enhanced.emit(field, text, result, error)

        threading.Thread(target=work, daemon=True).start()

    def _frameJpeg(self, img):
        """A start / end frame as a base64 JPEG (longest side 1024 px) to attach to the request, or None."""
        if img is None or img.isNull():
            return None
        import base64
        from PyQt5.QtCore import QBuffer, QByteArray, QIODevice
        img = img.convertToFormat(QImage.Format_RGB32)
        if max(img.width(), img.height()) > 1024:
            img = img.scaled(1024, 1024, Qt.KeepAspectRatio, Qt.SmoothTransformation)
        data = QByteArray()
        buf = QBuffer(data)
        buf.open(QIODevice.WriteOnly)
        if not img.save(buf, "JPEG", 85):
            return None
        return base64.b64encode(bytes(data.data())).decode("ascii")

    def _onEnhanced(self, field, original, result, error):
        self._enhancing.discard(field)
        label = enhancer.FIELD_LABELS[field]
        if error:
            self._addLog(f"Could not enhance {label}: {error}")
        elif self._text(field).strip() != original.strip():
            self._addLog(f"{label} was changed while it was being enhanced, so the result was not applied.")
        else:
            self._undo[field] = original
            self._values.set(field, result)
            if self._enhancerStyle() == enhancer.H3_STYLE:
                self._addLog("Complete Duckyshell H3 prompt written into Scene / action. While it is there the server uses it as it is and ignores "
                             "the Spoken line, Sound and Music boxes (what they said is already inside it). "
                             "Right click > Undo enhance (or Ctrl+Shift+E) brings the old Scene text back.")
            else:
                self._addLog(f"{label} enhanced. Right click the box > Undo enhance (or Ctrl+Shift+E) brings the old text back.")
        self.enhanceUpdated.emit()

    @pyqtSlot(str)
    def undoEnhance(self, field):
        if field in self._undo:
            self._values.set(field, self._undo.pop(field))
            self.enhanceUpdated.emit()

    @pyqtSlot()
    def testEnhancer(self):
        """Settings > Enhancer: sends a tiny request to check the provider, key and model."""
        self._enhancerStatus = "Testing..."
        self.enhanceUpdated.emit()
        settings = self._enhancerSettings()
        style = self._enhancerStyle()

        def work():
            try:
                if style == enhancer.H3_STYLE:
                    result = enhancer.enhance_h3(settings, {"prompt": "a cat on a sofa"}, {}, [], 5.17)
                else:
                    result = enhancer.enhance(settings, "prompt", "a cat on a sofa")
                self._enhancerTested.emit("Working. Example: " + result[:90])
            except enhancer.EnhancerError as ex:
                self._enhancerTested.emit("Failed: " + str(ex))
            except Exception as ex:
                self._enhancerTested.emit("Failed: " + str(ex))

        threading.Thread(target=work, daemon=True).start()

    def _onEnhancerTested(self, status):
        self._enhancerStatus = status
        self.enhanceUpdated.emit()

    # ---- enhancer presets
    def _savePresets(self):
        try:
            with open(PRESETS_FILE, "w", encoding="utf-8") as f:
                json.dump({"presets": self._presets, "current": self._presetCurrent}, f, ensure_ascii=False, indent=2)
        except OSError as ex:
            self._addLog(f"Could not save the enhancer presets: {ex}")

    def _presetStatus(self, text):
        self._enhancerStatus = text
        self.enhancePresetsUpdated.emit()
        self.enhanceUpdated.emit()

    def _findPreset(self, name):
        name = name.strip().lower()
        return next((p for p in self._presets if p["name"].lower() == name), None)

    @pyqtProperty('QStringList', notify=enhancePresetsUpdated)
    def enhancerPresetEntries(self):
        return ["Current settings"] + [p["name"] for p in self._presets]

    @pyqtProperty(str, notify=enhancePresetsUpdated)
    def enhancerPreset(self):
        return self._presetCurrent if self._findPreset(self._presetCurrent) else "Current settings"

    @pyqtSlot(str)
    def applyPreset(self, name):
        preset = self._findPreset(name)
        if not preset:
            return
        for field, key in PRESET_KEYS.items():
            value = preset.get(field)
            self.gui.config.set(key, bool(value) if field == "send_images" else (value if isinstance(value, str) else ""))
        self.gui.config.set("enhancer_preset_name", preset["name"])
        self._presetCurrent = preset["name"]
        self._savePresets()
        self._presetStatus(f'Preset "{preset["name"]}" loaded.')

    @pyqtSlot()
    def savePreset(self):
        """Saves the current Enhancer settings under the name in the Preset name box (same name = overwrite)."""
        name = " ".join(str(self.gui.config.get("enhancer_preset_name") or "").split())[:40]
        if not name:
            self._presetStatus("Write a name for the preset first.")
            return
        preset = {"name": name}
        for field, key in PRESET_KEYS.items():
            value = self.gui.config.get(key)
            preset[field] = (value is not False) if field == "send_images" else (value if isinstance(value, str) else "")
        old = self._findPreset(name)
        if old:
            self._presets[self._presets.index(old)] = preset
        else:
            self._presets.append(preset)
        self._presetCurrent = name
        self._savePresets()
        self._presetStatus(f'Preset "{name}" saved.')

    @pyqtSlot()
    def deletePreset(self):
        name = str(self.gui.config.get("enhancer_preset_name") or "")
        preset = self._findPreset(name)
        if not preset:
            self._presetStatus("There is no preset with that name.")
            return
        self._presets.remove(preset)
        if self._presetCurrent.lower() == preset["name"].lower():
            self._presetCurrent = ""
        self._savePresets()
        self._presetStatus(f'Preset "{preset["name"]}" deleted.')

    @pyqtProperty('QStringList', constant=True)
    def enhancerProviders(self):
        return enhancer.PROVIDER_NAMES

    @pyqtSlot()
    def reusePrompts(self):
        """Loads only the prompts of the selected clip into the text boxes (not the other settings)."""
        item = self._selectedItem()
        meta = item["meta"] if item else {}
        keys = ("prompt", "dialogue", "sound", "music")
        if not any(str(meta.get(k) or "").strip() for k in keys):
            self._addLog("This video has no saved prompt.")
            return
        for key in keys:
            self._values.set(key, meta.get(key) or "")
        self._addLog("Prompts loaded.")

    @pyqtSlot()
    def reuseSelected(self):
        """Loads the settings of the selected clip back into the form."""
        item = self._selectedItem()
        meta = item["meta"] if item else {}
        if not meta:
            self._addLog("This video has no saved parameters.")
            return
        v = self._values
        for key in ("prompt", "dialogue", "sound", "music"):
            v.set(key, meta.get(key) or "")
        for key, listkey in (("language", "languages"), ("aspect", "aspects"), ("resolution", "resolutions"),
                             ("sampler", "samplers")):
            if meta.get(key) in v.get(listkey):
                v.set(key, meta[key])
        if meta.get("duration"):
            v.set("seconds", label_seconds(meta["duration"], meta.get("frames")))
        if meta.get("seed") is not None:
            v.set("seed", int(meta["seed"]))
        if meta.get("shift") is not None:
            v.set("shift", float(meta["shift"]))
        v.set("steps", int(meta.get("steps") or 0))
        if meta.get("ref_size") is not None:
            v.set("ref_size", max(self._refCfg["min"], min(self._refCfg["top"], int(meta["ref_size"]))))
        for i, name in enumerate(meta.get("ref_names") or []):      # names go to the reference images already in the form
            if i < len(self._refs):
                self._refs[i]["name"] = name
        self.referencesUpdated.emit()
        # LoRAs: the catalog ones go to LoRA 1/2, the rest to the list (uploaded files only if still on the server)
        catalog = [x for x in meta.get("loras", []) if x.get("source") == "catalog"][:2]
        for i in (1, 2):
            entry = catalog[i - 1] if len(catalog) >= i else None
            v.set(f"lora{i}", entry["name"] if entry and entry["name"] in v.get("loras") else NO_LORA)
            v.set(f"strength{i}", float(entry["strength"]) if entry else 1.0)
        for i in range(len(self._myLoras) - 1, -1, -1):
            self._removeAt(i)
        skipped = 0
        for x in meta.get("loras", []):
            if x.get("source") == "link":
                ok, link, label = parse_lora_link(x["name"])
                if ok and self._addLora("url", link, label):
                    v.set(f"mylora_s{len(self._myLoras) - 1}", float(x["strength"]))
            elif x.get("source") == "file":
                if x["name"] in self._uploadedKnown and self._addLora("file", x["name"], os.path.basename(x["name"])):
                    v.set(f"mylora_s{len(self._myLoras) - 1}", float(x["strength"]))
                else:
                    skipped += 1
        up = meta.get("upscale")
        if up:
            if up.get("output") in v.get("outputs"):
                v.set("output", up["output"])
            if up.get("preset") in v.get("presets"):
                v.set("preset", up["preset"])
            v.set("refine_seed", int(up.get("seed") if up.get("seed") is not None else -1))
            v.set("anchor", bool(up.get("anchor", True)))
        else:
            v.set("output", self._preview_only)
        note = " Start/end and reference images, and uploaded LoRAs that are no longer on the server, were not restored (reference names went to the images already in the form)." \
            if (meta.get("start_frame") or meta.get("end_frame") or meta.get("references") or skipped) else ""
        self._addLog("Settings of the selected video loaded into the form." + note)
        self.updated.emit()

    # ------------------------------------------------------------ helpers
    def _ratio(self):
        img = self._frameImages.get("start_frame") or self._frameImages.get("end_frame")
        if (img is None or img.isNull()) and self._usingReferences():
            img = self._refs[0]["image"]
        if img is not None and not img.isNull() and img.height() > 0:
            return img.width() / img.height()
        return None

    def _addLog(self, text):
        stamp = datetime.datetime.now().strftime("%H:%M:%S")
        self._log.append(f"{stamp}  {text}")
        self.logUpdated.emit()

    def onValue(self, key):
        if key in {"seconds", "aspect", "output", "start_frame", "end_frame", "resolution"}:
            self.updated.emit()

    def _keep(self, key, listkey, default):
        options = self._values.get(listkey)
        if self._values.get(key) not in options:
            self._values.set(key, default if default in options else (options[0] if options else ""))

    def applyOptions(self, o):
        """The server's tables for the pickers (reply to the 'options' request of video_server.py)."""
        v = self._values
        self._preview_only = o.get("preview_only", PREVIEW_ONLY)
        self._durations = dict(o.get("durations") or FALLBACK["durations"])
        v.set("aspects", list(o.get("aspects") or FALLBACK["aspects"]))
        v.set("outputs", [self._preview_only] + list(o.get("outputs") or FALLBACK["outputs"]))
        v.set("presets", list(o.get("presets") or FALLBACK["presets"]))
        v.set("languages", list(o.get("languages") or FALLBACK["languages"]))
        self._default_resolution = o.get("default_resolution") or DEFAULT_RESOLUTION
        v.set("resolutions", list(o.get("resolutions") or [self._default_resolution]))
        v.set("samplers", list(o.get("samplers") or ["euler", "res_multistep"]))
        self._maxLoras = min(MAX_MY_LORAS, int(o.get("max_extra_loras") or MAX_MY_LORAS))
        self._uploadedKnown = list(o.get("uploaded_loras") or [])
        if "uploaded_loras" in o:   # files that vanished with the Kaggle session are dropped from the list
            keep = set(o["uploaded_loras"])
            gone = [x for x in self._myLoras if x["kind"] == "file" and x["ref"] not in keep]
            for x in gone:
                self._removeAt(self._myLoras.index(x))
        no_lora = o.get("no_lora", NO_LORA)
        v.set("loras", [no_lora] + list((o.get("loras") or {}).keys()))
        presets = v.get("presets")
        balanced = next((p for p in presets if "Balanced" in p), presets[0])
        self._keep("aspect", "aspects", "Auto (match image)")
        self._keep("output", "outputs", self._preview_only)
        self._keep("preset", "presets", balanced)
        self._keep("language", "languages", "English")
        self._keep("lora1", "loras", no_lora)
        self._keep("lora2", "loras", no_lora)
        self._keep("resolution", "resolutions", self._default_resolution)
        self._keep("sampler", "samplers", o.get("default_sampler") or "euler")
        # what the server can do: reference images (Ref2VA mode) and the 2K upscale (FL2VA mode)
        refs = o.get("references") or {}
        size = refs.get("size") or {}
        self._refCfg = {"enabled": bool(refs.get("enabled")), "max": 9 if refs.get("enabled") else 0,
                        "min": int(size.get("min") or 50), "top": int(size.get("max") or 200),
                        "default": int(size.get("default") or 70)}
        self._serverUpscale = o.get("upscale", True) is not False
        self._serverMode = str(o.get("mode") or "fl2va")
        if not self._serverUpscale:
            v.set("output", self._preview_only)     # nothing to upscale with: the options panel shows the preview estimate
        cfg = self._refCfg
        current = v.get("ref_size")
        v.set("ref_size", max(cfg["min"], min(cfg["top"], int(current) if isinstance(current, (int, float)) else cfg["default"])))
        # QComfy UI supports up to nine Ref2VA identity references.
        # The connected workflow/server still needs to accept the submitted reference count.
        self.referencesUpdated.emit()
        self.updated.emit()

    # ------------------------------------------------------------ frames
    @pyqtSlot(str, str)
    def setFrame(self, key, path):
        """key: start_frame | end_frame. Empty path clears it."""
        if path.startswith("file:"):
            path = QUrl(path).toLocalFile()
        img = QImage(path) if path else None
        if path and (img is None or img.isNull()):
            self._addLog(f"Could not read image: {path}")
            return
        self._frameImages[key] = img
        self._values.set(key, path)
        self.referencesUpdated.emit()      # reference pictures are numbered after the start / end frames
        self.updated.emit()

    # ------------------------------------------------------------ reference images (Ref2VA servers)
    def _hasFrame(self, key):
        img = self._frameImages.get(key)
        return img is not None and not img.isNull()

    def _usingReferences(self):
        return self._refCfg["enabled"] and bool(self._refs)

    @pyqtProperty(bool, notify=updated)
    def referencesEnabled(self):
        return self._refCfg["enabled"]

    @pyqtProperty(int, notify=updated)
    def maxReferences(self):
        return self._refCfg["max"]

    @pyqtProperty(int, notify=updated)
    def refSizeMin(self):
        return self._refCfg["min"]

    @pyqtProperty(int, notify=updated)
    def refSizeMax(self):
        return self._refCfg["top"]

    @pyqtProperty(bool, notify=updated)
    def serverUpscale(self):
        """False when the server only makes previews (Ref2VA mode)."""
        return self._serverUpscale

    @pyqtProperty(str, notify=updated)
    def serverMode(self):
        return self._serverMode

    @pyqtProperty('QVariantList', notify=referencesUpdated)
    def references(self):
        offset = int(self._hasFrame("start_frame")) + int(self._hasFrame("end_frame"))
        return [{"path": r["path"], "name": r["name"], "label": f"Picture {offset + i + 1}"}
                for i, r in enumerate(self._refs)]

    @pyqtSlot(str, str)
    def addStudioReference(self, path, name):
        """Add one H3 Studio image to Ref2VA references and retain its identity label."""
        path = str(path or "")
        if not path:
            return
        local = QUrl(path).toLocalFile() if path.startswith("file:") else path
        before = len(self._refs)
        self.addReferences([local])
        # addReferences ignores duplicates and images beyond the server/UI limit.
        for index, ref in enumerate(self._refs):
            if ref.get("path") == local:
                if name and (index >= before or not ref.get("name")):
                    ref["name"] = str(name).strip()
                self.referencesUpdated.emit()
                self.updated.emit()
                return

    @pyqtSlot('QVariantList')
    def addReferences(self, paths):
        limit = 9 if self._refCfg["enabled"] else 0
        added = False
        for path in paths:
            path = str(path)
            local = QUrl(path).toLocalFile() if path.startswith("file:") else path
            if len(self._refs) >= limit:
                self._addLog(f"QComfy supports up to {limit} reference images: the rest were ignored.")
                break
            if any(r["path"] == local for r in self._refs):
                continue
            img = QImage(local)
            if img.isNull():
                self._addLog(f"Could not read image: {local}")
                continue
            self._refs.append({"path": local, "image": img, "name": ""})
            added = True
        if added:
            self.referencesUpdated.emit()
            self.updated.emit()

    @pyqtSlot(int)
    def removeReference(self, index):
        if 0 <= index < len(self._refs):
            del self._refs[index]
            self.referencesUpdated.emit()
            self.updated.emit()

    @pyqtSlot(int, int)
    def moveReference(self, index, delta):
        other = index + delta
        if 0 <= index < len(self._refs) and 0 <= other < len(self._refs):
            self._refs[index], self._refs[other] = self._refs[other], self._refs[index]
            self.referencesUpdated.emit()

    @pyqtSlot(int, str)
    def setReferenceName(self, index, name):
        if 0 <= index < len(self._refs):
            self._refs[index]["name"] = name      # no signal: the text field keeps what is being typed

    @pyqtSlot()
    def clearReferences(self):
        if self._refs:
            self._refs.clear()
            self.referencesUpdated.emit()
            self.updated.emit()

    @pyqtSlot(MimeData, result='QVariantList')
    def pathsDrop(self, mimeData):
        return [url.toLocalFile() for url in mimeData.mimeData.urls() if url.isLocalFile()]

    @pyqtSlot(MimeData, result=str)
    def pathDrop(self, mimeData):
        for url in mimeData.mimeData.urls():
            if url.isLocalFile():
                return url.toLocalFile()
        return ""

    # ------------------------------------------------------------ requests
    def buildGenerateRequest(self):
        v = self._values
        data = {
            "prompt": v.get("prompt"), "dialogue": v.get("dialogue"), "language": v.get("language"),
            "sound": v.get("sound"), "music": v.get("music"),
            "aspect": v.get("aspect"),
            "duration": nearest_duration(v.get("seconds"), self._durations),
            "seed": int(v.get("seed")),
            "lora1": v.get("lora1"), "s1": float(v.get("strength1")),
            "lora2": v.get("lora2"), "s2": float(v.get("strength2")),
            "resolution": v.get("resolution"),
            "sampler": v.get("sampler"), "shift": float(v.get("shift")), "steps": int(v.get("steps")),
        }
        extras = []
        for i, x in enumerate(self._myLoras):
            strength = float(v.get(f"mylora_s{i}"))
            if strength != 0.0:
                extras.append({("file" if x["kind"] == "file" else "url"): x["ref"], "strength": strength})
        if extras:
            data["custom_loras"] = extras
        for key, field in (("start_frame", "start_img"), ("end_frame", "end_img")):
            img = self._frameImages.get(key)
            if img is not None and not img.isNull():
                data[field] = encodeImage(img)
        if self._usingReferences():
            data["refs"] = [encodeImage(r["image"]) for r in self._refs]
            data["ref_names"] = ref_names_for_request([r["name"] for r in self._refs])
            data["ref_size"] = int(v.get("ref_size"))
        return {"type": REQ_GENERATE, "data": data}

    def buildUpscaleRequest(self, name):
        v = self._values
        return {"type": REQ_UPSCALE, "data": {
            "name": name, "output": v.get("output"), "preset": v.get("preset"),
            "seed": int(v.get("refine_seed")), "anchor": bool(v.get("anchor"))}}

    def _jobMeta(self, req):
        v = self._values
        job = {k: req[k] for k in ("prompt", "dialogue", "language", "sound", "music", "aspect", "duration",
                                   "resolution", "sampler", "shift", "steps") if k in req}
        title = " ".join(str(v.get("title") or "").split())[:120]
        if title:
            job["custom_title"] = title      # saved in the clip's .json: shown in the gallery and searchable
        job["seed_requested"] = req.get("seed", -1)
        job["frames"] = self._durations.get(req.get("duration"))
        job["start_frame"] = "start_img" in req
        job["end_frame"] = "end_img" in req
        if "refs" in req:
            job["references"] = len(req["refs"])
            job["ref_names"] = req["ref_names"]
            job["ref_size"] = req["ref_size"]
        job["loras"] = []
        for name, key in ((req.get("lora1"), "strength1"), (req.get("lora2"), "strength2")):
            if name and name != NO_LORA:
                job["loras"].append({"name": name, "strength": float(v.get(key)), "source": "catalog"})
        for x in req.get("custom_loras", []):
            job["loras"].append({"name": x.get("file") or x.get("url"), "strength": float(x["strength"]),
                                 "source": "file" if x.get("file") else "link"})
        return job

    @pyqtSlot()
    def generate(self):
        v = self._values
        if not str(v.get("prompt")).strip() and not (self._hasFrame("start_frame") or self._hasFrame("end_frame")
                                                    or self._usingReferences()):
            self._addLog("Write a scene / action prompt, give a start frame or add a reference image first.")
            return
        self._stage = "preview"
        self._previewName = None
        self._chunks = {}
        self._started = time.time()
        wants_upscale = v.get("output") != self._preview_only and self._serverUpscale
        self._upscale = wants_upscale and v.get("resolution") == self._default_resolution
        if wants_upscale and not self._upscale:
            self._addLog(f"Upscale only works from the {self._default_resolution} preview: "
                         f"generating at {v.get('resolution')} without it.")
        request = self.buildGenerateRequest()
        self._job = self._jobMeta(request["data"])
        self._upscaleJob = {}
        self._requestId = self.gui.makeRequest(request)
        self.gui.setSending()
        label = nearest_duration(v.get("seconds"), self._durations)
        self._addLog(f"Generating a {label} clip at {v.get('resolution')}"
                     f"{' + ' + v.get('output') + ' upscale' if self._upscale else ''}...")
        self.updated.emit()

    @pyqtSlot()
    def cancel(self):
        if self._requestId is not None:
            self.gui.cancelRequest(self._requestId)
            self.gui.setCancelling()
            self._addLog("Cancelling...")

    @pyqtSlot()
    def openOutputFolder(self):
        folder = os.path.abspath(os.path.join(self.gui.outputDirectory(), "video"))
        os.makedirs(folder, exist_ok=True)
        QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

    @pyqtSlot()
    def openLast(self):
        if self._lastFile and os.path.exists(self._lastFile):
            QDesktopServices.openUrl(QUrl.fromLocalFile(os.path.abspath(self._lastFile)))

    # ------------------------------------------------------------ my LoRAs (uploaded files and links)
    def _addLora(self, kind, ref, label):
        if any(x["kind"] == kind and x["ref"] == ref for x in self._myLoras):
            self._addLog(f"{label} is already in the list.")
            return False
        if len(self._myLoras) >= self._maxLoras:
            self._addLog(f"At most {self._maxLoras} extra LoRAs per clip.")
            return False
        self._values.set(f"mylora_s{len(self._myLoras)}", 1.0)
        self._myLoras.append({"kind": kind, "ref": ref, "label": label})
        self.updated.emit()
        return True

    def _removeAt(self, index):
        n = len(self._myLoras)
        del self._myLoras[index]
        for i in range(index, n - 1):          # strengths follow their LoRA
            self._values.set(f"mylora_s{i}", self._values.get(f"mylora_s{i + 1}"))
        self._values.set(f"mylora_s{n - 1}", 1.0)
        self.updated.emit()

    @pyqtSlot(int)
    def removeLora(self, index):
        if 0 <= index < len(self._myLoras):
            self._removeAt(index)

    @pyqtSlot(str)
    def addLoraLink(self, text):
        ok, link, label = parse_lora_link(text)
        if not ok:
            self._addLog(link)
            return
        if self._addLora("url", link, label):
            self._addLog(f"Added {label}: the server downloads it when you generate.")

    @pyqtSlot(str)
    def uploadLora(self, path):
        """Uploads one .safetensors to the server; it joins the list when the upload finishes."""
        if path.startswith("file:"):
            path = QUrl(path).toLocalFile()
        path = path.replace("/", os.path.sep)
        if not path or not os.path.isfile(path):
            return
        if not path.lower().endswith(".safetensors"):
            self._addLog("A LoRA must be a .safetensors file.")
            return
        if self.gui.remoteInfoStatus != "Connected":
            self._addLog("Connect to the server before uploading a LoRA.")
            return
        name = os.path.basename(path)
        id = self.gui.makeRequest({"type": "upload", "data": {"type": "custom", "file": path}})
        self.gui.network.create(name, id, False)
        self._uploads[id] = name
        self._addLog(f"Uploading LoRA {name}...")

    # ------------------------------------------------------------ responses
    def _finish(self, outcome=None, detail=""):
        """Ends the job. outcome: "done" | "error" notify the user; None (cancelled) stays quiet."""
        stage = self._stage
        self._requestId = None
        self._stage = None
        self._chunks = {}
        self.gui.setReady()
        self.updated.emit()
        if outcome == "done" and self._lastFile:
            self.select(self._lastFile)
        if outcome == "done":
            took = fmt_secs(time.time() - self._started) if self._started else ""
            what = "Preview ready" if stage == "preview" else "Video ready"
            name = os.path.basename(self._lastFile) if self._lastFile else ""
            self._notify(what, (f"{name}\n" if name else "") + (f"Took {took}" if took else ""), True)
        elif outcome == "error":
            self._notify("Video generation failed", (detail or "See the log of the Video tab.")[:200], False)

    def _appActive(self):
        return QGuiApplication.applicationState() == Qt.ApplicationActive

    def _trackWindowState(self):
        def update(state=None):
            self.gui.windowActive = self._appActive()
        QGuiApplication.instance().applicationStateChanged.connect(update)
        update()

    def _notify(self, title, text, ok=True):
        """Sound always; taskbar flash and a popup only while qComfy is not the active window."""
        if not self._values.get("notify"):
            return
        try:
            try:
                import winsound
                winsound.MessageBeep(winsound.MB_ICONASTERISK if ok else winsound.MB_ICONHAND)
            except Exception:
                QApplication.beep()
            if self._appActive():
                return
            for window in QGuiApplication.topLevelWindows():
                if window.isVisible():
                    window.alert(0)      # flashes the taskbar button until the window is focused
            if QSystemTrayIcon.isSystemTrayAvailable():
                if self._tray is None:
                    self._tray = QSystemTrayIcon(QApplication.windowIcon(), self)
                self._tray.show()
                icon = QSystemTrayIcon.Information if ok else QSystemTrayIcon.Warning
                # Windows needs a moment between showing the tray icon and the balloon
                QTimer.singleShot(400, lambda: self._tray.showMessage(title, text, icon, 10000))
                QTimer.singleShot(15000, self._tray.hide)
        except Exception as ex:
            self._addLog(f"Could not show the notification: {ex}")

    def _discard(self):
        if self._previewName:
            self.gui.makeRequest({"type": REQ_DISCARD, "data": {"name": self._previewName}})
            self._previewName = None

    def _save(self, data, suffix):
        parts = self._chunks.pop(data.get("id"), {})
        video = b"".join(parts[i] for i in sorted(parts))
        if not video or len(video) != data.get("size", len(video)):
            self._addLog(f"The video arrived incomplete ({len(video)} of {data.get('size')} bytes).")
            return False
        folder = os.path.join(self.gui.outputDirectory(), "video")
        os.makedirs(folder, exist_ok=True)
        stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        path = os.path.join(folder, f"{stamp}_{suffix}.mp4")
        with open(path, "wb") as f:
            f.write(video)
        self._lastFile = path
        self._addLog(f"Saved {path}")
        self._saveSidecar(path[:-4], data, suffix)
        return True

    def _saveSidecar(self, stem, data, suffix):
        """outputs/video/<clip>.json (what made it) and <clip>.jpg (poster frame from the server) for the gallery."""
        try:
            poster = data.get("poster")
            if isinstance(poster, (bytes, bytearray)) and poster:
                with open(stem + ".jpg", "wb") as f:
                    f.write(bytes(poster))
            meta = dict(self._job)
            seed_requested = meta.pop("seed_requested", -1)
            found = re.search(r"_seed(\d+)$", str(data.get("name", "")))
            meta["seed"] = int(found.group(1)) if found else seed_requested
            meta.update(app="qComfy", version=1, kind="final" if suffix == "final" else "preview",
                        created=datetime.datetime.now().isoformat(timespec="seconds"),
                        took_seconds=round(time.time() - self._started, 1) if self._started else None,
                        width=data.get("width"), height=data.get("height"), seconds=data.get("seconds"),
                        server_name=data.get("name"))
            if suffix == "final" and self._upscaleJob:
                up = dict(self._upscaleJob)
                if up.get("seed", -1) is None or int(up["seed"]) < 0:
                    up["seed"] = meta["seed"]     # the engine reuses the preview's seed
                meta["upscale"] = up
            with open(stem + ".json", "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)
        except Exception as ex:
            self._addLog(f"Could not save the parameters next to the video: {ex}")
        self.refreshLibrary()

    def onResponse(self, id, response):
        type = response.get("type", "")
        data = response.get("data", {}) or {}

        if type == "options" and isinstance(data.get("video"), dict):
            self.applyOptions(data["video"])
            return

        if id in self._uploads:
            name = self._uploads[id]
            status = data.get("status") if type == "download" else None
            if status == "success":
                self._addLog(f"LoRA {name} uploaded.")
                del self._uploads[id]
                self._addLora("file", f"custom/{name}", name)
            elif type in {"error", "remote_error"}:
                self._addLog(f"Upload of {name} failed: {data.get('message', '')}")
                del self._uploads[id]
            return

        if self._requestId is None:
            return

        # errors must show up even if the server did not tag them with our request id
        if type in {"error", "remote_error"}:
            self._addLog("Server error: " + str(data.get("message", "")))
            if data.get("trace"):
                self._addLog(str(data["trace"]))
            self._finish("error", str(data.get("message", "")))
            return

        if id != self._requestId:
            return

        if type == RES_PROGRESS:
            fraction = max(0.0, min(1.0, float(data.get("fraction", 0.0))))
            self.gui.onResponse({"id": id, "type": "progress",
                                 "data": {"current": fraction * 1000, "total": 1000, "rate": 0, "unit": ""}})
            if data.get("text"):
                self.gui.onResponse({"id": id, "type": "status",
                                     "data": {"message": str(data["text"]), "reset": False}})
        elif type == RES_CHUNK:
            self._chunks.setdefault(data["id"], {})[data["index"]] = bytes(data["data"])
        elif type == RES_VIDEO:
            if self._stage == "preview":
                self._previewName = data.get("name")
                if not self._save(data, "preview"):
                    self._finish("error", "The video arrived incomplete.")
                    return
                output = self._values.get("output")
                if self._upscale and self._previewName:
                    self._stage = "upscale"
                    request = self.buildUpscaleRequest(self._previewName)
                    self._upscaleJob = {k: request["data"][k] for k in ("output", "preset", "seed", "anchor")}
                    self._requestId = self.gui.makeRequest(request)
                    self._addLog(f"Upscaling to {output}...")
                    self.updated.emit()
                    return
            else:
                saved = self._save(data, "final")
                self._discard()
                self._finish("done" if saved else "error", "" if saved else "The video arrived incomplete.")
                return
            self._discard()
            self._finish("done")
        elif type == "aborted":
            self._addLog("Cancelled.")
            self._discard()
            self._finish()
