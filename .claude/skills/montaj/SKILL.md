---
name: montaj
description: Var olan video/görsel kliplerini (inbox/, assets/ ya da kullanıcının verdiği klasör) müzikle birleştirip kurgu yapar. "şu klipleri birleştir", "montaj yap", "videoları arka arkaya koy", "kurgu" isteklerinde kullan.
---

# Klip montajı

1. **Klipleri bul**: kullanıcı klasör vermediyse `inbox/` ve `assets/`. Her biri için süre/çözünürlük:
   ```python
   from vedit.media import probe; print(probe("inbox/a.mp4"))
   ```
2. **Sırala**: dosya adı sırası (ya da kullanıcının söylediği). Gereksiz uzun klipleri kırp
   (`Video(src, source_in=1.0, duration=3)`) — varsayılan klip başına en fazla 4–6 sn.
3. **Format**: çoğunluğun en-boy oranını seç. Farklı orandaki klipler için `fit="cover"`
   (kırparak doldur) ya da `fit="contain"` + bulanık arka plan:
   ```python
   s.add(Video(src, fit="cover", mute=True, effects=[{"type":"blur","params":{"radius":40}}]))
   s.add(Video(src, fit="contain"))
   ```
4. **Kurgu**: her klip bir `p.scene(...)`; aralarına `transition="fade"` (0.3–0.5 sn).
   Ritim müziğe uysun: müzik varsa sahne sürelerini eşit böl.
5. **Ses**: klip sesleri gerekmezse `mute=True`; müzik `p.music(..., volume=0.5)`;
   konuşmalı kliplerde müzik `volume=0.15`.
6. **Üstüne**: istenirse başlık (`template("title_card")`), alt bant, altyazı, ilerleme çubuğu.
7. Kaydet → `vedit preview` → kare panosunu kontrol et → teslim (video-olustur 5–6 adımları).
