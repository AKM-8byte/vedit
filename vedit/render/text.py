"""Yazı katmanı render'ı: satır kaydırma, kontur, gölge, arka kutu, harf harf animasyon.

Harf animasyonu katmanda `char_anim` alanıyla tanımlanır:

    "char_anim": {"type": "rise", "unit": "char", "stagger": 0.04, "duration": 0.4,
                  "delay": 0, "ease": "out_cubic"}

Türler: typewriter, fade, rise, drop, pop, wave, decode, write, blur, glitch, highlight.
`unit`: char | word | line.
"""
from __future__ import annotations

import functools
import math
import random

from PIL import Image, ImageDraw, ImageFilter

from .. import easing
from ..model import value_at
from ..util import stable_hash

CHAR_ANIMS = {
    "typewriter": "Daktilo",
    "fade": "Harf harf belirme",
    "rise": "Aşağıdan yüksel",
    "drop": "Yukarıdan düş",
    "pop": "Pop",
    "wave": "Dalga (sürekli)",
    "decode": "Şifre çözme (matrix)",
    "write": "El yazısı gibi",
    "blur": "Bulanıktan netleş",
    "glitch": "Glitch",
    "highlight": "Kelime vurgulama (karaoke)",
}

DECODE_CHARS = "01ABCDEFGHIJKLMNOPQRSTUVWXYZ#$%&*+=<>?/\\|"
MOTION_ANIMS = {"rise", "drop", "pop", "wave", "glitch", "highlight", "write"}


def format_counter(value, cfg: dict) -> str:
    dec = int(cfg.get("decimals", 0))
    try:
        v = float(value)
    except (TypeError, ValueError):
        return str(value)
    s = f"{v:,.{dec}f}" if cfg.get("thousands", True) else f"{v:.{dec}f}"
    if cfg.get("locale", "tr") == "tr":
        s = s.replace(",", "\0").replace(".", ",").replace("\0", ".")
    return f"{cfg.get('prefix', '')}{s}{cfg.get('suffix', '')}"


def _wrap(text: str, font, max_w: float, ls: float) -> list[str]:
    lines: list[str] = []
    for para in text.split("\n"):
        if max_w <= 0:
            lines.append(para)
            continue
        words = para.split(" ")
        cur = ""
        for w in words:
            trial = (cur + " " + w) if cur else w
            if _line_width(trial, font, ls) <= max_w or not cur:
                cur = trial
            else:
                lines.append(cur)
                cur = w
        lines.append(cur)
    return lines


def _line_width(line: str, font, ls: float) -> float:
    if not line:
        return 0.0
    return font.getlength(line) + ls * max(0, len(line) - 1)


@functools.lru_cache(maxsize=4096)
def _glyph(ch: str, font, color: tuple, stroke_w: int, stroke_color: tuple, pad: int):
    ascent, descent = font.getmetrics()
    w = int(math.ceil(font.getlength(ch))) + 2 * pad
    h = ascent + descent + 2 * pad
    im = Image.new("RGBA", (max(1, w), max(1, h)), (0, 0, 0, 0))
    ImageDraw.Draw(im).text((pad, pad + ascent), ch, font=font, fill=color, anchor="ls",
                            stroke_width=stroke_w, stroke_fill=stroke_color)
    return im


