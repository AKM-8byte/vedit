# VEdit SDK Başvurusu

## Hızlı örnek

```python
# projects/tanitim.py   →   .venv/Scripts/python.exe projects/tanitim.py
from vedit import Project, Text, Shape, Image, Video, Audio, Solid, Script, Adjustment

p = Project(1080, 1920, fps=30, name="Tanıtım", theme="neon", brand="brand/brand.json")

s1 = p.scene("Giriş", duration=3.5)
title = s1.add(Text("Yeni Bölüm!", size=140, y=820, color="brand.primary"))
title.preset("pop_in").preset("fade_out")
s1.add(Text("Her şey değişiyor", size=60, y=980, opacity=0.8), start=0.6).preset("rise_words")

s2 = p.scene("Klip", duration=5, transition="slide_left")
s2.add(Video("assets/klip.mp4", fit="cover", volume=0.8)).preset("ken_burns")
s2.template("lower_third", at=0.8, title="Ahmet", subtitle="Kurucu")

s3 = p.scene("Kapanış", duration=3, transition="fade")
s3.template("subscribe")

p.music("assets/muzik.mp3", volume=0.35, fade_out=2)
p.save("projects/tanitim.vedit.json")
print(p.sheet("projects/tanitim_sheet.png"))   # sonra PNG'yi Read ile aç
for i in p.lint(): print(i)
```

## Project

`Project(width=1080, height=1920, fps=30, name, theme=None, theme_params=None, brand=None, background="#000000")`

| Metot | Açıklama |
|---|---|
| `p.scene(name, duration, background=None, transition=None, transition_duration=0.5)` | Yeni sahne; ana zaman çizelgesine sıradaki olarak eklenir. Geçiş verilirse önceki sahneyle üst üste biner. Tema varsa arka plan `"theme"` olur. |
| `p.add(layer, start, duration, track)` | Ana zaman çizelgesine, tüm sahnelerin üstüne katman (filigran, ilerleme çubuğu). |
| `p.music(src, volume=0.6, fade_in=0.5, fade_out=1.5, loop=True)` | Tüm videoya müzik. **Sahneler eklendikten sonra çağır.** |
| `p.template(name, at, duration, **params)` | Ana zaman çizelgesine şablon. |
| `p.save(path)` / `Project.load(path)` | Kaydet / mevcut projeyi düzenlemek için aç. |
| `p.sheet(path, times=None, count=12)` | Kare panosu PNG. |
| `p.frame(t, path)` | Tek kare PNG. |
| `p.lint()` | Kalite uyarıları listesi. |
| `p.render(path, profile="default")` | Video çıktısı (sadece istenince). |
| `p.data` | Ham proje sözlüğü. `p.duration` toplam süre. |

## Scene

`scene.add(layer, start=None, duration=None, track=None)` — süre verilmezse sahnenin sonuna kadar;
video katmanında kaynak süresi kadar. Track verilmezse en üste konur.
`scene.template(name, at=0, duration=None, **params)`; `scene.duration`; `scene.id`.

## Katmanlar

Ortak argümanlar: `start, duration, track, name`, dönüşüm propları ve aşağıdaki alanlar.
Bilinmeyen anahtar kelimeler **prop** olarak kaydedilir (`Text("a", size=90)` → `props.size`).

| Ortak prop | Varsayılan | Not |
|---|---|---|
| `x`, `y` | ortası | piksel, anchor noktasının konumu |
| `anchor_x`, `anchor_y` | 0.5 | 0 = sol/üst, 1 = sağ/alt |
| `scale`, `scale_x`, `scale_y` | 1 | negatif değer aynalar |
| `rotation` | 0 | derece, saat yönü |
| `opacity` | 1 | 0..1 |

Diğer alanlar (prop değil): `blend` (normal, add, multiply, screen, overlay, lighten, darken,
difference, soft_light), `effects=[...]`, `transition_in/out`, `theme_style=False` (temayı bu
katmanda kapat).

