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

Use the install script — it fills in **your** username and repo path
automatically, so the service can't fail with a wrong user:

```bash
bash install-service.sh

# ...or bake in a password at the same time:
SHRIMPCAM_USER=yourname SHRIMPCAM_PASS=a-long-random-password bash install-service.sh
```

Then:

```bash
systemctl status shrimpcam.service     # check it's active
journalctl -u shrimpcam.service -f     # live logs
```

<details>
<summary>Doing it manually instead</summary>

`shrimpcam.service` ships with `__USER__` / `__DIR__` placeholders. Replace both
before installing, or systemd will fail with `status=217/USER`:

```bash
sed -e "s|__USER__|$(whoami)|g" -e "s|__DIR__|$PWD|g" shrimpcam.service \
  | sudo tee /etc/systemd/system/shrimpcam.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable --now shrimpcam.service
```
</details>

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

## Security & authentication

The app supports optional **HTTP Basic Auth**. Set two environment variables and
every endpoint (except `/healthz`) requires a username/password:

```bash
export SHRIMPCAM_USER=yourname
export SHRIMPCAM_PASS=a-long-random-password
python3 app.py
```

If `SHRIMPCAM_USER` is unset, auth is disabled (LAN-only mode). In the systemd
service, add them under `[Service]`:

```ini
Environment=SHRIMPCAM_USER=yourname
Environment=SHRIMPCAM_PASS=a-long-random-password
```

> ⚠️ **Never put this app directly on the public internet** (no port-forwarding!).
> Even with Basic Auth, that exposes your home IP and an unhardened dev server.
> Use a tunnel — see below.

## Publish to the internet with Cloudflare Tunnel

[Cloudflare Tunnel](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/)
gives your Pi a public HTTPS URL **without opening any ports or revealing your
home IP** — `cloudflared` makes an outbound-only connection to Cloudflare.

**The tunnel itself is not access control.** Anyone with the URL can watch unless
you add auth. Use both layers below: Cloudflare Access (auth at the edge) **and**
the app's Basic Auth (defense in depth).

### Prerequisites
- A **domain on Cloudflare** (free plan is fine). Buy a cheap domain and change
  its nameservers to Cloudflare, or register one in the Cloudflare dashboard.
- *No domain yet?* You can smoke-test with a **quick tunnel** — run
  `cloudflared tunnel --url http://localhost:8080` and it prints a random
  `https://<random>.trycloudflare.com` URL. It's ephemeral and **has no Access
  protection**, so add `SHRIMPCAM_USER/PASS` and treat it as a temporary test
  only.

### 1. Install cloudflared on the Pi

```bash
# ARMv6 (original Pi Zero / Zero W):
curl -L -o cloudflared https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm
# (Pi Zero 2 W / 64-bit OS: use ...cloudflared-linux-arm64)
sudo install -m 755 cloudflared /usr/local/bin/cloudflared
cloudflared --version
```

### 2. Authenticate and create the tunnel

```bash
cloudflared tunnel login                 # opens a browser link; pick your domain
cloudflared tunnel create shrimpcam      # prints a TUNNEL_ID + creds JSON path
cloudflared tunnel route dns shrimpcam shrimp.example.com   # your hostname
```

### 3. Configure it and install the service

> ⚠️ **The config must live in `/etc/cloudflared/`, not `~/.cloudflared/`.**
> `sudo cloudflared service install` runs as **root**, so `~` means `/root` — a
> config in your own home directory is invisible to it and you get:
> `Cannot determine default configuration path. No file [config.yml config.yaml]`
> The tunnel **credentials JSON** must be copied there too, for the same reason.

The script handles all of that — writing the config, copying the credentials
with safe permissions, validating the ingress rules, and installing the service:

```bash
TUNNEL_HOSTNAME=shrimp.example.com bash install-tunnel.sh
```

It looks up the tunnel UUID by name (`shrimpcam` by default; override with
`TUNNEL_NAME=`), so you never have to paste it by hand.

<details>
<summary>Doing it manually instead</summary>

