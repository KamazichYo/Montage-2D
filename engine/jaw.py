#!/usr/bin/env python3
"""
Режет вырезанную голову на «верх» и «челюсть» для говорящей хлопушки
(приём коллажной анимации: челюсть опускается, под ней — тёмная «пасть»).

    python3 engine/jaw.py assets/chars/gosha/gosha_head_neutral.png --mouth 0.74 --tilt 0
    → gosha_head_neutral_top.png, gosha_head_neutral_jaw.png

--mouth  линия рта в долях высоты головы (0 — макушка, 1 — подбородок)
--tilt   наклон линии реза в пикселях (правый край ниже/выше левого)
--gap    сколько добавить тёмной «пасти» сверху челюсти, px
"""
import argparse
import os

import numpy as np
from PIL import Image


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("head")
    ap.add_argument("--mouth", type=float, required=True)
    ap.add_argument("--tilt", type=float, default=0)
    ap.add_argument("--gap", type=int, default=14)
    ap.add_argument("--mouth-color", default="45,15,20")
    args = ap.parse_args()

    img = Image.open(args.head).convert("RGBA")
    w, h = img.size
    y0 = args.mouth * h
    yy, xx = np.mgrid[0:h, 0:w]
    line = y0 + args.tilt * (xx / max(w - 1, 1) - 0.5)
    alpha = np.asarray(img.getchannel("A"))

    top = img.copy()
    top.putalpha(Image.fromarray(np.where(yy < line, alpha, 0).astype(np.uint8)))

    # челюсть: всё ниже линии рта + тёмная «пасть» шириной ~40% лица над линией
    color = np.array([int(c) for c in args.mouth_color.split(",")], dtype=np.uint8)
    rgba = np.asarray(img).copy()
    row = alpha[int(min(h - 1, y0))]
    xs = np.where(row > 40)[0]
    x0, x1 = (xs.min(), xs.max()) if len(xs) else (0, w)
    mx0, mx1 = x0 + (x1 - x0) * 0.3, x0 + (x1 - x0) * 0.7
    below = yy >= line
    mouth = (~below) & (yy >= line - args.gap) & (xx >= mx0) & (xx <= mx1)
    out = np.zeros_like(rgba)
    out[below] = rgba[below]
    out[mouth, :3] = color
    out[mouth, 3] = 255
    cut_top = int(max(0, y0 - abs(args.tilt) / 2 - args.gap))
    jaw = Image.fromarray(out).crop((0, cut_top, w, h))

    base = os.path.splitext(args.head)[0]
    top.crop(top.getchannel("A").getbbox()).save(base + "_top.png")
    jaw.save(base + "_jaw.png")
    print("→", base + "_top.png", "|", base + "_jaw.png")
    print("в риге: jaw.at = [0.5, ~1.0] от верха, anchor = [0.5, 0.0]")


if __name__ == "__main__":
    main()
