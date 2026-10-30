# VEdit — Proje Planı

Claude ile Python (MoviePy / Pillow / NumPy) kullanarak üretilen videoları
**oluşturmak, düzenlemek ve animasyonlandırmak** için masaüstü aracı.

## Temel fikir

```
Claude script yazar ──► vedit SDK ──► .vedit.json proje ──► Arayüzde düzenle ──► FFmpeg export
        ▲                                   │
        └──── kare panosu (PNG) ◄───────────┘   (Claude kendi çıktısını görür ve düzeltir)
```

* Tek render motoru (Pillow + NumPy): önizleme ve export **aynı** kodu kullanır → ekranda ne
  görüyorsan çıktıda o vardır.
* Proje dosyası okunabilir JSON: hem arayüz hem Claude düzenleyebilir.

## Mimari

| Katman | Teknoloji | Klasör |
|---|---|---|
| Arayüz | HTML + CSS + saf JavaScript (derleme adımı yok), pywebview penceresi | `ui/` |
| Sunucu | FastAPI (yerel) | `vedit/server/` |
| Motor | Pillow + NumPy render, FFmpeg encode/decode, MoviePy uyumluluğu | `vedit/render/`, `vedit/export.py` |
| SDK | `from vedit import Project, Text, ...` | `vedit/sdk.py` |
| Temalar | matrix, cizim, neon, retro, sinematik, minimal, glitch | `vedit/themes/` |
| Claude sistemi | CLAUDE.md, skill'ler, hook'lar, MCP sunucusu | `CLAUDE.md`, `.claude/`, `vedit/mcp_server.py` |

## Aşamalar

1. **Çekirdek motor** — veri modeli, keyframe + easing, katmanlar (video, görsel, yazı, şekil,
   ses, kompozisyon), efektler, blend modları, FFmpeg export, paralel render.
   CLI: `vedit render`, `vedit preview --sheet`, `vedit frame`, `vedit lint`.
2. **Claude sistemi** — CLAUDE.md, marka kiti (`brand/`), skill'ler (video-olustur, montaj,
   intro-outro, altyazi, revize, tema), proje doğrulama hook'u.
3. **Arayüz** — çok kanallı timeline (taşı, kes, kırp, snap, zoom), önizleme (kare + parça
   cache'li oynatma, render çubuğu), medya paneli, özellikler paneli, geri al/yinele, kısayollar,
   izlenen klasör (`inbox/`), diskteki proje değişince yeniden yükleme.
4. **Animasyon modu** — keyframe şeridi, easing seçimi ve eğri önizlemesi, hazır animasyonlar,
   harf harf yazı animasyonları, şablonlar (lower third, abone ol, sayaç…), iç içe sahneler.
5. **Cila ve entegrasyon** — Script katmanı (PARAMS → arayüz kontrolleri), filtreler ve renk,
   chroma key, LUT, export profilleri (YouTube, Shorts/Reels/TikTok, kare, GIF, ProRes, WebM),
   SRT altyazı, MCP sunucusu, otomatik kayıt.
   **Temalar:** çizim, matrix, neon, retro VHS, sinematik, minimal, glitch — arka plan, katman
   filtresi, son işlem, varsayılan yazı stili ve geçiş tek seçimle değişir.

## Kapsam dışı / bilinen sınırlar

* GPU hızlandırmalı render yok (CPU, çok çekirdekli).
* 4K'da önizleme düşük çözünürlükte yapılır.
* Konuşmadan otomatik altyazı için ek paket gerekir (`faster-whisper`), varsayılan kurulumda yok.
