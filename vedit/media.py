"""Medya erişimi: FFmpeg ile video okuma, görsel cache'i, bilgi, küçük resim, dalga formu."""
from __future__ import annotations

import functools
import os
import re
import subprocess
import threading
from pathlib import Path

import numpy as np
from PIL import Image

from .util import NO_WINDOW, ffmpeg_exe

VIDEO_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".gif", ".wmv", ".flv", ".mpg", ".mpeg"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp", ".bmp", ".tif", ".tiff"}
AUDIO_EXT = {".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac", ".opus", ".wma"}


def media_kind(path: str) -> str | None:
    ext = Path(path).suffix.lower()
    if ext in VIDEO_EXT:
        return "video"
    if ext in IMAGE_EXT:
        return "image"
    if ext in AUDIO_EXT:
        return "audio"
    if ext == ".py":
        return "script"
    if path.endswith(".vedit.json"):
        return "project"
    return None


# --------------------------------------------------------------------------- probe

_probe_lock = threading.Lock()
_probe_cache: dict[tuple[str, float], dict] = {}


def probe(path: str) -> dict:
    """{'duration', 'width', 'height', 'fps', 'has_video', 'has_audio'}"""
    path = str(path)
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        raise FileNotFoundError(path) from None
    key = (path, mtime)
    with _probe_lock:
        if key in _probe_cache:
            return _probe_cache[key]
    proc = subprocess.run([ffmpeg_exe(), "-hide_banner", "-i", path], capture_output=True,
                          creationflags=NO_WINDOW)
    txt = proc.stderr.decode("utf-8", "replace")
    info = {"duration": 0.0, "width": 0, "height": 0, "fps": 30.0, "has_video": False,
            "has_audio": False}
    m = re.search(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)", txt)
    if m:
        h, mi, s = m.groups()
        info["duration"] = int(h) * 3600 + int(mi) * 60 + float(s)
    for line in txt.splitlines():
        if "Stream #" in line and "Video:" in line and "attached pic" not in line \
                and not info["has_video"]:
            info["has_video"] = True
            ms = re.search(r",\s*(\d{2,5})x(\d{2,5})", line)
            if ms:
                info["width"], info["height"] = int(ms.group(1)), int(ms.group(2))
            mf = re.search(r"([\d.]+)\s*fps", line) or re.search(r"([\d.]+)\s*tbr", line)
            if mf:
                info["fps"] = float(mf.group(1)) or 30.0
            if re.search(r"rotate\s*:\s*-?90", txt) or "displaymatrix: rotation of -90" in txt \
                    or "rotation of 90" in txt:
                info["width"], info["height"] = info["height"], info["width"]
        if "Stream #" in line and "Audio:" in line:
            info["has_audio"] = True
    if media_kind(path) == "image":
        with Image.open(path) as im:
            info["width"], info["height"] = im.size
            info["has_video"] = True
            info["duration"] = 0.0
    with _probe_lock:
        _probe_cache[key] = info
    return info


# --------------------------------------------------------------------------- video okuyucu


