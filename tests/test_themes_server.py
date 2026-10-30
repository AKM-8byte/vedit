from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from vedit import model
from vedit.render import Renderer
from vedit.themes import get_theme, list_themes

ROOT = Path(__file__).resolve().parent.parent


@pytest.mark.parametrize("name", [t["name"] for t in list_themes()])
def test_theme_renders(name):
    p = model.new_project(360, 640, name=name)
    p["theme"] = {"name": name, "params": {}}
    c = p["comps"]["main"]
    c["background"] = "theme"
    c["layers"] += [
        model.new_layer("text", 0, 2, 1, props={"text": "Tema"}, char_anim="theme",
                        transition_in="theme"),
        model.new_layer("image", 0, 2, 0, src=str(ROOT / "brand" / "logo.png")),
        model.new_layer("shape", 0, 2, 2, props={"shape": "star", "fill": "theme.accent"}),
    ]
    with Renderer(p, str(ROOT), 0.5) as r:
        for t in (0.1, 1.0, 1.9):
            img = r.render_image(t)
            assert img.size == (180, 320)
        assert not r.warnings, r.warnings
    th = get_theme(name)
    assert th.label and isinstance(th.PARAMS, dict)


@pytest.fixture()
def client():
    from vedit.server.app import app

    return TestClient(app)


def test_settings_language(client):
    before = client.get("/api/settings").json()
    try:
        assert client.put("/api/settings", json={"lang": "en", "evil": 1}).json()["lang"] == "en"
        got = client.get("/api/settings").json()
        assert got["lang"] == "en" and "evil" not in got
    finally:
        client.put("/api/settings", json={"lang": before.get("lang", "tr")})


def test_server_roundtrip(client, tmp_path):
    lib = client.get("/api/library").json()
    assert lib["presets"] and lib["themes"] and lib["effects"]
    st = client.post("/api/new", json={"width": 320, "height": 568, "duration": 2}).json()
    p = st["project"]
    p["comps"]["main"]["layers"].append(model.new_layer("text", 0, 2, 0, props={"text": "Hi"}))
    assert client.put("/api/project", json={"project": p}).json()["errors"] == []
    r = client.get("/api/frame", params={"t": 1, "scale": 0.5})
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg"
    lid = p["comps"]["main"]["layers"][0]["id"]
    assert client.get("/api/pick", params={"x": 160, "y": 284, "t": 1}).json()["id"] == lid
    assert len(client.get("/api/bbox", params={"layer": lid, "t": 1}).json()["corners"]) == 4
    out = tmp_path / "s.vedit.json"
    assert client.post("/api/save", json={"path": str(out)}).json()["ok"]
    assert out.exists()
    res = client.post("/api/preset", json={"layer": p["comps"]["main"]["layers"][0], "name": "pop_in"}).json()
    assert "keyframes" in res["props"]["scale"]
    assert client.post("/api/lint", json={}).status_code == 200
