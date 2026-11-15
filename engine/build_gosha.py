#!/usr/bin/env python3
"""
Собирает марионетку Гоши из сгенерированных картинок (Nano Banana Pro / GPT Image).

Вход  (assets/chars/gosha/gen/):
    gosha__03__heads_front.jpg   лист голов 3x2 (6 эмоций)
    gosha__06__torso.jpg         торс с руками в А-позе
    gosha__10__lower.jpg         джинсы и кроссовки
Выход (assets/chars/gosha/parts/): legs, torso, arm_l, arm_r, head_<эмоция>
      + scenes/test_gosha.json   тестовая сцена с ригом

Маски фона считает BiRefNet (rembg) один раз и кладёт в assets/chars/gosha/cut/masks/ —
дальше сборка мгновенная и воспроизводимая.

Запуск:  python3 engine/build_gosha.py
"""
from __future__ import annotations

import json
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", "assets", "chars", "gosha"))
GEN, MASKS, PARTS = (os.path.join(ROOT, d) for d in ("gen", os.path.join("cut", "masks"), "parts"))

S = 0.5  # масштаб деталей относительно кадра торса (2576 px) — рабочее разрешение

# --- линии шва рукава (координаты кадра торса, 2576x1438) ----------------------
# По шву плечо-проймы рука отделяется от корпуса. Правый шов — зеркало левого.
CENTER_X = 1295
LEFT_SEAM = [(868, 290), (905, 340), (940, 410), (970, 470), (985, 540), (985, 775)]
RIGHT_SEAM = [(2 * CENTER_X - x, y) for x, y in LEFT_SEAM]
LEFT_SEAM = LEFT_SEAM + [(978, 830), (965, 900), (950, 960)]   # слева рукав касается корпуса ниже проймы
SHOULDER_L = (930, 400)                         # ось вращения плеча
SHOULDER_R = (2 * CENTER_X - SHOULDER_L[0], SHOULDER_L[1])
V_TIP_TORSO = (1290, 244)                       # нижняя точка выреза капюшона на торсе
ARM_PROBE_L, ARM_PROBE_R, TORSO_PROBE = (700, 800), (1890, 800), (1290, 700)

EMOTIONS = ["neutral", "smug", "shock", "blank", "panic", "proud"]


# --------------------------------------------------------------------------- маски

def mask_path(name):
    return os.path.join(MASKS, f"{name}.png")


def compute_mask(src, dst):
    from rembg import new_session, remove
    im = Image.open(src).convert("RGB")
    out = remove(im, session=new_session("birefnet-general"), post_process_mask=True)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    out.getchannel("A").save(dst)


def ensure_mask(name):
    dst = mask_path(name)
    if not os.path.exists(dst):
        src = os.path.join(GEN, name + ".jpg")
        print("маска:", name, "(BiRefNet, ~1 мин)")
        # отдельным процессом: BiRefNet жадный до памяти
        subprocess.run([sys.executable, os.path.abspath(__file__), "--mask", src, dst], check=True)
    return dst


def load(name):
    rgb = np.asarray(Image.open(os.path.join(GEN, name + ".jpg")).convert("RGB"))
    a = np.asarray(Image.open(ensure_mask(name)).convert("L")).astype(np.float32) / 255.0
    return rgb, a


# --------------------------------------------------------------------------- утилиты

def to_rgba(rgb, a):
    return Image.fromarray(np.dstack([rgb, (np.clip(a, 0, 1) * 255).astype(np.uint8)]), "RGBA")


def trim(img: Image.Image):
    bb = img.getchannel("A").point(lambda v: 255 if v > 8 else 0).getbbox()
    return img.crop(bb), bb[:2]


def resized(img, s):
    return img.resize((max(1, round(img.width * s)), max(1, round(img.height * s))), Image.LANCZOS)


def largest(mask):
    lab, n = ndimage.label(mask)
    if n <= 1:
        return mask
    sizes = ndimage.sum(mask, lab, range(1, n + 1))
    return lab == (1 + int(np.argmax(sizes)))


def row_width(mask_row):
    xs = np.where(mask_row)[0]
    return (xs.min(), xs.max()) if len(xs) else (0, 0)


def skin_mask(rgb, a):
    r, g = rgb[..., 0].astype(np.float32), rgb[..., 1].astype(np.float32)
    return (a > 0.5) & (r > 110) & (g / (r + 1) > 0.66)


def hood_mask(rgb, rmin=60):
    r, g = rgb[..., 0].astype(np.float32), rgb[..., 1].astype(np.float32)
    return (r > rmin) & (g / (r + 1) < 0.62)


def fill_masked(rgb, mask):
    """Заливает пиксели mask цветом ближайшего «чистого» соседа (для тонких проводов)."""
    idx = ndimage.distance_transform_edt(mask, return_distances=False, return_indices=True)
    out = rgb.copy()
    out[mask] = rgb[idx[0][mask], idx[1][mask]]
    return out


# --------------------------------------------------------------------------- торс и руки

