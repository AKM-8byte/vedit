"""Script katmanı örneği: yükselen parlak parçacıklar.

PARAMS arayüzde kaydırıcı/renk seçici olarak görünür ve keyframe'lenebilir.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

PARAMS = {
    "renk": {"type": "color", "default": "#ffd60a", "label": "Renk"},
    "adet": {"type": "int", "default": 120, "min": 10, "max": 600, "label": "Parçacık sayısı"},
    "hiz": {"type": "float", "default": 1.0, "min": 0.1, "max": 5, "label": "Hız"},
    "boyut": {"type": "float", "default": 6, "min": 1, "max": 30, "label": "Boyut"},
    "parlama": {"type": "bool", "default": True, "label": "Parlama"},
}


def _rgb(hex_):
    h = hex_.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4))


def make_frame(t, params, w, h):
    rng = np.random.default_rng(7)
    n = int(params["adet"])
    xs = rng.uniform(0, w, n)
    ys0 = rng.uniform(0, h, n)
    speeds = rng.uniform(0.3, 1.0, n) * h * 0.15 * params["hiz"]
    sizes = rng.uniform(0.4, 1.0, n) * params["boyut"]
    phase = rng.uniform(0, 6.28, n)
    ys = (ys0 - speeds * t) % h
    xs = xs + np.sin(t * 1.5 + phase) * 20
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    r, g, b = _rgb(params["renk"])
    for x, y, s, p in zip(xs, ys, sizes, phase):
        a = int(160 + 95 * np.sin(t * 3 + p))
        d.ellipse([x - s, y - s, x + s, y + s], fill=(r, g, b, max(0, a)))
    if params["parlama"]:
        glow = img.filter(ImageFilter.GaussianBlur(params["boyut"] * 1.5))
        glow.alpha_composite(img)
        img = glow
    return img
