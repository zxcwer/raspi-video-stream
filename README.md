# Shrimp Cam 🦐 — Raspberry Pi video stream

A tiny web app that live-streams your Raspberry Pi camera to any browser, so you
can check on your shrimp (or any pet/plant/project) from your phone or laptop.

Built for a **Raspberry Pi Zero W** + **Camera Module v1.3 (OV5647)** running a
recent **Raspberry Pi OS** (Bullseye/Bookworm, libcamera/Picamera2 stack). It
streams **MJPEG** at a modest 640×480 / ~10 fps — light enough for the Pi Zero's
single ARMv6 core, and plenty to see if your shrimp is moving.

```
Camera v1.3 ──CSI ribbon──▶ Pi Zero W ──WiFi──▶ your browser (http://<pi-ip>:8080)
```

## Features
- Live MJPEG stream viewable in any browser — no app or plugin needed
- Clean mobile-friendly page (`/`)
- Save a still photo (`/snapshot.jpg`)
- `/healthz` endpoint for uptime checks
- Auto-starts on boot via systemd
- **Runs on a laptop too**: if there's no Pi camera, it serves a synthetic test
  pattern so you can develop/preview without hardware

---

## 1. Hardware setup

1. **Power off** the Pi. Connect the camera v1.3 ribbon to the CSI port:
   - On a Pi Zero, the camera connector is the small one near the corner. The Pi
     Zero needs the **narrower** camera cable (it ships with the Zero camera kit,
     or buy a "Pi Zero camera adapter cable").
   - Ribbon **contacts face the board** (away from the "Raspberry Pi" silkscreen
     side). Push the black tab back in to lock it.
2. Lighting matters! The OV5647 is not great in dim light, and you're shooting
   through glass. Add a small lamp/LED near the jar and angle the camera ~15°
   off the glass to avoid glare/reflections.

## 2. Flash and configure Raspberry Pi OS

Use **Raspberry Pi Imager**. Choose **Raspberry Pi OS Lite (32-bit)** (no
desktop needed). Before writing, open the ⚙️ settings and set:
- **Hostname**: e.g. `shrimpcam` (lets you reach it at `shrimpcam.local`)
- **Enable SSH** + set a username/password
- **WiFi**: your network SSID + password + country

Boot the Pi, then SSH in:

```bash
ssh <user>@shrimpcam.local      # or use the Pi's IP address
```

On **Bookworm** the camera works out of the box. On **Bullseye**, enable it once:

```bash
sudo raspi-config        # Interface Options → Camera → Enable, then reboot
```

Quick camera test:

```bash
rpicam-hello -t 2000     # (older OS: libcamera-hello -t 2000)
```

If you get a preview/no error, the camera is detected.

## 3. Install the app

```bash
sudo apt update
sudo apt install -y git python3-flask python3-picamera2 python3-pil

git clone https://github.com/zxcwer/raspi-video-stream.git
cd raspi-video-stream
```

> We install Flask/Pillow/Picamera2 as **system apt packages** rather than via
> `pip`, because `python3-picamera2` is only distributed through apt and needs
> the system libcamera libraries. `requirements.txt` is provided mainly for
> running the app on a non-Pi machine in a virtualenv.

## 4. Run it

```bash
python3 app.py
```

You'll see `Running on http://0.0.0.0:8080`. From any device on the same WiFi,
open:

```
http://shrimpcam.local:8080/
```

(or `http://<pi-ip>:8080/` — find the IP with `hostname -I` on the Pi).

🦐 You should see your shrimp.

## 5. Auto-start on boot (systemd)

So the stream comes back automatically after a reboot or power blip:

```bash
# Edit shrimpcam.service first if your username/path isn't pi:/home/pi
sudo cp shrimpcam.service /etc/systemd/system/shrimpcam.service
sudo systemctl daemon-reload
sudo systemctl enable --now shrimpcam.service

systemctl status shrimpcam.service     # check it's active
journalctl -u shrimpcam.service -f     # live logs
```

---

## Endpoints

| Path            | What it does                                  |
|-----------------|-----------------------------------------------|
| `/`             | Web page with the live view                   |
| `/stream.mjpg`  | Raw MJPEG stream (embed in an `<img>`)         |
| `/snapshot.jpg` | Single still frame                            |
| `/healthz`      | Returns `ok`                                  |

## Tuning

Edit the constants at the top of [`camera.py`](camera.py):

```python
WIDTH = 640
HEIGHT = 480
FPS = 10
JPEG_QUALITY = 75
```

- Stream stuttering / Pi struggling? Lower `FPS` (5 is fine for a shrimp) or
  `JPEG_QUALITY`.
- Want it sharper? Raise the resolution — but watch CPU on a Pi Zero.
- Change the port with the `PORT` env var (default `8080`).

## Watching from outside your home

This app has **no authentication** — only expose it on your trusted LAN. To
check on the shrimp while away, don't port-forward it directly. Instead use a
secure tunnel such as **Tailscale** (`curl -fsSL https://tailscale.com/install.sh
| sh`) or **Cloudflare Tunnel**, which give you private remote access without
opening ports to the internet.

## Develop without a Pi

On your laptop:

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python app.py
# open http://127.0.0.1:8080/  — shows a moving mock "shrimp" + timestamp
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| Page loads but image is broken | Camera not detected — re-seat ribbon, run `rpicam-hello`, check logs |
| `Picamera2 unavailable ... using mock source` on the Pi | Install `sudo apt install -y python3-picamera2` and run with system `python3` (not a venv) |
| Can't reach `shrimpcam.local` | Use the IP from `hostname -I`; some networks block mDNS |
| Image is dark/blurry | Add light; clean the glass; let auto-exposure settle a few seconds |
| Stream freezes occasionally | Click **Reconnect** on the page; check WiFi signal to the Pi |
