"""Katman efektleri. Her efekt (img, origin, params, r, lt) → (img, origin) döndürür.

`origin` = (ox, oy, bw, bh): katmanın mantıksal kutusunun görüntü içindeki konumu.
Efekt görüntüyü genişletirse (blur, glow, gölge) origin kaydırılır; böylece anchor sabit kalır.
"""
from __future__ import annotations

import functools
import math
import os

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps

from ..model import value_at
from ..util import parse_color, resolve_path

# parametre şemaları: arayüz ve dokümantasyon için
EFFECTS: dict[str, dict] = {
    "blur": {"label": "Bulanıklık", "params": {"radius": 8}},
    "glow": {"label": "Parlama", "params": {"radius": 20, "color": None, "strength": 1.0}},
    "shadow": {"label": "Gölge", "params": {"color": "#000000aa", "x": 8, "y": 12, "blur": 16}},
    "outline": {"label": "Dış çizgi", "params": {"color": "#000000", "width": 6}},
    "brightness": {"label": "Parlaklık", "params": {"amount": 0.1}},
    "contrast": {"label": "Kontrast", "params": {"amount": 0.2}},
    "saturation": {"label": "Doygunluk", "params": {"amount": 0.3}},
    "hue": {"label": "Ton kaydır", "params": {"degrees": 30}},
    "grayscale": {"label": "Siyah-beyaz", "params": {"amount": 1.0}},
    "sepia": {"label": "Sepya", "params": {"amount": 1.0}},
    "invert": {"label": "Ters çevir", "params": {"amount": 1.0}},
    "tint": {"label": "Renk tonu", "params": {"color": "#ff8800", "amount": 0.3}},
    "temperature": {"label": "Sıcaklık", "params": {"amount": 0.2}},
    "vignette": {"label": "Vinyet", "params": {"amount": 0.5, "radius": 0.75}},
    "noise": {"label": "Kumlanma", "params": {"amount": 0.08}},
    "pixelate": {"label": "Pikselleştir", "params": {"size": 16}},
    "posterize": {"label": "Posterize", "params": {"levels": 4}},
    "sharpen": {"label": "Keskinleştir", "params": {"amount": 1.0}},
    "rgb_split": {"label": "RGB kayması", "params": {"amount": 6, "angle": 0}},
    "chroma_key": {"label": "Yeşil perde", "params": {"color": "#00ff00", "threshold": 0.35,
                                                        "softness": 0.15}},
    "lut": {"label": "LUT (.cube)", "params": {"file": "", "amount": 1.0}},
    "sketch": {"label": "Karakalem", "params": {"amount": 1.0, "detail": 6}},
    "crop": {"label": "Kırp", "params": {"left": 0.0, "top": 0.0, "right": 0.0, "bottom": 0.0}},
    "rounded": {"label": "Yuvarlak köşe", "params": {"radius": 40}},
    "border": {"label": "Çerçeve", "params": {"color": "#ffffff", "width": 8}},
    "mirror": {"label": "Ayna", "params": {"axis": "x"}},
    "opacity_mask": {"label": "Kenar yumuşat", "params": {"feather": 60}},
}


# --------------------------------------------------------------------------- yardımcılar


def _pad(img: Image.Image, origin, p: int):
    p = int(math.ceil(max(0, p)))
    if p <= 0:
        return img, origin
    out = Image.new("RGBA", (img.width + 2 * p, img.height + 2 * p), (0, 0, 0, 0))
    out.paste(img, (p, p))
    ox, oy, bw, bh = origin
    return out, (ox + p, oy + p, bw, bh)


def _rgb_op(img: Image.Image, fn) -> Image.Image:
    a = np.asarray(img, dtype=np.float32)
    rgb = fn(a[..., :3])
    out = np.concatenate([np.clip(rgb, 0, 255), a[..., 3:4]], axis=2).astype(np.uint8)
    return Image.fromarray(out)


def _gray(rgb):
    return (rgb[..., 0:1] * 0.299 + rgb[..., 1:2] * 0.587 + rgb[..., 2:3] * 0.114)


def _colored_from_alpha(alpha: Image.Image, color) -> Image.Image:
    r, g, b, a = color
    layer = Image.new("RGBA", alpha.size, (r, g, b, 0))
    if a < 255:
        alpha = alpha.point(lambda v: v * a // 255)
    layer.putalpha(alpha)
    return layer


# --------------------------------------------------------------------------- efektler


def fx_blur(img, origin, p, r, lt):
    rad = float(p.get("radius", 8)) * r.scale
    if rad <= 0.3:
        return img, origin
    img, origin = _pad(img, origin, rad * 2)
    return img.filter(ImageFilter.GaussianBlur(rad)), origin


def fx_glow(img, origin, p, r, lt):
    rad = float(p.get("radius", 20)) * r.scale
    strength = float(p.get("strength", 1.0))
    if rad <= 0.3 or strength <= 0:
        return img, origin
    img, origin = _pad(img, origin, rad * 2.2)
    color = p.get("color")
    if color:
        glow = _colored_from_alpha(img.getchannel("A"), r.color(color))
    else:
        glow = img.copy()
    glow = glow.filter(ImageFilter.GaussianBlur(rad))
    if strength != 1.0:
        a = np.asarray(glow.getchannel("A"), np.float32) * strength
        glow.putalpha(Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)))
    base = Image.new("RGBA", img.size, (0, 0, 0, 0))
    base.alpha_composite(glow)
    if strength > 1.5:
        base.alpha_composite(glow)
    base.alpha_composite(img)
    return base, origin


