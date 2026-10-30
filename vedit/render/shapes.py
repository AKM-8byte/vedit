"""Şekil katmanı render'ı (2x süper örnekleme ile kenar yumuşatma).

shape: rect | ellipse | line | path | polygon | star | arrow | triangle
`progress` (0..1) çizginin ne kadarının çizileceğini belirler (çizim / "draw-on" animasyonu).
line / path / arrow için `points` kompozisyon koordinatlarıdır; katmanın x/y'si boş bırakılırsa
şekil tam o noktalarda durur.
"""
from __future__ import annotations

import math
import random

import numpy as np
from PIL import Image, ImageDraw

from ..util import stable_hash

SHAPES = {
    "rect": "Dikdörtgen", "ellipse": "Elips", "line": "Çizgi", "path": "Yol",
    "polygon": "Çokgen", "star": "Yıldız", "arrow": "Ok", "triangle": "Üçgen",
}

SS = 2


def gradient_image(size, c1, c2, angle_deg: float) -> Image.Image:
    w, h = size
    a = math.radians(angle_deg)
    y, x = np.mgrid[0:h, 0:w].astype(np.float32)
    dx, dy = math.sin(a), -math.cos(a)  # 0° = yukarıdan aşağı değil, 90° = soldan sağa
    proj = (x - w / 2) * dx + (y - h / 2) * dy
    half = (abs(w * dx) + abs(h * dy)) / 2 or 1
    u = np.clip(proj / (2 * half) + 0.5, 0, 1)[..., None]
    c1 = np.array(c1, np.float32)
    c2 = np.array(c2, np.float32)
    out = c1 + (c2 - c1) * u
    return Image.fromarray(out.astype(np.uint8))


def _poly_len(pts):
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def trim_path(pts, progress: float):
    if progress >= 1 or len(pts) < 2:
        return list(pts)
    target = _poly_len(pts) * max(0.0, progress)
    out = [pts[0]]
    acc = 0.0
    for a, b in zip(pts, pts[1:]):
        seg = math.dist(a, b)
        if acc + seg >= target:
            u = (target - acc) / seg if seg else 0
            out.append((a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u))
            return out
        out.append(b)
        acc += seg
    return out


def _ellipse_pts(x0, y0, x1, y1, n=96):
    cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
    return [(cx + rx * math.cos(-math.pi / 2 + i / n * math.tau),
             cy + ry * math.sin(-math.pi / 2 + i / n * math.tau)) for i in range(n + 1)]


