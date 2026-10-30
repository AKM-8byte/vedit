"""Claude'un video üretirken kullandığı Python API'si.

    from vedit import Project, Text, Shape, Image, Video, Audio

    p = Project(1080, 1920, name="Tanıtım", theme="matrix")
    s1 = p.scene("Giriş", duration=4)
    s1.add(Text("Merhaba!", size=140, y=800)).preset("pop_in")
    s2 = p.scene("Detay", duration=5, transition="fade")
    s2.add(Image("gorsel.png", fit="cover")).preset("ken_burns")
    p.music("muzik.mp3", volume=0.4, fade_out=2)
    p.save("projects/tanitim.vedit.json")      # arayüzde açılabilir
    p.sheet("projects/tanitim_sheet.png")      # Claude kontrol eder
    p.render("exports/tanitim.mp4", profile="shorts")

Tüm katman sınıfları bir `dict` sarmalar (`layer.data`); proje dosyası bu sözlüklerden oluşur.
"""
from __future__ import annotations

import os
from pathlib import Path

from . import model
from .presets import apply_preset
from .templates import make_template

TOP_LEVEL = {"src", "fit", "in", "speed", "loop", "volume", "mute", "audio_fade_in",
             "audio_fade_out", "char_anim", "counter", "closed", "rough", "blend", "theme_style",
             "comp", "script", "params", "width", "height", "enabled", "id", "locked", "filled", "smooth"}


class Layer:
    type = "shape"

    def __init__(self, start: float = 0.0, duration: float | None = None, track: int | None = None,
                 name: str | None = None, **kw):
        fields = {k: kw.pop(k) for k in list(kw) if k in TOP_LEVEL}
        if "source_in" in kw:  # `in` Python'da ayrılmış kelime
            fields["in"] = float(kw.pop("source_in"))
        trans_in = kw.pop("transition_in", None) or kw.pop("transition", None)
        trans_out = kw.pop("transition_out", None)
        effects = kw.pop("effects", None)
        self.data = model.new_layer(self.type, start, duration or 0.0, track or 0, name, props=kw,
                                    **fields)
        self._auto_duration = duration is None
        self._auto_track = track is None
        if effects:
            self.data["effects"] = list(effects)
        if trans_in:
            self.transition(trans_in)
        if trans_out:
            self.transition_out(trans_out)

    # ---- zaman
    @property
    def id(self) -> str:
        return self.data["id"]

    @property
    def start(self) -> float:
        return self.data["start"]

    @property
    def end(self) -> float:
        return self.data["start"] + self.data["duration"]

    def at(self, start: float, duration: float | None = None) -> "Layer":
        self.data["start"] = float(start)
        if duration is not None:
            self.data["duration"] = float(duration)
            self._auto_duration = False
        return self

    def set(self, **props) -> "Layer":
        for k, v in props.items():
            if k in TOP_LEVEL:
                self.data[k] = v
            else:
                self.data["props"][k] = v
        return self

    # ---- animasyon
    def animate(self, prop: str, keys: dict | list, ease="out_cubic") -> "Layer":
        """keys: {zaman: değer} ya da [(zaman, değer, ease?), ...]. Zaman katmana görelidir."""
        items = keys.items() if isinstance(keys, dict) else keys
        for item in items:
            t, v = item[0], item[1]
            e = item[2] if len(item) > 2 else ease
            model.set_keyframe(self.data, prop, float(t), v, e)
        return self

    def expr(self, prop: str, expression: str) -> "Layer":
        """Sürekli animasyon ifadesi, ör. expr("rotation", "sin(t*2)*10")."""
        self.data["props"][prop] = {"expr": expression}
        return self

    def preset(self, name: str, at: float | None = None, duration: float | None = None,
               **opts) -> "Layer":
        if self._auto_duration and self.data["duration"] <= 0:
            self._pending_presets = getattr(self, "_pending_presets", []) + [(name, at, duration, opts)]
            return self
        apply_preset(self.data, name, at, duration, **opts)
        return self

    def effect(self, type_: str, **params) -> "Layer":
        self.data["effects"].append({"type": type_, "params": params})
        return self

    def transition(self, kind, duration: float = 0.5, ease: str | None = None) -> "Layer":
        self.data["transition_in"] = _tr(kind, duration, ease)
        return self

    def transition_out(self, kind, duration: float = 0.5, ease: str | None = None) -> "Layer":
        self.data["transition_out"] = _tr(kind, duration, ease)
        return self

    def blend(self, mode: str) -> "Layer":
        self.data["blend"] = mode
        return self

    def _finalize(self):
        for name, at, dur, opts in getattr(self, "_pending_presets", []):
            apply_preset(self.data, name, at, dur, **opts)
        self._pending_presets = []


