"""Ses: projedeki tüm ses kaynaklarını toplayıp FFmpeg ile tek parça halinde karıştırır.

Ses veren katmanlar: "audio" ve sesi olan "video" katmanları (iç içe kompozisyonlar dahil).
Katman alanları: "volume" (1.0), "mute", "audio_fade_in", "audio_fade_out", "in", "speed", "loop".
"""
from __future__ import annotations

import os

from . import model
from .media import probe
from .util import resolve_path, run_ffmpeg


def collect_events(project: dict, base_dir, comp_id=None, offset=0.0, window=None,
                   depth=0) -> list[dict]:
    """→ [{src, at, src_in, dur, speed, volume, fade_in, fade_out, loop}] (ana zaman çizelgesinde)"""
    if depth > 8:
        return []
    comp = model.get_comp(project, comp_id)
    events = []
    for layer in comp["layers"]:
        if not layer.get("enabled", True) or layer.get("mute"):
            continue
        t = layer["type"]
        start, dur = float(layer["start"]), float(layer["duration"])
        if t in ("audio", "video"):
            path = resolve_path(layer.get("src"), base_dir)
            if not path or not os.path.exists(path):
                continue
            try:
                if t == "video" and not probe(path)["has_audio"]:
                    continue
            except Exception:  # noqa: BLE001
                continue
            ev = {
                "src": path, "at": start, "src_in": float(layer.get("in", 0)), "dur": dur,
                "speed": float(layer.get("speed", 1.0)),
                "volume": float(layer.get("volume", 1.0)),
                "fade_in": float(layer.get("audio_fade_in", 0)),
                "fade_out": float(layer.get("audio_fade_out", 0)),
                "loop": bool(layer.get("loop")),
            }
            events.append(ev)
        elif t == "comp" and layer.get("comp") in project["comps"]:
            sub_in = float(layer.get("in", 0))
            for ev in collect_events(project, base_dir, layer["comp"], 0.0, None, depth + 1):
                # alt kompozisyon zamanını [sub_in, sub_in + dur] penceresine kırp
                s = max(ev["at"], sub_in)
                e = min(ev["at"] + ev["dur"], sub_in + dur)
                if e <= s:
                    continue
                ev = dict(ev)
                ev["src_in"] += (s - ev["at"]) * ev["speed"]
                ev["at"] = start + (s - sub_in)
                ev["dur"] = e - s
                ev["volume"] *= float(layer.get("volume", 1.0))
                events.append(ev)
    for ev in events:
        ev["at"] += offset
    return events


def _atempo_chain(speed: float) -> list[str]:
    out = []
    s = speed
    while s > 2.0:
        out.append("atempo=2.0")
        s /= 2.0
    while s < 0.5:
        out.append("atempo=0.5")
        s /= 0.5
    if abs(s - 1.0) > 1e-3:
        out.append(f"atempo={s:.4f}")
    return out


def render_audio(project: dict, base_dir, out_path: str, t0: float, t1: float,
                 comp_id=None, sample_rate=48000) -> bool:
    """[t0, t1] aralığının sesini WAV olarak yazar. Ses yoksa False döner (dosya yazılmaz)."""
    length = max(0.01, t1 - t0)
    events = collect_events(project, base_dir, comp_id)
    args: list[str] = []
    filters: list[str] = []
    labels: list[str] = []
    n = 0
    for ev in events:
        s = max(t0, ev["at"])
        e = min(t1, ev["at"] + ev["dur"])
        if e <= s + 1e-3:
            continue
        src_off = ev["src_in"] + (s - ev["at"]) * ev["speed"]
        if ev["loop"]:
            args += ["-stream_loop", "-1"]
        args += ["-ss", f"{src_off:.4f}", "-t", f"{(e - s) * ev['speed']:.4f}", "-i", ev["src"]]
        chain = [f"[{n}:a]aresample={sample_rate}", "aformat=channel_layouts=stereo"]
        chain += _atempo_chain(ev["speed"])
        if abs(ev["volume"] - 1.0) > 1e-3:
            chain.append(f"volume={ev['volume']:.3f}")
        seg = e - s
        if ev["fade_in"] > 0 and s <= ev["at"] + 1e-3:
            chain.append(f"afade=t=in:st=0:d={min(ev['fade_in'], seg):.3f}")
        if ev["fade_out"] > 0 and e >= ev["at"] + ev["dur"] - 1e-3:
            fo = min(ev["fade_out"], seg)
            chain.append(f"afade=t=out:st={seg - fo:.3f}:d={fo:.3f}")
        delay = int(round((s - t0) * 1000))
        if delay > 0:
            chain.append(f"adelay={delay}|{delay}")
        lab = f"a{n}"
        filters.append(",".join(chain) + f"[{lab}]")
        labels.append(f"[{lab}]")
        n += 1
    if n == 0:
        return False
    mix = "".join(labels) + (f"amix=inputs={n}:normalize=0:dropout_transition=0," if n > 1 else "anull,")
    mix += f"apad=whole_dur={length:.4f},atrim=0:{length:.4f}[out]"
    filters.append(mix)
    run_ffmpeg([*args, "-filter_complex", ";".join(filters), "-map", "[out]",
                "-ac", "2", "-ar", str(sample_rate), "-c:a", "pcm_s16le", out_path])
    return True