def build_torso():
    rgb, a = load("gosha__06__torso")
    H, W = a.shape
    a = a.copy()
    a[:95, :] = 0                                           # убираем нижнюю часть лица сверху кадра
    yy = np.arange(H)[:, None]
    r, b = rgb[..., 0].astype(np.float32), rgb[..., 2].astype(np.float32)
    a[(yy > 1200) & (b > r * 0.95)] = 0                     # джинсы — отдельная деталь

    sep = Image.new("L", (W, H), 0)
    d = ImageDraw.Draw(sep)
    d.line(LEFT_SEAM, fill=255, width=9)
    d.line(RIGHT_SEAM, fill=255, width=9)
    sepm = np.asarray(sep) > 0
    lab, _ = ndimage.label((a > 0.05) & ~sepm)
    lt, ll, lr = lab[TORSO_PROBE[1], TORSO_PROBE[0]], lab[ARM_PROBE_L[1], ARM_PROBE_L[0]], lab[ARM_PROBE_R[1], ARM_PROBE_R[0]]
    assert len({lt, ll, lr}) == 3 and 0 not in (lt, ll, lr), f"шов не разделил детали: {lt, ll, lr}"

    def part(L):
        base = lab == L
        seam = sepm & (a > 0.05) & ndimage.binary_dilation(base, iterations=6)
        return a * (base | seam)

    return rgb, part(lt), part(ll), part(lr)


# --------------------------------------------------------------------------- ноги

def hem_info(rgb, a, y_lo, y_hi, x_lo, x_hi):
    """Нижний край худи (последняя строка с терракотой у центра) и его ширина."""
    r, g = rgb[..., 0].astype(np.float32), rgb[..., 1].astype(np.float32)
    org = (a > 0.5) & (r > 90) & (g / (r + 1) < 0.62)
    rows = [y for y in range(y_lo, y_hi) if org[y, x_lo:x_hi].any()]
    y_hem = max(rows)
    x0, x1 = row_width(org[y_hem - 12])
    return y_hem, x1 - x0, (x0 + x1) / 2


def build_legs(torso_rgb, torso_a):
    rgb, a = load("gosha__10__lower")
    ht, wt, cxt = hem_info(torso_rgb, torso_a_full, 1100, 1300, 900, 1700)
    hl, wl, cxl = hem_info(rgb, a, 20, 220, 900, 1700)
    k = wt / wl
    a = a.copy()
    a[: hl + 2, :] = 0                                      # худи — часть торса
    img, (bx, by) = trim(to_rgba(rgb, a))
    return img, (bx, by), k, (ht, cxt), (hl, cxl)


# --------------------------------------------------------------------------- головы

