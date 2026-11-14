#!/usr/bin/env python3
"""
Болванки для проверки движка, пока нет сгенерированных персонажей.
Рисует «фото-подобные» вырезки (шум, градиенты) и фон-комнату.
Заменяются настоящими ассетами из Nano Banana без правки сцены — имена те же.

    python3 engine/make_placeholders.py assets/demo
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

OUT = sys.argv[1] if len(sys.argv) > 1 else "assets/demo"
os.makedirs(OUT, exist_ok=True)
rng = np.random.default_rng(1)


def photoize(img: Image.Image, amount=10, blur=0.6):
    """Шум + лёгкое размытие, чтобы плоская заливка выглядела как фото."""
    a = np.asarray(img).astype(np.float32)
    n = rng.normal(0, amount, a.shape[:2])[..., None]
    a[..., :3] = np.clip(a[..., :3] + n, 0, 255)
    out = Image.fromarray(a.astype(np.uint8), img.mode)
    return out.filter(ImageFilter.GaussianBlur(blur))


def shade(d, box, c1, c2, steps=40, vertical=True):
    x0, y0, x1, y1 = box
    for i in range(steps):
        t = i / (steps - 1)
        c = tuple(int(c1[k] + (c2[k] - c1[k]) * t) for k in range(3))
        if vertical:
            yy = y0 + (y1 - y0) * i / steps
            d.rectangle([x0, yy, x1, yy + (y1 - y0) / steps + 1], fill=c)
        else:
            xx = x0 + (x1 - x0) * i / steps
            d.rectangle([xx, y0, xx + (x1 - x0) / steps + 1, y1], fill=c)


# ---------------- фон: гостиная-«хата» ----------------
W, H = 1400, 2400
bg = Image.new("RGB", (W, H))
d = ImageDraw.Draw(bg)
shade(d, (0, 0, W, 1500), (196, 170, 140), (150, 125, 100))          # стена
shade(d, (0, 1500, W, H), (120, 84, 58), (70, 46, 30))                # пол
d.rectangle([840, 260, 1300, 900], fill=(60, 70, 90))                 # окно (ночь)
for i in range(30):                                                    # огни города
    x, y = rng.integers(860, 1280), rng.integers(500, 880)
    d.rectangle([x, y, x + 8, y + 12], fill=(255, 210, 120))
d.rectangle([830, 250, 1310, 910], outline=(240, 236, 228), width=18)
d.line([1070, 250, 1070, 910], fill=(240, 236, 228), width=12)
d.rectangle([80, 300, 560, 700], fill=(40, 40, 46))                    # постер/телик
d.text((120, 470), "SHIP IT", fill=(255, 80, 80))
shade(d, (60, 1250, 1340, 1700), (88, 96, 120), (60, 66, 86))         # диван
d.rounded_rectangle([60, 1150, 1340, 1330], 40, fill=(98, 106, 130))
d.rectangle([380, 1820, 1020, 1900], fill=(150, 110, 70))             # журнальный стол
d.rectangle([420, 1900, 450, 2100], fill=(110, 80, 50))
d.rectangle([950, 1900, 980, 2100], fill=(110, 80, 50))
photoize(bg, 9, 1.2).save(os.path.join(OUT, "bg_living.png"))


# ---------------- персонаж ----------------
def character(prefix, hoodie, skin, hair, glasses=False, cap=False):
    # тело
    body = Image.new("RGBA", (520, 760), (0, 0, 0, 0))
    bd = ImageDraw.Draw(body)
    bd.rounded_rectangle([40, 60, 480, 760], 120, fill=hoodie + (255,))
    bd.polygon([(200, 60), (320, 60), (260, 150)], fill=tuple(max(0, c - 40) for c in hoodie) + (255,))
    bd.line([230, 150, 225, 330], fill=(230, 230, 230, 255), width=6)
    bd.line([290, 150, 295, 330], fill=(230, 230, 230, 255), width=6)
    photoize(body, 8).save(os.path.join(OUT, f"{prefix}_body.png"))

    # рука (одна деталь, вращается в плече)
    arm = Image.new("RGBA", (140, 460), (0, 0, 0, 0))
    ad = ImageDraw.Draw(arm)
    ad.rounded_rectangle([20, 0, 120, 380], 50, fill=hoodie + (255,))
    ad.ellipse([25, 350, 115, 455], fill=skin + (255,))
    photoize(arm, 8).save(os.path.join(OUT, f"{prefix}_arm.png"))

    def head(expr):
        h = Image.new("RGBA", (420, 520), (0, 0, 0, 0))
        hd = ImageDraw.Draw(h)
        hd.ellipse([40, 40, 380, 500], fill=skin + (255,))
        hd.chord([30, 10, 390, 300], 180, 360, fill=hair + (255,))
        if cap:
            hd.chord([20, 0, 400, 240], 180, 360, fill=(30, 30, 30, 255))
            hd.rectangle([200, 110, 420, 140], fill=(30, 30, 30, 255))
        ey = 250
        if expr == "shock":
            for ex in (140, 280):
                hd.ellipse([ex - 38, ey - 38, ex + 38, ey + 38], fill=(255, 255, 255, 255))
                hd.ellipse([ex - 12, ey - 12, ex + 12, ey + 12], fill=(20, 20, 20, 255))
            hd.line([95, 180, 175, 165], fill=hair + (255,), width=12)
            hd.line([245, 165, 325, 180], fill=hair + (255,), width=12)
        elif expr == "smug":
            for ex in (140, 280):
                hd.chord([ex - 30, ey - 22, ex + 30, ey + 22], 0, 180, fill=(255, 255, 255, 255))
                hd.ellipse([ex - 10, ey - 4, ex + 10, ey + 16], fill=(20, 20, 20, 255))
                hd.line([ex - 32, ey, ex + 32, ey], fill=(60, 40, 30, 255), width=7)
        else:
            for ex in (140, 280):
                hd.ellipse([ex - 26, ey - 22, ex + 26, ey + 22], fill=(255, 255, 255, 255))
                hd.ellipse([ex - 11, ey - 11, ex + 11, ey + 11], fill=(20, 20, 20, 255))
        if glasses:
            for ex in (140, 280):
                hd.ellipse([ex - 48, ey - 42, ex + 48, ey + 42], outline=(30, 30, 30, 255), width=8)
            hd.line([188, ey, 232, ey], fill=(30, 30, 30, 255), width=8)
        hd.polygon([(210, 280), (190, 345), (225, 345)], fill=tuple(max(0, c - 30) for c in skin) + (255,))
        hd.line([160, 385, 260, 385], fill=(120, 40, 40, 255), width=10)   # линия рта
        return photoize(h, 7)

    mouth_y = 385  # линия, по которой «челюсть» отрезается от головы
    for expr in ("neutral", "shock", "smug"):
        full = head(expr)
        top = full.copy()
        ta = np.asarray(top.getchannel("A")).copy()
        ta[mouth_y:, :] = 0
        top.putalpha(Image.fromarray(ta))
        top.save(os.path.join(OUT, f"{prefix}_head_{expr}.png"))
    # челюсть — нижняя часть лица с подбородком, тёмная «пасть» сверху
    full = head("neutral")
    jaw = full.crop((0, mouth_y - 10, full.width, full.height))
    jd = ImageDraw.Draw(jaw)
    jd.rectangle([150, 0, 270, 14], fill=(70, 20, 25, 255))
    jaw.save(os.path.join(OUT, f"{prefix}_jaw.png"))


character("gosha", hoodie=(230, 120, 40), skin=(232, 190, 160), hair=(40, 28, 20), cap=True)
character("lyova", hoodie=(70, 110, 90), skin=(240, 205, 180), hair=(120, 70, 40), glasses=True)

# ---------------- реквизит ----------------
lap = Image.new("RGBA", (520, 360), (0, 0, 0, 0))
ld = ImageDraw.Draw(lap)
ld.polygon([(40, 0), (480, 0), (460, 280), (60, 280)], fill=(170, 172, 178, 255))
ld.rectangle([80, 25, 440, 250], fill=(25, 30, 40, 255))
for i in range(8):
    ld.line([100, 50 + i * 24, 100 + rng.integers(80, 300), 50 + i * 24], fill=(90, 230, 120, 255), width=6)
ld.polygon([(0, 280), (520, 280), (500, 350), (20, 350)], fill=(150, 152, 158, 255))
photoize(lap, 6).save(os.path.join(OUT, "prop_laptop.png"))

can = Image.new("RGBA", (130, 240), (0, 0, 0, 0))
cd = ImageDraw.Draw(can)
cd.rounded_rectangle([10, 10, 120, 230], 18, fill=(20, 20, 24, 255))
cd.rectangle([10, 80, 120, 150], fill=(140, 255, 60, 255))
photoize(can, 6).save(os.path.join(OUT, "prop_can.png"))

# ---------------- лист-развёртка на сером (для теста cut.py --split --key) ----------------
sheet = Image.new("RGB", (1600, 1000), (128, 128, 128))
x = 40
for name in ("gosha_head_neutral", "gosha_jaw", "gosha_arm", "prop_can"):
    p = Image.open(os.path.join(OUT, f"{name}.png"))
    sheet.paste(p, (x, 60), p)
    x += p.width + 60
sheet.save(os.path.join(OUT, "_test_parts_sheet.png"))
print("placeholders →", OUT)
