"""Render motoru: (proje, zaman) → kare.

Önizleme ve export aynı `Renderer` sınıfını kullanır; önizlemede yalnızca `scale` küçüktür.
"""
from __future__ import annotations

import json
import math
import os
from collections import OrderedDict
from pathlib import Path

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter

from .. import model
from ..media import VideoReader, load_image, probe
from ..util import ROOT, load_font, parse_color, resolve_path, stable_hash
from . import transitions
from .blend import composite
from .effects import apply_effects, effects_animated
from .shapes import gradient_image, render_shape
from .text import render_text

TRANSFORM_PROPS = set(model.COMMON_PROPS)
MAX_DEPTH = 8


class Renderer:
    def __init__(self, project: dict, base_dir=None, scale: float = 1.0, preview: bool = False):
        self.project = model.normalize(project)
        self.base_dir = str(base_dir or ROOT)
        self.scale = float(scale)
        self.preview = preview
        self.fps = float(self.project.get("fps", 30))
        self.warnings: list[str] = []
        self._readers: dict[tuple, VideoReader] = {}
        self._cache: OrderedDict = OrderedDict()
        self._cache_limit = 96
        self._themes: dict[str, object] = {}
        self._current_theme = None
        self._current_effects: list = []
        self.brand = self._load_brand()
        self.palette = self._build_palette()

    def set_project(self, project: dict) -> None:
        """Projeyi değiştirir; video okuyucular ve içerik cache'i korunur (arayüz için)."""
        self.project = model.normalize(project)
        self.fps = float(self.project.get("fps", 30))
        self.brand = self._load_brand()
        self.palette = self._build_palette()
        self._themes.clear()
        self.warnings = []

    # ------------------------------------------------------------------ kaynaklar

    def _load_brand(self) -> dict:
        ref = self.project.get("brand")
        if not ref:
            return {}
        path = resolve_path(ref, self.base_dir)
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:  # noqa: BLE001
            self.warn(f"Marka dosyası okunamadı: {ref}")
            return {}

    def _build_palette(self) -> dict:
        pal = {}
        for k, v in (self.brand.get("colors") or {}).items():
            pal[f"brand.{k}"] = v
        return pal

    def warn(self, msg: str) -> None:
        if msg not in self.warnings and len(self.warnings) < 100:
            self.warnings.append(msg)

    def color(self, v):
        if isinstance(v, str) and v.startswith("theme.") and self._current_theme is not None:
            v = self._current_theme.palette.get(v[6:], v)
        return parse_color(v, self.palette)

    def font(self, name, size):
        if not name:
            th = self._current_theme
            fonts = self.brand.get("fonts") or {}
            # marka: büyük yazılarda başlık, küçüklerde gövde fontu
            brand_font = fonts.get("heading") if size / max(self.scale, 1e-6) >= 72 else \
                (fonts.get("body") or fonts.get("heading"))
            name = (th.text_defaults.get("font") if th else None) or brand_font or "arial"
        return load_font(name, size, self.base_dir)

    def prop(self, layer, name, t):
        return model.prop(layer, name, t)

    def text_prop(self, layer, name, t):
        if name in layer.get("props", {}):
            return model.prop(layer, name, t)
        th = self._current_theme
        if th is not None and name in th.text_defaults and layer.get("theme_style", True):
            return th.text_defaults[name]
        if name == "color" and self.brand.get("colors", {}).get("text"):
            return self.brand["colors"]["text"]
        return model.default_prop("text", name)

    def char_anim(self, layer):
        a = layer.get("char_anim")
        if a == "theme":
            th = self._current_theme
            return th.char_anim if th is not None else None
        return a or None

    def theme_rough(self) -> float:
        th = self._current_theme
        return float(getattr(th, "rough", 0.0)) if th is not None else 0.0

    def theme_for(self, comp: dict):
        spec = comp.get("theme") or self.project.get("theme")
        if not spec:
            return None
        if isinstance(spec, str):
            spec = {"name": spec}
        key = json.dumps(spec, sort_keys=True)
        if key not in self._themes:
            from ..themes import get_theme

            try:
                self._themes[key] = get_theme(spec.get("name"), spec.get("params") or {})
            except KeyError:
                self.warn(f"Tema bulunamadı: {spec.get('name')}")
                self._themes[key] = None
        return self._themes[key]

    def reader(self, path: str, size: tuple[int, int]) -> VideoReader:
        key = (path, size)
        r = self._readers.get(key)
        if r is None:
            # aynı dosyanın farklı boyuttaki eski okuyucularını kapat
            for k in [k for k in self._readers if k[0] == path]:
                self._readers.pop(k).close()
            r = self._readers[key] = VideoReader(path, size)
        return r

    def close(self) -> None:
        for r in self._readers.values():
            r.close()
        self._readers.clear()
        self._cache.clear()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    # ------------------------------------------------------------------ dış API

    def comp_pixel_size(self, comp_id=None) -> tuple[int, int]:
        comp = model.get_comp(self.project, comp_id)
        w, h = model.comp_size(self.project, comp)
        return max(2, int(round(w * self.scale))), max(2, int(round(h * self.scale)))

    def render_image(self, t: float, comp_id=None) -> Image.Image:
        cid = comp_id or self.project["main"]
        return self.render_comp(cid, t, 0)

    def render_rgb(self, t: float, comp_id=None) -> np.ndarray:
        """Opak RGB kare (export için). Şeffaf kısımlar siyah olur."""
        img = self.render_image(t, comp_id)
        bg = Image.new("RGBA", img.size, (0, 0, 0, 255))
        bg.alpha_composite(img)
        return np.asarray(bg.convert("RGB"))

    # ------------------------------------------------------------------ kompozisyon

    def render_comp(self, cid: str, t: float, depth: int) -> Image.Image:
        comp = model.get_comp(self.project, cid)
        cw, ch = model.comp_size(self.project, comp)
        W, H = max(2, int(round(cw * self.scale))), max(2, int(round(ch * self.scale)))
        if depth > MAX_DEPTH:
            return Image.new("RGBA", (W, H), (0, 0, 0, 0))
        theme = self.theme_for(comp)
        prev = self._current_theme
        self._current_theme = theme
        try:
            canvas = self._background(comp, theme, t, W, H)
            for layer in model.sorted_layers(comp):
                if not model.is_active(layer, t) or layer["type"] == "audio":
                    continue
                try:
                    self._draw_layer(canvas, layer, t - layer["start"], W, H, depth)
                except Exception as e:  # noqa: BLE001
                    self.warn(f"Katman '{layer.get('name')}' çizilemedi: {e}")
            if depth == 0 and theme is not None:
                canvas = theme.post(self, canvas, t)
        finally:
            self._current_theme = prev
        return canvas

    def _background(self, comp, theme, t, W, H) -> Image.Image:
        bg = comp.get("background")
        if bg == "theme":
            if theme is not None:
                img = theme.background(self, t, W, H)
                if img is not None:
                    return img.convert("RGBA") if img.mode != "RGBA" else img.copy()
            return Image.new("RGBA", (W, H), (0, 0, 0, 255))
        if isinstance(bg, dict) and bg.get("gradient"):
            c = bg["gradient"]
            return gradient_image((W, H), self.color(c[0]), self.color(c[-1]),
                                  float(bg.get("angle", 180)))
        if bg:
            return Image.new("RGBA", (W, H), self.color(bg))
        return Image.new("RGBA", (W, H), (0, 0, 0, 0))

    # ------------------------------------------------------------------ katman

    def _draw_layer(self, canvas: Image.Image, layer: dict, lt: float, W: int, H: int, depth: int):
        theme = self._current_theme
        tst = transitions.state(layer, lt, W, H, getattr(theme, "transition", None))
        P = lambda n: model.prop(layer, n, lt)  # noqa: E731

        if layer["type"] == "adjustment":
            op = float(P("opacity")) * tst.opacity
            if op <= 0:
                return
            img, origin = apply_effects(canvas.copy(), (0, 0, W, H), layer.get("effects"), self, lt)
            ox, oy = int(origin[0]), int(origin[1])
            img = img.crop((ox, oy, ox + W, oy + H))
            if op < 1:
                img = Image.blend(canvas, img, op)
            canvas.paste(img, (0, 0))
            return

        res = self.layer_content(layer, lt, W, H, depth)
        if res is None:
            return
        img, origin, default_pos = res
        if tst.blur > 0.3:
            pad = int(tst.blur * self.scale * 2)
            big = Image.new("RGBA", (img.width + 2 * pad, img.height + 2 * pad), (0, 0, 0, 0))
            big.paste(img, (pad, pad))
            img = big.filter(ImageFilter.GaussianBlur(tst.blur * self.scale))
            origin = (origin[0] + pad, origin[1] + pad, origin[2], origin[3])
        if tst.glitch > 0:
            img = _glitch(img, tst.glitch, lt, self.scale)

        ox, oy, bw, bh = origin
        ax = ox + float(P("anchor_x")) * bw
        ay = oy + float(P("anchor_y")) * bh
        x, y = P("x"), P("y")
        if x is None:
            x = anchored(default_pos, 0, P("anchor_x")) if default_pos else W / 2 / self.scale
        if y is None:
            y = anchored(default_pos, 1, P("anchor_y")) if default_pos else H / 2 / self.scale
        jx = jy = jr = 0.0
        if theme is not None and layer.get("theme_style", True):
            jx, jy, jr = theme.jitter(self, layer, lt)
        X = (float(x) + jx) * self.scale + tst.dx
        Y = (float(y) + jy) * self.scale + tst.dy
        sc = float(P("scale")) * tst.scale
        sx, sy = sc * float(P("scale_x")), sc * float(P("scale_y"))
        rot = float(P("rotation")) + tst.rotation + jr
        moving = (tst.dx or tst.dy or tst.scale != 1 or not model.static_props(layer) or jx or jy)
        placed = _transform(img, ax, ay, sx, sy, rot, X, Y, W, H, bool(moving))
        if placed is None:
            return
        pimg, px, py = placed
        op = float(P("opacity")) * tst.opacity
        if op <= 0.003:
            return
        if op < 0.999:
            pimg = pimg.copy() if pimg is img else pimg
            pimg.putalpha(pimg.getchannel("A").point(lambda v, o=op: int(v * o + 0.5)))
        if tst.wipe is not None or tst.circle is not None:
            pimg = _reveal_mask(pimg, px, py, W, H, tst)
        composite(canvas, pimg, px, py, layer.get("blend", "normal"))

    def layer_corners(self, comp_id: str, layer: dict, t: float):
        """Katmanın mantıksal kutusunun ekrandaki 4 köşesi (kompozisyon pikseli). Arayüz için."""
        comp = model.get_comp(self.project, comp_id)
        cw, ch = model.comp_size(self.project, comp)
        W, H = max(2, int(round(cw * self.scale))), max(2, int(round(ch * self.scale)))
        lt = t - layer["start"]
        if layer["type"] in ("audio", "adjustment"):
            return None
        self._current_theme = self.theme_for(comp)
        try:
            res = self.layer_content(layer, lt, W, H, 0)
        finally:
            self._current_theme = None
        if res is None:
            return None
        img, origin, default_pos = res
        P = lambda n: model.prop(layer, n, lt)  # noqa: E731
        ox, oy, bw, bh = origin
        ax = ox + float(P("anchor_x")) * bw
        ay = oy + float(P("anchor_y")) * bh
        x, y = P("x"), P("y")
        if x is None:
            x = anchored(default_pos, 0, P("anchor_x")) if default_pos else cw / 2
        if y is None:
            y = anchored(default_pos, 1, P("anchor_y")) if default_pos else ch / 2
        sc = float(P("scale"))
        sx, sy = sc * float(P("scale_x")), sc * float(P("scale_y"))
        th = math.radians(float(P("rotation")))
        c, s = math.cos(th), math.sin(th)
        pts = []
        for px, py in ((ox, oy), (ox + bw, oy), (ox + bw, oy + bh), (ox, oy + bh)):
            dx, dy = (px - ax) / self.scale * sx, (py - ay) / self.scale * sy
            pts.append([float(x) + c * dx - s * dy, float(y) + s * dx + c * dy])
        out = {"corners": pts, "anchor": [float(x), float(y)]}
        if default_pos and layer["type"] == "shape":
            # nokta uzayı → kompozisyon: X = a*px + b*py + c,  Y = d*px + e*py + f
            a_, b_ = c * sx, -s * sy
            d_, e_ = s * sx, c * sy
            vx = -default_pos[0] + (ox - ax) / self.scale
            vy = -default_pos[1] + (oy - ay) / self.scale
            out["matrix"] = [a_, b_, float(x) + a_ * vx + b_ * vy,
                             d_, e_, float(y) + d_ * vx + e_ * vy]
        return out

    def _content_key(self, layer: dict):
        t = layer["type"]
        if t not in ("text", "shape", "image", "solid"):
            return None
        props = layer.get("props", {})
        for k, v in props.items():
            if k not in TRANSFORM_PROPS and model.is_animated(v):
                return None
        if effects_animated(layer.get("effects")):
            return None
        if t == "text" and layer.get("char_anim"):
            return None
        if t == "shape" and (layer.get("rough") or self.theme_rough()):
            return None
        th = self._current_theme
        relevant = {k: v for k, v in props.items() if k not in TRANSFORM_PROPS}
        return (layer["id"], self.scale, getattr(th, "key", None), model.content_hash(
            [relevant, layer.get("effects"), layer.get("src"), layer.get("fit"),
             layer.get("counter"), layer.get("closed"), layer.get("filled"), layer.get("smooth"), layer.get("theme_style", True)]))

    def layer_content(self, layer: dict, lt: float, W: int, H: int, depth: int = 0):
        key = self._content_key(layer)
        if key is not None and key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        res = self._build_content(layer, lt, W, H, depth)
        if res is None:
            return None
        img, origin, default_pos = res
        theme = self._current_theme
        if theme is not None and layer["type"] in ("video", "image", "script") \
                and layer.get("theme_style", True):
            img = theme.media_filter(self, layer, img, lt)
        img, origin = apply_effects(img, origin, layer.get("effects"), self, lt)
        out = (img, origin, default_pos)
        if key is not None:
            self._cache[key] = out
            if len(self._cache) > self._cache_limit:
                self._cache.popitem(last=False)
        return out

    def _fit_factor(self, layer, w, h, W, H):
        fit = layer.get("fit") or "none"
        if fit == "contain":
            return min(W / w, H / h), min(W / w, H / h)
        if fit == "cover":
            k = max(W / w, H / h)
            return k, k
        if fit == "fill":
            return W / w, H / h
        return self.scale, self.scale

    def _missing(self, layer, W, H, msg):
        self.warn(msg)
        w, h = int(W * 0.6), int(H * 0.12)
        img = Image.new("RGBA", (w, h), (60, 20, 30, 220))
        d = ImageDraw.Draw(img)
        d.rectangle([0, 0, w - 1, h - 1], outline=(255, 80, 100, 255), width=max(1, int(3 * self.scale)))
        d.text((w / 2, h / 2), msg[:60], fill=(255, 220, 220, 255), anchor="mm",
               font=load_font("arial", max(8, int(h * 0.22))))
        return img, (0, 0, w, h), None

    def _build_content(self, layer, lt, W, H, depth):
        t = layer["type"]
        if t == "text":
            img, origin = render_text(self, layer, lt)
            return img, origin, None
        if t == "shape":
            return render_shape(self, layer, lt)
        if t == "solid":
            c1 = self.color(model.prop(layer, "color", lt))
            c2 = model.prop(layer, "fill2", lt)
            img = gradient_image((W, H), c1, self.color(c2), float(model.prop(
                layer, "gradient_angle", lt))) if c2 else Image.new("RGBA", (W, H), c1)
            return img, (0, 0, W, H), None
        if t == "image":
            path = resolve_path(layer.get("src"), self.base_dir)
            if not path or not os.path.exists(path):
                return self._missing(layer, W, H, f"Dosya yok: {Path(str(layer.get('src'))).name}")
            src = load_image(path)
            fx, fy = self._fit_factor(layer, src.width, src.height, W, H)
            size = (max(1, int(round(src.width * fx))), max(1, int(round(src.height * fy))))
            img = src if size == src.size else src.resize(size, Image.LANCZOS)
            return img, (0, 0, img.width, img.height), None
        if t == "video":
            path = resolve_path(layer.get("src"), self.base_dir)
            if not path or not os.path.exists(path):
                return self._missing(layer, W, H, f"Dosya yok: {Path(str(layer.get('src'))).name}")
            info = probe(path)
            fx, fy = self._fit_factor(layer, info["width"] or W, info["height"] or H, W, H)
            size = (max(2, int(round(info["width"] * fx))), max(2, int(round(info["height"] * fy))))
            st = float(layer.get("in", 0)) + lt * float(layer.get("speed", 1.0))
            if layer.get("loop") and info["duration"] > 0:
                st %= info["duration"]
            frame = self.reader(path, size).get_frame(st)
            img = Image.fromarray(frame).convert("RGBA")
            return img, (0, 0, img.width, img.height), None
        if t == "comp":
            ref = layer.get("comp")
            sub = model.get_comp(self.project, ref)
            st = float(layer.get("in", 0)) + lt * float(layer.get("speed", 1.0))
            if layer.get("loop"):
                st %= max(1e-3, model.comp_duration(sub))
            img = self.render_comp(ref, st, depth + 1)
            return img, (0, 0, img.width, img.height), None
        if t == "script":
            from ..scripting import render_script

            img = render_script(self, layer, lt, W, H)
            if img is None:
                return None
            fx, fy = self._fit_factor(layer, img.width, img.height, W, H) \
                if layer.get("fit") else (1.0, 1.0)
            if (fx, fy) != (1.0, 1.0):
                img = img.resize((max(1, int(img.width * fx)), max(1, int(img.height * fy))),
                                 Image.LANCZOS)
            return img, (0, 0, img.width, img.height), None
        return None


