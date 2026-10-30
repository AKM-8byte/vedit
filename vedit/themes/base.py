"""Tema taban sınıfı.

Bir tema, projenin genel görünümünü tek seçimle değiştirir:
  * background(): "theme" arka planlı sahnelere animasyonlu arka plan
  * media_filter(): video/görsel katmanlarına filtre (ör. karakalem)
  * jitter():      katmanlara titreşim (ör. el çizimi "boil" etkisi)
  * post():        son kareye işlem (ör. tarama çizgileri, kumlanma)
  * text_defaults: yazı katmanlarının varsayılan font/renk/kontur değerleri
  * char_anim:     `"char_anim": "theme"` olan yazıların harf animasyonu
  * transition:    `"transition_in": "theme"` olan katmanların geçişi
  * palette:       "theme.accent" gibi renk adları
"""
from __future__ import annotations

from PIL import Image


class Theme:
    name = "base"
    label = "Tema"
    description = ""
    PARAMS: dict = {}
    text_defaults: dict = {}
    char_anim: dict | None = None
    transition: dict | None = {"type": "fade", "duration": 0.4}
    palette: dict = {}
    rough: float = 0.0
    preview_bg = "#000000"

    def __init__(self, params: dict | None = None):
        self.p = {k: v.get("default") for k, v in self.PARAMS.items()}
        self.p.update(params or {})
        self.key = (self.name, tuple(sorted((k, str(v)) for k, v in self.p.items())))
        self.setup()

    def setup(self):
        """Parametrelere göre sınıf değerlerini güncellemek için."""

    def background(self, r, t: float, w: int, h: int) -> Image.Image | None:
        return Image.new("RGBA", (w, h), r.color(self.palette.get("background", "#000000")))

    def media_filter(self, r, layer: dict, img: Image.Image, lt: float) -> Image.Image:
        return img

    def jitter(self, r, layer: dict, lt: float) -> tuple[float, float, float]:
        return 0.0, 0.0, 0.0

    def post(self, r, frame: Image.Image, t: float) -> Image.Image:
        return frame

    @classmethod
    def info(cls) -> dict:
        return {
            "name": cls.name,
            "label": cls.label,
            "description": cls.description,
            "params": cls.PARAMS,
            "palette": cls.palette,
            "text_defaults": cls.text_defaults,
            "char_anim": cls.char_anim,
            "transition": cls.transition,
            "preview_bg": cls.preview_bg,
        }
