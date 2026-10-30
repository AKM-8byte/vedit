"""Her tema için aynı içerikle bir proje üretir: projects/tema_<ad>.vedit.json

Çalıştır:  .venv/Scripts/python.exe examples/tema_demolari.py
"""
from vedit import Project, Shape, Text, Video
from vedit.themes import list_themes


def build(theme: str) -> Project:
    p = Project(1080, 1920, name=f"Tema: {theme}", theme=theme)
    s1 = p.scene("Başlık", duration=3.5)
    s1.add(Text(theme.upper(), size=150, y=760, char_anim="theme"))
    s1.add(Text("Tek tıkla tüm görünüm değişir", size=56, y=930, max_width=860,
                transition_in="theme"), start=0.8)
    s1.add(Shape("arrow", points=[[260, 1250], [540, 1150], [820, 1250]],
                 stroke_color="theme.accent", stroke_width=12), start=1.2).preset("draw_on")
    s1.add(Shape("star", w=220, h=220, y=1450, fill="theme.accent"), start=1.6).preset("pop_in")
    s2 = p.scene("Video", duration=3, transition="theme")
    s2.add(Video("assets/ornek_klip.mp4", fit="cover", mute=True)).preset("ken_burns")
    s2.add(Text("Videolar da temaya uyar", size=64, y=1150, max_width=860,
                transition_in="theme"), start=0.3)
    return p


if __name__ == "__main__":
    for t in list_themes():
        path = build(t["name"]).save(f"projects/tema_{t['name']}.vedit.json")
        print("Kaydedildi:", path)
