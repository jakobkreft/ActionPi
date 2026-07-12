"""ActionPi web server.

A small, self-contained Flask app that drives the camera and serves a gallery.
Everything the browser needs is served locally (no CDNs) so it works with no
internet connection - which is the whole point of an underwater camera.

Design notes:
  * Captures never block a request. `POST /api/capture/*` returns immediately
    and the browser polls `GET /api/status` to follow progress. Because the
    camera allows only one job at a time, starting is idempotent: hitting start
    (or refreshing) while a capture runs just reports the running capture.
  * `GET /api/status` includes `server_time` and `ends_at` so the browser can
    keep counting down the remaining time even while disconnected, and re-sync
    on reconnect.
  * Downloads of folders / multiple files are streamed as an uncompressed
    (STORED) zip on the fly - no temp file, no re-compression, fast on a Pi.
"""

import os
import shutil
import zipfile
from subprocess import Popen

from flask import (
    Flask, abort, jsonify, render_template, request, send_file, Response,
)

from camera import (
    CameraController, KINDS, PHOTOS, VIDEOS, TIMELAPSES,
    make_image_thumbnail, make_video_thumbnail,
)

BASE_DIR = os.environ.get("ACTIONPI_DIR", os.path.expanduser("~/camera"))
os.makedirs(BASE_DIR, exist_ok=True)
THUMB_DIR = os.path.join(BASE_DIR, "thumbnails")

app = Flask(__name__)
camera = CameraController(BASE_DIR)


# --------------------------------------------------------------------------- #
# Path safety                                                                  #
# --------------------------------------------------------------------------- #

def safe_path(rel):
    """Resolve a media path and make sure it stays inside BASE_DIR."""
    rel = (rel or "").strip("/")
    full = os.path.realpath(os.path.join(BASE_DIR, rel))
    base = os.path.realpath(BASE_DIR)
    if full != base and not full.startswith(base + os.sep):
        abort(403)
    return full


# --------------------------------------------------------------------------- #
# Pages                                                                        #
# --------------------------------------------------------------------------- #

@app.route("/")
def index():
    return render_template("index.html")


# --------------------------------------------------------------------------- #
# Status & capture control                                                     #
# --------------------------------------------------------------------------- #

@app.route("/api/status")
def api_status():
    return jsonify({"camera": camera.status(), "system": system_status()})


def _int_param(name, default=0):
    data = request.get_json(silent=True) or request.form or {}
    try:
        return int(data.get(name, default))
    except (TypeError, ValueError):
        return default


@app.route("/api/capture/photo", methods=["POST"])
def api_photo():
    return jsonify(camera.start_photo())


@app.route("/api/capture/video", methods=["POST"])
def api_video():
    return jsonify(camera.start_video(_int_param("duration", 60)))


@app.route("/api/capture/timelapse", methods=["POST"])
def api_timelapse():
    return jsonify(camera.start_timelapse(_int_param("interval", 5), _int_param("duration", 3600)))


@app.route("/api/capture/stop", methods=["POST"])
def api_stop():
    return jsonify(camera.stop())


# --------------------------------------------------------------------------- #
# Media listing                                                                #
# --------------------------------------------------------------------------- #

def _kind_dir(kind):
    return os.path.join(BASE_DIR, kind)


@app.route("/api/media")
def api_media():
    items = []

    for name in _listdir(_kind_dir(PHOTOS)):
        if name.lower().endswith((".jpg", ".jpeg", ".png")):
            path = os.path.join(_kind_dir(PHOTOS), name)
            items.append({
                "kind": "photo", "name": name, "path": f"{PHOTOS}/{name}",
                "url": f"/media/{PHOTOS}/{name}", "thumb": f"/thumb/{PHOTOS}/{name}",
                "size": _size(path), "mtime": _mtime(path),
            })

    for name in _listdir(_kind_dir(VIDEOS)):
        if name.lower().endswith(".mp4"):
            path = os.path.join(_kind_dir(VIDEOS), name)
            items.append({
                "kind": "video", "name": name, "path": f"{VIDEOS}/{name}",
                "url": f"/media/{VIDEOS}/{name}", "thumb": f"/thumb/{VIDEOS}/{name}",
                "size": _size(path), "mtime": _mtime(path),
            })

    for name in _listdir(_kind_dir(TIMELAPSES)):
        folder = os.path.join(_kind_dir(TIMELAPSES), name)
        if os.path.isdir(folder):
            frames = [f for f in _listdir(folder) if f.lower().endswith(".jpg")]
            items.append({
                "kind": "timelapse", "name": name, "path": f"{TIMELAPSES}/{name}",
                "thumb": f"/thumb/{TIMELAPSES}/{name}", "count": len(frames),
                "mtime": _mtime(folder),
            })

    items.sort(key=lambda i: i["mtime"], reverse=True)
    return jsonify(items)


