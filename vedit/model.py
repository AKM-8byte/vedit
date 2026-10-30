"""Proje veri modeli.

Proje dosyası (.vedit.json) düz bir JSON'dur:

    {
      "version": 1, "name": "...", "width": 1080, "height": 1920, "fps": 30,
      "brand": "brand/brand.json",            # isteğe bağlı
      "theme": {"name": "matrix", "params": {}},   # isteğe bağlı
      "main": "main",
      "comps": {
        "main": {"name": "Ana", "duration": 10, "background": "#000000", "layers": [...]}
      }
    }

Katman:

    {"id": "l1", "type": "text", "name": "Başlık", "track": 1,
     "start": 0, "duration": 3, "props": {"text": "Merhaba", "y": 800, ...},
     "effects": [{"type": "glow", "params": {"radius": 20}}],
     "transition_in": {"type": "fade", "duration": 0.4}, "blend": "normal"}

Herhangi bir prop sabit bir değer, keyframe listesi ya da ifade olabilir:

    "opacity": 1
    "opacity": {"keyframes": [{"t": 0, "v": 0, "ease": "out_cubic"}, {"t": 0.5, "v": 1}]}
    "rotation": {"expr": "sin(t*3)*10"}

Keyframe zamanları katmanın başlangıcına görelidir.
"""
from __future__ import annotations

import copy
import hashlib
import json
import math
import random
import uuid
from pathlib import Path

from . import easing
from .util import color_to_hex, parse_color

VERSION = 1

LAYER_TYPES = ("video", "image", "text", "shape", "audio", "comp", "script", "adjustment", "solid")

COMMON_PROPS = {
    "x": None,  # None → kompozisyonun ortası
    "y": None,
    "anchor_x": 0.5,
    "anchor_y": 0.5,
    "scale": 1.0,
    "scale_x": 1.0,
    "scale_y": 1.0,
    "rotation": 0.0,
    "opacity": 1.0,
}

TYPE_PROPS = {
    "text": {
        "text": "",
        "font": None,
        "size": 80,
        "color": "#ffffff",
        "stroke_color": "#000000",
        "stroke_width": 0,
        "shadow_color": "#00000099",
        "shadow_x": 0,
        "shadow_y": 0,
        "shadow_blur": 0,
        "align": "center",
        "max_width": 0,
        "line_height": 1.2,
        "letter_spacing": 0,
        "bg_color": None,
        "bg_padding": 24,
        "bg_radius": 18,
        "reveal": 1.0,
        "value": None,
    },
    "shape": {
        "shape": "rect",
        "w": 400,
        "h": 200,
        "radius": 0,
        "fill": "#ffffff",
        "fill2": None,
        "gradient_angle": 90,
        "stroke_color": None,
        "stroke_width": 0,
        "points": [],
        "progress": 1.0,
        "sides": 5,
        "inner": 0.5,
    },
    "solid": {"color": "#000000", "fill2": None, "gradient_angle": 90},
    "image": {},
    "video": {},
    "comp": {},
    "script": {},
    "adjustment": {},
    "audio": {},
}

ANIMATABLE_HINT = {
    # Arayüzün sayı kaydırıcısı göstereceği proplar ve aralıkları
    "x": (-4000, 8000), "y": (-4000, 8000), "scale": (0, 10), "scale_x": (0, 10),
    "scale_y": (0, 10), "rotation": (-720, 720), "opacity": (0, 1), "anchor_x": (0, 1),
    "anchor_y": (0, 1), "size": (4, 600), "stroke_width": (0, 60), "shadow_x": (-100, 100),
    "shadow_y": (-100, 100), "shadow_blur": (0, 80), "max_width": (0, 4000),
    "line_height": (0.5, 3), "letter_spacing": (-20, 80), "bg_padding": (0, 200),
    "bg_radius": (0, 200), "reveal": (0, 1), "value": (-1e9, 1e9), "w": (0, 8000),
    "h": (0, 8000), "radius": (0, 2000), "progress": (0, 1), "sides": (3, 24),
    "inner": (0.05, 1), "gradient_angle": (0, 360),
}


# --------------------------------------------------------------------------- oluşturma


