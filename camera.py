"""Camera frame source for Shrimp Cam.

On a Raspberry Pi this uses Picamera2 (the modern libcamera-based stack that
ships with recent Raspberry Pi OS). On any other machine — or if Picamera2
isn't installed — it falls back to a synthetic test pattern so you can run and
develop the web app on a laptop before deploying to the Pi.

The public API is intentionally tiny:

    cam = Camera()
    for jpeg_bytes in cam.frames():
        ...   # each item is a complete JPEG image
"""

from __future__ import annotations

import io
import threading
import time
from datetime import datetime

# Resolution and frame rate are kept modest on purpose: the original Pi Zero is
# a single-core ARMv6 chip, and a shrimp in a jar does not need 1080p60.
WIDTH = 640
HEIGHT = 480
FPS = 10
JPEG_QUALITY = 75


class _PicameraSource:
    """Real camera backed by Picamera2."""

    def __init__(self) -> None:
        from picamera2 import Picamera2  # imported lazily so the mock can run anywhere

        self._picam2 = Picamera2()
        config = self._picam2.create_video_configuration(
            main={"size": (WIDTH, HEIGHT), "format": "RGB888"}
        )
        self._picam2.configure(config)
        self._picam2.start()
        # Give the sensor a moment to settle (auto exposure / white balance).
        time.sleep(2)

    def capture_jpeg(self) -> bytes:
        from PIL import Image

        array = self._picam2.capture_array()
        image = Image.fromarray(array)
        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=JPEG_QUALITY)
        return buf.getvalue()

    def close(self) -> None:
        try:
            self._picam2.stop()
            self._picam2.close()
        except Exception:
            pass


class _MockSource:
    """Synthetic camera so the app runs without Pi hardware.

    Draws a moving marker and a live timestamp so you can confirm the stream is
    actually updating in the browser.
    """

    def __init__(self) -> None:
        self._start = time.time()

    def capture_jpeg(self) -> bytes:
        from PIL import Image, ImageDraw

        image = Image.new("RGB", (WIDTH, HEIGHT), (20, 40, 60))
        draw = ImageDraw.Draw(image)

        # A little "shrimp" that drifts across the frame.
        t = time.time() - self._start
        x = int((WIDTH - 40) * (0.5 + 0.5 * _triangle(t / 6)))
        y = int(HEIGHT * 0.5 + 60 * _triangle(t / 4 + 0.25))
        draw.ellipse([x, y, x + 36, y + 18], fill=(255, 140, 120))

        stamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        draw.text((10, 10), f"MOCK CAMERA  {stamp}", fill=(255, 255, 255))

        buf = io.BytesIO()
        image.save(buf, format="JPEG", quality=JPEG_QUALITY)
        return buf.getvalue()

    def close(self) -> None:
        pass


def _triangle(x: float) -> float:
    """A smooth-ish triangle wave in [-1, 1] for the mock animation."""
    x = x % 1.0
    return 4 * abs(x - 0.5) - 1


class Camera:
    """Thread-safe single-camera reader shared by all HTTP clients.

    The camera is read once in a background loop and the latest JPEG frame is
    handed out to every connected viewer. This means 1 or 50 browser tabs put
    the same (small) load on the Pi.
    """

    def __init__(self) -> None:
        self._source = self._make_source()
        self._latest: bytes | None = None
        self._lock = threading.Condition()
        self._running = True
        self._thread = threading.Thread(target=self._loop, daemon=True)
        self._thread.start()

    @staticmethod
    def _make_source():
        try:
            return _PicameraSource()
        except Exception as exc:  # noqa: BLE001 - any failure means "no real camera"
            print(f"[camera] Picamera2 unavailable ({exc!r}); using mock source.")
            return _MockSource()

    def _loop(self) -> None:
        period = 1.0 / FPS
        while self._running:
            start = time.time()
            try:
                frame = self._source.capture_jpeg()
            except Exception as exc:  # noqa: BLE001
                print(f"[camera] capture failed: {exc!r}")
                time.sleep(0.5)
                continue
            with self._lock:
                self._latest = frame
                self._lock.notify_all()
            elapsed = time.time() - start
            if elapsed < period:
                time.sleep(period - elapsed)

    def frames(self):
        """Yield the latest JPEG frame as it becomes available."""
        last_id = None
        while True:
            with self._lock:
                # Wait until a new frame is ready.
                self._lock.wait_for(lambda: self._latest is not None and id(self._latest) != last_id)
                frame = self._latest
                last_id = id(frame)
            yield frame

    def snapshot(self) -> bytes | None:
        with self._lock:
            return self._latest

    def close(self) -> None:
        self._running = False
        self._thread.join(timeout=2)
        self._source.close()
