"""Yerel FastAPI sunucusu: arayüz ile render motoru arasındaki köprü."""
from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

from fastapi import Body, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

from .. import model
from ..export import PROFILES, PreviewBuilder, export
from ..media import media_kind, probe, thumbnail_jpeg, waveform
from ..render import Renderer
from ..util import ROOT, list_system_fonts, resolve_path
from .jobs import JobManager

UI_DIR = ROOT / "ui"
CACHE_DIR = ROOT / ".vedit_cache"
INBOX_DIR = ROOT / "inbox"


class AppState:
    def __init__(self):
        self.project: dict = model.new_project(name="Yeni Proje")
        self.path: str | None = None
        self.base_dir: str = str(ROOT)
        self.disk_mtime: float = 0.0
        self.version = 0
        self.lock = threading.RLock()
        self.renderers: dict[float, Renderer] = {}
        self.preview = PreviewBuilder(str(CACHE_DIR / "preview"))
        self.jobs = JobManager()
        self.dialog = None  # pywebview tarafından atanır: fn(kind, opts) -> list[str] | str | None

    def renderer(self, scale: float) -> Renderer:
        scale = round(scale, 3)
        r = self.renderers.get(scale)
        if r is None:
            if len(self.renderers) > 3:
                old = self.renderers.pop(next(iter(self.renderers)))
                old.close()
            r = self.renderers[scale] = Renderer(model.clone(self.project), self.base_dir, scale,
                                                 preview=True)
            r._version = self.version
        elif getattr(r, "_version", -1) != self.version:
            r.base_dir = self.base_dir
            r.set_project(model.clone(self.project))
            r._version = self.version
        return r

    def set_project(self, project: dict, path: str | None = None, keep_path=True):
        with self.lock:
            self.project = model.normalize(project)
            if not keep_path:
                self.path = path
                self.base_dir = str(Path(path).resolve().parent) if path else str(ROOT)
                self.disk_mtime = os.path.getmtime(path) if path and os.path.exists(path) else 0.0
            self.version += 1


S = AppState()
app = FastAPI(title="VEdit")


@app.middleware("http")
async def no_cache_ui(request, call_next):
    # arayüz dosyaları güncellendiğinde tarayıcı eski sürümü kullanmasın
    response = await call_next(request)
    if request.url.path.startswith("/ui"):
        response.headers["Cache-Control"] = "no-cache"
    return response


def _rel(path: str) -> str:
    try:
        return str(Path(path).resolve().relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(Path(path)).replace("\\", "/")


# ---------------------------------------------------------------------- proje


@app.get("/")
def index():
    return RedirectResponse("/ui/index.html")


@app.get("/api/state")
def get_state():
    return {"project": S.project, "path": S.path and _rel(S.path), "base_dir": S.base_dir,
            "disk_mtime": S.disk_mtime, "root": str(ROOT)}


SETTINGS_FILE = ROOT / ".vedit_settings.json"


@app.get("/api/settings")
def get_settings():
    try:
        return json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}


@app.put("/api/settings")
def put_settings(values: dict = Body(...)):
    cur = get_settings()
    cur.update({k: v for k, v in values.items() if k in ("lang",)})
    SETTINGS_FILE.write_text(json.dumps(cur, ensure_ascii=False, indent=2), encoding="utf-8")
    return cur


@app.get("/api/about")
def about():
    from .. import __author__, __copyright__, __license__, __version__

    lic = ROOT / "LICENSE"
    return {"name": "VEdit", "version": __version__, "author": __author__,
            "copyright": __copyright__, "license": __license__,
            "license_text": lic.read_text(encoding="utf-8") if lic.exists() else ""}


@app.put("/api/project")
def put_project(project: dict = Body(..., embed=True)):
    S.set_project(project)
    return {"ok": True, "errors": model.validate(S.project), "version": S.version}


@app.post("/api/open")
def open_project(path: str = Body(..., embed=True)):
    p = resolve_path(path, ROOT)
    if not p or not os.path.exists(p):
        raise HTTPException(404, f"Dosya yok: {path}")
    try:
        proj = model.load_project(p)
    except json.JSONDecodeError as e:
        raise HTTPException(400, f"JSON hatası: {e}") from e
    S.set_project(proj, p, keep_path=False)
    return get_state()


@app.post("/api/new")
def new_project(width: int = Body(1080), height: int = Body(1920), fps: float = Body(30),
                name: str = Body("Yeni Proje"), duration: float = Body(10),
                theme: str | None = Body(None)):
    p = model.new_project(width, height, fps, name, duration)
    if theme:
        p["theme"] = {"name": theme, "params": {}}
        p["comps"]["main"]["background"] = "theme"
    S.set_project(p, None, keep_path=False)
    return get_state()