class VideoReader:
    """Bir videodan rastgele zamanlı kare okur. Ardışık okumada süreç yeniden başlatılmaz."""

    def __init__(self, path: str, size: tuple[int, int] | None = None):
        self.path = path
        self.info = probe(path)
        self.fps = self.info["fps"] or 30.0
        w, h = size or (self.info["width"], self.info["height"])
        self.w, self.h = max(2, int(w) // 2 * 2), max(2, int(h) // 2 * 2)
        self.frame_bytes = self.w * self.h * 3
        self.n_frames = max(1, int(self.info["duration"] * self.fps))
        self.proc: subprocess.Popen | None = None
        self.next_idx = -1
        self.last_idx = -2
        self.last: np.ndarray | None = None
        self.lock = threading.Lock()

    def _start(self, idx: int):
        self.close()
        t = idx / self.fps
        cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error"]
        if t > 0:
            cmd += ["-ss", f"{t:.4f}"]
        cmd += ["-i", self.path, "-an", "-sn",
                "-vf", f"fps={self.fps},scale={self.w}:{self.h}:flags=bilinear",
                "-f", "rawvideo", "-pix_fmt", "rgb24", "-"]
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                                     stdin=subprocess.DEVNULL, bufsize=self.frame_bytes * 2,
                                     creationflags=NO_WINDOW)
        self.next_idx = idx

    def _read_one(self) -> np.ndarray | None:
        assert self.proc and self.proc.stdout
        buf = self.proc.stdout.read(self.frame_bytes)
        if not buf or len(buf) < self.frame_bytes:
            return None
        self.next_idx += 1
        return np.frombuffer(buf, np.uint8).reshape(self.h, self.w, 3)

    def get_frame(self, t: float) -> np.ndarray:
        with self.lock:
            idx = int(t * self.fps + 1e-6)
            idx = max(0, min(idx, self.n_frames - 1))
            if idx == self.last_idx and self.last is not None:
                return self.last
            if self.proc is None or not (self.next_idx <= idx <= self.next_idx + int(self.fps * 2)):
                self._start(idx)
            frame = None
            while self.next_idx <= idx:
                f = self._read_one()
                if f is None:
                    break
                frame = f
            if frame is None:
                if self.last is not None:
                    return self.last
                # okuma tamamen başarısız → siyah kare
                return np.zeros((self.h, self.w, 3), np.uint8)
            self.last, self.last_idx = frame, idx
            return frame

    def close(self):
        if self.proc:
            try:
                self.proc.stdout.close()  # type: ignore[union-attr]
                self.proc.kill()
                self.proc.wait(timeout=2)
            except Exception:  # noqa: BLE001
                pass
            self.proc = None


# --------------------------------------------------------------------------- görseller


@functools.lru_cache(maxsize=64)
def _load_image(path: str, mtime: float) -> Image.Image:
    im = Image.open(path)
    im.load()
    return im.convert("RGBA")


def load_image(path: str) -> Image.Image:
    return _load_image(path, os.path.getmtime(path))


# --------------------------------------------------------------------------- küçük resim / dalga formu


def thumbnail_jpeg(path: str, t: float = 0.0, width: int = 160) -> bytes:
    kind = media_kind(path)
    if kind == "image":
        import io

        im = load_image(path).copy()
        im.thumbnail((width, width * 4))
        bg = Image.new("RGB", im.size, (30, 30, 36))
        bg.paste(im, mask=im.split()[3])
        out = io.BytesIO()
        bg.save(out, "JPEG", quality=80)
        return out.getvalue()
    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error"]
    if t > 0:
        cmd += ["-ss", f"{t:.3f}"]
    cmd += ["-i", path, "-frames:v", "1", "-vf", f"scale={width}:-2", "-f", "image2pipe",
            "-vcodec", "mjpeg", "-q:v", "5", "-"]
    proc = subprocess.run(cmd, capture_output=True, creationflags=NO_WINDOW)
    return proc.stdout


@functools.lru_cache(maxsize=64)
def _waveform(path: str, mtime: float, buckets: int) -> list[float]:
    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-i", path, "-vn", "-ac", "1",
           "-ar", "4000", "-f", "s16le", "-"]
    proc = subprocess.run(cmd, capture_output=True, creationflags=NO_WINDOW)
    data = np.frombuffer(proc.stdout, np.int16).astype(np.float32) / 32768.0
    if data.size == 0:
        return []
    n = min(buckets, data.size)
    chunks = np.array_split(np.abs(data), n)
    peaks = np.array([c.max() if c.size else 0 for c in chunks])
    m = peaks.max() or 1.0
    return [round(float(p / m), 3) for p in peaks]


def waveform(path: str, buckets: int = 800) -> list[float]:
    """Saniye başına sabit sayıda değil, toplam `buckets` adet tepe değeri (0..1)."""
    return _waveform(path, os.path.getmtime(path), buckets)
