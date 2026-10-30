"""Hazır şablonlar: birden çok katmandan oluşan, tek komutla eklenen öğeler.

    layers = make_template("lower_third", W=1080, H=1920, at=2, title="Ahmet", subtitle="Kurucu")
"""
from __future__ import annotations

from . import model
from .presets import apply_preset

TEMPLATES: dict[str, dict] = {
    "title_card": {"label": "Başlık kartı", "params": {"title": "Başlık", "subtitle": "Alt başlık",
                                                      "color": "#ffffff", "accent": "#ffd60a"},
                   "duration": 3.0},
    "lower_third": {"label": "Alt bant (isim)", "params": {"title": "İsim Soyisim",
                                                          "subtitle": "Unvan", "color": "#0a84ff"},
                    "duration": 4.0},
    "subscribe": {"label": "Abone ol butonu", "params": {"text": "ABONE OL",
                                                        "done_text": "ABONE OLUNDU ✓"},
                  "duration": 3.0},
    "counter": {"label": "Sayaç", "params": {"to": 1000, "label": "Takipçi", "prefix": "",
                                            "suffix": "", "color": "#ffffff"}, "duration": 3.0},
    "quote": {"label": "Alıntı kartı", "params": {"quote": "Alıntı metni buraya.",
                                                  "author": "Yazar"}, "duration": 5.0},
    "progress_bar": {"label": "İlerleme çubuğu", "params": {"color": "#ff375f", "height": 12},
                     "duration": 10.0},
    "caption": {"label": "Altyazı (vurgulu)", "params": {"text": "Bu bir altyazı örneğidir",
                                                         "highlight": "#ffd60a"}, "duration": 3.0},
    "countdown": {"label": "Geri sayım", "params": {"from": 3, "color": "#ffffff"},
                  "duration": 3.0},
    "callout": {"label": "Ok + açıklama", "params": {"text": "Buraya bak!", "x": 700, "y": 600},
                "duration": 3.0},
    "end_screen": {"label": "Bitiş ekranı", "params": {"text": "İzlediğiniz için teşekkürler!"},
                   "duration": 5.0},
    "logo_reveal": {"label": "Logo gösterimi", "params": {"src": "brand/logo.png",
                                                          "text": ""}, "duration": 3.0},
}


def _L(type_, at, dur, track, **kw):
    return model.new_layer(type_, at, dur, track, **kw)