# ---------------------------------------------------------------------- yardımcılar


def anchored(default_pos, axis: int, anchor) -> float:
    """Noktalı şekillerde varsayılan konum: nokta kutusunun anchor'a karşılık gelen yeri."""
    return default_pos[axis] + float(anchor) * default_pos[axis + 2]


def _transform(img, ax, ay, sx, sy, rot, X, Y, W, H, moving):
    """img'yi anchor noktası (ax, ay) kanvasta (X, Y)'ye gelecek şekilde ölçekler/döndürür.

    → (görüntü, sol, üst) ya da tamamen ekran dışındaysa None
    """
    if abs(sx) < 1e-4 or abs(sy) < 1e-4:
        return None
    if sx < 0:
        img = img.transpose(Image.FLIP_LEFT_RIGHT)
        ax, sx = img.width - ax, -sx
    if sy < 0:
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
        ay, sy = img.height - ay, -sy
    if sx < 0.75 or sy < 0.75:
        fx, fy = min(1.0, sx), min(1.0, sy)
        nw, nh = max(1, int(round(img.width * fx))), max(1, int(round(img.height * fy)))
        rfx, rfy = nw / img.width, nh / img.height
        img = img.resize((nw, nh), Image.LANCZOS)
        ax, ay, sx, sy = ax * rfx, ay * rfy, sx / rfx, sy / rfy

    rot = rot % 360
    if rot == 0 and abs(sx - 1) < 1e-3 and abs(sy - 1) < 1e-3:
        x0, y0 = X - ax, Y - ay
        if not moving or (abs(x0 - round(x0)) < 0.05 and abs(y0 - round(y0)) < 0.05):
            x0, y0 = int(round(x0)), int(round(y0))
            if x0 >= W or y0 >= H or x0 + img.width <= 0 or y0 + img.height <= 0:
                return None
            return img, x0, y0

    th = math.radians(rot)
    c, s = math.cos(th), math.sin(th)
    corners = []
    for (px, py) in ((0, 0), (img.width, 0), (0, img.height), (img.width, img.height)):
        dx, dy = (px - ax) * sx, (py - ay) * sy
        corners.append((c * dx - s * dy + X, s * dx + c * dy + Y))
    x0 = max(0, int(math.floor(min(p[0] for p in corners))))
    y0 = max(0, int(math.floor(min(p[1] for p in corners))))
    x1 = min(W, int(math.ceil(max(p[0] for p in corners))))
    y1 = min(H, int(math.ceil(max(p[1] for p in corners))))
    if x1 <= x0 or y1 <= y0:
        return None
    a = c / sx
    b = s / sx
    cc = (c * (x0 - X) + s * (y0 - Y)) / sx + ax
    d = -s / sy
    e = c / sy
    f = (-s * (x0 - X) + c * (y0 - Y)) / sy + ay
    out = img.transform((x1 - x0, y1 - y0), Image.AFFINE, (a, b, cc, d, e, f),
                        resample=Image.BICUBIC)
    return out, x0, y0


