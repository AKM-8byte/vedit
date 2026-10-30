# Üçüncü taraf bileşenler

VEdit'in kendi kaynak kodu MIT Lisansı ile lisanslanmıştır (bkz. `LICENSE`).
Aşağıdaki bileşenler VEdit ile birlikte **kurulur**, ancak bu depoda **dağıtılmaz**;
her biri kendi lisansına tabidir.

| Bileşen | Lisans | Kullanım |
|---|---|---|
| [Pillow](https://python-pillow.org) | MIT-CMU (HPND) | Görüntü işleme, yazı ve şekil çizimi |
| [NumPy](https://numpy.org) | BSD-3-Clause | Kare işlemleri, efektler |
| [MoviePy](https://zulko.github.io/moviepy/) | MIT | Eski MoviePy scriptleriyle uyumluluk |
| [imageio-ffmpeg](https://github.com/imageio/imageio-ffmpeg) | BSD-2-Clause | FFmpeg ikili dosyasını sağlar |
| [FFmpeg](https://ffmpeg.org) | LGPL-2.1+ / GPL-2.0+ (derlemeye göre) | Video okuma ve kodlama |
| [FastAPI](https://fastapi.tiangolo.com) | MIT | Yerel sunucu |
| [Uvicorn](https://www.uvicorn.org) | BSD-3-Clause | Yerel sunucu |
| [pywebview](https://pywebview.flowrl.com) | BSD-3-Clause | Masaüstü penceresi |
| [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk) | MIT | Claude entegrasyonu (isteğe bağlı) |

## FFmpeg hakkında not

`imageio-ffmpeg` ile gelen FFmpeg derlemesi GPL lisanslı bileşenler (ör. libx264) içerir.
VEdit FFmpeg'i ayrı bir program olarak çalıştırır; bu, VEdit'in kaynak kodunu GPL yapmaz.
**Ancak** VEdit'i FFmpeg ikili dosyasıyla birlikte paketleyip dağıtırsanız (ör. tek bir .exe
kurulum dosyası), o FFmpeg derlemesinin lisans koşullarına (GPL: lisans metnini eklemek ve
kaynak koduna erişim sağlamak) uymanız gerekir.

## Fontlar

VEdit sistemde kurulu fontları kullanır (ör. Windows fontları); bu fontlar VEdit ile
dağıtılmaz. `brand/fonts/` klasörüne eklediğiniz fontların lisansı size aittir.