def fx_shadow(img, origin, p, r, lt):
    s = r.scale
    dx, dy = float(p.get("x", 8)) * s, float(p.get("y", 12)) * s
    blur = float(p.get("blur", 16)) * s
    img, origin = _pad(img, origin, blur * 2 + max(abs(dx), abs(dy)))
    sh = _colored_from_alpha(img.getchannel("A"), r.color(p.get("color", "#000000aa")))
    if blur > 0.3:
        sh = sh.filter(ImageFilter.GaussianBlur(blur))
    base = Image.new("RGBA", img.size, (0, 0, 0, 0))
    base.alpha_composite(sh, (0, 0)) if (dx, dy) == (0, 0) else base.paste(
        sh, (int(round(dx)), int(round(dy))), sh)
    base.alpha_composite(img)
    return base, origin


def fx_outline(img, origin, p, r, lt):
    w = max(1, int(round(float(p.get("width", 6)) * r.scale)))
    img, origin = _pad(img, origin, w + 2)
    alpha = img.getchannel("A")
    grown = alpha
    remaining = w
    while remaining > 0:
        step = min(remaining, 5)
        grown = grown.filter(ImageFilter.MaxFilter(step * 2 + 1))
        remaining -= step
    out = _colored_from_alpha(grown, r.color(p.get("color", "#000000")))
    out.alpha_composite(img)
    return out, origin


def fx_brightness(img, origin, p, r, lt):
    a = float(p.get("amount", 0.1)) * 255
    return _rgb_op(img, lambda rgb: rgb + a), origin


def fx_contrast(img, origin, p, r, lt):
    k = 1 + float(p.get("amount", 0.2))
    return _rgb_op(img, lambda rgb: (rgb - 128) * k + 128), origin


def fx_saturation(img, origin, p, r, lt):
    k = 1 + float(p.get("amount", 0.3))
    return _rgb_op(img, lambda rgb: _gray(rgb) + (rgb - _gray(rgb)) * k), origin


def fx_hue(img, origin, p, r, lt):
    deg = float(p.get("degrees", 30)) % 360
    if deg == 0:
        return img, origin
    alpha = img.getchannel("A")
    hsv = np.array(img.convert("RGB").convert("HSV"))
    hsv[..., 0] = (hsv[..., 0].astype(np.int16) + int(deg / 360 * 255)) % 256
    out = Image.merge("HSV", [Image.fromarray(np.ascontiguousarray(hsv[..., i])) for i in range(3)]).convert("RGB").convert("RGBA")
    out.putalpha(alpha)
    return out, origin


def fx_grayscale(img, origin, p, r, lt):
    k = float(p.get("amount", 1.0))
    return _rgb_op(img, lambda rgb: rgb + (_gray(rgb) - rgb) * k), origin


def fx_sepia(img, origin, p, r, lt):
    k = float(p.get("amount", 1.0))
    m = np.array([[0.393, 0.769, 0.189], [0.349, 0.686, 0.168], [0.272, 0.534, 0.131]],
                 np.float32)
    return _rgb_op(img, lambda rgb: rgb + ((rgb @ m.T) - rgb) * k), origin


def fx_invert(img, origin, p, r, lt):
    k = float(p.get("amount", 1.0))
    return _rgb_op(img, lambda rgb: rgb + ((255 - rgb) - rgb) * k), origin


def fx_tint(img, origin, p, r, lt):
    c = np.array(r.color(p.get("color", "#ff8800"))[:3], np.float32)
    k = float(p.get("amount", 0.3))
    return _rgb_op(img, lambda rgb: rgb + (c * (_gray(rgb) / 255) * 1.2 - rgb) * k), origin


def fx_temperature(img, origin, p, r, lt):
    k = float(p.get("amount", 0.2)) * 40
    shift = np.array([k, k * 0.2, -k], np.float32)
    return _rgb_op(img, lambda rgb: rgb + shift), origin