def _reveal_mask(img, px, py, W, H, tst):
    mask = Image.new("L", img.size, 0)
    d = ImageDraw.Draw(mask)
    if tst.wipe is not None:
        side, p = tst.wipe
        if side == "left":  # soldan sağa açılır
            d.rectangle([0 - px, 0, W * p - px, img.height], fill=255)
        elif side == "right":
            d.rectangle([W * (1 - p) - px, 0, W - px, img.height], fill=255)
        elif side == "up":
            d.rectangle([0, H * (1 - p) - py, img.width, H - py], fill=255)
        else:
            d.rectangle([0, 0 - py, img.width, H * p - py], fill=255)
    if tst.circle is not None:
        cx, cy = W / 2 - px, H / 2 - py
        rad = math.hypot(W, H) / 2 * tst.circle
        d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=255)
    out = img.copy()
    out.putalpha(ImageChops.multiply(img.getchannel("A"), mask))
    return out


def _glitch(img, amount, lt, scale):
    import random

    rnd = random.Random(int(lt * 30) * 7 + 3)
    if rnd.random() > 0.35 + amount * 0.6:
        return img
    out = img.copy()
    w, h = img.size
    for _ in range(int(3 + amount * 8)):
        y = rnd.randint(0, max(0, h - 2))
        hh = rnd.randint(2, max(3, int(h * 0.08)))
        dx = int(rnd.uniform(-1, 1) * w * 0.08 * amount)
        strip = img.crop((0, y, w, min(h, y + hh)))
        out.paste((0, 0, 0, 0), (0, y, w, min(h, y + hh)))
        out.paste(strip, (dx, y))
    r, g, b, a = out.split()
    shift = int(6 * amount * scale) + 1
    r = ImageChops.offset(r, shift, 0)
    b = ImageChops.offset(b, -shift, 0)
    return Image.merge("RGBA", (r, g, b, a))
