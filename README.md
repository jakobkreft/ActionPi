# ActionPi

Turn a Raspberry Pi + camera into a standalone, web-controlled action / underwater
camera. Everything is controlled from a phone browser over the Pi's local network —
no screen, no buttons, no buzzer, no internet required.

ActionPi is built for the one thing that makes underwater use hard: **the connection
drops all the time, and that's fine.** Recordings run entirely on the Pi, independent
of your phone. If you walk out of Wi-Fi range mid-timelapse, the browser keeps
estimating the time remaining and shows a *disconnected* badge; when you reconnect it
re-syncs to the real camera state. Refreshing or reopening the page never starts a
second recording.

![ActionPi](https://github.com/jakobkreft/ActionPi/assets/70409100/aa58d77d-f926-4b22-aeda-e2a39844f04f)

## Features

- **Photo, Video and Timelapse** capture, started from the web UI.
- **Non-blocking**: starting a capture returns instantly; the camera runs in the
  background. Only one capture runs at a time, and starting is idempotent.
- **Connection-loss friendly**: live countdown of remaining recording time that keeps
  running while offline and re-syncs on reconnect.
- **Gallery**: browse photos, videos and timelapse folders. View full-size, play
  videos, step through timelapse frames, download or delete — individually or
  multi-select.
- **Fast downloads**: single files stream directly; folders and multi-selections
  stream as an *uncompressed* zip on the fly — no re-zipping, no temp files, easy on a
  Pi Zero.
- **Self-contained**: no CDNs. All CSS/JS is served from the Pi so it works with zero
  internet access.
- **System status**: CPU temperature and disk space; shutdown / reboot buttons.

## Hardware

- A Raspberry Pi with Wi-Fi (a Pi Zero W works).
- A camera module supported by `libcamera` (`libcamera-still` / `libcamera-vid`).

That's it — no GPIO wiring, sensors or buzzer.

## Install

Clone onto the Pi and install the dependencies:

```bash
git clone https://github.com/jakobkreft/ActionPi.git
cd ActionPi

# System camera + video tools (usually already present on Raspberry Pi OS)
sudo apt-get update
sudo apt-get install -y libcamera-apps ffmpeg python3-flask python3-pil

# Or, if you prefer pip:
# pip3 install -r requirements.txt
```

Media is stored under `~/camera` by default (`photos/`, `videos/`, `timelapses/`,
`thumbnails/`). Override with the `ACTIONPI_DIR` environment variable.

## Run

```bash
python3 server.py
```

Then open `http://<pi-ip>:8000` from your phone on the same network (or the Pi's
Wi-Fi hotspot).

> If `libcamera-still` isn't installed (e.g. you're testing on a laptop), ActionPi
> automatically runs in **mock mode** and generates placeholder media so you can try
> the whole interface without a camera.

## Run at boot (systemd)

An `actionpi.service` unit is included. Edit the `User`, `WorkingDirectory` and paths
if your username isn't `pi`, then:

```bash
sudo cp actionpi.service /etc/systemd/system/actionpi.service
sudo systemctl daemon-reload
sudo systemctl enable --now actionpi.service
```

Check logs with `journalctl -u actionpi -f`.

The Shutdown / Reboot buttons call `sudo shutdown` / `sudo reboot`. On Raspberry Pi OS
the default user already has passwordless sudo; otherwise add a sudoers rule for those
two commands.

## How it works

| Part | File |
|------|------|
| Camera controller — background capture, state persistence, crash recovery | `camera.py` |
| Web server — REST API, media listing, streaming downloads, system status | `server.py` |
| Single-page web UI (offline-resilient) | `templates/index.html`, `static/` |

The browser polls `GET /api/status`, which returns the camera state together with the
server clock and the recording's `ends_at` timestamp. The UI uses these to count down
locally, so the estimate stays correct even with no connection.
