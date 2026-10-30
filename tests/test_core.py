import os
from pathlib import Path

import numpy as np
import pytest

from vedit import Project, Script, Shape, Text, Video, model
from vedit.audio import collect_events
from vedit.export import export
from vedit.lint import lint
from vedit.presets import PRESETS, apply_preset
from vedit.render import Renderer
from vedit.sheet import contact_sheet
from vedit.srt import export_srt, import_srt, parse_srt
from vedit.templates import TEMPLATES, make_template

ROOT = Path(__file__).resolve().parent.parent
ASSETS = ROOT / "tests" / "assets"
VIDEO = str(ASSETS / "test.mp4")
TONE = str(ASSETS / "tone.wav")


def small_project():
    p = Project(360, 640, fps=12, name="test", base_dir=str(ROOT))
    s = p.scene("A", duration=1.5)
    s.add(Text("Merhaba ğüşiöç", size=40)).preset("pop_in")
    s.add(Shape("star", w=80, h=80, fill="#ffd60a")).preset("spin_in")
    s2 = p.scene("B", duration=1.5, transition="fade", transition_duration=0.3)
    s2.add(Video(VIDEO, fit="cover"))
    p.music(TONE, volume=0.3)
    return p


def test_value_at_keyframes_and_expr():
    v = {"keyframes": [{"t": 0, "v": 0, "ease": "linear"}, {"t": 1, "v": 10}]}
    assert model.value_at(v, 0.5) == pytest.approx(5)
    assert model.value_at(v, -1) == 0 and model.value_at(v, 2) == 10
    assert model.value_at({"expr": "t*2"}, 1.5) == pytest.approx(3)
    assert model.value_at({"keyframes": [{"t": 0, "v": "#000000"}, {"t": 1, "v": "#ffffff"}]}, 0.5) \
        .startswith("#80")


def test_validate_catches_errors():
    p = model.new_project()
    p["comps"]["main"]["layers"].append({"id": "x", "type": "bogus", "duration": 0})
    errs = model.validate(p)
    assert any("bilinmeyen" in e for e in errs)
    p = model.new_project()
    p["comps"]["a"] = model.new_comp()
    p["comps"]["a"]["layers"].append(model.new_layer("comp", comp="main"))
    p["comps"]["main"]["layers"].append(model.new_layer("comp", comp="a"))
    assert any("Döngüsel" in e for e in model.validate(p))


def test_render_frame_and_scale():
    p = small_project()
    with Renderer(p.data, str(ROOT), scale=1.0) as r:
        img = r.render_image(1.0)
        assert img.size == (360, 640)
        assert np.asarray(img)[..., 3].max() == 255
        assert not r.warnings
        rgb = r.render_rgb(2.0)
        assert rgb.shape == (640, 360, 3) and rgb.std() > 5  # video görünüyor
    with Renderer(p.data, str(ROOT), scale=0.5) as r:
        assert r.render_image(1.0).size == (180, 320)


@pytest.mark.parametrize("name", list(PRESETS))
def test_presets_apply(name):
    layer = model.new_layer("text", 0, 2, props={"text": "abc def", "x": 100, "y": 100})
    apply_preset(layer, name)
    p = model.new_project(200, 200)
    p["comps"]["main"]["layers"].append(layer)
    assert not model.validate(p)
    with Renderer(p, str(ROOT), 0.5) as r:
        r.render_image(0.3)
        assert not r.warnings, r.warnings


@pytest.mark.parametrize("name", list(TEMPLATES))
def test_templates(name):
    layers = make_template(name, 1080, 1920, at=0.5, src=str(ROOT / "brand" / "logo.png")) \
        if name == "logo_reveal" else make_template(name, 1080, 1920, at=0.5)
    p = model.new_project()
    p["comps"]["main"]["layers"] += layers
    assert layers and not model.validate(p)
    with Renderer(p, str(ROOT), 0.25) as r:
        r.render_image(1.5)
        assert not r.warnings, r.warnings