def make_template(name: str, W: int = 1080, H: int = 1920, at: float = 0.0,
                  duration: float | None = None, track: int = 10, **params) -> list[dict]:
    if name not in TEMPLATES:
        raise KeyError(f"Bilinmeyen şablon: {name}. Seçenekler: {', '.join(TEMPLATES)}")
    meta = TEMPLATES[name]
    p = {**meta["params"], **params}
    d = float(duration or meta["duration"])
    cx, cy = W / 2, H / 2
    vertical = H > W
    u = min(W, H) / 1080  # ölçek birimi
    out: list[dict] = []

    if name == "title_card":
        t = _L("text", at, d, track, name="Başlık", props={
            "text": p["title"], "size": 120 * u, "y": cy - 60 * u, "color": p["color"],
            "max_width": W * 0.85, "shadow_y": 6, "shadow_blur": 12})
        apply_preset(t, "rise_chars", at=0.0)
        apply_preset(t, "fade_out", duration=0.4)
        line = _L("shape", at + 0.3, d - 0.3, track + 1, name="Çizgi", props={
            "shape": "line", "points": [[cx - 220 * u, cy + 30 * u], [cx + 220 * u, cy + 30 * u]],
            "stroke_color": p["accent"], "stroke_width": 8 * u})
        apply_preset(line, "draw_on", at=0, duration=0.7)
        apply_preset(line, "fade_out", duration=0.4)
        sub = _L("text", at + 0.6, d - 0.6, track + 2, name="Alt başlık", props={
            "text": p["subtitle"], "size": 56 * u, "y": cy + 100 * u, "color": p["color"],
            "opacity": 0.85, "max_width": W * 0.85})
        apply_preset(sub, "fade_in", duration=0.5)
        apply_preset(sub, "fade_out", duration=0.4)
        out += [t, line, sub]

    elif name == "lower_third":
        y = H * (0.72 if vertical else 0.8)
        x0 = W * 0.08
        bar = _L("shape", at, d, track, name="Bant", props={
            "shape": "rect", "w": W * 0.62, "h": 150 * u, "radius": 14 * u, "fill": p["color"],
            "anchor_x": 0, "x": x0, "y": y, "opacity": 0.95})
        apply_preset(bar, "flip_in", duration=0.4)
        bar["props"]["anchor_x"] = 0.0
        apply_preset(bar, "fade_out", duration=0.4)
        title = _L("text", at + 0.25, d - 0.25, track + 1, name="İsim", props={
            "text": p["title"], "size": 58 * u, "anchor_x": 0, "x": x0 + 36 * u, "y": y - 24 * u,
            "align": "left", "color": "#ffffff"})
        apply_preset(title, "slide_in_left", duration=0.5, distance=60)
        apply_preset(title, "fade_out", duration=0.4)
        sub = _L("text", at + 0.4, d - 0.4, track + 2, name="Unvan", props={
            "text": p["subtitle"], "size": 38 * u, "anchor_x": 0, "x": x0 + 36 * u,
            "y": y + 34 * u, "align": "left", "color": "#ffffffcc"})
        apply_preset(sub, "slide_in_left", duration=0.5, distance=60)
        apply_preset(sub, "fade_out", duration=0.4)
        out += [bar, title, sub]

    elif name == "subscribe":
        y = H * (0.68 if vertical else 0.78)
        btn = _L("shape", at, d, track, name="Buton", props={
            "shape": "rect", "w": 460 * u, "h": 120 * u, "radius": 60 * u, "y": y,
            "fill": {"keyframes": [{"t": 0, "v": "#ff0033"}, {"t": 1.2, "v": "#ff0033"},
                                   {"t": 1.35, "v": "#3a3a3c"}]}})
        apply_preset(btn, "pop_in", duration=0.5)
        model.set_keyframe(btn, "scale", 1.1, 1.0, "out_cubic")
        model.set_keyframe(btn, "scale", 1.2, 0.9, "out_back")
        model.set_keyframe(btn, "scale", 1.45, 1.0, "linear")
        apply_preset(btn, "pop_out", duration=0.35)
        txt = _L("text", at, d, track + 1, name="Buton yazısı", props={
            "text": {"keyframes": [{"t": 0, "v": p["text"]}, {"t": 1.3, "v": p["done_text"]}]},
            "size": 50 * u, "y": y, "color": "#ffffff", "font": "segoe bold"})
        apply_preset(txt, "pop_in", duration=0.5)
        apply_preset(txt, "pop_out", duration=0.35)
        cursor = _L("shape", at + 0.5, 1.2, track + 2, name="İmleç", props={
            "shape": "polygon", "sides": 3, "w": 50 * u, "h": 60 * u, "fill": "#ffffff",
            "stroke_color": "#000000", "stroke_width": 3, "rotation": -30,
            "x": {"keyframes": [{"t": 0, "v": cx + 300 * u, "ease": "out_cubic"},
                                {"t": 0.6, "v": cx + 120 * u}]},
            "y": {"keyframes": [{"t": 0, "v": y + 200 * u, "ease": "out_cubic"},
                                {"t": 0.6, "v": y + 30 * u}]}})
        apply_preset(cursor, "fade_out", duration=0.3)
        out += [btn, txt, cursor]

    elif name == "counter":
        num = _L("text", at, d, track, name="Sayı", props={
            "text": "0", "value": 0, "size": 160 * u, "y": cy - 40 * u, "color": p["color"],
            "font": "segoe black"}, counter={"prefix": p["prefix"], "suffix": p["suffix"],
                                             "decimals": 0})
        apply_preset(num, "count_up", at=0.1, duration=min(2.0, d * 0.7), to=p["to"])
        apply_preset(num, "pop_in", duration=0.4)
        lab = _L("text", at + 0.3, d - 0.3, track + 1, name="Etiket", props={
            "text": p["label"], "size": 60 * u, "y": cy + 90 * u, "color": p["color"],
            "opacity": 0.8})
        apply_preset(lab, "slide_in_up", duration=0.5, distance=40)
        out += [num, lab]

    elif name == "quote":
        mark = _L("text", at, d, track, name="Tırnak", props={
            "text": "“", "size": 260 * u, "y": cy - 300 * u, "color": "#ffd60a", "font": "georgia"})
        apply_preset(mark, "pop_in")
        q = _L("text", at + 0.3, d - 0.3, track + 1, name="Alıntı", props={
            "text": p["quote"], "size": 64 * u, "y": cy, "max_width": W * 0.8, "font": "georgia",
            "line_height": 1.35})
        apply_preset(q, "rise_words", at=0)
        a = _L("text", at + 1.2, d - 1.2, track + 2, name="Yazar", props={
            "text": "— " + p["author"], "size": 44 * u, "y": cy + 260 * u, "opacity": 0.75})
        apply_preset(a, "fade_in", duration=0.6)
        for layer in (mark, q, a):
            apply_preset(layer, "fade_out", duration=0.4)
        out += [mark, q, a]

    elif name == "progress_bar":
        h = float(p["height"]) * u
        bar = _L("shape", at, d, track, name="İlerleme", props={
            "shape": "rect", "w": W, "h": h, "fill": p["color"], "anchor_x": 0, "x": 0,
            "y": H - h / 2, "scale_x": {"keyframes": [{"t": 0, "v": 0.0}, {"t": d, "v": 1.0}]}})
        out += [bar]

    elif name == "caption":
        cap = _L("text", at, d, track, name="Altyazı", props={
            "text": p["text"], "size": 72 * u, "y": H * (0.62 if vertical else 0.85),
            "max_width": W * 0.82, "stroke_width": 6 * u, "font": "segoe black"})
        words = max(1, len(str(p["text"]).split()))
        cap["char_anim"] = {"type": "highlight", "unit": "word", "stagger": d / words,
                            "color": p["highlight"]}
        out += [cap]

    elif name == "countdown":
        n = int(p["from"])
        step = d / n
        for i in range(n):
            num = _L("text", at + i * step, step, track + i, name=f"Sayı {n - i}", props={
                "text": str(n - i), "size": 400 * u, "color": p["color"], "font": "segoe black"})
            apply_preset(num, "pop_in", duration=0.35)
            apply_preset(num, "zoom_out", duration=0.3)
            out.append(num)
        ring = _L("shape", at, d, track + n, name="Halka", props={
            "shape": "ellipse", "w": 560 * u, "h": 560 * u, "fill": None,
            "stroke_color": p["color"], "stroke_width": 10 * u,
            "progress": {"expr": f"1 - (t % {step}) / {step}"}})
        out.append(ring)

    elif name == "callout":
        tx, ty = float(p["x"]), float(p["y"])
        bx, by = tx - 260 * u, ty + 260 * u
        arrow = _L("shape", at, d, track, name="Ok", props={
            "shape": "arrow", "points": [[bx, by], [(bx + tx) / 2 + 40 * u, (by + ty) / 2 + 30 * u],
                                         [tx, ty]],
            "stroke_color": "#ffd60a", "stroke_width": 9 * u})
        apply_preset(arrow, "draw_on", duration=0.6)
        apply_preset(arrow, "fade_out", duration=0.3)
        lab = _L("text", at + 0.4, d - 0.4, track + 1, name="Açıklama", props={
            "text": p["text"], "size": 52 * u, "x": bx, "y": by + 60 * u, "color": "#000000",
            "bg_color": "#ffd60a", "bg_padding": 22 * u, "bg_radius": 18 * u})
        apply_preset(lab, "pop_in", duration=0.4)
        apply_preset(lab, "fade_out", duration=0.3)
        out += [arrow, lab]

    elif name == "end_screen":
        t = _L("text", at, d, track, name="Teşekkür", props={
            "text": p["text"], "size": 80 * u, "y": H * 0.25, "max_width": W * 0.85})
        apply_preset(t, "rise_words")
        out.append(t)
        for i, (x, label) in enumerate(((W * 0.3, "Sonraki video"), (W * 0.7, "Oynatma listesi"))):
            box = _L("shape", at + 0.3 + i * 0.15, d - 0.3 - i * 0.15, track + 1 + i,
                     name=label, props={"shape": "rect", "w": W * 0.36, "h": W * 0.36 * 9 / 16,
                                        "radius": 16 * u, "x": x, "y": H * 0.55,
                                        "fill": "#ffffff22", "stroke_color": "#ffffff",
                                        "stroke_width": 4 * u})
            apply_preset(box, "pop_in")
            lab = _L("text", at + 0.5 + i * 0.15, d - 0.5 - i * 0.15, track + 3 + i,
                     name=label + " yazı", props={"text": label, "size": 36 * u, "x": x,
                                                  "y": H * 0.55 + W * 0.13})
            apply_preset(lab, "fade_in")
            out += [box, lab]

    elif name == "logo_reveal":
        logo = _L("image", at, d, track, name="Logo", src=p["src"], props={"y": cy - 40 * u},
                  transition_in={"type": "circle", "duration": 0.8},
                  effects=[{"type": "glow", "params": {"radius": 30, "strength": 0.8}}])
        apply_preset(logo, "zoom_in", duration=1.0)
        apply_preset(logo, "fade_out", duration=0.4)
        out.append(logo)
        if p.get("text"):
            t = _L("text", at + 0.8, d - 0.8, track + 1, name="Logo yazısı", props={
                "text": p["text"], "size": 70 * u, "y": cy + 260 * u})
            apply_preset(t, "rise_chars")
            apply_preset(t, "fade_out", duration=0.4)
            out.append(t)
    return out


def list_templates() -> list[dict]:
    return [{"name": k, "label": v["label"], "params": v["params"], "duration": v["duration"]}
            for k, v in TEMPLATES.items()]
