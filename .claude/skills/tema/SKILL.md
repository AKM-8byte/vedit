---
name: tema
description: Projeye görsel tema uygular veya yeni tema yazar (matrix, çizim/karakalem, neon, retro VHS, sinematik, minimal, glitch). "matrix temalı", "çizim tarzında", "el çizimi gibi", "neon", "retro", "sinematik yap", "yeni tema ekle" isteklerinde kullan.
---

# Temalar

`.venv/Scripts/vedit.exe themes` → temalar ve parametreleri.

**Uygulama**
- Yeni proje: `Project(..., theme="cizim", theme_params={"paper": "lined"})`.
  Sahneler otomatik `background="theme"` olur.
- Var olan proje: `p.data["theme"] = {"name": "matrix", "params": {}}` ve tema arka planını
  istediğin sahnelerde `comp["background"] = "theme"`.
- Yazılarda temanın harf animasyonu: `Text(..., char_anim="theme")`; geçiş: `transition="theme"`.
- Tema yazı varsayılanları (font, renk, glow) yalnızca katmanda **verilmemiş** proplara uygulanır;
  temanın görünümünü istiyorsan font/renk verme.
- Bir katmanı temadan muaf tut: `theme_style=False` (ör. logo).

**Temaya uygun içerik**
- matrix: kısa, büyük harf metinler; `char_anim="theme"` (decode); yeşil vurgular.
- cizim: el yazısı fontu otomatik; şekiller titrer (`rough`); oklar/çizgiler için `draw_on`.
- neon: koyu arka plan, az sayıda parlak öğe; `glow` zaten tema tarafından eklenir.
- retro: VHS kayıt etiketi otomatik; 4:3 hissi için kenarlardan uzak yerleşim.
- sinematik: yavaş fade geçişler (0.8–1.2 sn), geniş harf aralıklı başlıklar, ken_burns.

**Yeni tema yazmak**: `vedit/themes/builtin.py`'deki bir temayı örnek al, `Theme` alt sınıfı
(background / media_filter / jitter / post / text_defaults / char_anim / transition / palette),
`@register` ile kaydet, `tests/test_themes.py` çalıştır, kare panosuyla kontrol et.
