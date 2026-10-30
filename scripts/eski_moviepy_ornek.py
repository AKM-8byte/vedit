"""Eski tarz MoviePy kodunu Script katmanına sarma örneği.

Var olan bir MoviePy scriptini `make_clip(params)` fonksiyonuna taşı ve klibi döndür.
VEdit klibin karelerini (ve varsa maskesini) timeline'da kullanır; ses kullanılmaz
(ses için ayrı bir Ses katmanı ekle).
"""
import numpy as np
from moviepy import ColorClip, CompositeVideoClip, VideoClip

PARAMS = {
    "renk1": {"type": "color", "default": "#ff375f"},
    "renk2": {"type": "color", "default": "#0a84ff"},
    "sure": {"type": "float", "default": 5.0, "min": 1, "max": 30},
}


def _rgb(hex_):
    h = hex_.lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], np.float32)


def make_clip(params):
    w, h = 1080, 1920
    c1, c2 = _rgb(params["renk1"]), _rgb(params["renk2"])
    yy = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]

    def frame(t):
        u = (np.sin(t * 1.2) + 1) / 2
        top = c1 * (1 - u) + c2 * u
        bottom = c2 * (1 - u) + c1 * u
        img = top * (1 - yy) + bottom * yy
        return np.broadcast_to(img, (h, w, 3)).astype(np.uint8)

    bg = VideoClip(frame, duration=params["sure"])
    bar = ColorClip((w, 40), color=(255, 255, 255)).with_duration(params["sure"]).with_position(
        lambda t: ("center", 200 + 1400 * ((t * 0.3) % 1)))
    return CompositeVideoClip([bg, bar], size=(w, h))