@app.route("/api/media/timelapse/<name>")
def api_timelapse_frames(name):
    folder = safe_path(f"{TIMELAPSES}/{name}")
    if not os.path.isdir(folder):
        abort(404)
    frames = []
    for fname in sorted(f for f in _listdir(folder) if f.lower().endswith(".jpg")):
        frames.append({
            "name": fname, "path": f"{TIMELAPSES}/{name}/{fname}",
            "url": f"/media/{TIMELAPSES}/{name}/{fname}",
            "size": _size(os.path.join(folder, fname)),
        })
    return jsonify({"name": name, "count": len(frames), "frames": frames})


# --------------------------------------------------------------------------- #
# Serving media & thumbnails                                                    #
# --------------------------------------------------------------------------- #

@app.route("/media/<path:subpath>")
def media(subpath):
    full = safe_path(subpath)
    if not os.path.isfile(full):
        abort(404)
    as_attachment = request.args.get("download") == "1"
    # conditional=True enables range requests so <video> seeking works.
    return send_file(full, conditional=True, as_attachment=as_attachment)


@app.route("/thumb/<kind>/<path:name>")
def thumb(kind, name):
    if kind not in KINDS:
        abort(404)
    thumb_file, source, is_video = _thumb_target(kind, name)
    if not os.path.exists(thumb_file) and source and os.path.exists(source):
        if is_video:
            make_video_thumbnail(source, thumb_file)
        else:
            make_image_thumbnail(source, thumb_file)
    if not os.path.exists(thumb_file):
        abort(404)
    return send_file(thumb_file, max_age=86400)


def _thumb_target(kind, name):
    """Return (thumb_file, source_file, is_video) for a media item."""
    if kind == PHOTOS:
        return (os.path.join(THUMB_DIR, PHOTOS, name),
                os.path.join(_kind_dir(PHOTOS), name), False)
    if kind == VIDEOS:
        stem = name.rsplit(".", 1)[0]
        return (os.path.join(THUMB_DIR, VIDEOS, stem + ".jpg"),
                os.path.join(_kind_dir(VIDEOS), name), True)
    # timelapse: thumbnail is the folder's first frame
    folder = os.path.join(_kind_dir(TIMELAPSES), name)
    first = CameraController._first_timelapse_image(folder)
    return (os.path.join(THUMB_DIR, TIMELAPSES, name + ".jpg"), first, False)


# --------------------------------------------------------------------------- #
# Download (single file direct, folder/multiple as streamed zip)               #
# --------------------------------------------------------------------------- #

@app.route("/api/download")
def api_download():
    rels = request.args.getlist("path")
    if not rels:
        abort(400)

    # Build the flat list of (arcname, absolute path) to include.
    entries = []
    for rel in rels:
        full = safe_path(rel)
        if os.path.isfile(full):
            entries.append((os.path.basename(full), full))
        elif os.path.isdir(full):
            base = os.path.basename(full)
            for root, _dirs, files in os.walk(full):
                for f in files:
                    fp = os.path.join(root, f)
                    arc = os.path.join(base, os.path.relpath(fp, full))
                    entries.append((arc, fp))
    if not entries:
        abort(404)

    # A single plain file: stream it directly, no zip needed.
    if len(rels) == 1 and os.path.isfile(safe_path(rels[0])):
        return send_file(safe_path(rels[0]), as_attachment=True)

    if len(rels) == 1 and os.path.isdir(safe_path(rels[0])):
        zip_name = os.path.basename(safe_path(rels[0])) + ".zip"
    else:
        zip_name = "actionpi_selection.zip"

    resp = Response(_stream_zip(entries), mimetype="application/zip")
    resp.headers["Content-Disposition"] = f'attachment; filename="{zip_name}"'
    return resp