### Text(text, ...)
`font` (arial, segoe bold, segoe black, impact, consolas, georgia, handwriting, ink free veya .ttf
yolu), `size`=80, `color`, `stroke_width`, `stroke_color`, `shadow_x`, `shadow_y`, `shadow_blur`,
`shadow_color`, `align` (left/center/right), `max_width` (otomatik satır kaydırma, px),
`line_height`=1.2, `letter_spacing`, `bg_color` (arka kutu), `bg_padding`, `bg_radius`,
`reveal` (0..1 görünen harf oranı).
- Sayaç: `Text("", value=0, counter={"prefix": "", "suffix": " TL", "decimals": 0})` +
  `.preset("count_up", to=5000)`.
- Harf animasyonu: `.chars(type, unit="char|word|line", stagger, duration, delay, ease, color)`.
  Türler: `rise, fade, pop, drop, wave, typewriter, decode, write, blur, glitch, highlight`.
  `char_anim="theme"` → temanın yazı animasyonu.

### Shape(shape, ...)
`shape`: rect, ellipse, line, path, polygon, star, arrow, triangle.
`w`, `h`, `radius` (köşe), `fill` (None = dolgusuz), `fill2` + `gradient_angle` (gradyan),
`stroke_color`, `stroke_width`, `progress` (0..1 çizgi çizilme oranı), `sides`, `inner` (yıldız).
`line/path/arrow`: `points=[[x,y],...]` **kompozisyon koordinatlarında**; x/y verme.
`closed=True` (path), `rough=2.5` (el çizimi titreşimi), `smooth=True` (noktalardan geçen
yumuşak eğri), `filled=True` (açık yolun içini `fill` rengiyle boya; çizgi açık kalır).
**Kap içindeki sıvı/dolgu** (bardaktaki su, grafik altı alan): sadece çizgi çizme; ayrı bir
`Shape("path", filled=True, fill=..., stroke_color=None, points=[yüzey noktaları..., sağ alt, sol alt])`
katmanı ekle, noktaları kabın iç duvarlarına göre ver. Dolma animasyonu: `anchor_y=1` +
`animate("scale_y", {0: 0, 0.9: 1})`.

