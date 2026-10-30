"""Kare panosu (contact sheet): videonun önemli anlarını tek PNG'de toplar.

Claude bu görsele bakarak çıktısını kontrol eder (taşan yazı, üst üste binen öğeler…).
"""
from __future__ import annotations

import math

from PIL import Image, ImageDraw

from . import model
from .lint import safe_margins
from .render import Renderer
from .util import load_font


def key_times(project: dict, comp_id=None, count: int = 12) -> list[float]:
    """Eşit aralıklı anlar + katmanların tam göründüğü anlar (en fazla `count`)."""
    comp = model.get_comp(project, comp_id)
    dur = model.comp_duration(comp)
    if dur <= 0:
        return [0.0]
    times = {round(dur * (i + 0.5) / count, 2) for i in range(count)}
    for layer in comp["layers"]:
        if layer["type"] in ("audio",):
            continue
        tr = layer.get("transition_in")
        t_in = float(tr.get("duration", 0.5)) if isinstance(tr, dict) else 0.0
        times.add(round(min(layer["start"] + layer["duration"] * 0.98,
                            layer["start"] + max(0.6, t_in + 0.1)), 2))
    times = sorted(t for t in times if 0 <= t < dur)
    min_gap = dur / (count * 3)
    deduped: list[float] = []
    for t in times:
        if not deduped or t - deduped[-1] >= min_gap:
            deduped.append(t)
    times = deduped
    if len(times) > count:
        step = len(times) / count
        times = [times[int(i * step)] for i in range(count)]
    return times


def contact_sheet(project: dict, base_dir=None, out_path="sheet.png", times=None, comp_id=None,
                  cols: int | None = None, thumb_w: int = 360, guides: bool = True,
                  count: int = 12) -> dict:
    project = model.normalize(model.clone(project))
    comp = model.get_comp(project, comp_id)
    W, H = model.comp_size(project, comp)
    times = list(times) if times else key_times(project, comp_id, count)
    scale = thumb_w / W
    r = Renderer(project, base_dir, scale=scale, preview=True)
    thumbs = []
    try:
        for t in times:
            img = r.render_image(t, comp_id)
            bg = Image.new("RGBA", img.size, (0, 0, 0, 255))
            bg.alpha_composite(img)
            thumbs.append(bg.convert("RGB"))
    finally:
        r.close()
    tw, th = thumbs[0].size
    cols = cols or min(len(thumbs), 6 if H <= W else 6)
    rows = math.ceil(len(thumbs) / cols)
    label_h = 28
    gap = 10
    sheet = Image.new("RGB", (cols * (tw + gap) + gap, rows * (th + label_h + gap) + gap + 40),
                      (24, 24, 28))
    d = ImageDraw.Draw(sheet)
    font = load_font("consolas", 18)
    d.text((gap, 10), f"{project.get('name', '')}  —  {W}x{H}  {project.get('fps')}fps  "
                      f"{model.comp_duration(comp):.2f}s", fill=(220, 220, 230), font=font)
    m = safe_margins(W, H)
    for i, (t, im) in enumerate(zip(times, thumbs)):
        x = gap + (i % cols) * (tw + gap)
        y = 40 + gap + (i // cols) * (th + label_h + gap)
        sheet.paste(im, (x, y))
        if guides:
            gx0, gy0 = x + tw * m["left"], y + th * m["top"]
            gx1, gy1 = x + tw * (1 - m["right"]), y + th * (1 - m["bottom"])
            d.rectangle([gx0, gy0, gx1, gy1], outline=(255, 214, 10), width=1)
        d.text((x, y + th + 4), f"#{i + 1}  t={t:.2f}s", fill=(200, 200, 210), font=font)
    sheet.save(out_path)
    return {"path": str(out_path), "times": times, "warnings": r.warnings}