class _ZipBuffer:
    """A minimal non-seekable sink so zipfile streams with data descriptors."""

    def __init__(self):
        self.data = bytearray()

    def write(self, b):
        self.data += b
        return len(b)

    def flush(self):
        pass

    def close(self):
        pass


def _stream_zip(entries):
    buf = _ZipBuffer()
    zf = zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED, allowZip64=True)
    for arcname, path in entries:
        try:
            zinfo = zipfile.ZipInfo.from_file(path, arcname)
        except OSError:
            continue
        zinfo.compress_type = zipfile.ZIP_STORED
        with open(path, "rb") as src, zf.open(zinfo, "w") as dst:
            while True:
                chunk = src.read(262144)
                if not chunk:
                    break
                dst.write(chunk)
                if buf.data:
                    yield bytes(buf.data)
                    del buf.data[:]
        if buf.data:
            yield bytes(buf.data)
            del buf.data[:]
    zf.close()
    if buf.data:
        yield bytes(buf.data)
        del buf.data[:]


# --------------------------------------------------------------------------- #
# Delete                                                                       #
# --------------------------------------------------------------------------- #

@app.route("/api/delete", methods=["POST"])
def api_delete():
    data = request.get_json(silent=True) or {}
    paths = data.get("paths") or []
    deleted = []
    for rel in paths:
        full = safe_path(rel)
        base = os.path.realpath(BASE_DIR)
        if full == base:
            continue  # never delete the root
        if os.path.isdir(full):
            shutil.rmtree(full, ignore_errors=True)
        elif os.path.isfile(full):
            os.remove(full)
        else:
            continue
        _remove_thumbnail(rel)
        deleted.append(rel)
    return jsonify({"deleted": deleted})


def _remove_thumbnail(rel):
    rel = rel.strip("/")
    parts = rel.split("/")
    kind = parts[0]
    try:
        if kind == PHOTOS and len(parts) == 2:
            _unlink(os.path.join(THUMB_DIR, PHOTOS, parts[1]))
        elif kind == VIDEOS and len(parts) == 2:
            _unlink(os.path.join(THUMB_DIR, VIDEOS, parts[1].rsplit(".", 1)[0] + ".jpg"))
        elif kind == TIMELAPSES and len(parts) == 2:
            _unlink(os.path.join(THUMB_DIR, TIMELAPSES, parts[1] + ".jpg"))
    except OSError:
        pass


# --------------------------------------------------------------------------- #
# System status & power                                                        #
# --------------------------------------------------------------------------- #

def system_status():
    total, used, free = shutil.disk_usage(BASE_DIR)
    gb = 2 ** 30
    return {
        "cpu_temp": _cpu_temp(),
        "disk": {
            "total_gb": round(total / gb, 1),
            "used_gb": round(used / gb, 1),
            "free_gb": round(free / gb, 1),
            "percent": round(used / total * 100) if total else 0,
        },
    }


def _cpu_temp():
    try:
        with open("/sys/class/thermal/thermal_zone0/temp") as fh:
            return round(int(fh.read().strip()) / 1000.0, 1)
    except (OSError, ValueError):
        return None


@app.route("/api/shutdown", methods=["POST"])
def api_shutdown():
    Popen(["sudo", "shutdown", "-h", "now"])
    return jsonify({"ok": True})


@app.route("/api/reboot", methods=["POST"])
def api_reboot():
    Popen(["sudo", "reboot"])
    return jsonify({"ok": True})


# --------------------------------------------------------------------------- #
# Small filesystem helpers                                                     #
# --------------------------------------------------------------------------- #

def _listdir(path):
    try:
        return os.listdir(path)
    except OSError:
        return []


def _size(path):
    try:
        return os.path.getsize(path)
    except OSError:
        return 0


def _mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0


def _unlink(path):
    if os.path.exists(path):
        os.remove(path)


if __name__ == "__main__":
    # threaded=True so status polls and downloads are served while a capture
    # subprocess is running in the background.
    app.run(host="0.0.0.0", port=8000, threaded=True)
