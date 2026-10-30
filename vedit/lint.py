"""Kalite kontrolü: projede izleyiciyi rahatsız edecek sorunları bulur.

Claude üretimden sonra `vedit lint proje.vedit.json` çalıştırıp çıkan uyarıları düzeltir.
"""
from __future__ import annotations

import os

from . import model
from .media import probe
from .render import anchored
from .util import resolve_path

READ_WPS = 3.0  # saniyede okunabilen kelime


def safe_margins(w: int, h: int) -> dict:
    """Kenarlardan güvenli boşluk oranları. Dikey videoda platform arayüzü için alt/sağ geniş."""
    if h > w * 1.4:
        return {"left": 0.06, "right": 0.12, "top": 0.08, "bottom": 0.20}
    return {"left": 0.05, "right": 0.05, "top": 0.05, "bottom": 0.05}


def _issue(level, where, msg):
    return {"level": level, "where": where, "msg": msg}


def lint(project: dict, base_dir=None, render_check: bool = True) -> list[dict]:
    project = model.normalize(model.clone(project))
    issues = [_issue("error", "proje", e) for e in model.validate(project)]
    if issues:
        return issues
    renderer = None
    if render_check:
        from .render import Renderer

        renderer = Renderer(project, base_dir, scale=0.5)

    for cid, comp in project["comps"].items():
        W, H = model.comp_size(project, comp)
        dur = model.comp_duration(comp)
        margins = safe_margins(W, H)
        for layer in comp["layers"]:
            where = f"{cid}/{layer.get('name')} ({layer['id']})"
            t = layer["type"]
            if not layer.get("enabled", True):
                continue
            if layer["start"] >= dur - 1e-3:
                issues.append(_issue("warning", where, f"Katman sahne bittikten sonra başlıyor "
                                                       f"(başlangıç {layer['start']:.2f}s, sahne {dur:.2f}s)"))
            elif model.layer_end(layer) > dur + 1e-3:
                issues.append(_issue("info", where, "Katman sahne süresinden uzun; sonu kesilecek"))
            for key in ("src", "script"):
                if layer.get(key):
                    p = resolve_path(layer[key], base_dir)
                    if not p or not os.path.exists(p):
                        issues.append(_issue("error", where, f"Dosya bulunamadı: {layer[key]}"))
            for side in ("transition_in", "transition_out"):
                tr = layer.get(side)
                if isinstance(tr, dict) and float(tr.get("duration", 0.5)) > layer["duration"] / 2:
                    issues.append(_issue("warning", where, f"{side} süresi katmanın yarısından uzun"))
            for name, v in layer.get("props", {}).items():
                if isinstance(v, dict) and v.get("keyframes"):
                    last = v["keyframes"][-1]["t"]
                    if last > layer["duration"] + 1e-3:
                        issues.append(_issue("info", where, f"'{name}' keyframe'i katman bittikten "
                                                            f"sonra ({last:.2f}s) — görünmeyecek"))
            if t == "video" and layer.get("src"):
                p = resolve_path(layer["src"], base_dir)
                if p and os.path.exists(p) and not layer.get("loop"):
                    try:
                        src_dur = probe(p)["duration"]
                        need = float(layer.get("in", 0)) + layer["duration"] * float(layer.get("speed", 1))
                        if src_dur and need > src_dur + 0.1:
                            issues.append(_issue("warning", where,
                                                 f"Video kaynağı {src_dur:.2f}s ama {need:.2f}s "
                                                 "isteniyor; son kare donacak"))
                    except Exception:  # noqa: BLE001
                        pass
            if t == "comp" and not layer.get("loop"):
                sub = project["comps"].get(layer.get("comp"))
                if sub:
                    need = float(layer.get("in", 0)) + layer["duration"] * float(layer.get("speed", 1))
                    if need > model.comp_duration(sub) + 0.05:
                        issues.append(_issue("warning", where, "Alt sahne katmandan kısa; sonunda boş "
                                                               "kalacak"))
            if t == "text":
                text = str(model.value_at(layer["props"].get("text", ""), 0) or "")
                words = len(text.split())
                if layer["duration"] < 1.2 and words > 0:
                    issues.append(_issue("warning", where, f"Yazı sadece {layer['duration']:.2f}s "
                                                           "ekranda; en az 1.2s önerilir"))
                elif words and layer["duration"] < words / READ_WPS:
                    issues.append(_issue("warning", where, f"{words} kelime {layer['duration']:.1f}s'de "
                                                           f"okunamaz (~{words / READ_WPS:.1f}s gerekir)"))
                # animasyonlu değerlerde son (yerleşmiş) değere bak
                size = model.value_at(layer["props"].get("size", 80), layer["duration"]) or 80
                sc = model.value_at(layer["props"].get("scale", 1), layer["duration"] * 0.5)
                sc = sc if isinstance(sc, (int, float)) and sc > 0 else 1
                if isinstance(size, (int, float)) and size * sc < W * 0.03:
                    issues.append(_issue("warning", where, f"Yazı boyutu ({size}) küçük; telefonda "
                                                           "okunmayabilir"))
            if renderer is not None and t in ("text", "shape", "image") and comp is not None:
                issues += _bounds_check(renderer, project, comp, layer, W, H, margins, where)

        if cid == project["main"]:
            issues += _gap_check(comp, dur)
    if renderer is not None:
        for w in renderer.warnings:
            issues.append(_issue("warning", "render", w))
        renderer.close()
    return issues


