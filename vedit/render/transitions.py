"""Katman giriş/çıkış geçişleri.

Katmanda:  "transition_in": {"type": "slide_left", "duration": 0.5, "ease": "out_cubic"}
İki klip arasında crossfade: ikinci klibi farklı kanala, biraz üst üste koyup fade ver.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from .. import easing

TRANSITIONS = {
    "fade": "Solma",
    "slide_left": "Soldan kay",
    "slide_right": "Sağdan kay",
    "slide_up": "Aşağıdan kay",
    "slide_down": "Yukarıdan kay",
    "zoom_in": "Yakınlaşarak",
    "zoom_out": "Uzaklaşarak",
    "pop": "Pop",
    "spin": "Dönerek",
    "blur": "Bulanıklıktan",
    "wipe_left": "Silme (sol)",
    "wipe_right": "Silme (sağ)",
    "wipe_up": "Silme (yukarı)",
    "wipe_down": "Silme (aşağı)",
    "circle": "Daire açılım",
    "drop": "Düşerek (sekme)",
    "glitch": "Glitch",
}


@dataclass
class TState:
    opacity: float = 1.0
    dx: float = 0.0
    dy: float = 0.0
    scale: float = 1.0
    rotation: float = 0.0
    blur: float = 0.0
    wipe: tuple | None = None  # (yön, ilerleme 0..1)
    circle: float | None = None
    glitch: float = 0.0
    extra: dict = field(default_factory=dict)


def _apply(st: TState, kind: str, p: float, w: float, h: float, direction: str) -> None:
    """p: 0 = tamamen gizli, 1 = tamamen görünür."""
    q = 1 - p
    if kind == "fade":
        st.opacity *= p
    elif kind.startswith("slide_"):
        side = kind[6:]
        dist = {"left": (-w, 0), "right": (w, 0), "up": (0, h), "down": (0, -h)}[side]
        st.dx += dist[0] * q * 0.6
        st.dy += dist[1] * q * 0.6
        st.opacity *= min(1.0, p * 1.5)
    elif kind == "zoom_in":
        st.scale *= 0.6 + 0.4 * p
        st.opacity *= p
    elif kind == "zoom_out":
        st.scale *= 1.0 + 0.5 * q
        st.opacity *= p
    elif kind == "pop":
        st.scale *= max(0.0, p)
    elif kind == "spin":
        st.rotation += -180 * q
        st.scale *= p
        st.opacity *= min(1.0, p * 2)
    elif kind == "blur":
        st.blur = max(st.blur, 40 * q)
        st.opacity *= min(1.0, p * 1.3)
    elif kind.startswith("wipe_"):
        st.wipe = (kind[5:], p)
    elif kind == "circle":
        st.circle = p
    elif kind == "drop":
        st.dy += -h * 0.5 * q
        st.opacity *= min(1.0, p * 3)
    elif kind == "glitch":
        st.glitch = max(st.glitch, q)
        st.opacity *= 1.0 if p > 0.15 else p / 0.15


DEFAULT_EASE = {"pop": "out_back", "drop": "out_bounce", "spin": "out_cubic"}


def state(layer: dict, lt: float, w: float, h: float, theme_default: dict | None = None) -> TState:
    st = TState()
    dur = layer["duration"]
    for key, is_in in (("transition_in", True), ("transition_out", False)):
        tr = layer.get(key)
        if tr == "theme":
            tr = theme_default
        if not tr or not tr.get("type"):
            continue
        d = max(1e-3, float(tr.get("duration", 0.5)))
        local = lt if is_in else dur - lt
        if local >= d:
            continue
        kind = tr["type"]
        ease_name = tr.get("ease") or DEFAULT_EASE.get(kind, "out_cubic")
        # Çıkışta da aynı eğri: "kalan süre" üzerinden hesaplandığı için doğal hızlanma verir
        p = easing.apply(ease_name, max(0.0, local / d))
        if not is_in and kind.startswith("slide_"):
            # çıkışta ters yöne kay
            opposite = {"left": "right", "right": "left", "up": "down", "down": "up"}
            kind = "slide_" + opposite[kind[6:]]
        _apply(st, kind, p, w, h, "in" if is_in else "out")
    return st
