#!/usr/bin/env python3
"""
Собирает марионетку Гоши из сгенерированных картинок (Nano Banana Pro / GPT Image).

Вход  (assets/chars/gosha/gen/):
    gosha__03__heads_front.jpg   лист голов 3x2: 6 эмоций, рот закрыт
    gosha__05__heads_talk.jpg    лист голов 3x2: рот для речи, крик, смех
    gosha__06__torso.jpg         торс с руками в А-позе
    gosha__08__arm_hang.jpg      рука висит (рукав + кисть)
    gosha__09__hands.jpg         лист кистей 4x2: жесты
    gosha__10__lower.jpg         джинсы и кроссовки
Выход (assets/chars/gosha/parts/ + rig.json + scenes/test_gosha.json)

Маски фона считает BiRefNet (rembg) один раз и кладёт в assets/chars/gosha/cut/masks/ —
дальше сборка мгновенная и воспроизводимая.

Запуск:  python3 engine/build_gosha.py
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import sys

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
ROOT = os.path.join(REPO, "assets", "chars", "gosha")
GEN, MASKS, PARTS = (os.path.join(ROOT, d) for d in ("gen", os.path.join("cut", "masks"), "parts"))

S = 0.5  # масштаб деталей относительно кадра торса (2576 px) — рабочее разрешение

# --- шов рукава на торсе (координаты кадра торса 2576x1438) ----------------------
CENTER_X = 1295
LEFT_SEAM = [(868, 290), (905, 340), (940, 410), (970, 470), (985, 540), (985, 775)]
RIGHT_SEAM = [(2 * CENTER_X - x, y) for x, y in LEFT_SEAM]
LEFT_SEAM = LEFT_SEAM + [(978, 830), (965, 900), (950, 960)]   # слева рукав касается корпуса ниже проймы
SHOULDER_L = (935, 395)                          # плечо слева на кадре (ось вращения рукава)
SHOULDER_R = (2 * CENTER_X - SHOULDER_L[0], SHOULDER_L[1])
V_TIP_TORSO = (1290, 244)                        # нижняя точка выреза капюшона на торсе
TORSO_PROBE = (1290, 700)

ARM_SCALE = 1.0          # масштаб висящей руки относительно кадра торса (подбирается по тестовой сцене)
HAND_TUCK = 30           # на сколько пикселей запястье заходит под манжету
HEADS_FRONT = ["neutral", "smug", "shock", "blank", "panic", "proud"]
HEADS_TALK = ["t_closed", "t_mid", "t_open", "shout", "laugh", "oh"]
HANDS = ["wave", "fist", "point", "thumb", "beg", "pinch", "facepalm", "claw"]


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
        subprocess.run([sys.executable, os.path.abspath(__file__), "--mask", src, dst], check=True)
    return dst


def load(name):
    rgb = np.asarray(Image.open(os.path.join(GEN, name + ".jpg")).convert("RGB"))
    a = np.asarray(Image.open(ensure_mask(name)).convert("L")).astype(np.float32) / 255.0
    return rgb, a


# --------------------------------------------------------------------------- утилиты

def to_rgba(rgb, a):
    return Image.fromarray(np.dstack([rgb, (np.clip(a, 0, 1) * 255).astype(np.uint8)]), "RGBA")


def trim(img):
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


def row_span(mask_row):
    xs = np.where(mask_row)[0]
    return (int(xs.min()), int(xs.max())) if len(xs) else (0, 0)


def skin_mask(rgb, a):
    r, g = rgb[..., 0].astype(np.float32), rgb[..., 1].astype(np.float32)
    return (a > 0.5) & (r > 110) & (g / (r + 1) > 0.66)


def hood_mask(rgb, rmin=60):
    r, g = rgb[..., 0].astype(np.float32), rgb[..., 1].astype(np.float32)
    return (r > rmin) & (g / (r + 1) < 0.62)


def save_part(img, name):
    os.makedirs(PARTS, exist_ok=True)
    img.save(os.path.join(PARTS, f"{name}.png"))
    return img.size


# --------------------------------------------------------------------------- торс

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
    lt = lab[TORSO_PROBE[1], TORSO_PROBE[0]]
    base = lab == lt
    seam = sepm & (a > 0.05) & ndimage.binary_dilation(base, iterations=6)
    return rgb, a * (base | seam), a


# --------------------------------------------------------------------------- ноги

def hem_info(rgb, a, y_lo, y_hi, x_lo, x_hi):
    r, g = rgb[..., 0].astype(np.float32), rgb[..., 1].astype(np.float32)
    org = (a > 0.5) & (r > 90) & (g / (r + 1) < 0.62)
    rows = [y for y in range(y_lo, y_hi) if org[y, x_lo:x_hi].any()]
    y_hem = max(rows)
    x0, x1 = row_span(org[y_hem - 12])
    return y_hem, x1 - x0, (x0 + x1) / 2


def build_legs(t_rgb, t_a_all):
    rgb, a = load("gosha__10__lower")
    ht, wt, cxt = hem_info(t_rgb, t_a_all, 1100, 1300, 900, 1700)
    hl, wl, _ = hem_info(rgb, a, 20, 220, 900, 1700)
    a = a.copy()
    a[: hl + 2, :] = 0
    img, _ = trim(to_rgba(rgb, a))
    return img, wt / wl, ht, cxt


# --------------------------------------------------------------------------- головы

def build_head_cells(name):
    rgb, a = load(name)
    H, W = a.shape
    cw, ch = W // 3, H // 2
    out = []
    for i in range(6):
        c, rr = i % 3, i // 3
        sub = rgb[rr * ch:(rr + 1) * ch, c * cw:(c + 1) * cw].copy()
        sa = a[rr * ch:(rr + 1) * ch, c * cw:(c + 1) * cw].copy()
        hood = hood_mask(sub, rmin=35)
        hood[:470] = False
        # капюшон — большие терракотовые области, упирающиеся в край ячейки; рот и губы сюда не попадают
        lab, n = ndimage.label(hood)
        drop = np.zeros_like(hood)
        for j in range(1, n + 1):
            comp = lab == j
            ys, xs = np.where(comp)
            if comp.sum() > 6000 and (ys.max() >= ch - 3 or xs.min() <= 2 or xs.max() >= cw - 3):
                drop |= comp
        sa[ndimage.binary_dilation(drop, iterations=4)] = 0
        sa = sa * largest(sa > 0.05)
        out.append((sub, sa))
    return out


def neck_tip(rgb, a):
    """Кончик выреза (низ кожи шеи по центру) и центр шеи."""
    sk = skin_mask(rgb, a)
    h, w = sk.shape
    cx = int(np.mean(np.where(sk[560:600])[1])) if sk[560:600].any() else w // 2
    tip = int(max(np.where(sk[:, cx - 40:cx + 40].any(axis=1))[0]))
    return cx, tip


def skin_width(rgb, a, y, x_lo, x_hi):
    return int(skin_mask(rgb, a)[y, x_lo:x_hi].sum())


# --------------------------------------------------------------------------- рука и кисти

def rot_canvas(rgb, a, angle_ccw):
    img = to_rgba(rgb, a).rotate(angle_ccw, expand=True, resample=Image.BICUBIC)
    arr = np.asarray(img)
    return arr[..., :3], arr[..., 3].astype(np.float32) / 255.0


def build_arm():
    """Висящая рука → рукав (до манжеты) + расслабленная кисть."""
    rgb, a = load("gosha__08__arm_hang")
    H, W = a.shape
    terra = hood_mask(rgb, 35) & (a > 0.5)
    sl_core = largest(ndimage.binary_opening(terra, iterations=3))
    y_c = int(np.where(sl_core.any(axis=1))[0].max())        # нижняя строка манжеты
    sleeve_m = largest(ndimage.binary_dilation(sl_core, iterations=3) & (a > 0.05))
    yy = np.arange(H)[:, None]
    hand_m = largest((a > 0.05) & ~ndimage.binary_dilation(sl_core, iterations=2) & (yy > y_c - 25))
    top = int(np.where(sleeve_m.any(axis=1))[0].min())
    x0, x1 = row_span(sleeve_m[top + 110])
    shoulder = ((x0 + x1) / 2, top + 110)                    # центр головки рукава
    cx0, cx1 = row_span(sleeve_m[y_c - 6])
    cuff = ((cx0 + cx1) / 2, y_c)                            # низ манжеты (центр)
    return rgb, a * sleeve_m, a * hand_m, shoulder, cuff


def build_hands():
    """Лист кистей 4x2 → (имя, rgb, alpha, угол поворота ccw), ось предплечья направлена вниз."""
    rgb, a = load("gosha__09__hands")
    H, W = a.shape
    cw, ch = W // 4, H // 2
    out = []
    for i, name in enumerate(HANDS):
        c, rr = i % 4, i // 4
        sub = rgb[rr * ch:(rr + 1) * ch, c * cw:(c + 1) * cw].copy()
        sa = a[rr * ch:(rr + 1) * ch, c * cw:(c + 1) * cw].copy()
        cuff = largest(ndimage.binary_opening(hood_mask(sub, 35) & (sa > 0.5), iterations=3))
        near = ndimage.binary_dilation(cuff, iterations=5)
        skin = largest((sa > 0.05) & ~ndimage.binary_dilation(cuff, iterations=2))
        wy, wx = np.argwhere(skin & near).mean(axis=0)        # где рука входит в манжету
        cy, cx = np.argwhere(cuff).mean(axis=0)
        cur = math.atan2(wy - cy, wx - cx)                    # ось: от манжеты к кисти (y вниз)
        delta_cw = math.degrees(math.atan2(1, 0) - cur)       # до направления «вниз», по часовой
        out.append((name, sub, sa * skin, -delta_cw))
    return out


def wrist_profile(al, rows=(10, 130)):
    """Самая узкая строка у запястья: (ширина, центр x, y). Устойчиво к рваному краю манжеты."""
    ys, _ = np.where(al > 0.5)
    top = int(ys.min())
    best = None
    for y in range(top + rows[0], top + rows[1]):
        x0, x1 = row_span(al[y] > 0.5)
        w = x1 - x0
        if w > 5 and (best is None or w < best[0]):
            best = (w, (x0 + x1) / 2, y)
    return best, top


def hand_len(al):
    ys, _ = np.where(al > 0.5)
    return int(ys.max() - ys.min())


def hand_canvas(items, ref_len):
    """Кисти → один масштаб листа (по длине открытой ладони «wave» = длине расслабленной кисти), пивот запястья сверху."""
    rot = {}
    for name, rgb, a, ang in items:
        rr, ra = rot_canvas(rgb, a, ang)
        rot[name] = (rr, ra)
    k_sheet = ref_len / hand_len(rot["wave"][1])
    prepped = []
    for name, _, _, _ in items:
        rr, ra = rot[name]
        k = 1.0 if name == "relaxed" else k_sheet
        img, _ = trim(to_rgba(rr, ra))
        img = img.resize((max(1, round(img.width * k)), max(1, round(img.height * k))), Image.LANCZOS)
        al = np.asarray(img)[..., 3].astype(np.float32) / 255.0
        (_, cx, wy), top = wrist_profile(al)
        prepped.append((name, img, (cx, top)))
    return prepped, k_sheet


# --------------------------------------------------------------------------- сборка

def main():
    os.makedirs(PARTS, exist_ok=True)

    # ---- торс
    t_rgb, t_a, t_a_all = build_torso()
    torso_img, (tbx, tby) = trim(to_rgba(t_rgb, t_a))
    torso_s = resized(torso_img, S)
    tw, th = torso_s.size

    def torso_pt(p):
        return [(p[0] - tbx) * S / tw, (p[1] - tby) * S / th]

    # ---- ноги
    legs_img, k, hem_y, hem_cx = build_legs(t_rgb, t_a_all)
    legs_full = resized(legs_img, k * S)
    ext = int(40 * S)
    legs_s = Image.fromarray(np.vstack([np.repeat(np.asarray(legs_full)[0:1], ext, axis=0), np.asarray(legs_full)]), "RGBA")
    lw, lh = legs_s.size
    wx0, wx1 = row_span(np.asarray(legs_s.getchannel("A"))[ext + 2] > 128)
    legs_at = [((wx0 + wx1) / 2) / lw, ext / lh]
    torso_anchor = torso_pt((hem_cx, hem_y))

    # ---- головы: общий масштаб и точка шеи по первой голове
    front = build_head_cells("gosha__03__heads_front")
    talk = build_head_cells("gosha__05__heads_talk")
    h0_rgb, h0_a = front[0]
    cx_h, tip_h = neck_tip(h0_rgb, h0_a)
    neck_t = skin_width(t_rgb, np.clip(t_a_all, 0, 1), V_TIP_TORSO[1] - 55, 1100, 1480)
    neck_h = skin_width(h0_rgb, h0_a, tip_h - 55, cx_h - 250, cx_h + 250)
    sh = 0.92 * neck_t / max(neck_h, 1)
    heads = {}
    for names, cells in ((HEADS_FRONT, front), (HEADS_TALK, talk)):
        for nm, (sub, sa) in zip(names, cells):
            cxi, tipi = neck_tip(sub, sa)
            dx, dy = cx_h - cxi, tip_h - tipi                 # совмещаем кончик выреза с первой головой
            canvas = Image.new("RGBA", (sub.shape[1], sub.shape[0]), (0, 0, 0, 0))
            canvas.paste(to_rgba(sub, sa), (dx, dy))
            heads[nm] = resized(canvas, sh * S)
    for nm, img in heads.items():
        save_part(img, f"gosha_head_{nm}")
    hw, hh = heads["neutral"].size
    head_anchor = [cx_h * sh * S / hw, tip_h * sh * S / hh]

    # ---- рука: рукав + расслабленная кисть
    a_rgb, sl_a, hd_a, shoulder, cuff = build_arm()
    sleeve_img, (sbx, sby) = trim(to_rgba(a_rgb, sl_a))
    k_arm = ARM_SCALE * S
    sleeve_s = resized(sleeve_img, k_arm)
    sw, sh_ = sleeve_s.size
    sleeve_anchor = [(shoulder[0] - sbx) * k_arm / sw, (shoulder[1] - sby) * k_arm / sh_]
    cuff_at = [(cuff[0] - sbx) * k_arm / sw, (cuff[1] - sby - HAND_TUCK) * k_arm / sh_]

    ref_len = hand_len(hd_a)                                   # длина расслабленной кисти — эталон масштаба
    hands, k_sheet = hand_canvas([("relaxed", a_rgb, hd_a, 0.0)] + build_hands(), ref_len)
    pad = 20
    left = max(int(p[0]) for _, im, p in hands) + pad
    right = max(im.width - int(p[0]) for _, im, p in hands) + pad
    below = max(im.height - int(p[1]) for _, im, p in hands) + pad
    CW, CH = left + right, pad + below
    for nm, im, p in hands:
        cv = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
        cv.alpha_composite(im, (left - int(p[0]), pad - int(p[1])))
        small = resized(cv, k_arm)
        save_part(small, f"gosha_hand_{nm}_a")
        save_part(small.transpose(Image.FLIP_LEFT_RIGHT), f"gosha_hand_{nm}_b")
    hand_anchor_a = [left / CW, pad / CH]
    hand_anchor_b = [1 - left / CW, pad / CH]

    save_part(sleeve_s, "gosha_sleeve_a")
    save_part(sleeve_s.transpose(Image.FLIP_LEFT_RIGHT), "gosha_sleeve_b")
    sleeve_anchor_b = [1 - sleeve_anchor[0], sleeve_anchor[1]]
    cuff_at_b = [1 - cuff_at[0], cuff_at[1]]
    save_part(torso_s, "gosha_torso")
    save_part(legs_s, "gosha_legs")

    rig = {
        "talk_part": "head",
        "part_boil": 0.4,
        "talk": {"dy": 0, "mid_asset": "gosha_head_t_mid", "open_asset": "gosha_head_t_open"},
        "parts": [
            {"part": "legs", "asset": "gosha_legs", "anchor": [0.5, 1.0], "root": True, "z": -2},
            {"part": "torso", "asset": "gosha_torso", "parent": "legs", "at": legs_at, "anchor": torso_anchor, "z": 0,
             "idle": {"breath": [0.006, 3.4, 0.0]}},
            # рукава и кисти — ПОД торсом: плечо читается как плечо, а не накладка поверх груди;
            # чтобы рука легла поверх торса, задайте в сцене parts.sleeve_x.z = 1
            {"part": "hand_a", "asset": "gosha_hand_relaxed_a", "parent": "sleeve_a", "at": cuff_at, "anchor": hand_anchor_a, "z": -0.6},
            {"part": "hand_b", "asset": "gosha_hand_relaxed_b", "parent": "sleeve_b", "at": cuff_at_b, "anchor": hand_anchor_b, "z": -0.6},
            {"part": "sleeve_a", "asset": "gosha_sleeve_a", "parent": "torso", "at": torso_pt(SHOULDER_L), "anchor": sleeve_anchor,
             "rot": 2, "z": -0.5, "idle": {"rot": [1.6, 3.7, 0.1]}},
            {"part": "sleeve_b", "asset": "gosha_sleeve_b", "parent": "torso", "at": torso_pt(SHOULDER_R), "anchor": sleeve_anchor_b,
             "rot": -2, "z": -0.5, "idle": {"rot": [1.6, 3.7, 0.6]}},
            {"part": "head", "asset": "gosha_head_neutral", "parent": "torso", "at": torso_pt(V_TIP_TORSO), "anchor": head_anchor, "z": 2,
             "idle": {"rot": [1.3, 4.3, 0.25]}},
        ],
    }
    assets = {n: f"chars/gosha/parts/{n}.png" for n in ("gosha_torso", "gosha_legs", "gosha_sleeve_a", "gosha_sleeve_b")}
    for nm in HEADS_FRONT + HEADS_TALK:
        assets[f"gosha_head_{nm}"] = {"file": f"chars/gosha/parts/gosha_head_{nm}.png", "trim": False}
    for nm in ["relaxed"] + HANDS:
        for side in "ab":
            assets[f"gosha_hand_{nm}_{side}"] = {"file": f"chars/gosha/parts/gosha_hand_{nm}_{side}.png", "trim": False}
    json.dump({"rig": rig, "assets": assets}, open(os.path.join(ROOT, "rig.json"), "w"), ensure_ascii=False, indent=1)
    print(f"шея: торс {neck_t}px, голова {neck_h}px → голова ×{sh:.3f}; ноги ×{k:.3f}; рукав {sleeve_s.size}; "
          f"холст кисти {CW}x{CH}; масштаб листа кистей ×{k_sheet:.3f}")
    write_test_scene(rig, assets)


def write_test_scene(rig, assets):
    def shot(face=None, parts=None, rot=0):
        l = {"id": "g", "rig": "gosha", "pos": [540, 1840], "scale": 1.0, "rot": rot}
        if face:
            l["face"] = [{"t": 0, "asset": face}]
        if parts:
            l["parts"] = parts
        return {"dur": 1, "fill": [150, 150, 150], "layers": [l]}

    sc = {
        "title": "Тест марионетки Гоши", "size": [1080, 1920], "fps": 24, "anim_fps": 12, "asset_root": "../assets",
        "style": {"edge": 6, "boil": 0.0, "camera_boil": 0, "shadow_blur": 10, "shadow_offset": [10, 14],
                  "shadow_opacity": 0.4, "grain": 0, "flicker": 0, "vignette": 0,
                  "photo_look": {"sat": 0.94, "contrast": 1.05, "noise": 3, "fibre": 0.012, "edge_darken": 0.08}},
        "assets": assets, "rigs": {"gosha": rig},
        "shots": [
            shot(),
            shot("gosha_head_shock", {"sleeve_a": {"rot": 150}, "hand_a": {"asset": "gosha_hand_wave_a"},
                                      "sleeve_b": {"rot": -40}}),
            shot("gosha_head_smug", {"sleeve_a": {"rot": 8}, "sleeve_b": {"rot": -75},
                                     "hand_b": {"asset": "gosha_hand_point_b", "rot": -30}}),
            shot("gosha_head_shout", {"sleeve_a": {"rot": 25}, "hand_a": {"asset": "gosha_hand_fist_a"},
                                      "sleeve_b": {"rot": -25}, "hand_b": {"asset": "gosha_hand_fist_b"}}),
        ]}
    json.dump(sc, open(os.path.join(REPO, "scenes", "test_gosha.json"), "w"), ensure_ascii=False, indent=1)


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "--mask":
        compute_mask(sys.argv[2], sys.argv[3])
    else:
        main()
