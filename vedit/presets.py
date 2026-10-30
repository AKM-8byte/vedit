"""Hazır animasyonlar. Bir katmana keyframe olarak "pişirilir"; sonra arayüzde düzenlenebilir.

    apply_preset(layer, "pop_in", at=0, duration=0.5)
"""
from __future__ import annotations

from . import model

# isim → (etiket, kategori, varsayılan süre)
PRESETS: dict[str, tuple[str, str, float]] = {
    "fade_in": ("Belir", "giriş", 0.5),
    "pop_in": ("Pop", "giriş", 0.5),
    "zoom_in": ("Yakınlaş", "giriş", 0.6),
    "slide_in_left": ("Soldan gel", "giriş", 0.6),
    "slide_in_right": ("Sağdan gel", "giriş", 0.6),
    "slide_in_up": ("Aşağıdan gel", "giriş", 0.6),
    "slide_in_down": ("Yukarıdan gel", "giriş", 0.6),
    "bounce_in": ("Zıplayarak", "giriş", 0.8),
    "drop_in": ("Düşerek", "giriş", 0.9),
    "spin_in": ("Dönerek", "giriş", 0.7),
    "flip_in": ("Çevrilerek", "giriş", 0.5),
    "blur_in": ("Bulanıktan", "giriş", 0.6),
    "typewriter": ("Daktilo", "yazı", 0.0),
    "rise_words": ("Kelime kelime yüksel", "yazı", 0.0),
    "rise_chars": ("Harf harf yüksel", "yazı", 0.0),
    "pop_chars": ("Harf harf pop", "yazı", 0.0),
    "wave_text": ("Dalgalanan yazı", "yazı", 0.0),
    "decode_text": ("Şifre çözme", "yazı", 0.0),
    "write_text": ("El yazısı", "yazı", 0.0),
    "highlight_words": ("Kelime vurgulama", "yazı", 0.0),
    "glitch_text": ("Glitch yazı", "yazı", 0.0),
    "count_up": ("Sayaç", "yazı", 1.5),
    "draw_on": ("Çizerek belir", "şekil", 1.0),
    "fade_out": ("Kaybol", "çıkış", 0.5),
    "pop_out": ("Pop çıkış", "çıkış", 0.4),
    "zoom_out": ("Uzaklaşarak çık", "çıkış", 0.5),
    "slide_out_left": ("Sola çık", "çıkış", 0.5),
    "slide_out_right": ("Sağa çık", "çıkış", 0.5),
    "slide_out_up": ("Yukarı çık", "çıkış", 0.5),
    "slide_out_down": ("Aşağı çık", "çıkış", 0.5),
    "blur_out": ("Bulanıklaşarak çık", "çıkış", 0.5),
    "float": ("Süzülme", "sürekli", 0.0),
    "pulse": ("Nabız", "sürekli", 0.0),
    "heartbeat": ("Kalp atışı", "sürekli", 0.0),
    "shake": ("Titreme", "vurgu", 0.5),
    "wiggle": ("Kıpırdama", "sürekli", 0.0),
    "swing": ("Sallanma", "sürekli", 0.0),
    "spin": ("Sürekli dönme", "sürekli", 0.0),
    "ken_burns": ("Ken Burns (yavaş zoom)", "sürekli", 0.0),
}


def _base(layer, name, t):
    return model.prop(layer, name, t)


def _pos(layer, name):
    v = layer.get("props", {}).get(name)
    if v is None:
        return None
    return model.value_at(v, 0)


def _kf(layer, name, pairs, ease="out_cubic"):
    """pairs: [(t, değer), ...] — her keyframe'e aynı ease uygulanır."""
    for t, v in pairs:
        model.set_keyframe(layer, name, round(t, 4), v, ease)