### Image(src, fit=None) / Video(src, fit=None, source_in=0, speed=1, loop=False, volume=1, mute=False)
`source_in`: kaynağın kaçıncı saniyesinden başlanacağı (JSON'da `"in"`).
`fit`: none (doğal boyut), contain, cover, fill. Videoda ses otomatik karışır.
`audio_fade_in`, `audio_fade_out` (sn).

### Audio(src, volume=1, loop=False, audio_fade_in, audio_fade_out, source_in=0, speed=1)

### Solid(color, fill2=None, gradient_angle=90) — tam ekran renk/gradyan.

### Script(path, params={...}, fit=None) — Python kodundan kare üretir
```python
# scripts/parcacik.py
import numpy as np
PARAMS = {"renk": {"type": "color", "default": "#ff3366"},
          "adet": {"type": "int", "default": 80, "min": 10, "max": 500},
          "hiz":  {"type": "float", "default": 1.0, "min": 0.1, "max": 5}}
def make_frame(t, params, w, h):          # → (h, w, 4) uint8 RGBA ya da PIL.Image
    ...
```
PARAMS türleri: float, int, color, text, bool, choice (`"options": [...]`), file.
Arayüzde kaydırıcı/renk seçici olarak görünür, keyframe verilebilir:
`Script("scripts/parcacik.py", params={"hiz": {"keyframes": [...]}})`.
Eski MoviePy kodu: `def make_clip(params): return <moviepy clip>` tanımla.

### Adjustment(effects=[...]) — altındaki tüm katmanlara efekt uygular.

## Animasyon

```python
layer.animate("x", {0: -200, 0.6: 540}, ease="out_back")           # {zaman: değer}
layer.animate("color", [(0, "#ffffff"), (1, "#ff0000", "linear")])  # renkler de olur
layer.expr("y", "960 + sin(t*2*pi)*20")                             # sürekli
layer.preset("pop_in", at=0.2, duration=0.5)
layer.effect("glow", radius=25, color="#00ffcc")
layer.transition("slide_up", 0.5); layer.transition_out("fade", 0.4)
```
Zamanlar **katmanın başlangıcına göredir**. Easing: linear, ease_in, ease_out, ease_in_out,
in/out/in_out_cubic, in/out/in_out_sine, in/out/in_out_expo, in/out/in_out_back, in/out_elastic,
in/out_bounce, hold ya da `[x1,y1,x2,y2]` bezier.
İfade fonksiyonları: `t, sin, cos, pi, abs, min, max, clamp(v,a,b), lerp(a,b,u), ease(ad,u),
noise(x), wiggle(frekans, genlik), pingpong(x)`.

### Hazır animasyonlar (`vedit presets`)
Giriş: fade_in, pop_in, zoom_in, slide_in_left/right/up/down, bounce_in, drop_in, spin_in,
flip_in, blur_in. Çıkış (sona otomatik): fade_out, pop_out, zoom_out, slide_out_*, blur_out.
Yazı: typewriter, rise_words, rise_chars, pop_chars, wave_text, decode_text, write_text,
highlight_words, glitch_text, count_up. Şekil: draw_on.
Sürekli: float, pulse, heartbeat, wiggle, swing, spin, ken_burns. Vurgu: shake.
Seçenekler: `distance=300` (slide), `to=` (count_up), `amplitude`, `speed`, `ease`.

### Geçişler (transition_in / transition_out)
fade, slide_left/right/up/down, zoom_in, zoom_out, pop, spin, blur, wipe_left/right/up/down,
circle, drop, glitch, ya da `"theme"`.

### Efektler (`vedit effects`)
blur, glow, shadow, outline, brightness, contrast, saturation, hue, grayscale, sepia, invert, tint,
temperature, vignette, noise, pixelate, posterize, sharpen, rgb_split, chroma_key, lut, sketch,
crop, rounded, border, mirror, opacity_mask. Parametreler keyframe'lenebilir.

### Şablonlar (`vedit templates`)
title_card(title, subtitle), lower_third(title, subtitle, color), subscribe(text, done_text),
counter(to, label, prefix, suffix), quote(quote, author), progress_bar(color, height),
caption(text, highlight), countdown(from), callout(text, x, y), end_screen(text),
logo_reveal(src, text).

## Temalar (`vedit themes`)
`Project(..., theme="matrix", theme_params={...})`. Tema şunları değiştirir: "theme" arka planlı
sahnelerin arka planı, video/görsellere filtre, son kare efekti, yazı varsayılanları (font/renk),
`char_anim="theme"` ve `transition="theme"` davranışı. Bir katmanı temadan muaf tutmak için
`theme_style=False`. Sahneye özel tema: `p.data["comps"][scene.id]["theme"] = {"name": ...}`.

## Proje dosyası (JSON) — elle küçük düzeltmeler için

```json
{"version":1,"name":"...","width":1080,"height":1920,"fps":30,"theme":null,"brand":null,
 "main":"main","comps":{"main":{"name":"Ana","duration":8,"background":"#000000","layers":[
   {"id":"l_1","type":"text","name":"Başlık","track":1,"start":0,"duration":3,
    "props":{"text":"Merhaba","size":120,
             "opacity":{"keyframes":[{"t":0,"v":0,"ease":"out_cubic"},{"t":0.5,"v":1}]}},
    "effects":[],"transition_in":null,"transition_out":null,"blend":"normal"}]}}}
```
Kaydettikten sonra hook otomatik doğrular; hata mesajı gelirse düzelt.
`background`: renk, `null` (şeffaf), `"theme"` ya da `{"gradient":["#a","#b"],"angle":180}`.