@app.post("/api/save")
def save_project(path: str | None = Body(None, embed=True)):
    target = path or S.path
    if not target:
        raise HTTPException(400, "Kayıt yolu gerekli")
    target = resolve_path(target, ROOT) if not os.path.isabs(target) else target
    if not target.endswith(".vedit.json"):
        target = str(Path(target).with_suffix("")).removesuffix(".vedit") + ".vedit.json"
    errors = model.validate(S.project)
    if errors:
        raise HTTPException(400, "Proje geçersiz:\n" + "\n".join(errors))
    model.save_project(S.project, target)
    if target != S.path:
        S.path = target
        S.base_dir = str(Path(target).resolve().parent)
        S.version += 1
    S.disk_mtime = os.path.getmtime(target)
    return {"ok": True, "path": _rel(target), "disk_mtime": S.disk_mtime}


@app.get("/api/disk")
def disk_status():
    if not S.path or not os.path.exists(S.path):
        return {"mtime": 0, "changed": False}
    m = os.path.getmtime(S.path)
    return {"mtime": m, "changed": m > S.disk_mtime + 0.01}


@app.post("/api/reload")
def reload_from_disk():
    if not S.path:
        raise HTTPException(400, "Açık dosya yok")
    return open_project(S.path)


@app.post("/api/autosave")
def autosave(project: dict = Body(..., embed=True)):
    d = CACHE_DIR / "autosave"
    d.mkdir(parents=True, exist_ok=True)
    name = Path(S.path).name if S.path else "adsiz.vedit.json"
    model.save_project(project, d / name)
    return {"ok": True}


@app.get("/api/autosave")
def autosave_check():
    name = Path(S.path).name if S.path else "adsiz.vedit.json"
    f = CACHE_DIR / "autosave" / name
    if not f.exists():
        return {"exists": False}
    newer = not S.path or not os.path.exists(S.path) or f.stat().st_mtime > os.path.getmtime(S.path) + 2
    return {"exists": True, "newer": newer, "mtime": f.stat().st_mtime,
            "project": model.load_project(f) if newer else None}


# ---------------------------------------------------------------------- render


@app.get("/api/frame")
def frame(t: float = 0.0, comp: str | None = None, scale: float = 0.4, q: int = 82):
    scale = max(0.05, min(1.0, scale))
    with S.lock:
        r = S.renderer(scale)
        try:
            img = r.render_image(t, comp)
        except KeyError as e:
            raise HTTPException(404, str(e)) from e
        warnings = list(r.warnings)
    from PIL import Image

    bg = Image.new("RGBA", img.size, (0, 0, 0, 255))
    bg.alpha_composite(img)
    buf = io.BytesIO()
    bg.convert("RGB").save(buf, "JPEG", quality=q)
    return Response(buf.getvalue(), media_type="image/jpeg",
                    headers={"X-Warnings": json.dumps(warnings[:5], ensure_ascii=True),
                             "Cache-Control": "no-store"})


@app.get("/api/bbox")
def bbox(layer: str, t: float = 0.0, comp: str | None = None):
    cid, l = model.find_layer(S.project, layer)
    if l is None:
        raise HTTPException(404, "katman yok")
    with S.lock:
        r = S.renderer(0.25)
        res = r.layer_corners(comp or cid, l, t)
    return res or {}


@app.get("/api/pick")
def pick(x: float, y: float, t: float = 0.0, comp: str | None = None):
    """Önizlemede tıklanan noktadaki en üstteki katmanın id'si."""
    cid = comp or S.project["main"]
    c = model.get_comp(S.project, cid)
    with S.lock:
        r = S.renderer(0.25)
        for layer in reversed(model.sorted_layers(c)):
            if not model.is_active(layer, t) or layer.get("locked"):
                continue
            try:
                res = r.layer_corners(cid, layer, t)
            except Exception:  # noqa: BLE001
                continue
            if res and _inside(x, y, res["corners"]):
                return {"id": layer["id"]}
    return {"id": None}


def _inside(x, y, poly):
    inside = False
    j = len(poly) - 1
    for i in range(len(poly)):
        xi, yi = poly[i]
        xj, yj = poly[j]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / ((yj - yi) or 1e-9) + xi:
            inside = not inside
        j = i
    return inside


# ---------------------------------------------------------------------- medya


def _abspath(path: str) -> str:
    p = resolve_path(path, S.base_dir)
    if not p or not os.path.exists(p):
        raise HTTPException(404, f"Dosya yok: {path}")
    return p