@functools.lru_cache(maxsize=16)
def _vignette_mask(w, h, radius, amount):
    y, x = np.ogrid[-1:1:complex(0, h), -1:1:complex(0, w)]
    d = np.sqrt(x * x + y * y) / math.sqrt(2)
    m = 1 - np.clip((d - radius) / max(1e-3, 1 - radius), 0, 1) ** 1.5 * amount
    return m.astype(np.float32)[..., None]


def fx_vignette(img, origin, p, r, lt):
    m = _vignette_mask(img.width, img.height, float(p.get("radius", 0.75)),
                       float(p.get("amount", 0.5)))
    return _rgb_op(img, lambda rgb: rgb * m), origin


def fx_noise(img, origin, p, r, lt):
    amt = float(p.get("amount", 0.08)) * 255
    rng = np.random.default_rng(int(lt * 1000) & 0xFFFFFFFF)
    n = rng.normal(0, amt, (img.height, img.width, 1)).astype(np.float32)
    return _rgb_op(img, lambda rgb: rgb + n), origin


def fx_pixelate(img, origin, p, r, lt):
    size = max(1, int(float(p.get("size", 16)) * r.scale))
    if size <= 1:
        return img, origin
    small = img.resize((max(1, img.width // size), max(1, img.height // size)), Image.BILINEAR)
    return small.resize(img.size, Image.NEAREST), origin


def fx_posterize(img, origin, p, r, lt):
    lv = max(2, int(p.get("levels", 4)))
    step = 255 / (lv - 1)
    return _rgb_op(img, lambda rgb: np.round(rgb / step) * step), origin


def fx_sharpen(img, origin, p, r, lt):
    amt = float(p.get("amount", 1.0))
    return img.filter(ImageFilter.UnsharpMask(radius=2, percent=int(150 * amt), threshold=2)), origin


def fx_rgb_split(img, origin, p, r, lt):
    amt = float(p.get("amount", 6)) * r.scale
    ang = math.radians(float(p.get("angle", 0)))
    dx, dy = int(round(math.cos(ang) * amt)), int(round(math.sin(ang) * amt))
    if dx == 0 and dy == 0:
        return img, origin
    img, origin = _pad(img, origin, max(abs(dx), abs(dy)))
    rr, g, b, a = img.split()
    rr = ImageChops.offset(rr, -dx, -dy)
    b = ImageChops.offset(b, dx, dy)
    a2 = ImageChops.lighter(a, ImageChops.lighter(ImageChops.offset(a, -dx, -dy),
                                                  ImageChops.offset(a, dx, dy)))
    return Image.merge("RGBA", (rr, g, b, a2)), origin


def fx_chroma_key(img, origin, p, r, lt):
    key = np.array(r.color(p.get("color", "#00ff00"))[:3], np.float32) / 255
    thr = float(p.get("threshold", 0.35))
    soft = max(1e-3, float(p.get("softness", 0.15)))
    a = np.asarray(img, np.float32)
    rgb = a[..., :3] / 255
    dist = np.sqrt(((rgb - key) ** 2).sum(axis=2)) / math.sqrt(3)
    k = np.clip((dist - thr) / soft, 0, 1)
    # yeşil taşmasını azalt (spill)
    g = rgb[..., 1]
    spill = np.maximum(0, g - np.maximum(rgb[..., 0], rgb[..., 2]))
    if key[1] > key[0] and key[1] > key[2]:
        a[..., 1] -= spill * 255 * (1 - k) * 0.9
    a[..., 3] *= k
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8)), origin


@functools.lru_cache(maxsize=8)
def _load_cube(path: str, mtime: float):
    size = None
    rows = []
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            if line.upper().startswith("LUT_3D_SIZE"):
                size = int(line.split()[-1])
                continue
            parts = line.split()
            if len(parts) == 3:
                try:
                    rows.append([float(x) for x in parts])
                except ValueError:
                    continue
    if not size or len(rows) < size ** 3:
        raise ValueError("Geçersiz .cube dosyası")
    # .cube: R en hızlı değişir → [b][g][r]
    return np.array(rows[: size ** 3], np.float32).reshape(size, size, size, 3), size


def fx_lut(img, origin, p, r, lt):
    path = resolve_path(p.get("file"), r.base_dir)
    if not path or not os.path.exists(path):
        return img, origin
    lut, n = _load_cube(path, os.path.getmtime(path))
    amt = float(p.get("amount", 1.0))

    def apply(rgb):
        idx = np.clip(np.round(rgb / 255 * (n - 1)).astype(np.int32), 0, n - 1)
        mapped = lut[idx[..., 2], idx[..., 1], idx[..., 0]] * 255
        return rgb + (mapped - rgb) * amt

    return _rgb_op(img, apply), origin


def fx_sketch(img, origin, p, r, lt):
    amt = float(p.get("amount", 1.0))
    detail = max(1.0, float(p.get("detail", 6)) * r.scale)
    alpha = img.getchannel("A")
    gray = img.convert("L")
    inv = ImageOps.invert(gray).filter(ImageFilter.GaussianBlur(detail))
    g = np.asarray(gray, np.float32)
    b = np.asarray(inv, np.float32)
    dodge = np.clip(g * 255 / np.maximum(1, 255 - b), 0, 255)
    dodge = 255 - (255 - dodge) * 1.4  # çizgileri koyulaştır
    rgb = np.asarray(img, np.float32)[..., :3]
    sk = np.repeat(np.clip(dodge, 0, 255)[..., None], 3, axis=2)
    out = rgb + (sk - rgb) * amt
    res = Image.fromarray(np.clip(out, 0, 255).astype(np.uint8)).convert("RGBA")
    res.putalpha(alpha)
    return res, origin


def fx_crop(img, origin, p, r, lt):
    ox, oy, bw, bh = origin
    l_, t_ = float(p.get("left", 0)), float(p.get("top", 0))
    r_, b_ = float(p.get("right", 0)), float(p.get("bottom", 0))
    x0, y0 = int(ox + bw * l_), int(oy + bh * t_)
    x1, y1 = int(ox + bw * (1 - r_)), int(oy + bh * (1 - b_))
    mask = Image.new("L", img.size, 0)
    if x1 > x0 and y1 > y0:
        ImageDraw.Draw(mask).rectangle([x0, y0, x1 - 1, y1 - 1], fill=255)
    out = img.copy()
    out.putalpha(ImageChops.multiply(img.getchannel("A"), mask))
    return out, origin


def fx_rounded(img, origin, p, r, lt):
    ox, oy, bw, bh = origin
    rad = float(p.get("radius", 40)) * r.scale
    ss = 3
    mask = Image.new("L", (img.width * ss, img.height * ss), 0)
    ImageDraw.Draw(mask).rounded_rectangle(
        [ox * ss, oy * ss, (ox + bw) * ss - 1, (oy + bh) * ss - 1], radius=rad * ss, fill=255)
    mask = mask.resize(img.size, Image.LANCZOS)
    out = img.copy()
    out.putalpha(ImageChops.multiply(img.getchannel("A"), mask))
    return out, origin


def fx_border(img, origin, p, r, lt):
    w = float(p.get("width", 8)) * r.scale
    img, origin = _pad(img, origin, w + 1)
    ox, oy, bw, bh = origin
    out = img.copy()
    rad = 0.0
    for e in r._current_effects:
        if e.get("type") == "rounded":
            rad = float(e.get("params", {}).get("radius", 40)) * r.scale
    ImageDraw.Draw(out).rounded_rectangle(
        [ox - w / 2, oy - w / 2, ox + bw + w / 2, oy + bh + w / 2], radius=rad + w / 2,
        outline=r.color(p.get("color", "#ffffff")), width=max(1, int(round(w))))
    return out, origin


def fx_mirror(img, origin, p, r, lt):
    ax = p.get("axis", "x")
    return (img.transpose(Image.FLIP_LEFT_RIGHT) if ax == "x"
            else img.transpose(Image.FLIP_TOP_BOTTOM)), origin


def fx_opacity_mask(img, origin, p, r, lt):
    f = max(1.0, float(p.get("feather", 60)) * r.scale)
    w, h = img.size
    x = np.minimum(np.arange(w), np.arange(w)[::-1]) / f
    y = np.minimum(np.arange(h), np.arange(h)[::-1]) / f
    m = np.clip(np.minimum(y[:, None], x[None, :]), 0, 1)
    a = np.asarray(img.getchannel("A"), np.float32) * m
    out = img.copy()
    out.putalpha(Image.fromarray(a.astype(np.uint8)))
    return out, origin


FUNCS = {name[3:]: fn for name, fn in globals().items() if name.startswith("fx_")}


def apply_effects(img: Image.Image, origin, effects: list, r, lt: float):
    """Katmanın efekt listesini sırayla uygular."""
    r._current_effects = effects or []
    for eff in effects or []:
        if not eff.get("enabled", True):
            continue
        fn = FUNCS.get(eff.get("type"))
        if fn is None:
            continue
        defaults = EFFECTS.get(eff["type"], {}).get("params", {})
        raw = {**defaults, **(eff.get("params") or {})}
        params = {k: value_at(v, lt) for k, v in raw.items()}
        try:
            img, origin = fn(img, origin, params, r, lt)
        except Exception as e:  # noqa: BLE001 — tek efekt hatası tüm kareyi bozmasın
            r.warn(f"Efekt '{eff.get('type')}' hatası: {e}")
    return img, origin


def effects_animated(effects: list) -> bool:
    for eff in effects or []:
        if eff.get("type") == "noise":
            return True
        for v in (eff.get("params") or {}).values():
            if isinstance(v, dict) and ("keyframes" in v or "expr" in v):
                return True
    return False
