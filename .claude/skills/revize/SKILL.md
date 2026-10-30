---
name: revize
description: Var olan bir .vedit.json projesinde istenen değişikliği sadece ilgili katmanlara uygular (metin değiştir, renk, süre, animasyon, sıra, kaldır). "şunu değiştir", "daha hızlı olsun", "yazıyı büyüt", "rengi değiştir", "şu sahneyi sil" gibi revizyon isteklerinde kullan.
---

# Revizyon

Kullanıcı arayüzde elle düzenleme yapmış olabilir: **projeyi baştan üretme**, üretim scriptini
yeniden çalıştırma (elle yapılan düzenlemeler kaybolur). Proje dosyasını doğrudan düzenle.

1. `.venv/Scripts/vedit.exe info projects/x.vedit.json` → katman id'leri ve zamanlar.
2. Değişikliği `Project.load()` ile yap (ID'ler korunur):
   ```python
   from vedit import Project, model
   p = Project.load("projects/x.vedit.json")
   cid, layer = model.find_layer(p.data, "l_ab12cd34")
   layer["props"]["text"] = "Yeni metin"
   from vedit.presets import apply_preset; apply_preset(layer, "pop_in")
   p.save("projects/x.vedit.json")
   ```
   Tek bir değeri değiştirmek için JSON'u Edit ile düzenlemek de uygundur (hook doğrular).
3. Zamanlama değişikliklerinde sonraki katmanları/sahneleri de kaydır; boşluk bırakma
   (lint "boş aralık" uyarısı verir).
4. `vedit preview projects/x.vedit.json --times <değişen anlar>` ile **sadece değişen anları**
   kontrol et, sonucu kullanıcıya kısaca bildir.
5. Arayüz açıksa dosya değişikliğini otomatik algılar ve yeniden yükleme önerir.
