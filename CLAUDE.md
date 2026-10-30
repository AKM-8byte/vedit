# VEdit — Claude için çalışma kuralları

Bu klasör, Claude ile video üretip arayüzde düzenlemek için kurulmuş bir sistemdir.
Kullanıcı Türkçe konuşur; yanıtlar ve videodaki metinler aksi istenmedikçe **Türkçe**.

## Komutlar (Windows, proje kökünden)

| İş | Komut |
|---|---|
| Python | `.venv/Scripts/python.exe` |
| Kare panosu + lint | `.venv/Scripts/vedit.exe preview projects/X.vedit.json` |
| Tek kare | `.venv/Scripts/vedit.exe frame projects/X.vedit.json -t 2.5 -o kare.png` |
| Kalite kontrol | `.venv/Scripts/vedit.exe lint projects/X.vedit.json` |
| Video çıktısı | `.venv/Scripts/vedit.exe render projects/X.vedit.json -p shorts -o exports/X.mp4` |
| Proje özeti | `.venv/Scripts/vedit.exe info projects/X.vedit.json` |
| Listeler | `vedit themes`, `vedit presets`, `vedit templates`, `vedit effects`, `vedit profiles` |
| Arayüz | `.venv/Scripts/vedit.exe gui projects/X.vedit.json` |

SDK'nın tam başvurusu: `docs/CLAUDE_GUIDE.md` (gerektiğinde oku; her şeyi ezberleme).

## Her zaman

- Videolar **`vedit` SDK** ile yazılır (`from vedit import Project, Text, ...`). Doğrudan MoviePy ile
  MP4 üretme. Eski MoviePy/Pillow kodu gerekiyorsa onu bir **Script katmanına** sar
  (`scripts/` altında, `PARAMS` + `make_frame`).
- Üretim scripti `projects/<ad>.py`, çıktısı `projects/<ad>.vedit.json`. Script'i çalıştır, JSON'u
  elle yazma (küçük düzeltmeler hariç).
- MP4'ü **sadece kullanıcı isteyince** render et. Varsayılan teslim: proje dosyası + kare panosu.
- Renk ve font uydurma: `brand/brand.json` kullan (`brand="brand/brand.json"`, renkler
  `"brand.primary"` şeklinde). Tema seçildiyse renkler `"theme.accent"` gibi verilebilir.
- Varsayılan format: **1080x1920, 30fps** (dikey). Kullanıcı YouTube/yatay derse 1920x1080.
- Medya yolları proje dosyasına göre değil **proje köküne göre** yazılır (`assets/x.mp4`).
- Kullanıcının elle yaptığı düzenlemeleri koru: var olan bir `.vedit.json`'u değiştirirken
  `Project.load()` ile aç, sadece istenen katmanları değiştir, ID'leri koru.

## İş akışı (yeni video)

1. **Storyboard**: sahne listesi yaz (sahne adı, süre, ekrandaki metin, görsel, animasyon).
   Kısa bir video için onay beklemeden devam edebilirsin; 30 sn üzeri ise önce onay al.
2. **Projeyi oluştur**: `projects/<ad>.py` yaz ve çalıştır.
3. **Kontrol et**: `vedit preview` çalıştır, çıkan PNG'yi **Read ile aç ve bak**.
   Lint uyarılarını ve görselde gördüğün sorunları düzelt, tekrar kontrol et.
4. **Sun**: kullanıcıya proje yolunu, kare panosunu ve `vedit gui` komutunu ver.

## Kalite kontrol listesi (kare panosuna bakarken)

- Yazılar sarı güvenli alan çerçevesinin içinde mi? Ekrandan taşan bir şey var mı?
- Öğeler birbirinin üstüne istemeden biniyor mu? Yazı arka plandan okunuyor mu (kontrast)?
- Her yazı en az 1.2 sn ve kelime sayısı/3 sn kadar ekranda mı?
- Giriş animasyonları 0.3–0.8 sn, geçişler 0.3–0.6 sn arası mı?
- Siyah/boş kare var mı (lint "boş aralık" uyarısı)?
- Dikey videoda alt %20 ve sağ %12 platform arayüzüne ayrılmış; önemli metin oraya koyma.

## Animasyon ipuçları

- Hazır animasyon: `layer.preset("pop_in")`, çıkış: `.preset("fade_out")` (sona otomatik konur).
- Keyframe: `layer.animate("x", {0: 100, 0.6: 540}, ease="out_back")` — zaman katmana göredir.
- Sürekli hareket: `layer.expr("rotation", "sin(t*2)*8")` ya da `.preset("float")`.
- Harf animasyonu: `Text(...).chars("rise", unit="word", stagger=0.1)`.
- Şablon: `scene.template("lower_third", at=1, title="...", subtitle="...")`.
- Tema: `Project(..., theme="matrix")`; temanın yazı animasyonu için `char_anim="theme"`.
- Dolu görünmesi gereken alanları (bardaktaki su, kutu içi renk) sadece çizgiyle çizme:
  `Shape("path", filled=True, fill=...)` ile alanı boya (ayrıntı: CLAUDE_GUIDE "Kap içindeki sıvı").

## Revizyon istekleri

"Şunu değiştir" denince: projeyi yükle, **sadece ilgili katmanı** değiştir, kaydet, kare panosunu
yeniden üret ve değişen kareyi kontrol et. Bütün projeyi baştan üretme.

## Kod geliştirme (aracın kendisi)

- Motor: `vedit/` (render, export, SDK), arayüz: `ui/` (derleme yok, saf JS), testler: `tests/`.
- Değişiklikten sonra `.venv/Scripts/python.exe -m pytest -q` çalıştır.