def render_text(r, layer: dict, lt: float):
    """→ (RGBA görüntü, origin=(ox, oy, bw, bh))"""
    s = r.scale
    P = functools.partial(r.text_prop, layer, t=lt)

    text = P("text")
    text = "" if text is None else str(text)
    counter = layer.get("counter")
    if counter is not None:
        val = P("value")
        if val is not None:
            text = format_counter(val, counter)

    size = max(1.0, float(P("size")) * s)
    font = r.font(P("font"), size)
    color = r.color(P("color"))
    sw = int(round(float(P("stroke_width") or 0) * s))
    sc = r.color(P("stroke_color"))
    ls = float(P("letter_spacing") or 0) * s
    lh = float(P("line_height") or 1.2) * size
    align = P("align") or "center"
    max_w = float(P("max_width") or 0) * s
    reveal = float(P("reveal") if P("reveal") is not None else 1.0)
    bg = P("bg_color")
    bg_pad = float(P("bg_padding") or 0) * s if bg else 0.0
    bg_rad = float(P("bg_radius") or 0) * s
    sh_col = r.color(P("shadow_color"))
    sh_x, sh_y = float(P("shadow_x") or 0) * s, float(P("shadow_y") or 0) * s
    sh_blur = float(P("shadow_blur") or 0) * s
    has_shadow = (sh_x or sh_y or sh_blur) and sh_col[3] > 0

    anim = r.char_anim(layer)
    lines = _wrap(text, font, max_w, ls)
    ascent, descent = font.getmetrics()
    widths = [_line_width(ln, font, ls) for ln in lines]
    block_w = max(widths + [1.0])
    block_h = lh * (len(lines) - 1) + ascent + descent

    margin = sw + 2
    if anim and anim.get("type") in MOTION_ANIMS:
        margin += int(size * 0.9)
    if has_shadow:
        margin += int(abs(sh_x) + abs(sh_y) + sh_blur * 2)
    W = int(math.ceil(block_w + 2 * (margin + bg_pad)))
    H = int(math.ceil(block_h + 2 * (margin + bg_pad)))
    tx0, ty0 = margin + bg_pad, margin + bg_pad  # metin bloğunun sol üstü

    glyphs = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    total_chars = sum(len(ln) for ln in lines)
    visible = reveal * total_chars

    if anim is None and ls == 0:
        _draw_simple(glyphs, lines, widths, block_w, align, tx0, ty0, ascent, lh, font, color, sw,
                     sc, visible)
    else:
        _draw_per_char(r, glyphs, layer, lines, widths, block_w, align, tx0, ty0, ascent, lh, font,
                       color, sw, sc, ls, visible, anim, lt, size)

    out = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    if bg:
        bx0, by0 = margin, margin
        ss = 2
        box = Image.new("RGBA", (W * ss, H * ss), (0, 0, 0, 0))
        ImageDraw.Draw(box).rounded_rectangle(
            [bx0 * ss, by0 * ss, (bx0 + block_w + 2 * bg_pad) * ss, (by0 + block_h + 2 * bg_pad) * ss],
            radius=bg_rad * ss, fill=r.color(bg))
        out.alpha_composite(box.resize((W, H), Image.LANCZOS))
    if has_shadow:
        a = glyphs.getchannel("A")
        if sh_col[3] < 255:
            a = a.point(lambda v: v * sh_col[3] // 255)
        shadow = Image.new("RGBA", (W, H), sh_col[:3] + (0,))
        shadow.putalpha(a)
        if sh_blur > 0.3:
            shadow = shadow.filter(ImageFilter.GaussianBlur(sh_blur))
        out.paste(shadow, (int(round(sh_x)), int(round(sh_y))), shadow)
    out.alpha_composite(glyphs)
    if bg:
        origin = (margin, margin, block_w + 2 * bg_pad, block_h + 2 * bg_pad)
    else:
        origin = (tx0, ty0, block_w, block_h)
    return out, origin


def _line_x(align, tx0, block_w, w):
    if align == "left":
        return tx0
    if align == "right":
        return tx0 + block_w - w
    return tx0 + (block_w - w) / 2


def _draw_simple(img, lines, widths, block_w, align, tx0, ty0, ascent, lh, font, color, sw, sc,
                 visible):
    d = ImageDraw.Draw(img)
    shown = 0
    for i, (ln, w) in enumerate(zip(lines, widths)):
        if shown >= visible:
            break
        part = ln[: max(0, int(visible - shown))] if shown + len(ln) > visible else ln
        shown += len(ln)
        x = _line_x(align, tx0, block_w, w)
        d.text((x, ty0 + ascent + i * lh), part, font=font, fill=color, anchor="ls",
               stroke_width=sw, stroke_fill=sc)


def _draw_per_char(r, img, layer, lines, widths, block_w, align, tx0, ty0, ascent, lh, font, color,
                   sw, sc, ls, visible, anim, lt, size):
    kind = (anim or {}).get("type")
    unit = (anim or {}).get("unit", "word" if kind == "highlight" else "char")
    stagger = float((anim or {}).get("stagger", 0.04 if unit == "char" else 0.15))
    dur = max(1e-3, float((anim or {}).get("duration", 0.4)))
    delay = float((anim or {}).get("delay", 0))
    ease_name = (anim or {}).get("ease", "out_back" if kind == "pop" else "out_cubic")
    hl_color = r.color((anim or {}).get("color", "#ffd60a"))
    seed = stable_hash(layer.get("id", "")) & 0xFFFF
    frame_no = int(lt * 30)
    pad = sw + 2

    char_i = word_i = 0
    count = 0
    for li, (ln, w) in enumerate(zip(lines, widths)):
        x = _line_x(align, tx0, block_w, w)
        base = ty0 + ascent + li * lh
        prev_space = True
        for ch in ln:
            if ch == " ":
                prev_space = True
            elif prev_space:
                if char_i > 0:
                    word_i += 1
                prev_space = False
            adv = font.getlength(ch)
            if count >= visible:
                return
            count += 1
            idx = {"char": char_i, "word": word_i, "line": li}.get(unit, char_i)
            char_i += 1
            if ch == " ":
                x += adv + ls
                continue
            local = lt - delay - idx * stagger
            p = 0.0 if local <= 0 else min(1.0, local / dur)
            ep = easing.apply(ease_name, p)
            dx = dy = 0.0
            sc_ = 1.0
            alpha = 1.0
            glyph_ch = ch
            col = color
            if kind == "typewriter":
                alpha = 1.0 if local >= 0 else 0.0
            elif kind == "fade":
                alpha = ep
            elif kind == "rise":
                dy = (1 - ep) * size * 0.6
                alpha = min(1.0, p * 1.5)
            elif kind == "drop":
                dy = -(1 - easing.apply("out_bounce", p)) * size * 0.8
                alpha = min(1.0, p * 3)
            elif kind == "pop":
                sc_ = max(0.0, ep)
                alpha = min(1.0, p * 3)
            elif kind == "wave":
                amp = float(anim.get("amplitude", 0.15)) * size
                speed = float(anim.get("speed", 1.0))
                dy = math.sin(lt * speed * math.tau - idx * 0.5) * amp
            elif kind == "decode":
                if local < 0:
                    alpha = 0.0
                elif p < 1:
                    rnd = random.Random(seed * 7919 + idx * 131 + frame_no // 2)
                    glyph_ch = rnd.choice(DECODE_CHARS)
                    col = (*col[:3], int(col[3] * 0.7))
            elif kind == "write":
                alpha = 1.0 if p > 0 else 0.0
            elif kind == "blur":
                alpha = min(1.0, p * 1.5)
            elif kind == "glitch":
                if p < 1:
                    rnd = random.Random(seed + idx * 17 + frame_no)
                    dx = rnd.uniform(-1, 1) * size * 0.3 * (1 - p)
                    alpha = 0.0 if local < 0 else (1.0 if rnd.random() > 0.3 * (1 - p) else 0.3)
            elif kind == "highlight":
                active = 0 <= local < stagger
                if active:
                    col = hl_color
                    sc_ = 1.0 + 0.12 * (1 - abs(local / stagger * 2 - 1))
            if alpha <= 0.01 or sc_ <= 0.01:
                x += adv + ls
                continue
            g = _glyph(glyph_ch, font, tuple(col), sw, tuple(sc), pad)
            if kind == "write" and p < 1:
                cw = max(1, int(g.width * ep))
                g2 = Image.new("RGBA", g.size, (0, 0, 0, 0))
                g2.paste(g.crop((0, 0, cw, g.height)), (0, 0))
                g = g2
            if kind == "blur" and p < 1:
                g = g.filter(ImageFilter.GaussianBlur((1 - p) * size * 0.15))
            if sc_ != 1.0:
                nw, nh = max(1, int(g.width * sc_)), max(1, int(g.height * sc_))
                gx = x - pad + (g.width - nw) / 2
                gy = base - ascent - pad + (g.height - nh) / 2
                g = g.resize((nw, nh), Image.BICUBIC)
            else:
                gx, gy = x - pad, base - ascent - pad
            if alpha < 1:
                g = g.copy()
                g.putalpha(g.getchannel("A").point(lambda v, a=alpha: int(v * a)))
            img.alpha_composite(g, (max(0, int(round(gx + dx))), max(0, int(round(gy + dy)))))
            x += adv + ls


def char_anim_duration(layer: dict) -> float:
    """Harf animasyonunun bitmesi için gereken süre (lint için)."""
    a = layer.get("char_anim")
    if not a:
        return 0.0
    text = str(value_at(layer.get("props", {}).get("text", ""), 0) or "")
    n = len(text) if a.get("unit", "char") == "char" else len(text.split())
    return float(a.get("delay", 0)) + n * float(a.get("stagger", 0.04)) + float(a.get("duration", 0.4))
