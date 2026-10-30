"""Örnek medyayı (assets/ornek_*) ve örnek projeleri (projects/) üretir.

Depoda büyük dosya tutmamak için kurulumda çalıştırılır:
    .venv/Scripts/python.exe tools/ornekleri_uret.py
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from vedit.util import run_ffmpeg  # noqa: E402


def main():
    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)
    (ROOT / "projects").mkdir(exist_ok=True)
    klip = assets / "ornek_klip.mp4"
    if not klip.exists():
        print("Örnek klip üretiliyor…")
        run_ffmpeg(["-f", "lavfi", "-i", "mandelbrot=size=1080x1920:rate=30", "-t", "6",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "23", str(klip)])
    muzik = assets / "ornek_muzik.wav"
    if not muzik.exists():
        print("Örnek müzik üretiliyor…")
        run_ffmpeg(["-f", "lavfi", "-i", "sine=frequency=330:duration=20,volume=0.3",
                    "-f", "lavfi", "-i", "sine=frequency=495:duration=20,volume=0.2",
                    "-filter_complex", "[0][1]amix=inputs=2,aecho=0.8:0.7:120:0.3", str(muzik)])
    for script in ("demo_tanitim.py", "tema_demolari.py"):
        print(f"{script} çalıştırılıyor…")
        subprocess.run([sys.executable, str(ROOT / "examples" / script)], cwd=ROOT, check=True)
    print("Hazır.")


if __name__ == "__main__":
    main()
