"""Örnek: SDK ile 3 sahnelik tanıtım videosu.

Çalıştır:  .venv/Scripts/python.exe examples/demo_tanitim.py
Aç:        .venv/Scripts/vedit.exe gui projects/demo_tanitim.vedit.json
"""
from vedit import Project, Shape, Text, Video

p = Project(1080, 1920, fps=30, name="Demo Tanıtım", brand="brand/brand.json")

# 1) Giriş: gradyan arka plan, büyük başlık, çizilerek gelen alt çizgi
s1 = p.scene("Giriş", duration=3.5, background={"gradient": ["#1a1033", "#0f0f1a"], "angle": 160})
s1.add(Text("VEdit", size=200, y=820, font="segoe black", color="brand.primary",
            shadow_y=10, shadow_blur=24)).preset("pop_in").preset("fade_out")
s1.add(Shape("line", points=[[340, 960], [740, 960]], stroke_color="brand.accent", stroke_width=10),
       start=0.4).preset("draw_on", duration=0.7)
s1.add(Text("Claude ile video üret, burada düzenle", size=52, y=1060, max_width=900, opacity=0.85),
       start=0.7).preset("rise_words")

# 2) Video sahnesi: yavaş zoom + alt bant
s2 = p.scene("Klip", duration=4.5, transition="fade")
s2.add(Video("assets/ornek_klip.mp4", fit="cover", mute=True)).preset("ken_burns")
s2.template("lower_third", at=0.6, title="Örnek Klip", subtitle="assets/ornek_klip.mp4",
            color="brand.secondary")

# 3) Sayaç + abone ol
s3 = p.scene("Kapanış", duration=4, transition="slide_left",
             background={"gradient": ["#0f0f1a", "#2a0a1a"], "angle": 180})
s3.template("counter", at=0, duration=2.2, to=12500, label="İzlenme")
s3.template("subscribe", at=1.2, duration=2.8)

p.music("assets/ornek_muzik.wav", volume=0.35, fade_out=1.5)
path = p.save("projects/demo_tanitim.vedit.json")
print("Kaydedildi:", path)
