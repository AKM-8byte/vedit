---
name: intro-outro
description: Marka kitine (brand/brand.json, brand/logo.png) uygun giriş (intro) ve çıkış (outro/bitiş ekranı) animasyonları üretir ya da var olan projenin başına/sonuna ekler. "intro ekle", "outro", "bitiş ekranı", "logo animasyonu" isteklerinde kullan.
---

# Intro / Outro

- Önce `brand/brand.json`'u oku: renkler, fontlar, logo yolu.
- **Intro (2–4 sn)**: `template("logo_reveal", src=<logo>, text=<kanal adı>)` ya da
  `template("title_card", title=..., subtitle=...)`. Arka plan marka `background` rengi veya tema.
- **Outro (4–6 sn)**: `template("end_screen", text="İzlediğiniz için teşekkürler!")` +
  `template("subscribe")` (end_screen'den 0.5 sn sonra).
- **Var olan projeye eklemek**: `Project.load(path)`. Ana kompozisyondaki tüm katmanları intro
  süresi kadar ileri kaydır, intro'yu yeni bir sahne (comp) olarak başa koy:
  ```python
  from vedit import Project, model
  p = Project.load("projects/x.vedit.json")
  main = p.data["comps"][p.data["main"]]
  shift = 3.0
  for l in main["layers"]: l["start"] += shift
  main["duration"] += shift
  cid = model.new_id("s"); p.data["comps"][cid] = model.new_comp("Intro", shift, "brand.background")
  main["layers"].append(model.new_layer("comp", 0, shift, 0, "Intro", comp=cid))
  from vedit.sdk import Scene; Scene(p, cid).template("logo_reveal", src="brand/logo.png")
  p.save("projects/x.vedit.json")
  ```
  Müzik katmanı (audio) da kaydığı için gerekiyorsa müziği 0'dan başlat ve süresini uzat.
- Kaydet → `vedit preview` ile kontrol.
