#!/usr/bin/env python3
"""
Вырезалка: превращает сгенерированные картинки в PNG-вырезки для перекладки.

  # один персонаж / предмет → прозрачный PNG
  python3 engine/cut.py in/gosha_front.png -o assets/chars/gosha

  # «развёртка» (лист с частями тела на ровном фоне) → по файлу на каждую часть
  python3 engine/cut.py in/gosha_parts.png -o assets/chars/gosha --split

  # фон ровный и однотонный — можно без нейросети, ключом по цвету
  python3 engine/cut.py in/sheet.png -o out/ --split --key

Модели rembg (скачиваются при первом запуске):
  birefnet-general  — лучшая кромка волос/капюшонов (по умолчанию, медленнее)
  isnet-general-use — быстрее, хорошо для предметов
  u2net_human_seg   — только люди
"""
from __future__ import annotations

import argparse
import os

import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage


def remove_bg_ml(img: Image.Image, model: str) -> Image.Image:
    from rembg import new_session, remove
    session = new_session(model)
    return remove(img, session=session, post_process_mask=True)


def remove_bg_key(img: Image.Image, tol: float = 38.0) -> Image.Image:
    """Ключ по цвету фона (берётся медиана углов). Для ровных фонов листов-развёрток."""
    a = np.asarray(img.convert("RGB")).astype(np.float32)
    h, w, _ = a.shape
    k = max(4, min(h, w) // 50)
    corners = np.concatenate([a[:k, :k].reshape(-1, 3), a[:k, -k:].reshape(-1, 3),
                              a[-k:, :k].reshape(-1, 3), a[-k:, -k:].reshape(-1, 3)])
    bg = np.median(corners, axis=0)
    dist = np.sqrt(((a - bg) ** 2).sum(axis=2))
    alpha = np.clip((dist - tol * 0.6) / (tol * 0.8), 0, 1)
    # убираем «дырки» внутри объектов и мусор
    solid = ndimage.binary_fill_holes(alpha > 0.5)
    alpha = np.maximum(alpha, solid.astype(np.float32) * 0.999)
    alpha = ndimage.binary_opening(alpha > 0.5, iterations=1) * alpha
    out = img.convert("RGBA")
    out.putalpha(Image.fromarray((alpha * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(0.7)))
    return out


def split_parts(rgba: Image.Image, min_area_frac: float = 0.002, merge_px: int = 6):
    """Разбивает лист на отдельные части по связным областям альфы.
    merge_px — склеивает близкие кусочки (пальцы, пряди) в одну часть."""
    a = np.asarray(rgba.getchannel("A")) > 20
    grown = ndimage.binary_dilation(a, iterations=merge_px)
    labels, n = ndimage.label(grown)
    total = a.size
    parts = []
    for i, sl in enumerate(ndimage.find_objects(labels), start=1):
        if sl is None:
            continue
        mask = (labels[sl] == i) & a[sl]
        if mask.sum() < total * min_area_frac:
            continue
        crop = rgba.crop((sl[1].start, sl[0].start, sl[1].stop, sl[0].stop))
        ca = np.asarray(crop.getchannel("A")).copy()
        ca[~mask] = 0
        crop.putalpha(Image.fromarray(ca))
        parts.append(((sl[0].start, sl[1].start), crop))
    # порядок чтения: строками сверху вниз, слева направо
    row_h = max(1, rgba.height // 12)
    parts.sort(key=lambda p: (p[0][0] // row_h, p[0][1]))
    return [p[1] for p in parts]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("inputs", nargs="+")
    ap.add_argument("-o", "--out", required=True, help="папка для PNG")
    ap.add_argument("--split", action="store_true", help="лист-развёртка → отдельные части")
    ap.add_argument("--key", action="store_true", help="ключ по цвету фона вместо нейросети")
    ap.add_argument("--tol", type=float, default=38.0)
    ap.add_argument("--model", default="birefnet-general")
    ap.add_argument("--max", type=int, default=1600, help="макс. сторона результата")
    args = ap.parse_args()
    os.makedirs(args.out, exist_ok=True)

    for path in args.inputs:
        img = Image.open(path).convert("RGB")
        base = os.path.splitext(os.path.basename(path))[0]
        cut = remove_bg_key(img, args.tol) if args.key else remove_bg_ml(img, args.model)
        pieces = split_parts(cut) if args.split else [cut.crop(cut.getchannel("A").getbbox())]
        for i, p in enumerate(pieces, start=1):
            p.thumbnail((args.max, args.max), Image.LANCZOS)
            name = f"{base}_{i:02d}.png" if args.split else f"{base}.png"
            p.save(os.path.join(args.out, name))
            print("→", os.path.join(args.out, name), p.size)


if __name__ == "__main__":
    main()
