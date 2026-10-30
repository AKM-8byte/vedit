"""Tema kaydı. Yeni tema eklemek için bu klasöre bir modül yazıp THEMES'e ekleyin."""
from __future__ import annotations

from .base import Theme

THEMES: dict[str, type[Theme]] = {}


def register(cls: type[Theme]) -> type[Theme]:
    THEMES[cls.name] = cls
    return cls


def get_theme(name: str, params: dict | None = None) -> Theme:
    _load_all()
    if name not in THEMES:
        raise KeyError(name)
    return THEMES[name](params or {})


def list_themes() -> list[dict]:
    _load_all()
    return [cls.info() for cls in THEMES.values()]


_loaded = False


def _load_all():
    global _loaded
    if _loaded:
        return
    _loaded = True
    from . import builtin  # noqa: F401