def _bounds_check(r, project, comp, layer, W, H, margins, where):
    """Katmanın ekran üzerindeki kutusunu tam görünür olduğu anda ölçer."""
    out = []
    tr = layer.get("transition_in")
    t_in = float(tr.get("duration", 0.5)) if isinstance(tr, dict) else 0.0
    probe_t = min(layer["duration"] * 0.999, max(t_in + 0.05, layer["duration"] * 0.5))
    if layer.get("char_anim"):
        from .render.text import char_anim_duration

        probe_t = min(layer["duration"] * 0.999, max(probe_t, char_anim_duration(layer)))
    try:
        r._current_theme = r.theme_for(comp)
        res = r.layer_content(layer, probe_t, int(W * r.scale), int(H * r.scale))
    except Exception:  # noqa: BLE001
        return out
    if res is None:
        return out
    img, origin, default_pos = res
    bbox = img.getbbox()
    if not bbox:
        return out
    P = lambda n: model.prop(layer, n, probe_t)  # noqa: E731
    ox, oy, bw, bh = origin
    ax, ay = ox + float(P("anchor_x")) * bw, oy + float(P("anchor_y")) * bh
    x, y = P("x"), P("y")
    if x is None:
        x = anchored(default_pos, 0, P("anchor_x")) if default_pos else W / 2
    if y is None:
        y = anchored(default_pos, 1, P("anchor_y")) if default_pos else H / 2
    s = r.scale
    sx = float(P("scale")) * float(P("scale_x"))
    sy = float(P("scale")) * float(P("scale_y"))
    left = x + (bbox[0] - ax) / s * sx
    right = x + (bbox[2] - ax) / s * sx
    top = y + (bbox[1] - ay) / s * sy
    bottom = y + (bbox[3] - ay) / s * sy
    if abs(float(P("rotation")) % 360) > 1:
        return out
    if layer["type"] == "image" and (bw / s >= W * 0.9 or bh / s >= H * 0.9):
        return out  # arka plan görseli
    if right < 0 or left > W or bottom < 0 or top > H:
        out.append(_issue("info", where, "Katman tam görünür anında ekran dışında"))
        return out
    if left < 0 or right > W or top < 0 or bottom > H:
        out.append(_issue("warning", where, f"Ekrandan taşıyor (kutu {left:.0f},{top:.0f} → "
                                            f"{right:.0f},{bottom:.0f}; ekran {W}x{H})"))
    elif layer["type"] == "text":
        m = margins
        if left < W * m["left"] or right > W * (1 - m["right"]) or top < H * m["top"] or \
                bottom > H * (1 - m["bottom"]):
            out.append(_issue("warning", where, "Yazı güvenli alanın dışında; platform arayüzü "
                                                "(başlık, butonlar) kapatabilir"))
    return out


def _gap_check(comp, dur):
    visible = sorted((l["start"], model.layer_end(l)) for l in comp["layers"]
                     if l.get("enabled", True) and l["type"] != "audio")
    if comp.get("background") not in (None, "#000000", "#000", "black", "#00000000"):
        return []
    out = []
    cur = 0.0
    for s, e in visible:
        if s > cur + 0.1:
            out.append(_issue("warning", "ana sahne", f"{cur:.2f}s – {s:.2f}s arası boş (siyah ekran)"))
        cur = max(cur, e)
    if dur > cur + 0.1:
        out.append(_issue("warning", "ana sahne", f"{cur:.2f}s – {dur:.2f}s arası boş (siyah ekran)"))
    return out


def format_issues(issues: list[dict]) -> str:
    if not issues:
        return "✓ Sorun bulunamadı"
    icon = {"error": "✗ HATA", "warning": "! UYARI", "info": "i BİLGİ"}
    return "\n".join(f"{icon[i['level']]:8} {i['where']}: {i['msg']}" for i in issues)
