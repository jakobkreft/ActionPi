"""ActionPi camera controller.

All camera work runs in a background thread so the web request never blocks.
There is exactly one camera, so there is at most one active capture at a time.
The current state is kept in memory and mirrored to ``state.json`` so it can be
recovered if the server restarts while a capture was interrupted.

The real capture commands (``libcamera-still`` / ``libcamera-vid`` / ``ffmpeg``)
are the ones already proven on the Pi.  When ``libcamera-still`` is not present
(e.g. running on a laptop) the controller switches to a mock mode that produces
placeholder media, so the whole app can be developed and tested off-device.
"""

import json
import os
import shutil
import signal
import subprocess
import threading
import time
from datetime import datetime

# Longest-edge size for generated thumbnails (px).
THUMBNAIL_SIZE = 400

# Sub-directories, relative to the base directory.
PHOTOS = "photos"
VIDEOS = "videos"
TIMELAPSES = "timelapses"
KINDS = (PHOTOS, VIDEOS, TIMELAPSES)


def _log(msg):
    print(f"[camera] {msg}", flush=True)


# --------------------------------------------------------------------------- #
# Thumbnail helpers (shared by the controller and by on-demand generation in   #
# the web server, so old media without thumbnails still shows up).             #
# --------------------------------------------------------------------------- #

def make_image_thumbnail(src, dst, size=THUMBNAIL_SIZE):
    """Create a thumbnail of an image. Returns True on success."""
    from PIL import Image

    try:
        with Image.open(src) as img:
            img = img.convert("RGB")
            img.thumbnail((size, size))
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            img.save(dst, "JPEG", quality=75)
        return True
    except Exception as exc:  # noqa: BLE001 - never let a bad file break the app
        _log(f"thumbnail failed for {src}: {exc}")
        return False


def make_video_thumbnail(src, dst, size=THUMBNAIL_SIZE):
    """Grab a frame from a video and turn it into a thumbnail."""
    if not shutil.which("ffmpeg"):
        return False
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    # Try a frame ~0.5s in; fall back to the very first frame for short clips.
    for seek in ("00:00:00.5", "00:00:00"):
        proc = subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error", "-ss", seek, "-i", src,
                "-vframes", "1", "-vf", f"scale={size}:-1", dst,
            ],
            capture_output=True,
        )
        if proc.returncode == 0 and os.path.exists(dst):
            return True
    return False


# --------------------------------------------------------------------------- #
# Camera controller                                                            #
# --------------------------------------------------------------------------- #