def _tr(kind, duration, ease):
    if kind == "theme" or kind is None or isinstance(kind, dict):
        return kind
    d = {"type": kind, "duration": float(duration)}
    if ease:
        d["ease"] = ease
    return d


class Text(Layer):
    type = "text"

    def __init__(self, text: str = "", **kw):
        super().__init__(**{**kw, "text": text})

    def chars(self, kind="rise", **cfg) -> "Text":
        """Harf/kelime animasyonu: rise, fade, pop, drop, wave, typewriter, decode, write,
        blur, glitch, highlight. cfg: unit, stagger, duration, delay, ease, color."""
        self.data["char_anim"] = {"type": kind, **cfg}
        return self


class Shape(Layer):
    type = "shape"

    def __init__(self, shape: str = "rect", **kw):
        super().__init__(**{**kw, "shape": shape})


class Solid(Layer):
    type = "solid"

    def __init__(self, color="#000000", **kw):
        super().__init__(**{**kw, "color": color})


class Image(Layer):
    type = "image"

    def __init__(self, src: str, **kw):
        super().__init__(**{**kw, "src": str(src)})


class Video(Layer):
    type = "video"

    def __init__(self, src: str, **kw):
        super().__init__(**{**kw, "src": str(src)})

    def source_duration(self, base_dir=None) -> float:
        from .media import probe
        from .util import resolve_path

        return probe(resolve_path(self.data["src"], base_dir))["duration"]


class Audio(Layer):
    type = "audio"

    def __init__(self, src: str, **kw):
        super().__init__(**{**kw, "src": str(src)})


class Script(Layer):
    type = "script"

    def __init__(self, script: str, params: dict | None = None, **kw):
        super().__init__(**{**kw, "script": str(script), "params": params or {}})


class Adjustment(Layer):
    type = "adjustment"


class Scene:
    """Bir kompozisyon (sahne). Katmanlar sahne zamanına göre yerleştirilir."""

    def __init__(self, project: "Project", comp_id: str):
        self.project = project
        self.id = comp_id
        self.comp = project.data["comps"][comp_id]

    @property
    def duration(self) -> float:
        return float(self.comp["duration"])

    def add(self, layer: Layer, start: float | None = None, duration: float | None = None,
            track: int | None = None) -> Layer:
        d = layer.data
        if start is not None:
            d["start"] = float(start)
        if duration is not None:
            d["duration"] = float(duration)
        elif layer._auto_duration:
            if layer.type == "video":
                try:
                    src_d = layer.source_duration(self.project.base_dir) - float(d.get("in", 0))
                    d["duration"] = max(0.1, min(self.duration - d["start"], src_d / float(
                        d.get("speed", 1))) if not d.get("loop") else self.duration - d["start"])
                except Exception:  # noqa: BLE001
                    d["duration"] = max(0.1, self.duration - d["start"])
            else:
                d["duration"] = max(0.1, self.duration - d["start"])
        if track is not None:
            d["track"] = int(track)
        elif layer._auto_track:
            d["track"] = 1 + max([l["track"] for l in self.comp["layers"]] + [-1])
        layer._finalize()
        self.comp["layers"].append(d)
        return layer

    def template(self, name: str, at: float = 0.0, duration: float | None = None, **params):
        W, H = model.comp_size(self.project.data, self.comp)
        if duration is None:
            from .templates import TEMPLATES

            duration = min(TEMPLATES[name]["duration"], max(0.5, self.duration - at))
        track = 1 + max([l["track"] for l in self.comp["layers"]] + [-1])
        layers = make_template(name, W, H, at, duration, track, **params)
        self.comp["layers"].extend(layers)
        return layers

    def layers(self) -> list[dict]:
        return self.comp["layers"]