def test_audio_events_and_export(tmp_path):
    p = small_project()
    events = collect_events(p.data, str(ROOT))
    assert len(events) == 2  # müzik + videonun sesi
    out = export(p.data, str(tmp_path / "o.mp4"), str(ROOT), "draft", workers=2)
    from vedit.media import probe

    info = probe(out)
    assert info["has_audio"] and abs(info["duration"] - p.duration) < 0.2


def test_gif_export(tmp_path):
    p = small_project()
    out = export(p.data, str(tmp_path / "o.gif"), str(ROOT), "gif", workers=1, t1=1.0)
    assert os.path.getsize(out) > 1000


def test_lint_and_sheet(tmp_path):
    p = Project(1080, 1920, base_dir=str(ROOT))
    s = p.scene("A", duration=2)
    s.add(Text("Bu yazı çok uzun ve ekrandan taşacak kadar geniş bir satır", size=120, x=900))
    s.add(Text("kısa", size=20), duration=0.5)
    issues = lint(p.data, str(ROOT))
    msgs = " ".join(i["msg"] for i in issues)
    assert "taşıyor" in msgs and "küçük" in msgs and "1.2s" in msgs
    res = contact_sheet(p.data, str(ROOT), str(tmp_path / "s.png"), count=4)
    assert os.path.exists(res["path"]) and len(res["times"]) >= 2


def test_script_layers():
    p = Project(360, 640, base_dir=str(ROOT))
    s = p.scene("A", duration=1)
    s.add(Script("scripts/parcacik.py", params={"adet": 20}))
    s.add(Script("scripts/eski_moviepy_ornek.py", params={"sure": 1}))
    with Renderer(p.data, str(ROOT), 0.5) as r:
        r.render_image(0.5)
        assert not r.warnings, r.warnings


def test_srt_roundtrip(tmp_path):
    srt = tmp_path / "a.srt"
    srt.write_text("1\n00:00:00,500 --> 00:00:02,000\nMerhaba\n\n2\n00:00:02,000 --> 00:00:03,500\nDünya <b>!</b>\n",
                   encoding="utf-8")
    assert len(parse_srt(srt.read_text(encoding="utf-8"))) == 2
    p = model.new_project()
    assert import_srt(p, str(srt), style="highlight") == 2
    out = tmp_path / "b.srt"
    export_srt(p, str(out))
    assert "Dünya !" in out.read_text(encoding="utf-8")


def _alpha_at(p, x, y, t=0.5):
    with Renderer(p, str(ROOT), 1.0) as r:
        return np.asarray(r.render_image(t))[y, x, 3]


def test_filled_open_path_and_anchor():
    p = model.new_project(400, 400, background=None)
    water = model.new_layer("shape", 0, 1, props={
        "shape": "path", "fill": "#3b82c4", "stroke_color": None, "stroke_width": 0,
        "points": [[100, 200], [300, 200], [280, 350], [120, 350]]})
    p["comps"]["main"]["layers"].append(water)
    assert _alpha_at(p, 200, 280) == 0          # açık yol: boyanmaz
    water["filled"] = True
    assert _alpha_at(p, 200, 280) > 200         # filled: içi boyanır
    # anchor_y=1 iken şekil yerinde kalmalı (varsayılan konum noktalardan gelir)
    water["props"]["anchor_y"] = 1
    assert _alpha_at(p, 200, 280) > 200 and _alpha_at(p, 200, 150) == 0
    water["smooth"] = True
    assert _alpha_at(p, 200, 280) > 200


def test_shape_point_matrix_is_identity_when_unmoved():
    p = model.new_project(400, 400)
    layer = model.new_layer("shape", 0, 1, props={"shape": "path", "points": [[50, 60], [300, 90]]})
    p["comps"]["main"]["layers"].append(layer)
    with Renderer(p, str(ROOT), 0.25) as r:
        m = r.layer_corners("main", layer, 0.5)["matrix"]
    assert m == pytest.approx([1, 0, 0, 0, 1, 0], abs=1e-6)


def test_save_load_roundtrip(tmp_path):
    p = small_project()
    path = p.save(tmp_path / "x.vedit.json")
    q = Project.load(path)
    assert q.data == model.normalize(model.load_project(path))
    assert q.duration == pytest.approx(p.duration)