def _rect_pts(x0, y0, x1, y1):
    return [(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]


def _regular(cx, cy, rx, ry, sides, inner=None):
    pts = []
    n = sides * 2 if inner else sides
    for i in range(n):
        a = -math.pi / 2 + i / n * math.tau
        k = (inner if (inner and i % 2) else 1.0)
        pts.append((cx + rx * k * math.cos(a), cy + ry * k * math.sin(a)))
    return pts


def smooth_path(pts, closed=False, steps=10):
    """Noktalardan geçen yumuşak eğri (Catmull-Rom)."""
    if len(pts) < 3:
        return list(pts)
    src = list(pts[:-1]) if closed and pts[0] == pts[-1] else list(pts)
    n = len(src)
    out = []
    segs = n if closed else n - 1
    for i in range(segs):
        p0 = src[(i - 1) % n] if closed or i > 0 else src[0]
        p1, p2 = src[i], src[(i + 1) % n]
        p3 = src[(i + 2) % n] if closed or i + 2 < n else src[-1]
        for k in range(steps):
            t = k / steps
            t2, t3 = t * t, t * t * t
            out.append(tuple(0.5 * (2 * p1[j] + (-p0[j] + p2[j]) * t
                                    + (2 * p0[j] - 5 * p1[j] + 4 * p2[j] - p3[j]) * t2
                                    + (-p0[j] + 3 * p1[j] - 3 * p2[j] + p3[j]) * t3)
                            for j in (0, 1)))
    out.append(src[0] if closed else src[-1])
    return out


def _jitter(pts, amount, seed):
    rnd = random.Random(seed)
    return [(x + rnd.uniform(-amount, amount), y + rnd.uniform(-amount, amount)) for x, y in pts]


def _densify(pts, step):
    out = [pts[0]]
    for a, b in zip(pts, pts[1:]):
        n = max(1, int(math.dist(a, b) / step))
        for i in range(1, n + 1):
            out.append((a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n))
    return out


def render_shape(r, layer: dict, lt: float):
    """→ (RGBA görüntü, origin, varsayılan_konum | None)"""
    s = r.scale
    P = lambda n: r.prop(layer, n, lt)  # noqa: E731
    kind = P("shape") or "rect"
    sw = float(P("stroke_width") or 0) * s
    stroke = r.color(P("stroke_color")) if P("stroke_color") and sw > 0 else None
    fill_v = P("fill")
    fill = r.color(fill_v) if fill_v else None
    fill2 = r.color(P("fill2")) if P("fill2") else None
    progress = float(P("progress") if P("progress") is not None else 1.0)
    rough = float(layer.get("rough", r.theme_rough())) * s
    boil_seed = (stable_hash(layer["id"]) & 0xFFFF) * 31 + int(lt * 8)
    pad = sw + 2 + rough * 2
    default_pos = None

    w, h = float(P("w") or 0) * s, float(P("h") or 0) * s
    if kind in ("line", "path", "arrow"):
        raw = P("points") or [[0, 0], [400, 0]]
        pts = [(float(x) * s, float(y) * s) for x, y in raw]
        minx, miny = min(p[0] for p in pts), min(p[1] for p in pts)
        maxx, maxy = max(p[0] for p in pts), max(p[1] for p in pts)
        head = sw * 3 + 6 * s if kind == "arrow" else 0
        pad += head
        # noktaların kutusu (proje pikseli); konum anchor'a göre bu kutudan hesaplanır
        default_pos = (minx / s, miny / s, (maxx - minx) / s, (maxy - miny) / s)
        w, h = maxx - minx, maxy - miny
        pts = [(x - minx + pad, y - miny + pad) for x, y in pts]
        closed = bool(layer.get("closed", False)) and kind == "path"
        if closed:
            pts = pts + [pts[0]]
        if layer.get("smooth") and len(pts) >= 3:
            pts = smooth_path(pts, closed)
    W, H = int(math.ceil(w + 2 * pad)), int(math.ceil(h + 2 * pad))
    W, H = max(W, 1), max(H, 1)
    im = Image.new("RGBA", (W * SS, H * SS), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    x0, y0, x1, y1 = pad, pad, pad + w, pad + h

    outline: list | None = None
    fillable = True
    if kind == "rect":
        outline = _rect_pts(x0, y0, x1, y1)
    elif kind == "ellipse":
        outline = _ellipse_pts(x0, y0, x1, y1)
    elif kind in ("polygon", "triangle"):
        sides = 3 if kind == "triangle" else max(3, int(P("sides") or 5))
        outline = _regular((x0 + x1) / 2, (y0 + y1) / 2, w / 2, h / 2, sides)
        outline.append(outline[0])
    elif kind == "star":
        outline = _regular((x0 + x1) / 2, (y0 + y1) / 2, w / 2, h / 2, max(3, int(P("sides") or 5)),
                           float(P("inner") or 0.5))
        outline.append(outline[0])
    else:
        outline = pts
        # "filled": açık yolun da içi boyanır (ör. bardaktaki su); çizgi açık kalır
        fillable = kind in ("path", "line") and (bool(layer.get("closed")) or bool(layer.get("filled")))

    if rough > 0 and outline:
        outline = _jitter(_densify(outline, 30 * s), rough, boil_seed)

    fill_alpha = 1.0 if progress >= 1 else max(0.0, (progress - 0.7) / 0.3)
    if fill and fillable and fill_alpha > 0:
        mask = Image.new("L", im.size, 0)
        md = ImageDraw.Draw(mask)
        if kind == "rect" and rough == 0:
            md.rounded_rectangle([x0 * SS, y0 * SS, x1 * SS, y1 * SS],
                                 radius=float(P("radius") or 0) * s * SS, fill=255)
        elif kind == "ellipse" and rough == 0:
            md.ellipse([x0 * SS, y0 * SS, x1 * SS, y1 * SS], fill=255)
        else:
            md.polygon([(x * SS, y * SS) for x, y in outline], fill=255)
        if fill2:
            src = gradient_image(im.size, fill, fill2, float(P("gradient_angle") or 90))
        else:
            src = Image.new("RGBA", im.size, fill)
        if fill_alpha < 1:
            mask = mask.point(lambda v: int(v * fill_alpha))
        a = np.asarray(src.getchannel("A"), np.float32) * (np.asarray(mask, np.float32) / 255)
        src.putalpha(Image.fromarray(a.astype(np.uint8)))
        im.alpha_composite(src)

    draw_stroke = stroke is not None or (not fillable and fill is not None)
    if layer.get("filled") and not layer.get("closed") and stroke is None:
        draw_stroke = False
    if draw_stroke and outline:
        col = stroke or fill
        width = max(1, int(round((sw if sw > 0 else 4 * s) * SS)))
        if kind == "rect" and rough == 0 and progress >= 1 and float(P("radius") or 0) > 0:
            d.rounded_rectangle([x0 * SS, y0 * SS, x1 * SS, y1 * SS],
                                radius=float(P("radius")) * s * SS, outline=col, width=width)
        else:
            part = trim_path(outline, progress)
            if len(part) >= 2:
                sp = [(x * SS, y * SS) for x, y in part]
                d.line(sp, fill=col, width=width, joint="curve")
                rad = width / 2
                for (cx, cy) in (sp[0], sp[-1]):
                    d.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=col)
                if kind == "arrow" and len(part) >= 2:
                    (ax, ay), (bx, by) = part[-2], part[-1]
                    ang = math.atan2(by - ay, bx - ax)
                    hl = (sw if sw > 0 else 4 * s) * 3 + 6 * s
                    tip = (bx, by)
                    left = (bx - hl * math.cos(ang - 0.5), by - hl * math.sin(ang - 0.5))
                    right = (bx - hl * math.cos(ang + 0.5), by - hl * math.sin(ang + 0.5))
                    d.polygon([(p[0] * SS, p[1] * SS) for p in (tip, left, right)], fill=col)

    out = im.resize((W, H), Image.LANCZOS)
    return out, (x0, y0, w, h), default_pos