```bash
TUNNEL_ID=<uuid from `cloudflared tunnel list`>
HOST=shrimp.example.com

sudo mkdir -p /etc/cloudflared
sudo cp ~/.cloudflared/$TUNNEL_ID.json /etc/cloudflared/
sudo chmod 600 /etc/cloudflared/$TUNNEL_ID.json

sudo tee /etc/cloudflared/config.yml > /dev/null <<EOF
tunnel: $TUNNEL_ID
credentials-file: /etc/cloudflared/$TUNNEL_ID.json

ingress:
  - hostname: $HOST
    service: http://localhost:8080
  - service: http_status:404
EOF

sudo cloudflared service install
sudo systemctl enable --now cloudflared
```

[`cloudflared.example.yml`](cloudflared.example.yml) is the same file as a
template. To test *before* installing the service, you can run it in the
foreground as your normal user:
`cloudflared --config /etc/cloudflared/config.yml tunnel run shrimpcam`
</details>

Now both `shrimpcam.service` (the app) and `cloudflared` start on boot.

### 4. Check it

```bash
systemctl status cloudflared --no-pager
journalctl -u cloudflared -f          # look for "Registered tunnel connection"
```

Then visit `https://shrimp.example.com` — you should see the shrimp.

### 5. Lock it down with Cloudflare Access (do this!)

This is the real protection — auth happens at Cloudflare's edge before any
request reaches your Pi:

1. Cloudflare dashboard → **Zero Trust** → **Access** → **Applications** →
   **Add an application** → **Self-hosted**.
2. Set the application domain to `shrimp.example.com`.
3. Add a policy: **Allow** → include **Emails** → just your own email address.
4. Choose a login method (Email one-time PIN works with no extra setup).

Now visitors must verify your email before they ever reach the camera. Combined
with the app's `SHRIMPCAM_USER/PASS`, you have two independent locks.

### A note on Cloudflare's terms
Cloudflare's free plan discourages serving large amounts of video through their
proxy. A low-fps, low-quality MJPEG shrimp cam is very little bandwidth and fine
in practice — but if you later crank up resolution/fps, keep it reasonable.

### Alternative: Tailscale (private, no domain needed)
If you only want **yourself** (and people you invite) to watch — not a truly
public URL — [Tailscale](https://tailscale.com/) is even simpler: install it
(`curl -fsSL https://tailscale.com/install.sh | sh`), and reach the Pi at its
Tailscale IP from any of your devices. No domain, no ports, no Access policies.

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
| `status=217/USER` · `Failed at step USER spawning /usr/bin/python3` | The unit's `User=` doesn't exist on your Pi. Re-run `bash install-service.sh` (it uses your real username), or fix `User=`/paths by hand — see below |
| `status=200/CHDIR` | `WorkingDirectory=` points at a path that doesn't exist — set it to your actual repo location |
| `status=203/EXEC` | `/usr/bin/python3` or `app.py` path is wrong — check with `ls -l /usr/bin/python3` and the path in `ExecStart` |
| Service runs but camera fails, works when run by hand | The service user isn't in the `video` group: `sudo usermod -aG video $(whoami)` then reboot |
| Page loads but image is broken | Camera not detected — re-seat ribbon, run `rpicam-hello`, check logs |
| `Picamera2 unavailable ... using mock source` on the Pi | Install `sudo apt install -y python3-picamera2` and run with system `python3` (not a venv) |
| Can't reach `shrimpcam.local` | Use the IP from `hostname -I`; some networks block mDNS |
| Image is dark/blurry | Add light; clean the glass; let auto-exposure settle a few seconds |
| Stream freezes occasionally | Click **Reconnect** on the page; check WiFi signal to the Pi |
| `Cannot determine default configuration path. No file [config.yml config.yaml]` | The config isn't where the **root**-run service looks. Put it in `/etc/cloudflared/config.yml`, not `~/.cloudflared/` — or run `bash install-tunnel.sh` |
| cloudflared: `Tunnel credentials file not found` | Copy it where root can read it: `sudo cp ~/.cloudflared/<TUNNEL_ID>.json /etc/cloudflared/` |
| Public URL returns **502 Bad Gateway** | The tunnel is up but the app isn't. Check `systemctl status shrimpcam.service` and that the port matches `service: http://localhost:8080` |
| Public URL returns **1033 / no DNS** | Missing DNS route: `cloudflared tunnel route dns shrimpcam <your-hostname>` |