def apply_preset(layer: dict, name: str, at: float | None = None, duration: float | None = None,
                 **opts) -> dict:
    if name not in PRESETS:
        raise KeyError(f"Bilinmeyen hazır animasyon: {name}. Seçenekler: {', '.join(PRESETS)}")
    label, cat, d0 = PRESETS[name]
    d = float(duration if duration is not None else d0)
    L = layer["duration"]
    if at is None:
        at = max(0.0, L - d) if cat == "çıkış" else 0.0
    a = float(at)
    e = a + d
    dist = float(opts.get("distance", 300))
    ease = opts.get("ease")

    if name == "fade_in":
        _kf(layer, "opacity", [(a, 0.0), (e, _base(layer, "opacity", e))], ease or "out_cubic")
    elif name == "fade_out":
        _kf(layer, "opacity", [(a, _base(layer, "opacity", a)), (e, 0.0)], ease or "in_cubic")
    elif name in ("pop_in", "zoom_in", "bounce_in"):
        s1 = _base(layer, "scale", e)
        start = {"pop_in": 0.0, "zoom_in": 0.6, "bounce_in": 0.0}[name]
        eas = {"pop_in": "out_back", "zoom_in": "out_cubic", "bounce_in": "out_elastic"}[name]
        _kf(layer, "scale", [(a, start * s1), (e, s1)], ease or eas)
        _kf(layer, "opacity", [(a, 0.0), (a + d * 0.4, _base(layer, "opacity", e))], "linear")
    elif name in ("pop_out", "zoom_out"):
        s0 = _base(layer, "scale", a)
        _kf(layer, "scale", [(a, s0), (e, 0.0 if name == "pop_out" else s0 * 1.4)],
            ease or ("in_back" if name == "pop_out" else "in_cubic"))
        _kf(layer, "opacity", [(a + d * 0.5, _base(layer, "opacity", a)), (e, 0.0)], "linear")
    elif name.startswith("slide_in_") or name.startswith("slide_out_"):
        side = name.split("_")[-1]
        axis = "x" if side in ("left", "right") else "y"
        sign = {"left": -1, "right": 1, "up": 1, "down": -1}[side]
        if name.startswith("slide_out_"):
            sign = {"left": -1, "right": 1, "up": -1, "down": 1}[side]
        base = _pos(layer, axis)
        if base is None:
            base = opts.get("base", 540 if axis == "x" else 960)
        off = base + sign * dist
        if name.startswith("slide_in_"):
            _kf(layer, axis, [(a, off), (e, base)], ease or "out_cubic")
            _kf(layer, "opacity", [(a, 0.0), (a + d * 0.5, _base(layer, "opacity", e))], "linear")
        else:
            _kf(layer, axis, [(a, base), (e, off)], ease or "in_cubic")
            _kf(layer, "opacity", [(a + d * 0.4, _base(layer, "opacity", a)), (e, 0.0)], "linear")
    elif name == "drop_in":
        base = _pos(layer, "y") or opts.get("base", 960)
        _kf(layer, "y", [(a, base - dist * 2), (e, base)], ease or "out_bounce")
        _kf(layer, "opacity", [(a, 0.0), (a + d * 0.2, 1.0)], "linear")
    elif name == "spin_in":
        r1 = _base(layer, "rotation", e)
        _kf(layer, "rotation", [(a, r1 - 360), (e, r1)], ease or "out_cubic")
        _kf(layer, "scale", [(a, 0.0), (e, _base(layer, "scale", e))], ease or "out_back")
    elif name == "flip_in":
        _kf(layer, "scale_x", [(a, 0.0), (e, 1.0)], ease or "out_back")
    elif name in ("blur_in", "blur_out"):
        radius = float(opts.get("radius", 30))
        pairs = [(a, radius), (e, 0.0)] if name == "blur_in" else [(a, 0.0), (e, radius)]
        layer.setdefault("effects", []).append(
            {"type": "blur", "params": {"radius": {"keyframes": [
                {"t": pairs[0][0], "v": pairs[0][1], "ease": "out_cubic"},
                {"t": pairs[1][0], "v": pairs[1][1]}]}}})
        if name == "blur_in":
            _kf(layer, "opacity", [(a, 0.0), (a + d * 0.6, 1.0)], "linear")
        else:
            _kf(layer, "opacity", [(a + d * 0.4, 1.0), (e, 0.0)], "linear")
    elif name in ("typewriter", "rise_words", "rise_chars", "pop_chars", "wave_text",
                  "decode_text", "write_text", "highlight_words", "glitch_text"):
        cfg = {
            "typewriter": {"type": "typewriter", "unit": "char", "stagger": 0.05},
            "rise_words": {"type": "rise", "unit": "word", "stagger": 0.12, "duration": 0.45},
            "rise_chars": {"type": "rise", "unit": "char", "stagger": 0.03, "duration": 0.4},
            "pop_chars": {"type": "pop", "unit": "char", "stagger": 0.04, "duration": 0.35},
            "wave_text": {"type": "wave", "unit": "char", "amplitude": 0.12, "speed": 1.0},
            "decode_text": {"type": "decode", "unit": "char", "stagger": 0.04, "duration": 0.5},
            "write_text": {"type": "write", "unit": "char", "stagger": 0.06, "duration": 0.15},
            "highlight_words": {"type": "highlight", "unit": "word", "stagger": 0.35},
            "glitch_text": {"type": "glitch", "unit": "char", "stagger": 0.02, "duration": 0.5},
        }[name]
        cfg = {**cfg, "delay": a, **{k: v for k, v in opts.items() if k in (
            "stagger", "duration", "unit", "color", "amplitude", "speed", "ease")}}
        if duration:
            # süre verildiyse stagger'ı yazının tamamı o sürede bitecek şekilde ayarla
            text = str(model.value_at(layer.get("props", {}).get("text", ""), 0) or "")
            n = len(text) if cfg["unit"] == "char" else max(1, len(text.split()))
            cfg["stagger"] = max(0.005, (d - float(cfg.get("duration", 0.3))) / max(1, n))
        layer["char_anim"] = cfg
    elif name == "count_up":
        target = opts.get("to")
        if target is None:
            target = model.value_at(layer.get("props", {}).get("value"), 0)
        if target is None:
            try:
                target = float(str(model.value_at(layer["props"].get("text", "0"), 0)).replace(
                    ".", "").replace(",", "."))
            except ValueError:
                target = 100
        layer.setdefault("counter", {"decimals": int(opts.get("decimals", 0))})
        _kf(layer, "value", [(a, float(opts.get("from", 0))), (e, float(target))],
            ease or "out_cubic")
    elif name == "draw_on":
        _kf(layer, "progress", [(a, 0.0), (e, 1.0)], ease or "in_out_cubic")
    elif name == "float":
        amp = float(opts.get("amplitude", 15))
        base = _pos(layer, "y")
        base = 960 if base is None else base
        layer["props"]["y"] = {"expr": f"{base} + sin(t*{float(opts.get('speed', 1.5))}*2*pi)*{amp}"}
    elif name == "pulse":
        s = _base(layer, "scale", 0)
        layer["props"]["scale"] = {"expr": f"{s} * (1 + 0.06*sin(t*{float(opts.get('speed', 2))}*2*pi))"}
    elif name == "heartbeat":
        s = _base(layer, "scale", 0)
        layer["props"]["scale"] = {"expr": f"{s} * (1 + 0.12*max(0, sin(t*2*pi*1.2))**8)"}
    elif name == "wiggle":
        amp = float(opts.get("amplitude", 12))
        bx = _pos(layer, "x") or 540
        by = _pos(layer, "y") or 960
        f = float(opts.get("speed", 3))
        layer["props"]["x"] = {"expr": f"{bx} + wiggle({f}, {amp})"}
        layer["props"]["y"] = {"expr": f"{by} + wiggle({f}, {amp}, 7)"}
    elif name == "swing":
        amp = float(opts.get("amplitude", 8))
        layer["props"]["rotation"] = {"expr": f"sin(t*{float(opts.get('speed', 1))}*2*pi)*{amp}"}
    elif name == "spin":
        layer["props"]["rotation"] = {"expr": f"t*{float(opts.get('speed', 90))}"}
    elif name == "shake":
        amp = float(opts.get("amplitude", 14))
        bx = _pos(layer, "x") or 540
        layer["props"]["x"] = {"expr": f"{bx} + (sin(t*60)*{amp}*max(0, 1-(t-{a})/{max(d, 0.01)})"
                                       f" if {a} <= t <= {e} else 0)"}
    elif name == "ken_burns":
        s0 = _base(layer, "scale", 0)
        _kf(layer, "scale", [(0.0, s0), (L, s0 * float(opts.get("zoom", 1.15)))], "linear")
    return layer


def list_presets() -> list[dict]:
    return [{"name": k, "label": v[0], "category": v[1], "duration": v[2]} for k, v in PRESETS.items()]
