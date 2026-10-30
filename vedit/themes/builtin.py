"""Yerleşik temalar: matrix, cizim, neon, retro, sinematik, minimal, glitch."""
from __future__ import annotations

import functools
import math
import random

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

from ..util import find_font_file, load_font, parse_color, stable_hash
from . import register
from .base import Theme


# ---------------------------------------------------------------------- ortak yardımcılar


def _arr(img: Image.Image) -> np.ndarray:
    return np.asarray(img, dtype=np.float32)


def _img(a: np.ndarray) -> Image.Image:
    return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


def bloom(frame: Image.Image, strength: float, radius: float, threshold: float = 0.55) -> Image.Image:
    """Parlak bölgeleri yayarak parlama. Hız için 1/4 çözünürlükte bulanıklaştırır."""
    if strength <= 0:
        return frame
    w, h = frame.size
    small = frame.convert("RGB").resize((max(1, w // 4), max(1, h // 4)), Image.BILINEAR)
    a = np.asarray(small, np.float32) / 255
    lum = a.max(axis=2, keepdims=True)
    a = a * np.clip((lum - threshold) / (1 - threshold), 0, 1)
    glow = Image.fromarray((a * 255).astype(np.uint8)).filter(
        ImageFilter.GaussianBlur(max(1.0, radius / 4)))
    glow = glow.resize((w, h), Image.BILINEAR)
    f = _arr(frame)
    g = np.asarray(glow, np.float32) * strength
    f[..., :3] = 255 - (255 - f[..., :3]) * (255 - np.minimum(g, 255)) / 255  # screen
    return _img(f)


@functools.lru_cache(maxsize=8)
def _noise_tex(w: int, h: int, seed: int, scale: float) -> np.ndarray:
    rng = np.random.default_rng(seed)
    small = rng.normal(0, 1, (max(1, int(h / scale)), max(1, int(w / scale)))).astype(np.float32)
    img = Image.fromarray(((small * 0.5 + 0.5).clip(0, 1) * 255).astype(np.uint8))
    img = img.resize((w, h), Image.BICUBIC)
    return (np.asarray(img, np.float32) / 255 - 0.5)


@functools.lru_cache(maxsize=8)
def _vignette(w: int, h: int, amount: float, radius: float = 0.7) -> np.ndarray:
    y, x = np.ogrid[-1:1:complex(0, h), -1:1:complex(0, w)]
    d = np.sqrt(x * x + y * y) / math.sqrt(2)
    return (1 - np.clip((d - radius) / max(1e-3, 1 - radius), 0, 1) ** 1.6 * amount).astype(
        np.float32)[..., None]


def _grain(w, h, t, amount, fps=30):
    rng = np.random.default_rng(int(t * fps) * 7919 + 13)
    return rng.normal(0, amount * 255, (h, w, 1)).astype(np.float32)


def _scanlines(f: np.ndarray, period: int, depth: float) -> np.ndarray:
    period = max(2, period)
    mask = np.ones((f.shape[0], 1, 1), np.float32)
    mask[::period] = 1 - depth
    f[..., :3] *= mask
    return f


def _hex(c):
    return parse_color(c)


# ---------------------------------------------------------------------- MATRIX


GLYPHS = "ｱｲｳｴｵｶｷｸｹｺｻｼｽｾｿﾀﾁﾂﾃﾄﾅﾆﾇﾈﾉﾊﾋﾌﾍﾎﾏﾐﾑﾒﾓﾔﾕﾖﾗﾘﾙﾚﾛﾜﾝ0123456789Z:=*+-<>¦"


@functools.lru_cache(maxsize=8)
def _glyph_atlas(cell: int) -> np.ndarray:
    path = find_font_file("msgothic.ttc") or find_font_file("consolas")
    font = load_font(path, int(cell * 0.9))
    out = []
    for ch in GLYPHS:
        im = Image.new("L", (cell, cell), 0)
        d = ImageDraw.Draw(im)
        d.text((cell / 2, cell / 2), ch, fill=255, font=font, anchor="mm")
        if not im.getbbox():  # font karakteri desteklemiyorsa rakam kullan
            d.text((cell / 2, cell / 2), random.Random(len(out)).choice("0123456789"), fill=255,
                   font=load_font("consolas", int(cell * 0.9)), anchor="mm")
        out.append(np.asarray(im.transpose(Image.FLIP_LEFT_RIGHT), np.float32) / 255)
    return np.stack(out)


@register
class Matrix(Theme):
    name = "matrix"
    label = "Matrix"
    description = "Yağan yeşil karakterler, şifre çözme yazıları, yeşil tonlu görüntüler, parlama."
    PARAMS = {
        "color": {"type": "color", "default": "#00ff66", "label": "Renk"},
        "density": {"type": "float", "default": 0.75, "min": 0.1, "max": 1, "label": "Yoğunluk"},
        "speed": {"type": "float", "default": 1.0, "min": 0.1, "max": 4, "label": "Hız"},
        "glyph_size": {"type": "int", "default": 30, "min": 12, "max": 80, "label": "Karakter boyu"},
        "trail": {"type": "int", "default": 18, "min": 4, "max": 60, "label": "İz uzunluğu"},
        "rain_opacity": {"type": "float", "default": 0.85, "min": 0, "max": 1, "label": "Yağmur opaklığı"},
        "glow": {"type": "float", "default": 0.6, "min": 0, "max": 2, "label": "Parlama"},
        "scanlines": {"type": "bool", "default": True, "label": "Tarama çizgileri"},
        "tint_media": {"type": "float", "default": 0.85, "min": 0, "max": 1, "label": "Videoları yeşile boya"},
    }
    text_defaults = {"font": "consolas", "color": "#a8ffbf", "shadow_color": "#00ff66aa",
                     "shadow_blur": 14}
    char_anim = {"type": "decode", "unit": "char", "stagger": 0.045, "duration": 0.5}
    transition = {"type": "glitch", "duration": 0.35}
    palette = {"background": "#000000", "accent": "#00ff66", "text": "#a8ffbf"}
    preview_bg = "#000000"

    def setup(self):
        self.palette = {**self.palette, "accent": self.p["color"]}

    def background(self, r, t, w, h):
        cell = max(6, int(self.p["glyph_size"] * r.scale))
        atlas = _glyph_atlas(cell)
        cols, rows = w // cell + 1, h // cell + 1
        trail = int(self.p["trail"])
        rng = np.random.default_rng(1234)
        speed = rng.uniform(6, 16, cols) * self.p["speed"]
        offset = rng.uniform(0, rows + trail, cols)
        active = rng.random(cols) < self.p["density"]
        head = (offset + speed * t) % (rows + trail * 1.5)
        rr = np.arange(rows)[:, None]
        dist = head[None, :] - rr
        bright = np.where((dist >= 0) & (dist < trail), 1 - dist / trail, 0.0) * active[None, :]
        # ikinci (daha sönük) damla
        head2 = (offset * 1.7 + speed * 0.6 * t + rows / 2) % (rows + trail * 1.5)
        dist2 = head2[None, :] - rr
        bright = np.maximum(bright, np.where((dist2 >= 0) & (dist2 < trail * 0.6),
                                             (1 - dist2 / (trail * 0.6)) * 0.5, 0) * active[None, :])
        tick = np.floor(t * 8 + rng.uniform(0, 8, (rows, cols)))
        idx = ((np.arange(rows)[:, None] * 73 + np.arange(cols)[None, :] * 151 + tick * 17)
               .astype(np.int64)) % len(atlas)
        tiles = atlas[idx] * bright[..., None, None]  # (rows, cols, cell, cell)
        inten = tiles.transpose(0, 2, 1, 3).reshape(rows * cell, cols * cell)[:h, :w]
        headm = (np.abs(dist) < 1).astype(np.float32) * active[None, :]
        headt = (atlas[idx] * headm[..., None, None]).transpose(0, 2, 1, 3).reshape(
            rows * cell, cols * cell)[:h, :w]
        c = np.array(_hex(self.p["color"])[:3], np.float32)
        op = float(self.p["rain_opacity"])
        rgb = inten[..., None] * c * op + headt[..., None] * (255 - c) * 0.8 * op
        out = np.zeros((h, w, 4), np.float32)
        out[..., :3] = rgb
        out[..., 3] = 255
        return _img(out)

    def media_filter(self, r, layer, img, lt):
        k = float(self.p["tint_media"])
        if k <= 0:
            return img
        a = _arr(img)
        lum = a[..., 0:1] * 0.3 + a[..., 1:2] * 0.59 + a[..., 2:3] * 0.11
        c = np.array(_hex(self.p["color"])[:3], np.float32) / 255
        green = lum * (0.25 + 0.95 * c)
        a[..., :3] = a[..., :3] * (1 - k) + green * k
        return _img(a)

    def post(self, r, frame, t):
        frame = bloom(frame, float(self.p["glow"]), 24 * r.scale, 0.5)
        if self.p["scanlines"]:
            f = _scanlines(_arr(frame), max(2, int(4 * r.scale)), 0.18)
            frame = _img(f)
        return frame


# ---------------------------------------------------------------------- ÇİZİM


@functools.lru_cache(maxsize=8)
def _paper(w, h, scale, kind, color, line_color):
    base = np.zeros((h, w, 4), np.float32)
    base[..., :3] = np.array(_hex(color)[:3], np.float32)
    base[..., 3] = 255
    fib = _noise_tex(w, h, 3, max(1.0, 2 * scale))[..., None] * 18
    blot = _noise_tex(w, h, 9, max(2.0, 120 * scale))[..., None] * 12
    base[..., :3] += fib + blot
    img = _img(base)
    d = ImageDraw.Draw(img)
    lc = _hex(line_color)
    step = max(8, int(64 * scale))
    lw = max(1, int(2 * scale))
    if kind == "lined":
        for y in range(int(step * 2.5), h, step):
            d.line([(0, y), (w, y)], fill=lc[:3] + (110,), width=lw)
        x = int(w * 0.12)
        d.line([(x, 0), (x, h)], fill=(220, 70, 70, 140), width=lw)
    elif kind == "grid":
        for y in range(0, h, step):
            d.line([(0, y), (w, y)], fill=lc[:3] + (70,), width=lw)
        for x in range(0, w, step):
            d.line([(x, 0), (x, h)], fill=lc[:3] + (70,), width=lw)
    elif kind == "dots":
        rad = max(1, int(2.5 * scale))
        for y in range(step // 2, h, step):
            for x in range(step // 2, w, step):
                d.ellipse([x - rad, y - rad, x + rad, y + rad], fill=lc[:3] + (110,))
    return img


@register
class Cizim(Theme):
    name = "cizim"
    label = "Çizim"
    description = "Kâğıt arka plan, el yazısı, titreyen el çizimi şekiller, karakalem videolar."
    PARAMS = {
        "paper": {"type": "choice", "options": ["plain", "lined", "grid", "dots"],
                  "default": "plain", "label": "Kâğıt"},
        "paper_color": {"type": "color", "default": "#f4efe4", "label": "Kâğıt rengi"},
        "ink": {"type": "color", "default": "#2b2b2b", "label": "Mürekkep"},
        "line_color": {"type": "color", "default": "#7aa7d9", "label": "Çizgi rengi"},
        "boil": {"type": "bool", "default": True, "label": "El çizimi titremesi"},
        "boil_fps": {"type": "float", "default": 8, "min": 2, "max": 24, "label": "Titreme hızı"},
        "boil_amount": {"type": "float", "default": 1.5, "min": 0, "max": 6, "label": "Titreme miktarı"},
        "pencil": {"type": "bool", "default": True, "label": "Görüntüleri karakaleme çevir"},
        "keep_color": {"type": "float", "default": 0.25, "min": 0, "max": 1, "label": "Renk koru"},
    }
    text_defaults = {"font": "handwriting", "color": "#2b2b2b"}
    char_anim = {"type": "write", "unit": "char", "stagger": 0.05, "duration": 0.15}
    transition = {"type": "wipe_left", "duration": 0.6, "ease": "in_out_cubic"}
    palette = {"background": "#f4efe4", "text": "#2b2b2b", "accent": "#e63946", "blue": "#1d4ed8",
               "green": "#2a9d8f", "yellow": "#f4a261"}
    rough = 2.5
    preview_bg = "#f4efe4"

    def setup(self):
        self.text_defaults = {**self.text_defaults, "color": self.p["ink"]}
        self.palette = {**self.palette, "background": self.p["paper_color"], "text": self.p["ink"]}
        self.rough = 2.5 if self.p["boil"] else 1.2

    def background(self, r, t, w, h):
        return _paper(w, h, round(r.scale, 3), self.p["paper"], self.p["paper_color"],
                      self.p["line_color"]).copy()

    def media_filter(self, r, layer, img, lt):
        if not self.p["pencil"]:
            return img
        from ..render.effects import fx_sketch

        sk, _ = fx_sketch(img, (0, 0, img.width, img.height), {"amount": 1.0, "detail": 5}, r, lt)
        a = _arr(sk)
        orig = _arr(img)
        gray = a[..., 0]
        dark = np.clip((255 - gray) / 255 * 1.7, 0, 1)
        ink = np.array(_hex(self.p["ink"])[:3], np.float32)
        keep = float(self.p["keep_color"])
        rgb = ink * (1 - keep) + orig[..., :3] * keep
        out = np.zeros_like(a)
        out[..., :3] = rgb
        out[..., 3] = orig[..., 3] * np.clip(dark + keep * 0.35, 0, 1)
        return _img(out)

    def jitter(self, r, layer, lt):
        if not self.p["boil"]:
            return 0.0, 0.0, 0.0
        frame = int(lt * float(self.p["boil_fps"]))
        rnd = random.Random(stable_hash(layer["id"]) * 31 + frame)
        a = float(self.p["boil_amount"])
        return rnd.uniform(-a, a), rnd.uniform(-a, a), rnd.uniform(-a, a) * 0.3

    def post(self, r, frame, t):
        w, h = frame.size
        f = _arr(frame)
        grain = _noise_tex(w, h, 21, max(1.0, 1.5 * r.scale))[..., None]
        f[..., :3] *= 1 + grain * 0.06
        f[..., :3] *= _vignette(w, h, 0.25, 0.75)
        return _img(f)


# ---------------------------------------------------------------------- NEON


@register
class Neon(Theme):
    name = "neon"
    label = "Neon"
    description = "Koyu arka plan, hareketli synthwave ızgarası, parlayan yazılar ve bloom."
    PARAMS = {
        "color1": {"type": "color", "default": "#ff2bd6", "label": "Renk 1"},
        "color2": {"type": "color", "default": "#00e5ff", "label": "Renk 2"},
        "grid": {"type": "bool", "default": True, "label": "Izgara"},
        "glow": {"type": "float", "default": 0.9, "min": 0, "max": 2.5, "label": "Parlama"},
        "flicker": {"type": "bool", "default": True, "label": "Titreşim"},
    }
    text_defaults = {"font": "segoe bold", "color": "#ffffff", "shadow_color": "#ff2bd6",
                     "shadow_blur": 22, "stroke_width": 0}
    char_anim = {"type": "fade", "unit": "char", "stagger": 0.035, "duration": 0.3}
    transition = {"type": "zoom_in", "duration": 0.4}
    palette = {"background": "#0a0014", "accent": "#ff2bd6", "accent2": "#00e5ff", "text": "#ffffff"}
    preview_bg = "#12002b"

    def setup(self):
        self.text_defaults = {**self.text_defaults, "shadow_color": self.p["color1"]}
        self.palette = {**self.palette, "accent": self.p["color1"], "accent2": self.p["color2"]}

    def background(self, r, t, w, h):
        img = Image.new("RGBA", (w, h), (0, 0, 0, 255))
        top = np.array([18, 0, 43], np.float32)
        bot = np.array([0, 8, 20], np.float32)
        u = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
        grad = top * (1 - u) + bot * u
        a = np.zeros((h, w, 4), np.float32)
        a[..., :3] = grad
        a[..., 3] = 255
        img = _img(a)
        if not self.p["grid"]:
            return img
        d = ImageDraw.Draw(img)
        c1 = _hex(self.p["color1"])
        c2 = _hex(self.p["color2"])
        hy = int(h * 0.62)
        lw = max(1, int(3 * r.scale))
        # ufuk parlaması
        for i in range(30):
            alpha = int(90 * (1 - i / 30))
            d.line([(0, hy - i), (w, hy - i)], fill=c1[:3] + (alpha // 3,), width=1)
        # yatay çizgiler (izleyiciye doğru akar)
        n = 14
        phase = (t * 0.6) % 1
        for i in range(n):
            z = (i + phase) / n
            y = hy + (h - hy) * z ** 2.2
            d.line([(0, y), (w, y)], fill=c2[:3] + (int(60 + 160 * z),), width=lw)
        # dikey kaçış çizgileri
        for i in range(-12, 13):
            x_far = w / 2 + i * w * 0.03
            x_near = w / 2 + i * w * 0.22
            d.line([(x_far, hy), (x_near, h)], fill=c2[:3] + (150,), width=lw)
        # güneş
        sr = int(w * 0.22)
        sun = Image.new("RGBA", (sr * 2, sr * 2), (0, 0, 0, 0))
        sd = ImageDraw.Draw(sun)
        for yy in range(sr * 2):
            u2 = yy / (sr * 2)
            col = tuple(int(c1[k] * (1 - u2) + 255 * u2 * (k == 1) * 0.6 + c2[k] * u2 * 0.2)
                        for k in range(3))
            if yy > sr and (yy // max(2, int(14 * r.scale))) % 2 == 0:
                continue
            half = math.sqrt(max(0, sr * sr - (yy - sr) ** 2))
            sd.line([(sr - half, yy), (sr + half, yy)], fill=col + (230,))
        img.alpha_composite(sun, (w // 2 - sr, hy - int(sr * 1.75)))
        return img

    def media_filter(self, r, layer, img, lt):
        a = _arr(img)
        g = a[..., 0:1] * 0.3 + a[..., 1:2] * 0.59 + a[..., 2:3] * 0.11
        a[..., :3] = (g + (a[..., :3] - g) * 1.35 - 128) * 1.12 + 128
        return _img(a)

    def post(self, r, frame, t):
        frame = bloom(frame, float(self.p["glow"]), 40 * r.scale, 0.45)
        if self.p["flicker"]:
            rnd = random.Random(int(t * 30))
            if rnd.random() < 0.04:
                f = _arr(frame)
                f[..., :3] *= 0.82
                frame = _img(f)
        return frame


# ---------------------------------------------------------------------- RETRO VHS


@register
class Retro(Theme):
    name = "retro"
    label = "Retro VHS"
    description = "VHS kaset görünümü: renk kayması, tarama çizgileri, karıncalanma, REC etiketi."
    PARAMS = {
        "label": {"type": "bool", "default": True, "label": "PLAY/REC etiketi"},
        "date": {"type": "text", "default": "12.03.1996", "label": "Tarih yazısı"},
        "noise": {"type": "float", "default": 0.06, "min": 0, "max": 0.3, "label": "Karıncalanma"},
        "shift": {"type": "float", "default": 4, "min": 0, "max": 20, "label": "Renk kayması"},
        "tracking": {"type": "bool", "default": True, "label": "Bant bozulması"},
    }
    text_defaults = {"font": "consolas", "color": "#ffffff", "shadow_color": "#ff00aa99",
                     "shadow_x": 4, "shadow_y": 0, "shadow_blur": 2}
    char_anim = {"type": "typewriter", "unit": "char", "stagger": 0.06}
    transition = {"type": "glitch", "duration": 0.4}
    palette = {"background": "#140c26", "accent": "#ffcc66", "text": "#ffffff", "pink": "#ff4fa3"}
    preview_bg = "#1a1033"

    def background(self, r, t, w, h):
        u = np.linspace(0, 1, h, dtype=np.float32)[:, None, None]
        a = np.zeros((h, w, 4), np.float32)
        a[..., :3] = np.array([30, 16, 60], np.float32) * (1 - u) + np.array([10, 6, 20],
                                                                            np.float32) * u
        a[..., 3] = 255
        return _img(a)

    def post(self, r, frame, t):
        w, h = frame.size
        f = _arr(frame)
        s = int(round(float(self.p["shift"]) * r.scale))
        if s:
            f[..., 0] = np.roll(f[..., 0], s, axis=1)
            f[..., 2] = np.roll(f[..., 2], -s, axis=1)
        # sıcak, hafif soluk renk
        g = f[..., 0:1] * 0.3 + f[..., 1:2] * 0.59 + f[..., 2:3] * 0.11
        f[..., :3] = g + (f[..., :3] - g) * 0.85
        f[..., :3] = f[..., :3] * np.array([1.05, 0.98, 0.92], np.float32) + 8
        if self.p["tracking"]:
            band_y = int(((t * 0.35) % 1.3 - 0.15) * h)
            bh = max(4, int(h * 0.05))
            y0, y1 = max(0, band_y), min(h, band_y + bh)
            if y1 > y0:
                rng = np.random.default_rng(int(t * 30))
                shifts = (rng.normal(0, 8 * r.scale, y1 - y0)).astype(int)
                for i, sh in enumerate(shifts):
                    f[y0 + i] = np.roll(f[y0 + i], sh, axis=0)
                f[y0:y1, :, :3] += rng.normal(0, 40, (y1 - y0, w, 1))
        f[..., :3] += _grain(w, h, t, float(self.p["noise"]))
        f = _scanlines(f, max(2, int(3 * r.scale)), 0.22)
        f[..., :3] *= _vignette(w, h, 0.5, 0.6)
        out = _img(f)
        if self.p["label"]:
            d = ImageDraw.Draw(out)
            fs = max(8, int(min(w, h) * 0.045))
            font = load_font("consolas", fs)
            m = int(min(w, h) * 0.06)
            if int(t * 2) % 2 == 0:
                # ▶ karakteri her fontta yok; üçgeni elle çiz
                d.polygon([(m, m + fs * 0.15), (m, m + fs * 0.95), (m + fs * 0.7, m + fs * 0.55)],
                          fill=(255, 255, 255, 230))
                d.text((m + fs, m), "PLAY", fill=(255, 255, 255, 230), font=font)
            sec = int(t)
            d.text((w - m, h - m), f"{self.p['date']}\nSP {sec // 3600:02d}:{sec // 60 % 60:02d}:"
                                   f"{sec % 60:02d}", fill=(255, 255, 255, 220), font=font,
                   anchor="rd", align="right")
        return out


# ---------------------------------------------------------------------- SİNEMATİK


@register
class Sinematik(Theme):
    name = "sinematik"
    label = "Sinematik"
    description = "Sinema bantları, teal-orange renk düzenlemesi, film greni, yavaş geçişler."
    PARAMS = {
        "bars": {"type": "bool", "default": True, "label": "Sinema bantları"},
        "aspect": {"type": "float", "default": 2.39, "min": 1.5, "max": 3, "label": "Bant oranı"},
        "grade": {"type": "float", "default": 0.6, "min": 0, "max": 1, "label": "Renk düzenleme"},
        "grain": {"type": "float", "default": 0.045, "min": 0, "max": 0.2, "label": "Gren"},
        "vignette": {"type": "float", "default": 0.45, "min": 0, "max": 1, "label": "Vinyet"},
    }
    text_defaults = {"font": "georgia", "color": "#f1e6d2", "letter_spacing": 6}
    char_anim = {"type": "fade", "unit": "char", "stagger": 0.05, "duration": 0.8,
                 "ease": "in_out_sine"}
    transition = {"type": "fade", "duration": 0.9, "ease": "in_out_sine"}
    palette = {"background": "#0b0f14", "accent": "#e0a458", "text": "#f1e6d2", "teal": "#2a7f86"}
    preview_bg = "#0b0f14"

    def background(self, r, t, w, h):
        a = np.zeros((h, w, 4), np.float32)
        a[..., :3] = np.array([11, 15, 20], np.float32)
        a[..., 3] = 255
        a[..., :3] *= 1 + _noise_tex(w, h, 5, max(2.0, 200 * r.scale))[..., None] * 0.6
        return _img(a)

    def post(self, r, frame, t):
        w, h = frame.size
        f = _arr(frame)
        k = float(self.p["grade"])
        if k > 0:
            rgb = f[..., :3] / 255
            lum = rgb[..., 0:1] * 0.3 + rgb[..., 1:2] * 0.59 + rgb[..., 2:3] * 0.11
            teal = np.array([0.0, 0.45, 0.5], np.float32)
            orange = np.array([1.0, 0.62, 0.32], np.float32)
            tone = teal * (1 - lum) + orange * lum
            graded = rgb * (1 - 0.35 * k) + tone * lum * 0.35 * k + (rgb - lum) * 0.15 * k
            graded = np.clip((graded - 0.5) * (1 + 0.15 * k) + 0.5, 0, 1)
            f[..., :3] = graded * 255
        f[..., :3] += _grain(w, h, t, float(self.p["grain"]))
        f[..., :3] *= _vignette(w, h, float(self.p["vignette"]), 0.65)
        if self.p["bars"]:
            if h > w:
                bar = int(h * 0.07)
            else:
                bar = max(0, int((h - w / float(self.p["aspect"])) / 2))
            if bar > 0:
                f[:bar, :, :3] = 0
                f[h - bar:, :, :3] = 0
        return _img(f)


# ---------------------------------------------------------------------- MİNİMAL


@register
class Minimal(Theme):
    name = "minimal"
    label = "Minimal"
    description = "Sade, açık renkli, temiz yazılar ve yumuşak kaymalar."
    PARAMS = {
        "background": {"type": "color", "default": "#f5f5f2", "label": "Arka plan"},
        "text": {"type": "color", "default": "#1d1d1f", "label": "Yazı rengi"},
        "accent": {"type": "color", "default": "#0a84ff", "label": "Vurgu"},
    }
    text_defaults = {"font": "segoe bold", "color": "#1d1d1f"}
    char_anim = {"type": "rise", "unit": "word", "stagger": 0.1, "duration": 0.5}
    transition = {"type": "slide_up", "duration": 0.45}
    palette = {"background": "#f5f5f2", "text": "#1d1d1f", "accent": "#0a84ff"}
    preview_bg = "#f5f5f2"

    def setup(self):
        self.text_defaults = {**self.text_defaults, "color": self.p["text"]}
        self.palette = {"background": self.p["background"], "text": self.p["text"],
                        "accent": self.p["accent"]}

    def background(self, r, t, w, h):
        return Image.new("RGBA", (w, h), _hex(self.p["background"]))


# ---------------------------------------------------------------------- GLITCH


@register
class Glitch(Theme):
    name = "glitch"
    label = "Glitch"
    description = "Dijital bozulma: RGB ayrışması, kayan bloklar, ani parazit patlamaları."
    PARAMS = {
        "intensity": {"type": "float", "default": 0.5, "min": 0, "max": 1, "label": "Şiddet"},
        "frequency": {"type": "float", "default": 1.0, "min": 0.1, "max": 4, "label": "Sıklık"},
        "split": {"type": "float", "default": 3, "min": 0, "max": 20, "label": "Sürekli RGB kayması"},
    }
    text_defaults = {"font": "segoe black", "color": "#ffffff"}
    char_anim = {"type": "glitch", "unit": "char", "stagger": 0.03, "duration": 0.45}
    transition = {"type": "glitch", "duration": 0.35}
    palette = {"background": "#0a0a0a", "accent": "#ff0050", "accent2": "#00e5ff", "text": "#ffffff"}
    preview_bg = "#0a0a0a"

    def background(self, r, t, w, h):
        a = np.zeros((h, w, 4), np.float32)
        a[..., :3] = 10
        a[..., 3] = 255
        rng = np.random.default_rng(int(t * 12))
        for _ in range(6):
            y = int(rng.uniform(0, h))
            a[y:y + max(1, int(2 * r.scale)), :, :3] += rng.uniform(10, 35)
        return _img(a)

    def post(self, r, frame, t):
        w, h = frame.size
        f = _arr(frame)
        s = int(round(float(self.p["split"]) * r.scale))
        if s:
            f[..., 0] = np.roll(f[..., 0], s, axis=1)
            f[..., 2] = np.roll(f[..., 2], -s, axis=1)
        period = 1.0 / float(self.p["frequency"])
        seg = int(t / period)
        rnd = random.Random(seg * 9973)
        burst_at = rnd.uniform(0, period * 0.8)
        local = t - seg * period
        k = float(self.p["intensity"])
        if burst_at <= local < burst_at + 0.18 and k > 0:
            rng = np.random.default_rng(int(t * 30))
            for _ in range(int(4 + 10 * k)):
                y = int(rng.uniform(0, h))
                bh = int(rng.uniform(2, h * 0.06))
                dx = int(rng.normal(0, w * 0.06 * k))
                f[y:y + bh] = np.roll(f[y:y + bh], dx, axis=1)
                if rng.random() < 0.3:
                    f[y:y + bh, :, :3] = 255 - f[y:y + bh, :, :3]
            big = int(12 * k * r.scale) + 1
            f[..., 0] = np.roll(f[..., 0], big, axis=1)
            f[..., 1] = np.roll(f[..., 1], -big // 2, axis=0)
        return _img(f)