@app.get("/api/media/info")
def media_info(path: str):
    p = _abspath(path)
    info = dict(probe(p)) if media_kind(p) in ("video", "image", "audio") else {}
    info["kind"] = media_kind(p)
    info["path"] = _rel(p)
    if info["kind"] == "script":
        from ..scripting import read_params

        info["params"] = read_params(p)
    return info


@app.get("/api/media/thumb")
def media_thumb(path: str, t: float = 0.0, w: int = 160):
    p = _abspath(path)
    data = thumbnail_jpeg(p, t, w)
    return Response(data, media_type="image/jpeg", headers={"Cache-Control": "max-age=3600"})


@app.get("/api/media/waveform")
def media_waveform(path: str, n: int = 600):
    return {"peaks": waveform(_abspath(path), n)}


@app.get("/api/media/file")
def media_file(path: str):
    return FileResponse(_abspath(path))


@app.get("/api/files")
def list_files(dir: str = ""):
    d = Path(resolve_path(dir, ROOT) if dir else ROOT)
    if not d.is_dir():
        raise HTTPException(404, "Klasör yok")
    out = []
    for e in sorted(d.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
        if e.name.startswith(".") or e.name in ("__pycache__", "vedit", "ui", "vedit.egg-info",
                                                "tests") and d == ROOT:
            continue
        kind = "dir" if e.is_dir() else media_kind(e.name)
        if kind is None:
            continue
        out.append({"name": e.name, "path": _rel(str(e)), "kind": kind,
                    "mtime": e.stat().st_mtime, "size": e.stat().st_size if e.is_file() else 0})
    parent = _rel(str(d.parent)) if d != ROOT and ROOT in d.parents else None
    return {"dir": _rel(str(d)), "parent": parent, "entries": out}


@app.get("/api/inbox")
def inbox():
    INBOX_DIR.mkdir(exist_ok=True)
    files = [{"name": f.name, "path": _rel(str(f)), "kind": media_kind(f.name),
              "mtime": f.stat().st_mtime}
             for f in INBOX_DIR.iterdir() if f.is_file() and media_kind(f.name)]
    return {"files": sorted(files, key=lambda f: -f["mtime"])}


@app.post("/api/dialog")
def dialog(kind: str = Body("open"), filters: list[str] | None = Body(None),
           default: str | None = Body(None)):
    if S.dialog is None:
        return {"available": False, "paths": None}
    res = S.dialog(kind, {"filters": filters, "default": default})
    if res is None:
        return {"available": True, "paths": []}
    if isinstance(res, str):
        res = [res]
    return {"available": True, "paths": [_rel(p) for p in res]}


@app.post("/api/reveal")
def reveal(path: str = Body(..., embed=True)):
    p = resolve_path(path, ROOT)
    if p and os.path.exists(p) and sys.platform == "win32":
        subprocess.Popen(["explorer", "/select,", os.path.normpath(p)])
    return {"ok": True}


# ---------------------------------------------------------------------- kütüphane


@app.get("/api/library")
def library():
    from .. import easing
    from ..presets import list_presets
    from ..render.blend import BLEND_MODES
    from ..render.effects import EFFECTS
    from ..render.shapes import SHAPES
    from ..render.text import CHAR_ANIMS
    from ..render.transitions import TRANSITIONS
    from ..scripting import PARAM_TYPES
    from ..templates import list_templates
    from ..themes import list_themes

    return {
        "presets": list_presets(), "templates": list_templates(), "themes": list_themes(),
        "effects": EFFECTS, "transitions": TRANSITIONS, "char_anims": CHAR_ANIMS,
        "easings": list(easing.EASINGS), "blend_modes": BLEND_MODES, "shapes": SHAPES,
        "profiles": {k: v["label"] for k, v in PROFILES.items()},
        "fonts": list_system_fonts(), "param_types": PARAM_TYPES,
        "defaults": {"common": model.COMMON_PROPS, "types": model.TYPE_PROPS},
        "hints": model.ANIMATABLE_HINT,
    }


@app.post("/api/preset")
def preset(layer: dict = Body(...), name: str = Body(...), at: float | None = Body(None),
           duration: float | None = Body(None), opts: dict = Body(default_factory=dict)):
    from ..presets import apply_preset

    try:
        return apply_preset(model.clone(layer), name, at, duration, **opts)
    except KeyError as e:
        raise HTTPException(400, str(e)) from e


@app.post("/api/template")
def template(name: str = Body(...), comp: str | None = Body(None), at: float = Body(0.0),
             duration: float | None = Body(None), params: dict = Body(default_factory=dict),
             track: int = Body(10)):
    from ..templates import make_template

    c = model.get_comp(S.project, comp)
    W, H = model.comp_size(S.project, c)
    return {"layers": make_template(name, W, H, at, duration, track, **params)}


@app.get("/api/script_params")
def script_params(path: str):
    from ..scripting import read_params

    return read_params(_abspath(path))


# ---------------------------------------------------------------------- kontrol


@app.post("/api/lint")
def run_lint():
    from ..lint import lint

    return {"issues": lint(S.project, S.base_dir)}


@app.post("/api/sheet")
def run_sheet(comp: str | None = Body(None, embed=True)):
    from ..sheet import contact_sheet

    out = CACHE_DIR / f"sheet_{int(time.time())}.png"
    CACHE_DIR.mkdir(exist_ok=True)
    for old in CACHE_DIR.glob("sheet_*.png"):
        old.unlink(missing_ok=True)
    res = contact_sheet(S.project, S.base_dir, str(out), comp_id=comp)
    return {"url": f"/api/cache/{out.name}", "times": res["times"]}


@app.get("/api/cache/{name}")
def cache_file(name: str):
    f = CACHE_DIR / Path(name).name
    if not f.exists():
        raise HTTPException(404)
    return FileResponse(f)


@app.post("/api/srt/import")
def srt_import(path: str = Body(...), style: str = Body("caption"), comp: str | None = Body(None)):
    from ..srt import import_srt

    p = model.clone(S.project)
    n = import_srt(p, _abspath(path), comp, style)
    S.set_project(p)
    return {"count": n, "project": S.project}


@app.post("/api/srt/export")
def srt_export(path: str = Body(...), comp: str | None = Body(None)):
    from ..srt import export_srt

    target = resolve_path(path, ROOT)
    n = export_srt(S.project, target, comp)
    return {"count": n, "path": _rel(target)}


# ---------------------------------------------------------------------- önizleme ve export


def _preview_scale(comp: str | None) -> float:
    c = model.get_comp(S.project, comp)
    w, h = model.comp_size(S.project, c)
    return round(min(1.0, 640 / max(w, h)), 3)


@app.get("/api/preview/status")
def preview_status(comp: str | None = None):
    scale = _preview_scale(comp)
    chunks = S.preview.status(S.project, S.base_dir, comp, scale)
    jobs = [j.to_dict() for j in S.jobs.active("preview")]
    return {"chunks": [{"t0": c["t0"], "t1": c["t1"], "ready": c["ready"]} for c in chunks],
            "job": jobs[0] if jobs else None}


@app.post("/api/preview/build")
def preview_build(comp: str | None = Body(None, embed=True)):
    for j in S.jobs.active("preview"):
        j.cancel.set()
    project = model.clone(S.project)
    base = S.base_dir
    scale = _preview_scale(comp)

    def run(job):
        def prog(f, msg):
            job.progress, job.message = f, msg

        path = S.preview.build(project, base, comp, scale, prog, job.cancel)
        return {"url": f"/api/preview/file/{Path(path).name}"}

    job = S.jobs.start("preview", "Önizleme", run)
    return job.to_dict()


@app.get("/api/preview/file/{name}")
def preview_file(name: str):
    f = S.preview.cache_dir / Path(name).name
    if not f.exists():
        raise HTTPException(404)
    return FileResponse(f, media_type="video/mp4")


@app.post("/api/export")
def start_export(path: str = Body(...), profile: str = Body("default"),
                 comp: str | None = Body(None), start: float | None = Body(None),
                 end: float | None = Body(None)):
    if profile not in PROFILES:
        raise HTTPException(400, "Bilinmeyen profil")
    target = path if os.path.isabs(path) else str(ROOT / path)
    project = model.clone(S.project)
    base = S.base_dir

    def run(job):
        def prog(f, msg):
            job.progress, job.message = f, msg

        out = export(project, target, base, profile, comp, start or 0.0, end, None, prog, job.cancel)
        return {"path": _rel(out)}

    job = S.jobs.start("export", f"Export: {Path(target).name}", run)
    return job.to_dict()


@app.get("/api/jobs")
def list_jobs():
    return [j.to_dict() for j in S.jobs.jobs.values()]


@app.get("/api/jobs/{jid}")
def job_status(jid: str):
    j = S.jobs.get(jid)
    if not j:
        raise HTTPException(404)
    return j.to_dict()


@app.post("/api/jobs/{jid}/cancel")
def job_cancel(jid: str):
    j = S.jobs.get(jid)
    if j:
        j.cancel.set()
    return {"ok": True}


@app.exception_handler(Exception)
async def on_error(request, exc):  # noqa: ARG001
    return JSONResponse({"detail": str(exc)}, status_code=500)


if UI_DIR.exists():
    app.mount("/ui", StaticFiles(directory=str(UI_DIR), html=True), name="ui")


def shutdown():
    for r in S.renderers.values():
        r.close()
    S.preview.shutdown()
