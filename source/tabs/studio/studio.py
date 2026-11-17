"""Native QComfy workspace for multimodal MiniMax H3 prompt writing.

Uses QComfy's existing enhancer provider configuration and the existing Video tab
for final generation. Media is prepared locally; remote providers receive only the
brief and prepared reference images/contact sheets required by the selected mode.
"""
import os
import json
import base64
import threading
import mimetypes
import re
import hashlib
import tempfile

from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot, pyqtProperty, QUrl
from PyQt5.QtQml import qmlRegisterSingletonType

from tabs.video import enhancer

MAX_IMAGES = 9
MAX_VIDEOS = 3
MAX_AUDIOS = 3

MODES = ["T2VA", "I2VA", "FL2VA", "L2VA", "Reference", "Sequence"]


class H3Studio(QObject):
    updated = pyqtSignal()
    _finished = pyqtSignal(str, str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.gui = parent
        self.priority = 2.5
        self.name = "H3 Studio"
        self._brief = ""
        self._result = ""
        self._status = "Ready"
        self._busy = False
        self._images = []
        self._image_names = {}  # optional character/object identity labels keyed by image path
        self._videos = []
        self._audios = []
        self._sequence_count = 3
        self._last_mode = "T2VA"
        self._finished.connect(self._onFinished)
        qmlRegisterSingletonType(H3Studio, "gui", 1, 0, "H3STUDIO", lambda qml, js: self)

    @pyqtProperty(str, notify=updated)
    def result(self): return self._result

    @result.setter
    def result(self, value):
        self._result = str(value or "")
        self.updated.emit()

    @pyqtProperty(str, notify=updated)
    def status(self): return self._status

    @pyqtProperty(bool, notify=updated)
    def busy(self): return self._busy

    @pyqtProperty('QVariantList', notify=updated)
    def images(self): return [{"name": os.path.basename(p), "path": p} for p in self._images]

    @pyqtProperty('QVariantList', notify=updated)
    def videos(self): return [{"name": os.path.basename(p), "path": p} for p in self._videos]

    @pyqtProperty('QVariantList', notify=updated)
    def audios(self): return [{"name": os.path.basename(p), "path": p} for p in self._audios]

    def _video_thumbnail(self, path):
        """Create a small cached first-frame preview; never modify the source video."""
        try:
            import av
            from PIL import Image
            stat = os.stat(path)
            token = hashlib.sha1((os.path.abspath(path) + str(stat.st_mtime_ns)).encode("utf-8")).hexdigest()
            folder = os.path.join(tempfile.gettempdir(), "qcomfy_h3_thumbnails")
            os.makedirs(folder, exist_ok=True)
            target = os.path.join(folder, token + ".jpg")
            if not os.path.isfile(target):
                with av.open(path) as container:
                    frame = next(container.decode(video=0), None)
                    if frame is None:
                        return ""
                    image = frame.to_image().convert("RGB")
                    image.thumbnail((480, 270))
                    image.save(target, "JPEG", quality=82)
            return QUrl.fromLocalFile(target).toString()
        except Exception:
            return ""

    @pyqtProperty('QVariantList', notify=updated)
    def media(self):
        items = []
        for kind, paths in (("image", self._images), ("video", self._videos), ("audio", self._audios)):
            for index, path in enumerate(paths):
                thumb = QUrl.fromLocalFile(path).toString() if kind == "image" else (self._video_thumbnail(path) if kind == "video" else "")
                items.append({"kind": kind, "index": index, "name": os.path.basename(path),
                              "path": path, "thumbnail": thumb,
                              "identity": self._image_names.get(path, "") if kind == "image" else ""})
        return items

    @pyqtProperty(str, notify=updated)
    def firstImage(self): return self._images[0] if self._images else ""

    @pyqtProperty(str, notify=updated)
    def lastImage(self): return self._images[1] if len(self._images) > 1 else ""

    @pyqtProperty('QStringList', constant=True)
    def modes(self): return MODES

    def _local(self, value):
        value = str(value or "")
        return QUrl(value).toLocalFile() if value.startswith("file:") else value

    def _add(self, target, values, limit, allowed):
        added = 0
        for raw in values or []:
            path = self._local(raw)
            if not path or not os.path.isfile(path) or os.path.splitext(path)[1].lower() not in allowed:
                continue
            if path not in target and len(target) < limit:
                target.append(path)
                added += 1
        self._status = f"Added {added} file(s)" if added else "No compatible files added"
        self.updated.emit()

    @pyqtSlot('QVariantList')
    def addImages(self, paths): self._add(self._images, paths, MAX_IMAGES, {".png", ".jpg", ".jpeg", ".webp", ".bmp"})

    @pyqtSlot('QVariantList')
    def addVideos(self, paths): self._add(self._videos, paths, MAX_VIDEOS, {".mp4", ".mov", ".mkv", ".webm", ".avi"})

    @pyqtSlot('QVariantList')
    def addAudios(self, paths): self._add(self._audios, paths, MAX_AUDIOS, {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac"})

    @pyqtSlot(str, int)
    def removeMedia(self, kind, index):
        target = {"image": self._images, "video": self._videos, "audio": self._audios}.get(kind)
        if target is not None and 0 <= index < len(target):
            removed = target.pop(index)
            if kind == "image":
                self._image_names.pop(removed, None)
            self._status = "Reference removed"
            self.updated.emit()

    @pyqtSlot(int, str)
    def setImageIdentity(self, index, name):
        if 0 <= index < len(self._images):
            path = self._images[index]
            self._image_names[path] = str(name or "").strip()
            self.updated.emit()

    @pyqtSlot()
    def clearMedia(self):
        self._images, self._videos, self._audios = [], [], []
        self._image_names = {}
        self._status = "References cleared"
        self.updated.emit()

    def _settings(self):
        cfg = self.gui.config
        def get(key):
            value = cfg.get(key)
            return value if isinstance(value, str) else ""
        return {"provider": get("enhancer_provider") or "OpenAI", "url": get("enhancer_url"),
                "model": get("enhancer_model"), "key": get("enhancer_key")}

    @staticmethod
    def _image_payload(path):
        from PIL import Image
        import io
        with Image.open(path) as im:
            im = im.convert("RGB")
            im.thumbnail((1280, 1280))
            buf = io.BytesIO()
            im.save(buf, "JPEG", quality=88)
        return ("image/jpeg", base64.b64encode(buf.getvalue()).decode("ascii"))

    @staticmethod
    def _video_contact_sheet(path):
        """Sample up to six evenly spaced frames; H3 prompt models receive the sheet, not video bytes."""
        import io
        from PIL import Image, ImageDraw
        try:
            import av
            with av.open(path) as container:
                stream = container.streams.video[0]
                duration = float(stream.duration * stream.time_base) if stream.duration else 0
                if not duration and container.duration:
                    duration = float(container.duration) / 1_000_000
                times = [duration * x / 5 for x in range(6)] if duration > 0 else [0]
                frames = []
                for t in times:
                    try:
                        container.seek(int(t / float(stream.time_base)), stream=stream, backward=True)
                        frame = next(container.decode(video=0), None)
                        if frame is not None:
                            im = frame.to_image().convert("RGB")
                            im.thumbnail((480, 270))
                            frames.append((t, im.copy()))
                    except Exception:
                        continue
            if not frames:
                raise RuntimeError("No video frames could be decoded")
            cell_w, cell_h = 480, 300
            sheet = Image.new("RGB", (cell_w * 2, cell_h * 3), "#17191d")
            draw = ImageDraw.Draw(sheet)
            for i, (t, im) in enumerate(frames[:6]):
                x, y = (i % 2) * cell_w, (i // 2) * cell_h
                sheet.paste(im, (x + (cell_w-im.width)//2, y + 4))
                draw.text((x + 8, y + 278), f"{t:.1f}s", fill="white")
            buf = io.BytesIO(); sheet.save(buf, "JPEG", quality=85)
            return ("image/jpeg", base64.b64encode(buf.getvalue()).decode("ascii"))
        except ImportError:
            raise RuntimeError("Video reference analysis requires the optional 'av' package. Install it with: pip install av")

    def _build_request(self, mode, brief, seconds, aspect, extra, sequence_count, dialogue="", sound_effects="", music=""):
        mode = mode if mode in MODES else "T2VA"
        refs = []
        images = []
        for i, path in enumerate(self._images):
            identity = (self._image_names.get(path) or "").strip()
            if identity:
                refs.append(f"Picture {i+1}: {identity} (user-defined character/object identity; preserve this exact name and keep this subject visually distinct)")
            else:
                refs.append(f"Picture {i+1}: {os.path.basename(path)}")
            images.append(self._image_payload(path))
        for i, path in enumerate(self._videos):
            refs.append(f"Video {i+1}: {os.path.basename(path)} (represented to the model by an ordered contact sheet of sampled frames)")
            images.append(self._video_contact_sheet(path))
        for i, path in enumerate(self._audios):
            refs.append(f"Audio {i+1}: {os.path.basename(path)} (audio content is not sent to or interpreted by the prompt model; use the user's written brief for sound details)")
        if mode == "I2VA" and not self._images:
            raise RuntimeError("I2VA requires at least one image reference.")
        if mode == "FL2VA" and len(self._images) < 2:
            raise RuntimeError("FL2VA requires a first-frame image and a last-frame image (add at least two images).")
        if mode == "L2VA" and not self._images:
            raise RuntimeError("L2VA requires a last-frame image.")
        if mode == "Reference" and not (self._images or self._videos or self._audios):
            raise RuntimeError("Reference mode needs at least one image, video, or audio reference.")
        task = {"T2VA":"text-to-video", "I2VA":"image-to-video", "FL2VA":"first-and-last-frame-to-video", "L2VA":"last-frame-to-video", "Reference":"multi-reference video", "Sequence":"multi-clip sequence"}[mode]
        user = [f"Task: {task}", f"Target duration: {seconds} seconds per clip", f"Aspect ratio: {aspect}",
                f"Creative brief:\n{brief.strip() or '(Use the reference media and infer a coherent, visually clear action.)'}"]
        if refs:
            user.append("Reference media (use explicit <Picture N>, <Video N>, and <Audio N> tags when referring to them):\n" + "\n".join(refs))
            if any(self._image_names.get(path, "").strip() for path in self._images):
                user.append("Named identity references: the user assigned explicit names to selected picture references. Use those exact names in the prompt, bind each name only to its corresponding <Picture N>, preserve each subject's recognizable appearance, and never merge, rename, or swap identities.")
        if mode == "Sequence":
            count = max(2, min(8, sequence_count))
            user.append(f"Create exactly {count} sequential clips. Each clip must have its own complete, independently usable H3 prompt, with consistent character identity, wardrobe, setting, visual style, and causal continuity. Make each clip a distinct beat and avoid repeating the same action. Separate them using these exact headings on their own lines: " + ", ".join(f"=== CLIP {i} ===" for i in range(1, count + 1)) + ". Do not omit any clip.")
        else:
            user.append("Return one complete prompt for the selected task mode.")
        if extra.strip(): user.append("Additional direction:\n" + extra.strip())
        if dialogue.strip():
            user.append("Spoken line / dialogue (preserve these exact words; do not paraphrase or translate):\n" + dialogue.strip())
        if sound_effects.strip():
            user.append("Sound effects and ambience direction:\n" + sound_effects.strip())
        if music.strip():
            user.append("Background music direction:\n" + music.strip())
        user.append("Output the final prompt in the official MiniMax H3 structured format. Include integrated_multimodal_description, overall_soundscape, and non_diegetic_music where applicable. Use concrete, timed visual action, camera movement, lighting, and sound. Preserve user-provided dialogue exactly. Treat the spoken-line, sound-effects, and music fields as separate creative instructions and incorporate each into its corresponding H3 sound fields. Do not invent details that contradict the references.")
        return "\n\n".join(user), images, mode

    @pyqtSlot(str, str, str, str, str, int, str, str, str)
    def generate(self, mode, brief, seconds, aspect, extra, sequence_count, dialogue="", sound_effects="", music=""):
        if self._busy: return
        if not str(brief or "").strip() and not (self._images or self._videos):
            self._status = "Write a creative brief or add visual references first."; self.updated.emit(); return
        self._busy = True; self._last_mode = mode if mode in MODES else "T2VA"; self._status = "Preparing references and generating H3 prompt…"; self.updated.emit()
        def work():
            try:
                user, images, mode_used = self._build_request(mode, brief, seconds, aspect, extra, sequence_count, dialogue, sound_effects, music)
                system = enhancer.h3_system_prompt(mode_used if mode_used in ("T2VA", "I2VA", "FL2VA", "L2VA", "Reference") else "T2VA")
                result = enhancer.request(self._settings(), system, user, timeout=240, images=images or None)
                self._finished.emit(result, "Prompt generated successfully")
            except Exception as ex:
                self._finished.emit("", "Generation failed: " + str(ex))
        threading.Thread(target=work, daemon=True).start()

    @pyqtSlot(str, str)
    def refine(self, current, instruction):
        if self._busy: return
        if not str(current or "").strip():
            self._status = "Generate or paste a prompt before refining it."; self.updated.emit(); return
        self._busy = True; self._status = "Refining prompt…"; self.updated.emit()
        def work():
            try:
                system = (enhancer.REFERENCE_GUIDE if self._last_mode == "Reference" else enhancer.BASE_GUIDE) + "\n\nYou are revising an existing H3 prompt. Preserve its exact required section names/order, scene intent, speaker IDs, reference labels and dialogue. Apply the requested changes without adding unsupported reference assets. Return only the complete revised prompt."
                user = "Prompt to refine:\n" + current.strip() + "\n\nRequested refinement:\n" + (instruction.strip() or "Improve clarity, cinematic specificity, motion continuity, and H3 structure.")
                result = enhancer.request(self._settings(), system, user, timeout=180)
                self._finished.emit(result, "Prompt refined")
            except Exception as ex:
                self._finished.emit("", "Refine failed: " + str(ex))
        threading.Thread(target=work, daemon=True).start()

    @pyqtSlot(str)
    def setResult(self, text):
        self._result = str(text or "")
        self.updated.emit()

    @pyqtSlot(str, str, str, str, str, str)
    def sendToVideo(self, seconds, aspect, mode, dialogue="", sound_effects="", music=""):
        if not self._result.strip():
            self._status = "There is no prompt to send."; self.updated.emit(); return
        # Keep the prompt editable in the existing video tab; avoid silently starting a generation.
        video = None
        try:
            from tabs.video import video as video_module
            video = getattr(video_module, "VIDEO_INSTANCE", None)
        except Exception:
            pass
        prompt_to_send = self._result
        if self._last_mode == "Sequence":
            match = re.search(r"=== CLIP 1 ===\s*(.*?)(?=\n\s*=== CLIP 2 ===|$)", prompt_to_send, re.S | re.I)
            if match and match.group(1).strip():
                prompt_to_send = match.group(1).strip()
        if video is not None:
            video.values.set("prompt", prompt_to_send)
            try:
                video.values.set("seconds", float(seconds))
            except (TypeError, ValueError):
                pass
            available_aspects = video.values.get("aspects") or []
            if aspect in available_aspects:
                video.values.set("aspect", aspect)
            else:
                video.values.set("aspect", "Auto (match image)")
            video.values.set("dialogue", str(dialogue or ""))
            video.values.set("sound", str(sound_effects or ""))
            video.values.set("music", str(music or ""))
            if mode == "I2VA" and self._images:
                video.setFrame("start_frame", self._images[0])
                video.setFrame("end_frame", "")
            elif mode == "FL2VA" and len(self._images) > 1:
                video.setFrame("start_frame", self._images[0])
                video.setFrame("end_frame", self._images[1])
            elif mode == "L2VA" and self._images:
                video.setFrame("start_frame", "")
                video.setFrame("end_frame", self._images[0])
            elif mode == "Reference" and self._images:
                # Reference mode routes every Studio image to Video > References,
                # never to the start/end frame inputs. Keep the identity labels.
                video.setFrame("start_frame", "")
                video.setFrame("end_frame", "")
                for index, image_path in enumerate(self._images[:9]):
                    identity = self._image_names.get(image_path, "")
                    video.addStudioReference(image_path, identity)
        self.gui.currentTab = "Video"
        self._status = ("First sequence clip sent to Video. Advance through the sequence manually." if self._last_mode == "Sequence" else "Prompt sent to Video. Review settings, then press Generate."); self.updated.emit()

    def _onFinished(self, result, status):
        self._busy = False
        if result: self._result = result
        self._status = status
        self.updated.emit()


# loadTabs discovers tab classes by the directory name.
Studio = H3Studio