def build_heads():
    rgb, a = load("gosha__03__heads_front")
    H, W = a.shape
    cw, ch = W // 3, H // 2
    yy, xx = np.mgrid[:ch, :cw]
    protect = (yy < 610) & (np.abs(xx - cw // 2) < 120)      # лицо и губы — не трогаем
    heads = []
    for i in range(6):
        c, rr = i % 3, i // 3
        box = (c * cw, rr * ch, (c + 1) * cw, (rr + 1) * ch)
        sub = rgb[box[1]:box[3], box[0]:box[2]].copy()
        sa = a[box[1]:box[3], box[0]:box[2]].copy()
        # провода наушников: серые малонасыщенные тёмные линии ниже ушей
        mx, mn = sub.max(axis=2).astype(np.float32), sub.min(axis=2).astype(np.float32)
        wire = ((mx - mn) / (mx + 1) < 0.12) & (mx < 150) & (yy > 440) & (sa > 0.3)
        wire = ndimage.binary_dilation(wire, iterations=2) & (yy > 440)
        sub = fill_masked(sub, wire)
        # капюшон ниже челюсти
        hood = hood_mask(sub, rmin=35) & ~protect
        hood[:470] = False
        sa[ndimage.binary_dilation(hood, iterations=4)] = 0
        sa = sa * largest(sa > 0.05)
        heads.append((sub, sa))
    return heads


def neck_width(rgb, a, y, x_lo, x_hi):
    s = skin_mask(rgb, a)[y, x_lo:x_hi]
    return int(s.sum())


# --------------------------------------------------------------------------- сборка

def main():
    global torso_a_full
    os.makedirs(PARTS, exist_ok=True)

    t_rgb, t_a, la_a, ra_a = build_torso()
    torso_a_full = t_a + la_a + ra_a                         # для поиска края худи (без джинсов)
    torso_img, (tbx, tby) = trim(to_rgba(t_rgb, t_a))
    larm_img, (lbx, lby) = trim(to_rgba(t_rgb, la_a))
    rarm_img, (rbx, rby) = trim(to_rgba(t_rgb, ra_a))

    legs_img, (lgx, lgy), k, (hem_t_y, hem_t_cx), (hem_l_y, hem_l_cx) = build_legs(t_rgb, torso_a_full)

    heads = build_heads()
    # масштаб головы по ширине шеи на 55 px выше «вершины» выреза
    neck_t = neck_width(t_rgb, np.clip(t_a + la_a + ra_a, 0, 1), V_TIP_TORSO[1] - 55, 1100, 1480)
    h_rgb0, h_a0 = heads[0]
    skin0 = skin_mask(h_rgb0, h_a0)
    cx_h = int(np.mean(np.where(skin0[560:600])[1])) if skin0[560:600].any() else h_a0.shape[1] // 2
    tip_h = int(max(np.where(skin0[:, cx_h - 40:cx_h + 40].any(axis=1))[0]))
    neck_h = neck_width(h_rgb0, h_a0, tip_h - 55, cx_h - 250, cx_h + 250)
    sh = 0.92 * neck_t / max(neck_h, 1)            # голова чуть меньше по шее — ближе к пропорциям эталона
    print(f"ширина шеи: торс {neck_t}px, голова {neck_h}px → масштаб головы {sh:.3f}; ноги ×{k:.3f}; кончик выреза у головы {cx_h, tip_h}")

    # ---- сохраняем детали
    def save(img, name):
        p = os.path.join(PARTS, f"{name}.png")
        img.save(p)
        return img.size

    torso_s = resized(torso_img, S)
    arm_l_s, arm_r_s = resized(larm_img, S), resized(rarm_img, S)
    ext = 40                                                  # подхват под край худи, пикселей кадра торса
    legs_s_full = resized(legs_img, k * S)
    top_row = np.asarray(legs_s_full)[0:1]
    pad = np.repeat(top_row, int(ext * S), axis=0)
    legs_s = Image.fromarray(np.vstack([pad, np.asarray(legs_s_full)]), "RGBA")
    sizes = {n: save(i, n) for n, i in (("gosha_torso", torso_s), ("gosha_arm_l", arm_l_s),
                                         ("gosha_arm_r", arm_r_s), ("gosha_legs", legs_s))}

    head_size = None
    for name, (sub, sa) in zip(EMOTIONS, heads):
        img = resized(to_rgba(sub, sa), sh * S)
        head_size = save(img, f"gosha_head_{name}")
    sizes["head"] = head_size
    print("детали:", sizes)

    # ---- точки крепления (доли размера родителя / ребёнка)
    tw, th = torso_s.size
    def torso_pt(p):
        return [(p[0] - tbx) * S / tw, (p[1] - tby) * S / th]

    legs_w, legs_h = legs_s.size
    # центр пояса джинсов в legs: x по первой строке, y = подхват
    row0 = np.asarray(legs_s.getchannel("A"))[int(ext * S) + 2] > 128
    wx0, wx1 = row_width(row0)
    legs_at = [((wx0 + wx1) / 2) / legs_w, (ext * S) / legs_h]
    torso_anchor = torso_pt((hem_t_cx, hem_t_y))

    def arm_anchor(shoulder, bx, by, img):
        return [(shoulder[0] - bx) * S / img.width, (shoulder[1] - by) * S / img.height]

    hw, hh = head_size
    head_anchor = [cx_h * sh * S / hw, tip_h * sh * S / hh]

    rig = {
        "talk": {"dy": 22},
        "parts": [
            {"part": "legs", "asset": "gosha_legs", "anchor": [0.5, 1.0], "root": True, "z": -2},
            {"part": "torso", "asset": "gosha_torso", "parent": "legs", "at": legs_at, "anchor": torso_anchor, "z": 0},
            {"part": "arm_l", "asset": "gosha_arm_l", "parent": "torso", "at": torso_pt(SHOULDER_L),
             "anchor": arm_anchor(SHOULDER_L, lbx, lby, arm_l_s), "rot": -16, "z": 1},
            {"part": "arm_r", "asset": "gosha_arm_r", "parent": "torso", "at": torso_pt(SHOULDER_R),
             "anchor": arm_anchor(SHOULDER_R, rbx, rby, arm_r_s), "rot": 16, "z": 1},
            {"part": "head", "asset": "gosha_head_neutral", "parent": "torso", "at": torso_pt(V_TIP_TORSO),
             "anchor": head_anchor, "z": 2},
        ],
    }
    assets = {"gosha_torso": "chars/gosha/parts/gosha_torso.png",
              "gosha_arm_l": "chars/gosha/parts/gosha_arm_l.png",
              "gosha_arm_r": "chars/gosha/parts/gosha_arm_r.png",
              "gosha_legs": "chars/gosha/parts/gosha_legs.png"}
    for e in EMOTIONS:
        assets[f"gosha_head_{e}"] = {"file": f"chars/gosha/parts/gosha_head_{e}.png", "trim": False}
    json.dump({"rig": rig, "assets": assets}, open(os.path.join(ROOT, "rig.json"), "w"), ensure_ascii=False, indent=1)
    fig_h = legs_h + th * 0.9 + hh * 0.5
    print("высота фигуры ≈", int(fig_h), "px (в рабочем разрешении)")


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--mask":
        compute_mask(sys.argv[2], sys.argv[3])
    else:
        main()
