"""Ortak yardımcılar: renkler, fontlar, yollar, FFmpeg."""
from __future__ import annotations

import functools
import os
import re
import subprocess
import sys
from pathlib import Path

from PIL import ImageFont

ROOT = Path(__file__).resolve().parent.parent

# --------------------------------------------------------------------------- FFmpeg


@functools.lru_cache(maxsize=1)
def ffmpeg_exe() -> str:
    env = os.environ.get("VEDIT_FFMPEG")
    if env:
        return env
    try:
        import imageio_ffmpeg

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


def run_ffmpeg(args: list[str], check: bool = True) -> subprocess.CompletedProcess:
    cmd = [ffmpeg_exe(), "-hide_banner", "-loglevel", "error", "-y", *args]
    proc = subprocess.run(cmd, capture_output=True, creationflags=NO_WINDOW)
    if check and proc.returncode != 0:
        raise RuntimeError("FFmpeg hatası:\n" + proc.stderr.decode("utf-8", "replace")[-2000:])
    return proc


# --------------------------------------------------------------------------- renkler

NAMED_COLORS = {
    "white": "#ffffff", "black": "#000000", "red": "#ff3b30", "green": "#34c759",
    "blue": "#0a84ff", "yellow": "#ffd60a", "orange": "#ff9f0a", "purple": "#bf5af2",
    "pink": "#ff375f", "cyan": "#64d2ff", "gray": "#8e8e93", "grey": "#8e8e93",
    "transparent": "#00000000", "beyaz": "#ffffff", "siyah": "#000000",
    "kirmizi": "#ff3b30", "yesil": "#34c759", "mavi": "#0a84ff", "sari": "#ffd60a",
}


def parse_color(value, palette: dict | None = None) -> tuple[int, int, int, int]:
    """'#rgb', '#rrggbb', '#rrggbbaa', isim, 'brand.primary', [r,g,b(,a)] → RGBA tuple."""
    if value is None:
        return (0, 0, 0, 0)
    if isinstance(value, (list, tuple)):
        vals = [int(round(float(v))) for v in value]
        if len(vals) == 3:
            vals.append(255)
        return tuple(max(0, min(255, v)) for v in vals[:4])  # type: ignore[return-value]
    s = str(value).strip()
    if palette and s in palette:
        return parse_color(palette[s])
    s = NAMED_COLORS.get(s.lower(), s)
    m = re.fullmatch(r"#?([0-9a-fA-F]{3,8})", s)
    if not m:
        m2 = re.fullmatch(r"rgba?\(([^)]*)\)", s)
        if m2:
            parts = [float(p) for p in m2.group(1).split(",")]
            if len(parts) == 4 and parts[3] <= 1:
                parts[3] *= 255
            return parse_color(parts)
        return (255, 0, 255, 255)  # tanınmayan renk: göze batan pembe
    h = m.group(1)
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h)
    if len(h) == 6:
        h += "ff"
    if len(h) != 8:
        return (255, 0, 255, 255)
    return tuple(int(h[i:i + 2], 16) for i in (0, 2, 4, 6))  # type: ignore[return-value]


def color_to_hex(rgba) -> str:
    r, g, b, a = (int(round(v)) for v in rgba)
    return f"#{r:02x}{g:02x}{b:02x}" + ("" if a == 255 else f"{a:02x}")


# --------------------------------------------------------------------------- fontlar

FONT_DIRS = [
    ROOT / "brand" / "fonts",
    Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts",
    Path.home() / "AppData/Local/Microsoft/Windows/Fonts",
    Path("/usr/share/fonts"),
    Path("/Library/Fonts"),
    Path("/System/Library/Fonts"),
]

FONT_ALIASES = {
    "arial": ["arial.ttf", "DejaVuSans.ttf"],
    "arial bold": ["arialbd.ttf", "DejaVuSans-Bold.ttf"],
    "segoe": ["segoeui.ttf"],
    "segoe ui": ["segoeui.ttf"],
    "segoe bold": ["segoeuib.ttf"],
    "segoe black": ["seguibl.ttf", "segoeuib.ttf"],
    "impact": ["impact.ttf"],
    "consolas": ["consola.ttf", "DejaVuSansMono.ttf"],
    "mono": ["consola.ttf", "cour.ttf", "DejaVuSansMono.ttf"],
    "georgia": ["georgia.ttf"],
    "serif": ["georgia.ttf", "times.ttf", "DejaVuSerif.ttf"],
    "times": ["times.ttf"],
    "comic": ["comic.ttf"],
    "handwriting": ["inkfree.ttf", "segoepr.ttf", "comic.ttf"],
    "el yazisi": ["inkfree.ttf", "segoepr.ttf", "comic.ttf"],
    "segoe print": ["segoepr.ttf"],
    "ink free": ["inkfree.ttf"],
    "bahnschrift": ["bahnschrift.ttf"],
    "verdana": ["verdana.ttf"],
    "tahoma": ["tahoma.ttf"],
    "trebuchet": ["trebuc.ttf"],
}


@functools.lru_cache(maxsize=256)
def find_font_file(name: str | None, base_dir: str | None = None) -> str | None:
    if not name:
        name = "arial"
    candidates: list[str] = []
    p = Path(name)
    if p.suffix.lower() in (".ttf", ".otf", ".ttc"):
        if base_dir and (Path(base_dir) / p).exists():
            return str(Path(base_dir) / p)
        if p.exists():
            return str(p)
        candidates.append(p.name)
    candidates += FONT_ALIASES.get(name.lower(), [])
    candidates += [name + ".ttf", name.replace(" ", "") + ".ttf", name.lower() + ".ttf"]
    dirs = ([Path(base_dir) / "fonts", Path(base_dir)] if base_dir else []) + FONT_DIRS
    for c in candidates:
        for d in dirs:
            f = d / c
            if f.exists():
                return str(f)
    return None


@functools.lru_cache(maxsize=512)
def load_font(name: str | None, size: int, base_dir: str | None = None) -> ImageFont.FreeTypeFont:
    size = max(1, int(round(size)))
    path = find_font_file(name, base_dir) or find_font_file("arial")
    if path:
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default(size)


def list_system_fonts() -> list[str]:
    out = set(FONT_ALIASES.keys())
    for d in FONT_DIRS:
        if d.exists():
            for f in d.glob("*.tt[fc]"):
                out.add(f.name)
    return sorted(out)


# --------------------------------------------------------------------------- yollar


def resolve_path(path: str | None, base_dir: str | os.PathLike | None) -> str | None:
    if not path:
        return None
    p = Path(path)
    if p.is_absolute():
        return str(p)
    if base_dir:
        q = Path(base_dir) / p
        if q.exists():
            return str(q)
    if p.exists():
        return str(p.resolve())
    if (ROOT / p).exists():
        return str(ROOT / p)
    return str(Path(base_dir) / p) if base_dir else str(p)


def stable_hash(s: str) -> int:
    """Süreçler arasında sabit kalan hash (paralel render'da tutarlılık için)."""
    import hashlib

    return int(hashlib.md5(str(s).encode()).hexdigest()[:8], 16)


def clamp(v, lo, hi):
    return lo if v < lo else hi if v > hi else v
