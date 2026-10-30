# VEdit

Claude ile Python'da (Pillow / NumPy / MoviePy / FFmpeg) üretilen videoları **oluşturmak,
düzenlemek ve animasyonlandırmak** için masaüstü aracı.

```
Claude script yazar → vedit SDK → .vedit.json proje → arayüzde düzenle → MP4 / GIF / MOV
            ▲                              │
            └──── kare panosu (PNG) ◄──────┘  Claude kendi çıktısını görüp düzeltir
```

## Başlangıç

| İş | Nasıl |
|---|---|
| Arayüzü aç | `baslat.cmd` (çift tıkla) ya da `.venv\Scripts\vedit.exe gui projects\demo_tanitim.vedit.json` |
| Tarayıcıda aç | `.venv\Scripts\vedit.exe gui --browser` |
| Örnek projeler | `projects/demo_tanitim.vedit.json`, `projects/tema_*.vedit.json` (her tema için bir tane) — `tools/ornekleri_uret.py` üretir |
| Kurulum | `kurulum.cmd` (Python 3.10+ gerekir; FFmpeg pakette gömülü gelir; örnek medya ve projeler de üretilir) |

`projects/`, `assets/` ve `inbox/` kişisel çalışma alanıdır; içerikleri git'e eklenmez.

## Arayüz

- **🎬 Düzenle**: çok kanallı timeline (sürükle, kenarlardan kırp, `C` ile kes, mıknatıs, zoom),
  medya tarayıcı (sürükle-bırak), önizlemede tıklayarak seç ve sürükleyerek taşı/ölçekle/döndür,
  ses dalga formu, geçişler, efektler, geri al/yinele.
- **✨ Oluştur**: seçili katmanın keyframe şeritleri (sürükleyerek zamanla, çift tıkla ekle),
  40 hazır animasyon, harf/kelime animasyonları, 11 şablon (alt bant, abone ol, sayaç…),
  easing eğrisi önizlemesi, ifadeler (◇ düğmesine sağ tıkla → `sin(t*2)*20`).
- **🧩 Kod**: katman/sahne/proje JSON'u, kalite kontrol (lint), kare panosu, Claude komutları.
- **Temalar**: Matrix, Çizim, Neon, Retro VHS, Sinematik, Minimal, Glitch. Tek tıkla arka planı,
  video filtresini, yazı stilini, yazı animasyonunu ve geçişleri değiştirir.
- **Oynatma**: ilk oynatmada önizleme videosu hazırlanır. Timeline 2 saniyelik parçalara bölünür,
  sadece değişen parçalar yeniden render edilir (cetvelin altındaki yeşil/kırmızı çubuk).
- **Claude ile canlı çalışma**: Claude proje dosyasını değiştirirse üstte "Yeniden yükle" çıkar.
  `inbox/` klasörüne düşen yeni medya için bildirim gelir.
- Kısayollar: Space, ←/→ (Shift: 1 sn), Home/End, C, Del, Ctrl+D/C/V/Z/Y/S/E, K, +/−, 1/2/3 (mod).

## Komut satırı

```
vedit render P.vedit.json -p shorts -o exports/x.mp4   # profiller: vedit profiles
vedit preview P.vedit.json                             # kare panosu + lint
vedit frame P.vedit.json -t 2.5 -o kare.png
vedit lint | validate | info P.vedit.json
vedit srt import altyazi.srt P.vedit.json --style highlight
vedit themes | presets | templates | effects | profiles
```

## Claude sistemi

- `CLAUDE.md`: Claude'un bu klasördeki çalışma kuralları ve iş akışı.
- `docs/CLAUDE_GUIDE.md`: SDK başvurusu.
- `.claude/skills/`: video-olustur, montaj, intro-outro, altyazi, revize, tema.
- `.mcp.json`: Claude'un projeleri araçlarla düzenlemesi için MCP sunucusu (`vedit mcp`).
- `tools/hook_validate.py`: Claude bir `.vedit.json` yazınca otomatik doğrulama.
  **Etkinleştirmek için** `tools/claude-settings.example.json` içeriğini `.claude/settings.json`'a
  kopyala (Claude bu dosyayı güvenlik gereği kendisi yazamadı).
- `brand/brand.json`: renkler, fontlar, logo. Kendi markana göre düzenle.

## Klasörler

`vedit/` motor + SDK + sunucu · `ui/` arayüz (derleme yok) · `projects/` projeler ·
`assets/` medya · `inbox/` Claude çıktıları · `scripts/` script katmanları · `exports/` çıktılar ·
`examples/` örnek üretim scriptleri · `tests/` testler (`.venv\Scripts\python.exe -m pytest -q`)

## Lisans

© 2026 Ahmet Kayra — [MIT Lisansı](LICENSE) ile lisanslanmış açık kaynak yazılım.
Kullanılan üçüncü taraf bileşenler ve lisansları: [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).

## Bilinen sınırlar

- Render CPU'da yapılır (çok çekirdekli). 1080x1920 bir kare yaklaşık 0,1–0,7 sn sürer.
  10 saniyelik video 8 çekirdekte yaklaşık 10–30 sn'de çıkar.
- Script katmanları uygulama içinde çalışır; hatalı script kırmızı hata kutusu gösterir ama
  sonsuz döngüye giren bir script render'ı kilitler.
- Konuşmadan otomatik altyazı için `faster-whisper` ayrıca kurulmalı (bkz. altyazi skill'i).
