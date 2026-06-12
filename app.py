"""Shrimp Cam — a tiny MJPEG streaming web app for the Raspberry Pi.

Run it:

    python app.py

Then open http://<your-pi-ip>:8080/ in a browser.

Endpoints:
    /              HTML page that embeds the live stream
    /stream.mjpg   multipart MJPEG stream (works in an <img> tag)
    /snapshot.jpg  single still frame
    /healthz       plain-text "ok" for uptime checks
"""

from __future__ import annotations

import os

from flask import Flask, Response, render_template

from camera import Camera

app = Flask(__name__)
camera = Camera()

# multipart/x-mixed-replace is the classic, browser-native way to push a stream
# of JPEGs into an <img>. No JavaScript or special player needed.
_BOUNDARY = "shrimpframe"


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/stream.mjpg")
def stream():
    def generate():
        for frame in camera.frames():
            yield (
                f"--{_BOUNDARY}\r\n"
                "Content-Type: image/jpeg\r\n"
                f"Content-Length: {len(frame)}\r\n\r\n"
            ).encode("ascii") + frame + b"\r\n"

    return Response(
        generate(),
        mimetype=f"multipart/x-mixed-replace; boundary={_BOUNDARY}",
    )


@app.route("/snapshot.jpg")
def snapshot():
    frame = camera.snapshot()
    if frame is None:
        return Response("camera not ready", status=503)
    return Response(frame, mimetype="image/jpeg")


@app.route("/healthz")
def healthz():
    return Response("ok", mimetype="text/plain")


if __name__ == "__main__":
    port = int(os.environ.get("PORT", "8080"))
    # threaded=True so the streaming endpoint doesn't block other requests.
    app.run(host="0.0.0.0", port=port, threaded=True)
