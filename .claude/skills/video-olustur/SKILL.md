---
name: video-olustur
description: Kullanıcının fikrinden/brief'inden sıfırdan animasyonlu video projesi üretir (storyboard → vedit SDK scripti → kare panosu kontrolü). "video yap", "intro yap", "animasyon oluştur", "şu konuda kısa video" gibi isteklerde kullan.
---

# Sıfırdan video oluşturma

1. **Brief'i netleştir** (sormadan varsayılan kullan, belirsizse tek soru sor):
   format (varsayılan 1080x1920 dikey), süre, tema (`vedit themes`), ton, metinler, medya
   (`assets/`, `inbox/` klasörlerine bak).
2. **Storyboard yaz** — tablo: sahne | süre | ekrandaki metin | görsel/medya | animasyon.
   Kurallar: sahne başına 1 ana mesaj; metin süresi ≥ kelime/3 sn; toplam ritim 2–5 sn/sahne.
3. **Script yaz**: `projects/<ad>.py` — `docs/CLAUDE_GUIDE.md`'deki API'yi kullan.
   - `Project(..., brand="brand/brand.json")`, renkler `"brand.primary"` vb.
   - Sahneleri `p.scene(...)` ile sırala, sahneler arası `transition="fade"` (ya da temaya uygun).
   - Her yazıya giriş animasyonu (`preset`) ve uzun sahnelerde çıkış animasyonu ver.
   - Müzik varsa en sonda `p.music(...)`.
   - Script'in sonunda `p.save("projects/<ad>.vedit.json")`.
4. **Çalıştır**: `.venv/Scripts/python.exe projects/<ad>.py`
5. **Kontrol**: `.venv/Scripts/vedit.exe preview projects/<ad>.vedit.json`
   → çıkan `_sheet.png`'yi Read ile aç. CLAUDE.md'deki kalite listesine göre incele.
   Lint uyarısı ya da görsel sorun varsa script'i düzelt, 4–5'i tekrarla (en fazla 3 tur).
   Belirli bir anı yakından görmek için: `vedit frame ... -t 2.4 -o kare.png --scale 0.5`.
6. **Teslim**: storyboard özeti, proje yolu, kare panosu yolu ve
   `.venv/Scripts/vedit.exe gui projects/<ad>.vedit.json` komutu. MP4'ü sadece istenirse:
   `vedit render projects/<ad>.vedit.json -p shorts -o exports/<ad>.mp4`.
