"""Komut satırı: vedit <komut> ...

    vedit new proje.vedit.json --size 1080x1920 --theme matrix
    vedit render proje.vedit.json -o cikti.mp4 --profile shorts
    vedit preview proje.vedit.json --sheet          # kare panosu (Claude kontrolü için)
    vedit frame proje.vedit.json -t 2.5 -o kare.png
    vedit lint proje.vedit.json                     # kalite kontrol
    vedit validate proje.vedit.json                 # yapı doğrulama
    vedit info proje.vedit.json
    vedit srt import altyazi.srt proje.vedit.json
    vedit themes | presets | templates | effects | profiles
    vedit gui [proje.vedit.json]                    # arayüzü aç
    vedit mcp                                       # Claude için MCP sunucusu
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _load(path):
    from . import model

    return model.load_project(path), str(Path(path).resolve().parent)


def cmd_new(a):
    from . import model

    w, h = (int(x) for x in a.size.lower().split("x"))
    p = model.new_project(w, h, a.fps, a.name or Path(a.path).name.split(".")[0], a.duration)
    if a.theme:
        p["theme"] = {"name": a.theme, "params": {}}
        p["comps"]["main"]["background"] = "theme"
    if a.brand:
        p["brand"] = a.brand
    model.save_project(p, a.path)
    print(f"Oluşturuldu: {a.path}")


def cmd_render(a):
    from .export import export

    p, base = _load(a.project)
    out = a.output or str(Path("exports") / (Path(a.project).name.split(".")[0] + ".mp4"))

    def prog(f, msg):
        print(f"\r[{int(f * 100):3d}%] {msg:50}", end="", flush=True)

    t1 = a.end
    path = export(p, out, base, a.profile, a.comp, a.start or 0.0, t1, a.workers, prog)
    print(f"\nKaydedildi: {path}")


def cmd_preview(a):
    from .sheet import contact_sheet

    p, base = _load(a.project)
    out = a.output or str(Path(a.project).with_name(Path(a.project).name.split(".")[0] + "_sheet.png"))
    times = [float(x) for x in a.times.split(",")] if a.times else None
    res = contact_sheet(p, base, out, times, a.comp, a.cols, a.width, not a.no_guides, a.count)
    print(f"Kare panosu: {res['path']}")
    print("Anlar: " + ", ".join(f"{t:.2f}s" for t in res["times"]))
    for w in res["warnings"]:
        print(f"! {w}")
    if not a.no_lint:
        from .lint import format_issues, lint

        print(format_issues(lint(p, base, render_check=True)))


def cmd_frame(a):
    from .render import Renderer

    p, base = _load(a.project)
    with Renderer(p, base, scale=a.scale) as r:
        r.render_image(a.t, a.comp).save(a.output)
        for w in r.warnings:
            print(f"! {w}")
    print(f"Kare: {a.output}")


def cmd_lint(a):
    from .lint import format_issues, lint

    p, base = _load(a.project)
    issues = lint(p, base, render_check=not a.fast)
    if a.json:
        print(json.dumps(issues, ensure_ascii=False, indent=2))
    else:
        print(format_issues(issues))
    sys.exit(1 if any(i["level"] == "error" for i in issues) else 0)


def cmd_validate(a):
    from . import model

    try:
        with open(a.project, "r", encoding="utf-8") as f:
            data = json.load(f)
    except json.JSONDecodeError as e:
        print(f"✗ JSON hatası: {e}")
        sys.exit(1)
    errors = model.validate(model.normalize(data))
    if errors:
        print("\n".join("✗ " + e for e in errors))
        sys.exit(1)
    print("✓ Geçerli")


def cmd_info(a):
    from . import model

    p, base = _load(a.project)
    print(f"{p['name']}  {p['width']}x{p['height']}  {p['fps']}fps  tema={p.get('theme')}")
    for cid, c in p["comps"].items():
        mark = "*" if cid == p["main"] else " "
        print(f"{mark} [{cid}] {c['name']}  {model.comp_duration(c):.2f}s  {len(c['layers'])} katman")
        for l in model.sorted_layers(c):
            extra = l.get("src") or l.get("comp") or l.get("script") or \
                str(model.value_at(l["props"].get("text", ""), 0) or "")[:40]
            print(f"     t{l['track']:<3} {l['start']:6.2f}–{model.layer_end(l):6.2f}  "
                  f"{l['type']:<10} {l['name'][:24]:<24} {extra}")


def cmd_srt(a):
    from . import model
    from .srt import export_srt, import_srt

    if a.action == "import":
        p, _ = _load(a.project)
        n = import_srt(p, a.srt, style=a.style)
        model.save_project(p, a.project)
        print(f"{n} altyazı eklendi")
    else:
        p, _ = _load(a.project)
        export_srt(p, a.srt)
        print(f"Yazıldı: {a.srt}")


def cmd_list(a):
    if a.cmd == "themes":
        from .themes import list_themes

        for t in list_themes():
            print(f"{t['name']:<12} {t['label']:<16} {t['description']}")
            for k, v in t["params"].items():
                print(f"    {k} = {v.get('default')!r}  ({v.get('type')})")
    elif a.cmd == "presets":
        from .presets import list_presets

        for pr in list_presets():
            print(f"{pr['name']:<18} {pr['category']:<8} {pr['label']}")
    elif a.cmd == "templates":
        from .templates import list_templates

        for t in list_templates():
            print(f"{t['name']:<14} {t['label']:<20} {json.dumps(t['params'], ensure_ascii=False)}")
    elif a.cmd == "effects":
        from .render.effects import EFFECTS

        for k, v in EFFECTS.items():
            print(f"{k:<14} {v['label']:<16} {json.dumps(v['params'], ensure_ascii=False)}")
    elif a.cmd == "profiles":
        from .export import PROFILES

        for k, v in PROFILES.items():
            print(f"{k:<12} {v['label']}")


def cmd_gui(a):
    from .gui import main as gui_main

    gui_main(a.project, browser=a.browser, port=a.port, serve_only=a.serve)


def cmd_mcp(a):
    from .mcp_server import main as mcp_main

    mcp_main()


def main(argv=None):
    ap = argparse.ArgumentParser(prog="vedit", description="VEdit video aracı")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("new", help="yeni proje")
    s.add_argument("path")
    s.add_argument("--size", default="1080x1920")
    s.add_argument("--fps", type=float, default=30)
    s.add_argument("--duration", type=float, default=10)
    s.add_argument("--name")
    s.add_argument("--theme")
    s.add_argument("--brand")
    s.set_defaults(fn=cmd_new)

    s = sub.add_parser("render", help="videoya dönüştür")
    s.add_argument("project")
    s.add_argument("-o", "--output")
    s.add_argument("-p", "--profile", default="default")
    s.add_argument("--comp")
    s.add_argument("--start", type=float)
    s.add_argument("--end", type=float)
    s.add_argument("-w", "--workers", type=int)
    s.set_defaults(fn=cmd_render)

    s = sub.add_parser("preview", help="kare panosu (contact sheet)")
    s.add_argument("project")
    s.add_argument("--sheet", action="store_true", help="(varsayılan davranış)")
    s.add_argument("-o", "--output")
    s.add_argument("--times", help="virgülle ayrılmış saniyeler: 0.5,2,4")
    s.add_argument("--count", type=int, default=12)
    s.add_argument("--cols", type=int)
    s.add_argument("--width", type=int, default=360, help="küçük resim genişliği")
    s.add_argument("--comp")
    s.add_argument("--no-guides", action="store_true")
    s.add_argument("--no-lint", action="store_true")
    s.set_defaults(fn=cmd_preview)

    s = sub.add_parser("frame", help="tek kare PNG")
    s.add_argument("project")
    s.add_argument("-t", type=float, default=0.0)
    s.add_argument("-o", "--output", default="frame.png")
    s.add_argument("--scale", type=float, default=1.0)
    s.add_argument("--comp")
    s.set_defaults(fn=cmd_frame)

    s = sub.add_parser("lint", help="kalite kontrol")
    s.add_argument("project")
    s.add_argument("--fast", action="store_true", help="render gerektiren kontrolleri atla")
    s.add_argument("--json", action="store_true")
    s.set_defaults(fn=cmd_lint)

    s = sub.add_parser("validate", help="yapı doğrulama")
    s.add_argument("project")
    s.set_defaults(fn=cmd_validate)

    s = sub.add_parser("info", help="proje özeti")
    s.add_argument("project")
    s.set_defaults(fn=cmd_info)

    s = sub.add_parser("srt", help="altyazı içe/dışa aktar")
    s.add_argument("action", choices=["import", "export"])
    s.add_argument("srt")
    s.add_argument("project")
    s.add_argument("--style", default="caption", help="caption | highlight | plain")
    s.set_defaults(fn=cmd_srt)

    for name in ("themes", "presets", "templates", "effects", "profiles"):
        sub.add_parser(name, help=f"{name} listesi").set_defaults(fn=cmd_list)

    s = sub.add_parser("gui", help="arayüzü aç")
    s.add_argument("project", nargs="?")
    s.add_argument("--browser", action="store_true", help="pencere yerine tarayıcıda aç")
    s.add_argument("--serve", action="store_true", help="sadece sunucu (pencere/tarayıcı açma)")
    s.add_argument("--port", type=int, default=8765)
    s.set_defaults(fn=cmd_gui)

    sub.add_parser("mcp", help="MCP sunucusu (stdio)").set_defaults(fn=cmd_mcp)

    a = ap.parse_args(argv)
    if sys.platform == "win32":
        try:
            sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        except Exception:  # noqa: BLE001
            pass
    a.fn(a)


if __name__ == "__main__":
    main()