def new_id(prefix: str = "l") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def new_project(width=1080, height=1920, fps=30, name="Yeni Proje", duration=10.0,
                background="#000000") -> dict:
    return {
        "version": VERSION,
        "name": name,
        "width": int(width),
        "height": int(height),
        "fps": fps,
        "theme": None,
        "brand": None,
        "main": "main",
        "comps": {"main": new_comp("Ana Sahne", duration, background)},
    }


def new_comp(name="Sahne", duration=5.0, background="#000000", width=None, height=None) -> dict:
    c = {"name": name, "duration": float(duration), "background": background, "layers": []}
    if width:
        c["width"] = int(width)
    if height:
        c["height"] = int(height)
    return c


def new_layer(type_: str, start=0.0, duration=5.0, track=0, name=None, **fields) -> dict:
    if type_ not in LAYER_TYPES:
        raise ValueError(f"Bilinmeyen katman türü: {type_}")
    props = fields.pop("props", {}) or {}
    layer = {
        "id": fields.pop("id", None) or new_id(),
        "type": type_,
        "name": name or type_.capitalize(),
        "track": int(track),
        "start": float(start),
        "duration": float(duration),
        "enabled": True,
        "blend": "normal",
        "props": props,
        "effects": [],
        "transition_in": None,
        "transition_out": None,
    }
    layer.update(fields)
    return layer


# --------------------------------------------------------------------------- yükle / kaydet


