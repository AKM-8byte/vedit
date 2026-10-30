"""Script katmanı: Claude'un yazdığı Python kodunu timeline'da katman olarak çalıştırır.

Script dosyası şunlardan birini tanımlar:

    PARAMS = {"renk": {"type": "color", "default": "#ff3366"},
              "hiz":  {"type": "float", "default": 1.0, "min": 0.1, "max": 5}}

    def make_frame(t, params, w, h):   # → numpy (h, w, 3|4) ya da PIL.Image
        ...

ya da eski MoviePy scriptleri için:

    def make_clip(params):              # → moviepy Clip
        ...

`make_frame` parametreleri esnektir: (t), (t, params) veya (t, params, w, h).
Katmanın "params" alanındaki değerler keyframe'li olabilir.
"""
from __future__ import annotations

import ast
import importlib.util
import inspect
import os
import sys
import traceback

import numpy as np
from PIL import Image, ImageDraw

from .model import value_at
from .util import load_font, resolve_path

PARAM_TYPES = ("float", "int", "color", "text", "bool", "choice", "file")

_modules: dict[str, tuple[float, object]] = {}
_clips: dict[tuple, object] = {}


def read_params(path: str) -> dict:
    """Script'i çalıştırmadan PARAMS sözlüğünü okur (arayüz için güvenli)."""
    with open(path, "r", encoding="utf-8") as f:
        tree = ast.parse(f.read(), path)
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == "PARAMS" for t in node.targets):
            try:
                return ast.literal_eval(node.value)
            except ValueError:
                return {}
    return {}


def load_module(path: str):
    mtime = os.path.getmtime(path)
    cached = _modules.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    name = "vedit_script_" + str(abs(hash(path)))
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
    sys.path.insert(0, os.path.dirname(path))
    try:
        spec.loader.exec_module(mod)  # type: ignore[union-attr]
    finally:
        sys.path.pop(0)
    _modules[path] = (mtime, mod)
    for k in [k for k in _clips if k[0] == path]:
        _clips.pop(k, None)
    return mod


def resolve_params(layer: dict, schema: dict, lt: float) -> dict:
    out = {k: v.get("default") for k, v in schema.items()}
    for k, v in (layer.get("params") or {}).items():
        out[k] = value_at(v, lt)
    return out


def _call_make_frame(fn, t, params, w, h):
    try:
        n = len(inspect.signature(fn).parameters)
    except (TypeError, ValueError):
        n = 1
    if n >= 4:
        return fn(t, params, w, h)
    if n == 3:
        return fn(t, params, (w, h))
    if n == 2:
        return fn(t, params)
    return fn(t)


def _to_image(res) -> Image.Image:
    if isinstance(res, Image.Image):
        return res.convert("RGBA")
    arr = np.asarray(res)
    if arr.dtype != np.uint8:
        arr = np.clip(arr * (255 if arr.max() <= 1.0 else 1), 0, 255).astype(np.uint8)
    if arr.ndim == 2:
        arr = np.repeat(arr[..., None], 3, axis=2)
    return Image.fromarray(np.ascontiguousarray(arr)).convert("RGBA")


def error_image(w, h, msg: str) -> Image.Image:
    img = Image.new("RGBA", (w, h), (90, 10, 20, 200))
    d = ImageDraw.Draw(img)
    f = load_font("consolas", max(10, h // 40))
    d.text((20, 20), "Script hatası:\n" + msg[-600:], fill=(255, 230, 230, 255), font=f)
    return img


def render_script(r, layer: dict, lt: float, W: int, H: int) -> Image.Image | None:
    path = resolve_path(layer.get("script"), r.base_dir)
    if not path or not os.path.exists(path):
        r.warn(f"Script bulunamadı: {layer.get('script')}")
        return error_image(W, H, f"Dosya yok: {layer.get('script')}")
    # script'e proje çözünürlüğü verilir; ölçekleme render tarafında yapılır
    w = int(layer.get("width") or W / r.scale)
    h = int(layer.get("height") or H / r.scale)
    try:
        mod = load_module(path)
        schema = getattr(mod, "PARAMS", {}) or {}
        params = resolve_params(layer, schema, lt)
        if hasattr(mod, "make_frame"):
            res = _call_make_frame(mod.make_frame, lt, params, w, h)
        elif hasattr(mod, "make_clip"):
            key = (path, repr(sorted(params.items())))
            clip = _clips.get(key)
            if clip is None:
                clip = _clips[key] = mod.make_clip(params)
            dur = getattr(clip, "duration", None)
            tt = min(lt, dur - 1e-3) if dur else lt
            res = clip.get_frame(tt)
            mask = getattr(clip, "mask", None)
            if mask is not None:
                a = (np.asarray(mask.get_frame(tt)) * 255).astype(np.uint8)
                res = np.dstack([np.asarray(res)[..., :3], a])
        else:
            return error_image(w, h, "make_frame veya make_clip tanımlı değil")
        img = _to_image(res)
    except Exception:  # noqa: BLE001
        msg = traceback.format_exc(limit=3)
        r.warn(f"Script hatası ({os.path.basename(path)}): {msg.splitlines()[-1]}")
        img = error_image(w, h, msg)
    if r.scale != 1.0:
        img = img.resize((max(1, int(img.width * r.scale)), max(1, int(img.height * r.scale))),
                         Image.LANCZOS)
    return img
