"""MCP sunucusu: Claude'un açık projeyi araçlarla okuyup düzenlemesini sağlar.

Kayıt (proje kökünde `.mcp.json`):
    {"mcpServers": {"vedit": {"command": ".venv/Scripts/vedit.exe", "args": ["mcp"]}}}
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from . import model
from .util import ROOT


def _abs(path: str) -> str:
    p = Path(path)
    return str(p if p.is_absolute() else ROOT / p)


def build_server():
    try:  # mcp 2.x
        from mcp.server.mcpserver import MCPServer as Server
    except ImportError:  # mcp 1.x
        from mcp.server.fastmcp import FastMCP as Server

    mcp = Server("vedit")

    @mcp.tool()
    def list_projects() -> list[str]:
        """projects/ altındaki .vedit.json dosyalarını listeler."""
        return sorted(str(p.relative_to(ROOT)).replace("\\", "/")
                      for p in (ROOT / "projects").glob("**/*.vedit.json"))

    @mcp.tool()
    def project_summary(path: str) -> str:
        """Projenin sahne/katman özetini (id, tür, zaman, içerik) döndürür."""
        p = model.load_project(_abs(path))
        lines = [f"{p['name']} {p['width']}x{p['height']} {p['fps']}fps tema={p.get('theme')}"]
        for cid, c in p["comps"].items():
            lines.append(f"[{cid}] {c['name']} {model.comp_duration(c):.2f}s")
            for l in model.sorted_layers(c):
                info = l.get("src") or l.get("comp") or str(
                    model.value_at(l["props"].get("text", ""), 0) or "")[:40]
                lines.append(f"  {l['id']} t{l['track']} {l['start']:.2f}-{model.layer_end(l):.2f} "
                             f"{l['type']} '{l['name']}' {info}")
        return "\n".join(lines)

    @mcp.tool()
    def get_layer(path: str, layer_id: str) -> dict:
        """Bir katmanın tam JSON'unu döndürür."""
        p = model.load_project(_abs(path))
        _, layer = model.find_layer(p, layer_id)
        if layer is None:
            raise ValueError(f"Katman yok: {layer_id}")
        return layer

    @mcp.tool()
    def update_layer(path: str, layer_id: str, changes: dict) -> str:
        """Katmanı günceller. `changes` üst düzey alanlar (start, duration, track, name, effects,
        transition_in...) ve/veya {"props": {...}} içerebilir; props birleştirilir."""
        abspath = _abs(path)
        p = model.load_project(abspath)
        _, layer = model.find_layer(p, layer_id)
        if layer is None:
            raise ValueError(f"Katman yok: {layer_id}")
        for k, v in changes.items():
            if k == "props":
                layer["props"].update(v)
            elif k != "id":
                layer[k] = v
        errs = model.validate(p)
        if errs:
            raise ValueError("\n".join(errs))
        model.save_project(p, abspath)
        return "güncellendi"

    @mcp.tool()
    def add_layer(path: str, comp_id: str, layer: dict) -> str:
        """Kompozisyona yeni katman ekler (model.new_layer biçiminde dict). Yeni id'yi döndürür."""
        abspath = _abs(path)
        p = model.load_project(abspath)
        base = model.new_layer(layer.get("type", "text"), layer.get("start", 0),
                               layer.get("duration", 3), layer.get("track", 0), layer.get("name"))
        base.update({k: v for k, v in layer.items() if k != "id"})
        model.get_comp(p, comp_id)["layers"].append(base)
        errs = model.validate(p)
        if errs:
            raise ValueError("\n".join(errs))
        model.save_project(p, abspath)
        return base["id"]

    @mcp.tool()
    def remove_layer(path: str, layer_id: str) -> str:
        """Katmanı siler."""
        abspath = _abs(path)
        p = model.load_project(abspath)
        cid, layer = model.find_layer(p, layer_id)
        if layer is None:
            raise ValueError(f"Katman yok: {layer_id}")
        p["comps"][cid]["layers"].remove(layer)
        model.save_project(p, abspath)
        return "silindi"

    @mcp.tool()
    def apply_preset(path: str, layer_id: str, preset: str, at: float | None = None,
                     duration: float | None = None) -> str:
        """Katmana hazır animasyon uygular (vedit presets listesi)."""
        from .presets import apply_preset as ap

        abspath = _abs(path)
        p = model.load_project(abspath)
        _, layer = model.find_layer(p, layer_id)
        if layer is None:
            raise ValueError(f"Katman yok: {layer_id}")
        ap(layer, preset, at, duration)
        model.save_project(p, abspath)
        return "uygulandı"

    @mcp.tool()
    def preview_sheet(path: str, times: list[float] | None = None) -> str:
        """Kare panosu PNG üretir ve yolunu + lint sonucunu döndürür (PNG'yi Read ile aç)."""
        from .lint import format_issues, lint
        from .sheet import contact_sheet

        abspath = _abs(path)
        p = model.load_project(abspath)
        out = abspath.replace(".vedit.json", "_sheet.png")
        res = contact_sheet(p, os.path.dirname(abspath), out, times)
        return json.dumps({"sheet": res["path"], "times": res["times"],
                           "lint": format_issues(lint(p, os.path.dirname(abspath)))},
                          ensure_ascii=False)

    @mcp.tool()
    def render_video(path: str, profile: str = "default", output: str | None = None) -> str:
        """Videoyu render eder (uzun sürebilir). Çıktı yolunu döndürür."""
        from .export import export

        abspath = _abs(path)
        p = model.load_project(abspath)
        out = output or str(ROOT / "exports" / (Path(abspath).name.split(".")[0] + ".mp4"))
        return export(p, _abs(out), os.path.dirname(abspath), profile)

    return mcp


def main():
    build_server().run()