class Project:
    def __init__(self, width=1080, height=1920, fps=30, name="Proje", theme=None,
                 theme_params: dict | None = None, brand: str | None = None,
                 background="#000000", base_dir: str | None = None):
        self.data = model.new_project(width, height, fps, name, duration=0.0,
                                      background=background)
        self.data["comps"]["main"]["duration"] = 0.0
        self.base_dir = base_dir or os.getcwd()
        if theme:
            self.data["theme"] = {"name": theme, "params": theme_params or {}}
            self.data["comps"]["main"]["background"] = "theme"
        if brand:
            self.data["brand"] = brand
        self._scene_end = 0.0
        self._scene_track = 0

    @classmethod
    def load(cls, path) -> "Project":
        p = cls.__new__(cls)
        p.data = model.load_project(path)
        p.base_dir = str(Path(path).resolve().parent)
        main = p.data["comps"][p.data["main"]]
        p._scene_end = model.comp_content_end(main)
        p._scene_track = 0
        return p

    @property
    def main(self) -> Scene:
        return Scene(self, self.data["main"])

    @property
    def duration(self) -> float:
        return model.comp_duration(self.data["comps"][self.data["main"]])

    def scene(self, name: str = "Sahne", duration: float = 5.0, background=None,
              transition=None, transition_duration: float = 0.5) -> Scene:
        """Yeni bir sahne oluşturup ana zaman çizelgesine sıradaki olarak ekler."""
        cid = model.new_id("s")
        if background is None:
            background = "theme" if self.data.get("theme") else "#000000"
        self.data["comps"][cid] = model.new_comp(name, duration, background)
        overlap = transition_duration if (transition and self._scene_end > 0) else 0.0
        start = max(0.0, self._scene_end - overlap)
        track = self._scene_track if overlap == 0 else 1 - self._scene_track
        layer = model.new_layer("comp", start, duration, track, name, comp=cid)
        if transition and self._scene_end > 0:
            layer["transition_in"] = _tr(transition, transition_duration, None)
        self.data["comps"][self.data["main"]]["layers"].append(layer)
        self._scene_track = track
        self._scene_end = start + duration
        main = self.data["comps"][self.data["main"]]
        main["duration"] = max(main["duration"], self._scene_end)
        return Scene(self, cid)

    def add(self, layer: Layer, start: float | None = None, duration: float | None = None,
            track: int | None = None) -> Layer:
        """Ana zaman çizelgesine (tüm sahnelerin üstüne) katman ekler."""
        main = self.data["comps"][self.data["main"]]
        if main["duration"] <= 0 and duration:
            main["duration"] = (start or 0) + duration
        if track is None and layer._auto_track:
            track = 100 + len(main["layers"])
        res = self.main.add(layer, start, duration, track)
        main["duration"] = max(main["duration"], layer.end)
        return res

    def music(self, src: str, volume: float = 0.6, fade_in: float = 0.5, fade_out: float = 1.5,
              start: float = 0.0, loop: bool = True, in_: float = 0.0) -> Layer:
        dur = max(0.1, self.duration - start)
        a = Audio(src, start=start, duration=dur, volume=volume, audio_fade_in=fade_in,
                  audio_fade_out=fade_out, loop=loop, name="Müzik", track=200, **{"in": in_})
        self.data["comps"][self.data["main"]]["layers"].append(a.data)
        return a

    def template(self, name: str, at: float = 0.0, duration: float | None = None, **params):
        return self.main.template(name, at, duration, **params)

    # ---- çıktı
    def save(self, path) -> str:
        path = Path(path)
        if not path.name.endswith(".vedit.json"):
            path = path.with_name(path.stem.split(".")[0] + ".vedit.json")
        errors = model.validate(model.normalize(self.data))
        if errors:
            raise ValueError("Proje geçersiz:\n" + "\n".join(errors))
        model.save_project(self.data, path)
        return str(path)

    def lint(self) -> list[dict]:
        from .lint import lint

        return lint(self.data, self.base_dir)

    def sheet(self, out_path="sheet.png", **kw) -> dict:
        from .sheet import contact_sheet

        return contact_sheet(self.data, self.base_dir, out_path, **kw)

    def frame(self, t: float, out_path="frame.png", scale: float = 1.0) -> str:
        from .render import Renderer

        with Renderer(self.data, self.base_dir, scale=scale) as r:
            r.render_image(t).save(out_path)
        return str(out_path)

    def render(self, out_path="output.mp4", profile="default", progress=True, **kw) -> str:
        from .export import export

        def prog(f, msg):
            print(f"\r[{int(f * 100):3d}%] {msg:40}", end="", flush=True)

        out = export(self.data, out_path, self.base_dir, profile, progress=prog if progress else None,
                     **kw)
        if progress:
            print()
        return out
