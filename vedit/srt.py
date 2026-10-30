"""SRT altyazı içe/dışa aktarma."""
from __future__ import annotations

import re

from . import model

_TIME = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")


def _sec(h, m, s, ms):
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms.ljust(3, "0")[:3]) / 1000


def _fmt(t: float) -> str:
    ms = int(round(t * 1000))
    h, ms = divmod(ms, 3600000)
    m, ms = divmod(ms, 60000)
    s, ms = divmod(ms, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def parse_srt(text: str) -> list[tuple[float, float, str]]:
    out = []
    for block in re.split(r"\r?\n\s*\r?\n", text.strip()):
        lines = [l for l in block.splitlines() if l.strip()]
        for i, line in enumerate(lines):
            m = _TIME.search(line)
            if m:
                g = m.groups()
                body = "\n".join(lines[i + 1:]).strip()
                body = re.sub(r"<[^>]+>", "", body)
                if body:
                    out.append((_sec(*g[:4]), _sec(*g[4:]), body))
                break
    return out


def import_srt(project: dict, path: str, comp_id=None, style: str = "caption",
               track: int = 900) -> int:
    with open(path, "r", encoding="utf-8-sig") as f:
        cues = parse_srt(f.read())
    comp = model.get_comp(project, comp_id)
    W, H = model.comp_size(project, comp)
    u = min(W, H) / 1080
    y = H * (0.66 if H > W else 0.86)
    for start, end, text in cues:
        props = {"text": text, "size": 64 * u, "y": y, "max_width": W * 0.84,
                 "stroke_width": 5 * u, "stroke_color": "#000000"}
        if style == "plain":
            props.update(stroke_width=0, bg_color="#000000aa", bg_padding=16 * u, size=52 * u)
        layer = model.new_layer("text", start, max(0.2, end - start), track, name="Altyazı",
                                props=props)
        layer["subtitle"] = True
        if style == "highlight":
            words = max(1, len(text.split()))
            layer["char_anim"] = {"type": "highlight", "unit": "word",
                                  "stagger": (end - start) / words, "color": "#ffd60a"}
        elif style == "caption":
            layer["char_anim"] = {"type": "pop", "unit": "word", "stagger": 0.06, "duration": 0.25}
        comp["layers"].append(layer)
    comp["duration"] = max(model.comp_duration(comp), max((c[1] for c in cues), default=0))
    return len(cues)


def export_srt(project: dict, path: str, comp_id=None) -> int:
    comp = model.get_comp(project, comp_id)
    subs = [l for l in comp["layers"] if l["type"] == "text" and l.get("subtitle")]
    if not subs:
        subs = [l for l in comp["layers"] if l["type"] == "text"]
    subs.sort(key=lambda l: l["start"])
    with open(path, "w", encoding="utf-8") as f:
        for i, l in enumerate(subs, 1):
            text = str(model.value_at(l["props"].get("text", ""), 0) or "")
            f.write(f"{i}\n{_fmt(l['start'])} --> {_fmt(model.layer_end(l))}\n{text}\n\n")
    return len(subs)