def load_project(path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return normalize(data)


def save_project(project: dict, path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(project, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def normalize(p: dict) -> dict:
    """Eksik alanları doldurur; geçersiz yapıyı mümkün olduğunca onarır."""
    p.setdefault("version", VERSION)
    p.setdefault("name", "Proje")
    p.setdefault("width", 1080)
    p.setdefault("height", 1920)
    p.setdefault("fps", 30)
    p.setdefault("theme", None)
    p.setdefault("brand", None)
    comps = p.setdefault("comps", {})
    if not comps:
        comps["main"] = new_comp("Ana Sahne")
    p.setdefault("main", next(iter(comps)))
    for cid, c in comps.items():
        c.setdefault("name", cid)
        c.setdefault("background", "#000000")
        c.setdefault("layers", [])
        seen = set()
        for layer in c["layers"]:
            layer.setdefault("type", "shape")
            if not layer.get("id") or layer["id"] in seen:
                layer["id"] = new_id()
            seen.add(layer["id"])
            layer.setdefault("name", layer["type"].capitalize())
            layer.setdefault("track", 0)
            layer.setdefault("start", 0.0)
            layer.setdefault("duration", 5.0)
            layer.setdefault("enabled", True)
            layer.setdefault("blend", "normal")
            layer.setdefault("props", {})
            layer.setdefault("effects", [])
            layer.setdefault("transition_in", None)
            layer.setdefault("transition_out", None)
        if c.get("duration") is None:
            c["duration"] = comp_content_end(c) or 5.0
    return p


# --------------------------------------------------------------------------- sorgular


def get_comp(project: dict, comp_id: str | None = None) -> dict:
    cid = comp_id or project.get("main", "main")
    try:
        return project["comps"][cid]
    except KeyError:
        raise KeyError(f"Kompozisyon bulunamadı: {cid}") from None


def comp_size(project: dict, comp: dict) -> tuple[int, int]:
    return int(comp.get("width") or project["width"]), int(comp.get("height") or project["height"])


def comp_content_end(comp: dict) -> float:
    ends = [l["start"] + l["duration"] for l in comp.get("layers", [])]
    return max(ends) if ends else 0.0


def comp_duration(comp: dict) -> float:
    d = comp.get("duration")
    return float(d) if d else comp_content_end(comp)


def find_layer(project: dict, layer_id: str) -> tuple[str, dict] | tuple[None, None]:
    for cid, c in project["comps"].items():
        for layer in c["layers"]:
            if layer["id"] == layer_id:
                return cid, layer
    return None, None


def layer_end(layer: dict) -> float:
    return layer["start"] + layer["duration"]


def is_active(layer: dict, t: float) -> bool:
    return layer.get("enabled", True) and layer["start"] <= t < layer["start"] + layer["duration"]


def sorted_layers(comp: dict) -> list[dict]:
    """Alt kanaldan üste doğru çizim sırası."""
    return sorted(comp["layers"], key=lambda l: (l.get("track", 0), l["start"]))


def default_prop(layer_type: str, name: str):
    if name in COMMON_PROPS:
        return COMMON_PROPS[name]
    return TYPE_PROPS.get(layer_type, {}).get(name)


# --------------------------------------------------------------------------- değer hesaplama


def _lerp(a, b, u):
    if isinstance(a, bool) or isinstance(b, bool):
        return a if u < 1 else b
    if isinstance(a, (int, float)) and isinstance(b, (int, float)):
        return a + (b - a) * u
    if isinstance(a, (list, tuple)) and isinstance(b, (list, tuple)) and len(a) == len(b):
        return [_lerp(x, y, u) for x, y in zip(a, b)]
    if isinstance(a, str) and isinstance(b, str) and (a.startswith("#") or b.startswith("#")):
        ca, cb = parse_color(a), parse_color(b)
        return color_to_hex([x + (y - x) * u for x, y in zip(ca, cb)])
    return a if u < 1 else b


def _noise1(x: float, seed: int = 0) -> float:
    """Yumuşak 1B gürültü (-1..1)."""
    i = math.floor(x)
    f = x - i

    def h(n):
        return random.Random((n * 374761393 + seed * 668265263) & 0xFFFFFFFF).uniform(-1, 1)

    u = f * f * (3 - 2 * f)
    return h(i) * (1 - u) + h(i + 1) * u


_EXPR_ENV = {
    k: getattr(math, k)
    for k in ("sin", "cos", "tan", "asin", "acos", "atan", "atan2", "sqrt", "pi", "e", "floor",
              "ceil", "exp", "log", "hypot", "radians", "degrees")
}
_EXPR_ENV.update(abs=abs, min=min, max=max, round=round, int=int, float=float)


def _expr_env(t: float, seed: int):
    env = dict(_EXPR_ENV)
    env["t"] = t
    env["noise"] = lambda x, s=0: _noise1(x, seed + s)
    env["wiggle"] = lambda freq, amp, s=0: _noise1(t * freq, seed + s) * amp
    env["clamp"] = lambda v, lo, hi: max(lo, min(hi, v))
    env["lerp"] = lambda a, b, u: a + (b - a) * u
    env["ease"] = lambda name, u: easing.apply(name, u)
    env["pingpong"] = lambda x: 1 - abs((x % 2) - 1)
    return env


_EXPR_CACHE: dict[str, object] = {}


def eval_expr(expr: str, t: float, seed: int = 0):
    code = _EXPR_CACHE.get(expr)
    if code is None:
        code = compile(expr, "<expr>", "eval")
        if any(n.startswith("__") for n in code.co_names):
            raise ValueError("İfadede '__' kullanılamaz")
        _EXPR_CACHE[expr] = code
    return eval(code, {"__builtins__": {}}, _expr_env(t, seed))  # noqa: S307


def is_animated(v) -> bool:
    return isinstance(v, dict) and ("keyframes" in v or "expr" in v)


def value_at(v, t: float, seed: int = 0):
    """Bir prop değerini katman-içi t anında hesaplar."""
    if not isinstance(v, dict):
        return v
    if "expr" in v:
        try:
            base = eval_expr(v["expr"], t, seed)
        except Exception:
            base = v.get("fallback", 0)
        return base
    kfs = v.get("keyframes")
    if kfs is None:
        return v
    if not kfs:
        return None
    if len(kfs) == 1 or t <= kfs[0]["t"]:
        return kfs[0]["v"]
    if t >= kfs[-1]["t"]:
        return kfs[-1]["v"]
    for a, b in zip(kfs, kfs[1:]):
        if a["t"] <= t <= b["t"]:
            span = b["t"] - a["t"]
            u = 0.0 if span <= 0 else (t - a["t"]) / span
            u = easing.apply(a.get("ease", "linear"), u)
            return _lerp(a["v"], b["v"], u)
    return kfs[-1]["v"]


def prop(layer: dict, name: str, t: float, default=None):
    """Katmanın `name` prop'unu katman-içi t anında döndürür."""
    props = layer.get("props", {})
    if name in props:
        # açıkça null verilmiş değer "yok" demektir (ör. "fill": null → dolgu yok)
        val = value_at(props[name], t, seed=_seed(layer))
        if val is None and name in COMMON_PROPS:
            return COMMON_PROPS[name]
        return val
    if default is not None:
        return default
    return default_prop(layer["type"], name)


def _seed(layer: dict) -> int:
    return int(hashlib.md5(layer.get("id", "").encode()).hexdigest()[:6], 16)


def set_keyframe(layer: dict, name: str, t: float, value, ease="linear") -> None:
    props = layer.setdefault("props", {})
    cur = props.get(name)
    if not is_animated(cur) or "keyframes" not in (cur or {}):
        base = cur if cur is not None else default_prop(layer["type"], name)
        props[name] = {"keyframes": []}
        if base is not None and abs(t) > 1e-6:
            props[name]["keyframes"].append({"t": 0.0, "v": base, "ease": ease})
    kfs = props[name]["keyframes"]
    for k in kfs:
        if abs(k["t"] - t) < 1e-4:
            k["v"] = value
            k["ease"] = ease
            break
    else:
        kfs.append({"t": float(t), "v": value, "ease": ease})
    kfs.sort(key=lambda k: k["t"])


def static_props(layer: dict) -> bool:
    return not any(is_animated(v) for v in layer.get("props", {}).values())


def content_hash(obj) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:16]


def clone(obj):
    return copy.deepcopy(obj)


# --------------------------------------------------------------------------- doğrulama


def validate(project: dict) -> list[str]:
    """Yapısal hataları listeler (boş liste = geçerli)."""
    errors: list[str] = []
    for key in ("width", "height", "fps", "comps"):
        if key not in project:
            errors.append(f"Eksik alan: {key}")
    if errors:
        return errors
    if not isinstance(project["comps"], dict) or not project["comps"]:
        return ["'comps' boş olmayan bir sözlük olmalı"]
    if project.get("main") not in project["comps"]:
        errors.append(f"'main' kompozisyonu yok: {project.get('main')}")
    for cid, c in project["comps"].items():
        ids = set()
        for i, layer in enumerate(c.get("layers", [])):
            where = f"{cid}.layers[{i}] ({layer.get('name', layer.get('id'))})"
            t = layer.get("type")
            if t not in LAYER_TYPES:
                errors.append(f"{where}: bilinmeyen tür '{t}'")
            if layer.get("id") in ids:
                errors.append(f"{where}: tekrar eden id {layer.get('id')}")
            ids.add(layer.get("id"))
            try:
                if float(layer.get("duration", 0)) <= 0:
                    errors.append(f"{where}: süre 0'dan büyük olmalı")
                float(layer.get("start", 0))
            except (TypeError, ValueError):
                errors.append(f"{where}: start/duration sayı olmalı")
            if t in ("video", "image", "audio") and not layer.get("src"):
                errors.append(f"{where}: 'src' gerekli")
            if t == "comp":
                ref = layer.get("comp")
                if ref not in project["comps"]:
                    errors.append(f"{where}: kompozisyon yok '{ref}'")
                elif ref == cid:
                    errors.append(f"{where}: kompozisyon kendini içeremez")
            if t == "script" and not layer.get("script"):
                errors.append(f"{where}: 'script' yolu gerekli")
            for name, v in layer.get("props", {}).items():
                if isinstance(v, dict) and "keyframes" in v:
                    kfs = v["keyframes"]
                    if not isinstance(kfs, list) or any("t" not in k or "v" not in k for k in kfs):
                        errors.append(f"{where}.{name}: keyframe'ler {{t, v}} içermeli")
                    elif [k["t"] for k in kfs] != sorted(k["t"] for k in kfs):
                        errors.append(f"{where}.{name}: keyframe'ler zamana göre sıralı olmalı")
                if isinstance(v, dict) and "expr" in v:
                    try:
                        eval_expr(v["expr"], 0.0)
                    except Exception as e:  # noqa: BLE001
                        errors.append(f"{where}.{name}: ifade hatası: {e}")
    errors += _check_cycles(project)
    return errors


def _check_cycles(project: dict) -> list[str]:
    graph = {cid: [l.get("comp") for l in c.get("layers", []) if l.get("type") == "comp"]
             for cid, c in project["comps"].items()}
    errors = []
    state: dict[str, int] = {}

    def visit(n, stack):
        if state.get(n) == 1:
            errors.append("Döngüsel kompozisyon: " + " → ".join(stack + [n]))
            return
        if state.get(n) == 2 or n not in graph:
            return
        state[n] = 1
        for m in graph[n]:
            visit(m, stack + [n])
        state[n] = 2

    for n in graph:
        visit(n, [])
    return errors
