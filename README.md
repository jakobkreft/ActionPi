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
- **System status**: battery level (UPS-Lite HAT), CPU temperature and disk space;
  shutdown / reboot buttons.
- **Battery monitor**: reads percentage + voltage from a UPS-Lite fuel gauge over I2C
  and estimates charging / discharging.
- **Wi-Fi self-healing** (optional): disables Wi-Fi power-save and auto-reconnects if
  the Pi's Wi-Fi client link drops.

## Hardware

- A Raspberry Pi with Wi-Fi (a Pi Zero W works).
- A camera module supported by `libcamera` (`libcamera-still` / `libcamera-vid`).
- *(Optional)* a **UPS-Lite V1.3** battery HAT for the battery indicator.

No GPIO wiring, sensors or buzzer needed.

## Install

Clone onto the Pi and install the dependencies:

```bash
git clone https://github.com/jakobkreft/ActionPi.git
cd ActionPi

# System camera + video tools (usually already present on Raspberry Pi OS)
sudo apt-get update
sudo apt-get install -y libcamera-apps ffmpeg python3-flask python3-pil

# Optional: battery monitoring on the UPS-Lite HAT
sudo apt-get install -y python3-smbus

# Or, if you prefer pip:
# pip3 install -r requirements.txt
```

Media is stored under `~/camera` by default (`photos/`, `videos/`, `timelapses/`,
`thumbnails/`). Override with the `ACTIONPI_DIR` environment variable.

### Battery monitor (UPS-Lite)

The battery indicator reads a UPS-Lite fuel gauge over I2C, so enable I2C once:

```bash
sudo raspi-config    # Interface Options -> I2C -> Enable
```

If no UPS-Lite / I2C is present the app simply hides the battery indicator.

### Wi-Fi auto-reconnect (optional)

Set `ACTIONPI_WIFI_WATCHDOG=1` (already set in `actionpi.service`) to have ActionPi
disable Wi-Fi power-save and automatically reconnect the Pi's Wi-Fi **client** link if
it drops. It uses passwordless `sudo` for a few network commands (default on Raspberry
Pi OS).

> Only use this when the Pi connects to an existing Wi-Fi network. Do **not** enable it
> if the Pi hosts its own hotspot — it would bounce the connection your phone is on.

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
| Battery monitor — UPS-Lite fuel gauge over I2C | `battery.py` |
| Wi-Fi reconnect watchdog | `wifi.py` |
| Single-page web UI (offline-resilient) | `templates/index.html`, `static/` |

The browser polls `GET /api/status`, which returns the camera state together with the
server clock and the recording's `ends_at` timestamp. The UI uses these to count down
locally, so the estimate stays correct even with no connection.
