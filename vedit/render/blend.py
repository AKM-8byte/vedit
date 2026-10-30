"""Blend modları ile birleştirme."""
from __future__ import annotations

import numpy as np
from PIL import Image

BLEND_MODES = ("normal", "add", "multiply", "screen", "overlay", "lighten", "darken",
               "difference", "soft_light")


def _blend_fn(mode: str):
    if mode == "add":
        return lambda b, s: np.minimum(1, b + s)
    if mode == "multiply":
        return lambda b, s: b * s
    if mode == "screen":
        return lambda b, s: 1 - (1 - b) * (1 - s)
    if mode == "overlay":
        return lambda b, s: np.where(b < 0.5, 2 * b * s, 1 - 2 * (1 - b) * (1 - s))
    if mode == "lighten":
        return np.maximum
    if mode == "darken":
        return np.minimum
    if mode == "difference":
        return lambda b, s: np.abs(b - s)
    if mode == "soft_light":
        return lambda b, s: (1 - 2 * s) * b * b + 2 * s * b
    return None


def composite(canvas: Image.Image, img: Image.Image, x: int, y: int, mode: str = "normal") -> None:
    """`img`'yi `canvas` üzerine (x, y) noktasına çizer. Taşan kısımlar kırpılır."""
    cw, ch = canvas.size
    x0, y0 = max(0, x), max(0, y)
    x1, y1 = min(cw, x + img.width), min(ch, y + img.height)
    if x1 <= x0 or y1 <= y0:
        return
    src = img
    if (x0, y0, x1, y1) != (x, y, x + img.width, y + img.height):
        src = img.crop((x0 - x, y0 - y, x1 - x, y1 - y))
    fn = _blend_fn(mode)
    if fn is None:
        canvas.alpha_composite(src, (x0, y0))
        return
    region = canvas.crop((x0, y0, x1, y1))
    b = np.asarray(region, np.float32) / 255
    s = np.asarray(src, np.float32) / 255
    sa = s[..., 3:4]
    ba = b[..., 3:4]
    mixed = fn(b[..., :3], s[..., :3])
    # tuval şeffafsa blend sonucu yerine kaynağın kendisi görünür
    mixed = mixed * ba + s[..., :3] * (1 - ba)
    rgb = b[..., :3] * (1 - sa) + mixed * sa
    a = ba + sa * (1 - ba)
    out = np.concatenate([rgb, a], axis=2)
    canvas.paste(Image.fromarray(np.clip(out * 255 + 0.5, 0, 255).astype(np.uint8)),
                 (x0, y0))