class CameraController:
    def __init__(self, base_dir):
        self.base_dir = base_dir
        self.thumb_dir = os.path.join(base_dir, "thumbnails")
        self.state_file = os.path.join(base_dir, "state.json")

        # Real hardware if libcamera is installed, otherwise mock for dev.
        self.mock = os.environ.get("ACTIONPI_MOCK") == "1" or shutil.which("libcamera-still") is None

        self._lock = threading.RLock()
        self._proc = None            # subprocess.Popen of the active capture
        self._job = None             # dict describing the active job
        self._state = {"state": "idle"}

        for kind in KINDS:
            os.makedirs(os.path.join(base_dir, kind), exist_ok=True)
            os.makedirs(os.path.join(self.thumb_dir, kind), exist_ok=True)

        if self.mock:
            _log("libcamera not found -> running in MOCK mode (placeholder media)")

        self._recover()

    # -- public API --------------------------------------------------------- #

    def status(self):
        """Thread-safe snapshot of the current state for the web layer."""
        with self._lock:
            snap = dict(self._state)
        snap["server_time"] = time.time()
        snap["mock"] = self.mock
        return snap

    def is_busy(self):
        with self._lock:
            return self._state.get("state") != "idle"

    def start_photo(self):
        return self._start("photo")

    def start_video(self, duration):
        duration = self._clamp(duration, 1, 24 * 3600)
        return self._start("video", duration=duration)

    def start_timelapse(self, interval, duration):
        interval = self._clamp(interval, 1, 3600)
        duration = self._clamp(duration, interval, 30 * 24 * 3600)
        return self._start("timelapse", duration=duration, interval=interval)

    def stop(self):
        """Gracefully stop the active capture (SIGINT lets libcamera finalise)."""
        with self._lock:
            proc = self._proc
        if proc and proc.poll() is None:
            try:
                proc.send_signal(signal.SIGINT)
            except Exception as exc:  # noqa: BLE001
                _log(f"stop failed: {exc}")
        return self.status()

    # -- capture orchestration --------------------------------------------- #

    def _start(self, mode, duration=None, interval=None):
        with self._lock:
            if self._state.get("state") != "idle":
                # Busy: starting is idempotent, just report what is running.
                return self.status()

            stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            now = time.time()
            job = {"mode": mode, "stamp": stamp}

            if mode == "photo":
                name = f"photo_{stamp}.jpg"
                job["file"] = os.path.join(self.base_dir, PHOTOS, name)
                job["name"] = name
                cmd = ["libcamera-still", "-o", job["file"]]
                mock_seconds = 1
                ends_at = None
            elif mode == "video":
                stem = f"video_{stamp}"
                job["h264"] = os.path.join(self.base_dir, VIDEOS, stem + ".h264")
                job["mp4"] = os.path.join(self.base_dir, VIDEOS, stem + ".mp4")
                job["name"] = stem + ".mp4"
                cmd = [
                    "libcamera-vid", "-t", str(duration * 1000),
                    "--framerate", "24", "--width", "1920", "--height", "1080",
                    "-o", job["h264"],
                ]
                mock_seconds = duration
                ends_at = now + duration
            elif mode == "timelapse":
                folder_name = f"timelapse_{stamp}"
                job["folder"] = os.path.join(self.base_dir, TIMELAPSES, folder_name)
                job["name"] = folder_name
                os.makedirs(job["folder"], exist_ok=True)
                pattern = os.path.join(job["folder"], "image%04d.jpg")
                cmd = [
                    "libcamera-still", "-t", str(duration * 1000),
                    "--timelapse", str(interval * 1000), "--framestart", "1",
                    "-o", pattern,
                ]
                mock_seconds = duration
                ends_at = now + duration
                job["interval"] = interval
            else:
                raise ValueError(f"unknown mode {mode}")

            if self.mock:
                cmd = ["sleep", str(mock_seconds)]

            _log(f"start {mode}: {' '.join(cmd)}")
            try:
                self._proc = subprocess.Popen(cmd)
            except FileNotFoundError as exc:
                _log(f"cannot start capture: {exc}")
                self._proc = None
                return self.status()

            self._job = job
            self._state = {
                "state": "recording",
                "mode": mode,
                "name": job["name"],
                "started_at": now,
                "ends_at": ends_at,
                "duration": duration,
                "interval": interval,
            }
            self._persist()

            worker = threading.Thread(target=self._worker, args=(self._proc, job), daemon=True)
            worker.start()
            return self.status()

    def _worker(self, proc, job):
        """Wait for the capture to finish, then post-process and go idle."""
        proc.wait()
        with self._lock:
            if self._job is not job:
                return  # a newer job replaced this one; nothing to do
            self._state["state"] = "processing"
            self._persist()

        try:
            if self.mock:
                self._mock_output(job)
            elif job["mode"] == "video":
                self._convert_video(job)
            self._make_thumbnail(job)
        except Exception as exc:  # noqa: BLE001
            _log(f"post-processing failed: {exc}")

        with self._lock:
            if self._job is job:
                self._proc = None
                self._job = None
                self._state = {"state": "idle"}
                self._persist()
        _log(f"finished {job['mode']}: {job['name']}")

    def _convert_video(self, job):
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", job["h264"], "-vcodec", "copy", job["mp4"]],
            check=False,
        )
        if os.path.exists(job["mp4"]) and os.path.exists(job["h264"]):
            os.remove(job["h264"])

    def _make_thumbnail(self, job):
        mode = job["mode"]
        if mode == "photo":
            dst = os.path.join(self.thumb_dir, PHOTOS, job["name"])
            make_image_thumbnail(job["file"], dst)
        elif mode == "video":
            dst = os.path.join(self.thumb_dir, VIDEOS, job["name"].replace(".mp4", ".jpg"))
            make_video_thumbnail(job["mp4"], dst)
        elif mode == "timelapse":
            first = self._first_timelapse_image(job["folder"])
            if first:
                dst = os.path.join(self.thumb_dir, TIMELAPSES, job["name"] + ".jpg")
                make_image_thumbnail(first, dst)

    @staticmethod
    def _first_timelapse_image(folder):
        try:
            images = sorted(f for f in os.listdir(folder) if f.lower().endswith(".jpg"))
        except FileNotFoundError:
            return None
        return os.path.join(folder, images[0]) if images else None

    # -- recovery ----------------------------------------------------------- #

    def _recover(self):
        """On startup, finalise anything that was interrupted by a restart."""
        try:
            with open(self.state_file) as fh:
                saved = json.load(fh)
        except (OSError, ValueError):
            saved = None

        if not saved or saved.get("state") == "idle":
            self._state = {"state": "idle"}
            return

        _log(f"recovering interrupted {saved.get('mode')} capture")
        try:
            mode = saved.get("mode")
            name = saved.get("name")
            if mode == "video" and name:
                stem = name.replace(".mp4", "")
                job = {
                    "mode": "video", "name": name,
                    "h264": os.path.join(self.base_dir, VIDEOS, stem + ".h264"),
                    "mp4": os.path.join(self.base_dir, VIDEOS, stem + ".mp4"),
                }
                if os.path.exists(job["h264"]):
                    self._convert_video(job)
                if os.path.exists(job["mp4"]):
                    self._make_thumbnail(job)
            elif mode == "timelapse" and name:
                job = {"mode": "timelapse", "name": name,
                       "folder": os.path.join(self.base_dir, TIMELAPSES, name)}
                self._make_thumbnail(job)
            elif mode == "photo" and name:
                job = {"mode": "photo", "name": name,
                       "file": os.path.join(self.base_dir, PHOTOS, name)}
                if os.path.exists(job["file"]):
                    self._make_thumbnail(job)
        except Exception as exc:  # noqa: BLE001
            _log(f"recovery cleanup failed: {exc}")

        self._state = {"state": "idle"}
        self._persist()

    # -- helpers ------------------------------------------------------------ #

    def _persist(self):
        try:
            with open(self.state_file, "w") as fh:
                json.dump(self._state, fh)
        except OSError as exc:
            _log(f"could not persist state: {exc}")

    @staticmethod
    def _clamp(value, low, high):
        try:
            value = int(value)
        except (TypeError, ValueError):
            value = low
        return max(low, min(high, value))

    # -- mock media generation (dev only) ---------------------------------- #

    def _mock_output(self, job):
        from PIL import Image, ImageDraw

        def placeholder(path, text, color=(40, 90, 140)):
            img = Image.new("RGB", (1280, 720), color)
            ImageDraw.Draw(img).text((40, 40), text, fill=(255, 255, 255))
            img.save(path, "JPEG", quality=80)

        mode = job["mode"]
        if mode == "photo":
            placeholder(job["file"], f"MOCK PHOTO\n{job['stamp']}")
        elif mode == "video":
            made = False
            if shutil.which("ffmpeg"):
                r = subprocess.run(
                    ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
                     "-i", "testsrc=duration=3:size=640x360:rate=24", job["mp4"]],
                    check=False,
                )
                made = r.returncode == 0 and os.path.exists(job["mp4"])
            if not made:
                open(job["mp4"], "wb").close()
        elif mode == "timelapse":
            count = 8  # mock: just a handful of frames to browse
            for i in range(1, count + 1):
                placeholder(
                    os.path.join(job["folder"], f"image{i:04d}.jpg"),
                    f"MOCK FRAME {i}\n{job['stamp']}",
                    color=(30 + i * 6, 80, 120),
                )
