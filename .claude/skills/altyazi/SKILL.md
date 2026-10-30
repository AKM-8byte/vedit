---
name: altyazi
description: Videoya altyazı ekler — SRT dosyasından içe aktarma, metinden zamanlanmış altyazı üretme veya Shorts tarzı kelime vurgulu altyazı. "altyazı ekle", "srt", "caption", "yazıları ekrana koy" isteklerinde kullan.
---

# Altyazı

**SRT varsa**:
`.venv/Scripts/vedit.exe srt import altyazi.srt projects/x.vedit.json --style highlight`
Stiller: `caption` (kelime kelime pop), `highlight` (karaoke vurgusu), `plain` (kutulu, sade).

**Metin varsa, SRT yoksa**: cümlelere böl, her cümleye kelime sayısı / 2.8 sn süre ver
(en az 1.2 sn), ardışık yerleştir ve `template("caption", text=..., highlight="#ffd60a")` ile
ekle (`p.template(..., at=baslangic, duration=sure)`).

**Konuşmadan otomatik altyazı**: varsayılan kurulumda yok. Kullanıcı isterse:
`.venv/Scripts/python.exe -m pip install faster-whisper`, sonra küçük bir script ile
`WhisperModel("small").transcribe(path, language="tr", word_timestamps=True)` → SRT yaz →
yukarıdaki gibi içe aktar. Bunu yapmadan önce kullanıcıya indirme boyutunu (~500 MB) söyle.

**Kurallar**: dikey videoda y ≈ yüksekliğin %62–66'sı (alt %20 platform arayüzü),
`max_width` genişliğin %82'si, kontur (stroke) 5–6 px ya da yarı saydam kutu.
SRT dışa aktarma: `vedit srt export cikti.srt projects/x.vedit.json`.
