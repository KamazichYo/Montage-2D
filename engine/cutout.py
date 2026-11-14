#!/usr/bin/env python3
"""
Montage-2D — движок перекладки (cutout / photo-collage stop-motion).

Берёт JSON-сцену (фоны-фотографии + вырезанные PNG-слои персонажей) и
рендерит вертикальный ролик 1080x1920 через ffmpeg.

Что делает «перекладку» похожей на перекладку:
  * время ступенчатое: поза меняется 12 раз в секунду («на двойках»),
    видео при этом 24 fps;
  * каждый шаг — лёгкий «бойл»: микросдвиг/поворот вырезки, как будто
    кусочек фотки переложили руками;
  * у вырезок белая бумажная кромка и мягкая тень на фон;
  * «челюсть-хлопушка» для речи (как в коллажной анимации 70-х) или
    подмена рта/головы по таймингу;
  * поверх — бумажное зерно, виньетка и лёгкое мерцание экспозиции.

Запуск:
    python3 engine/cutout.py scenes/demo.json -o out/demo.mp4
    python3 engine/cutout.py scenes/demo.json --still 2.5 -o out/frame.png
"""
from __future__ import annotations

import argparse
import json
import math
import os
import random
import subprocess
import zlib
import sys
from dataclasses import dataclass, field
from functools import lru_cache

import numpy as np
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageFont

# --------------------------------------------------------------------------
# Математика 2D-аффинных матриц (3x3)
# --------------------------------------------------------------------------

def m_translate(x, y):
    return np.array([[1, 0, x], [0, 1, y], [0, 0, 1]], dtype=float)


def m_scale(sx, sy=None):
    sy = sx if sy is None else sy
    return np.array([[sx, 0, 0], [0, sy, 0], [0, 0, 1]], dtype=float)


def m_rotate(deg):
    r = math.radians(deg)
    c, s = math.cos(r), math.sin(r)
    return np.array([[c, -s, 0], [s, c, 0], [0, 0, 1]], dtype=float)


# --------------------------------------------------------------------------
# Изинги
# --------------------------------------------------------------------------

def _back_out(x, k=1.70158):
    x -= 1
    return x * x * ((k + 1) * x + k) + 1


EASES = {
    "linear": lambda x: x,
    "in": lambda x: x * x,
    "out": lambda x: 1 - (1 - x) * (1 - x),
    "inout": lambda x: 3 * x * x - 2 * x * x * x,
    "back": _back_out,  # перелёт и возврат — «хлоп» на место
    "step": lambda x: 0.0 if x < 1 else 1.0,  # мгновенная перекладка
}


def lerp(a, b, t):
    if isinstance(a, (list, tuple)):
        return [lerp(x, y, t) for x, y in zip(a, b)]
    return a + (b - a) * t


def sample_keys(keys, t, prop, default):
    """keys: [{"t":0,"pos":[..],"ease":"inout"}, ...] — интерполяция свойства."""
    pts = [k for k in keys if prop in k]
    if not pts:
        return default
    if t <= pts[0]["t"]:
        return pts[0][prop]
    for a, b in zip(pts, pts[1:]):
        if a["t"] <= t < b["t"]:
            span = max(b["t"] - a["t"], 1e-6)
            x = (t - a["t"]) / span
            x = EASES.get(b.get("ease", "inout"), EASES["inout"])(x)
            return lerp(a[prop], b[prop], x)
    return pts[-1][prop]


# --------------------------------------------------------------------------
# Ассеты: загрузка, бумажная кромка, тень
# --------------------------------------------------------------------------

@dataclass
class Asset:
    img: Image.Image          # RGBA с кромкой
    shadow: Image.Image       # чёрный силуэт, размытый, того же размера
    pad: int                  # сколько добавили по краям (для якоря)
    src_size: tuple           # размер исходной вырезки


class AssetBank:
    def __init__(self, root: str, defs: dict, style: dict):
        self.root = root
        self.defs = defs
        self.style = style
        self.cache: dict[str, Asset] = {}

    def get(self, name: str) -> Asset:
        if name in self.cache:
            return self.cache[name]
        d = self.defs[name]
        if isinstance(d, str):
            d = {"file": d}
        path = os.path.join(self.root, d["file"])
        img = Image.open(path).convert("RGBA")
        if d.get("trim", True):
            bbox = img.getchannel("A").point(lambda a: 255 if a > 8 else 0).getbbox()
            if bbox:
                img = img.crop(bbox)
        if "max_size" in d:
            img.thumbnail((d["max_size"], d["max_size"]), Image.LANCZOS)
        src_size = img.size
        is_bg = d.get("bg", False)
        edge = 0 if is_bg else d.get("edge", self.style.get("edge", 6))
        blur = self.style.get("shadow_blur", 10)
        pad = 0 if is_bg else edge + blur * 2 + 2
        if pad:
            canvas = Image.new("RGBA", (img.width + pad * 2, img.height + pad * 2), (0, 0, 0, 0))
            canvas.paste(img, (pad, pad))
            img = canvas
        a = img.getchannel("A")
        if edge:
            # белая бумажная кромка: расширенная альфа под картинкой
            grown = a.filter(ImageFilter.MaxFilter(edge * 2 + 1))
            grown = grown.filter(ImageFilter.GaussianBlur(0.8))
            paper = Image.new("RGBA", img.size, tuple(self.style.get("edge_color", [250, 248, 240])) + (0,))
            paper.putalpha(grown)
            paper.alpha_composite(img)
            img = paper
            a = img.getchannel("A")
        if is_bg:
            shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
        else:
            sh_a = a.filter(ImageFilter.GaussianBlur(blur)).point(
                lambda v: int(v * self.style.get("shadow_opacity", 0.45)))
            shadow = Image.new("RGBA", img.size, (0, 0, 0, 0))
            shadow.putalpha(sh_a)
        asset = Asset(img=img, shadow=shadow, pad=pad, src_size=src_size)
        self.cache[name] = asset
        return asset


# --------------------------------------------------------------------------
# Рендер слоя в холст по матрице (только в его bounding box — быстро)
# --------------------------------------------------------------------------

def blit(canvas: Image.Image, src: Image.Image, M: np.ndarray, resample=Image.BICUBIC):
    W, H = canvas.size
    w, h = src.size
    corners = np.array([[0, 0, 1], [w, 0, 1], [0, h, 1], [w, h, 1]], dtype=float).T
    pts = M @ corners
    x0, y0 = np.floor(pts[0].min()), np.floor(pts[1].min())
    x1, y1 = np.ceil(pts[0].max()), np.ceil(pts[1].max())
    x0, y0 = int(max(0, x0)), int(max(0, y0))
    x1, y1 = int(min(W, x1)), int(min(H, y1))
    if x1 <= x0 or y1 <= y0:
        return
    # PIL хочет обратное отображение: выход -> вход
    Minv = np.linalg.inv(m_translate(-x0, -y0) @ M)
    coeffs = (Minv[0, 0], Minv[0, 1], Minv[0, 2], Minv[1, 0], Minv[1, 1], Minv[1, 2])
    patch = src.transform((x1 - x0, y1 - y0), Image.AFFINE, coeffs, resample=resample)
    canvas.alpha_composite(patch, (x0, y0))


# --------------------------------------------------------------------------
# Сцена
# --------------------------------------------------------------------------

@dataclass
class Ctx:
    W: int
    H: int
    anim_fps: int
    style: dict
    bank: AssetBank
    font_path: str
    seed: int = 7


def stepped(t, anim_fps):
    return math.floor(t * anim_fps + 1e-6) / anim_fps


def jitter(seed_key, step, amount):
    """Детерминированный «бойл»: одна и та же поза на шаге = один и тот же сдвиг."""
    if amount <= 0:
        return 0.0, 0.0, 0.0
    rnd = random.Random(zlib.crc32(f"{seed_key}:{step}".encode()))
    return (rnd.uniform(-1, 1) * amount,
            rnd.uniform(-1, 1) * amount,
            rnd.uniform(-1, 1) * amount * 0.35)


def in_ranges(t, ranges):
    for r in ranges:
        if r[0] <= t < r[1]:
            return True
    return False


def layer_state(layer, t, step, ctx):
    """Возвращает (asset_name, local_matrix) или None, если слой скрыт."""
    if "show" in layer and not in_ranges(t, layer["show"]):
        return None
    keys = layer.get("keys", [])
    pos = sample_keys(keys, t, "pos", layer.get("pos", [0, 0]))
    rot = sample_keys(keys, t, "rot", layer.get("rot", 0.0))
    scale = sample_keys(keys, t, "scale", layer.get("scale", 1.0))
    flip = layer.get("flip", False)

    # подмена картинки (эмоции, позы рук): [{"t":1.2,"asset":"gosha_head_shock"}]
    asset_name = layer.get("asset")
    for sw in layer.get("swap", []):
        if t >= sw["t"]:
            asset_name = sw["asset"]

    # речь: челюсть-хлопушка или подмена рта
    talk = layer.get("talk")
    if talk and in_ranges(t, talk.get("ranges", [])):
        tick = int(round(t * ctx.anim_fps))
        rnd = random.Random(tick * 31 + sum(map(ord, layer.get("id", ""))))
        # каждый третий шаг рот закрыт, остальные — случайная степень открытия
        open_amt = rnd.choice([0.0, 0.6, 1.0, 1.0]) if tick % 3 != 0 else 0.0
        if "open_asset" in talk and open_amt > 0.5:
            asset_name = talk["open_asset"]
        pos = [pos[0] + talk.get("dx", 0) * open_amt, pos[1] + talk.get("dy", 18) * open_amt]
        rot = rot + talk.get("drot", 0) * open_amt

    # «вскок» — появление с перелётом
    if "pop" in layer:
        t0 = layer["pop"]
        k = min(max((t - t0) / 0.25, 0), 1)
        scale = scale * (EASES["back"](k) if k < 1 else 1.0)
        if k <= 0:
            return None

    jx, jy, jr = jitter(layer.get("id", asset_name), step, layer.get("boil", ctx.style.get("boil", 1.5)))
    asset = ctx.bank.get(asset_name)
    ax, ay = layer.get("anchor", [0.5, 0.5])
    # координаты детей (parent) — в пикселях исходной вырезки родителя, без полей
    apx = ax * asset.src_size[0]
    apy = ay * asset.src_size[1]
    sx = scale if not isinstance(scale, list) else scale[0]
    sy = scale if not isinstance(scale, list) else scale[1]
    if flip:
        sx = -sx
    M = (m_translate(pos[0] + jx, pos[1] + jy) @ m_rotate(rot + jr) @ m_scale(sx, sy)
         @ m_translate(-apx, -apy))
    return asset_name, M, asset


def camera_matrix(shot, t, ctx, step):
    cam = shot.get("camera", {})
    keys = cam.get("keys", [])
    W, H = ctx.W, ctx.H
    zoom = sample_keys(keys, t, "zoom", cam.get("zoom", 1.0))
    center = sample_keys(keys, t, "center", cam.get("center", [W / 2, H / 2]))
    rot = sample_keys(keys, t, "rot", cam.get("rot", 0.0))
    # тряска: [{"t":2.0,"dur":0.4,"amp":25}]
    sx = sy = 0.0
    for sh in cam.get("shake", []):
        if sh["t"] <= t < sh["t"] + sh.get("dur", 0.4):
            rnd = random.Random(int(t * ctx.anim_fps) * 7919)
            fall = 1 - (t - sh["t"]) / sh.get("dur", 0.4)
            sx += rnd.uniform(-1, 1) * sh.get("amp", 20) * fall
            sy += rnd.uniform(-1, 1) * sh.get("amp", 20) * fall
    # лёгкий «ручной» дрейф камеры-штатива по шагам
    cb = ctx.style.get("camera_boil", 1.0)
    jx, jy, _ = jitter("camera", step, cb)
    return (m_translate(W / 2 + sx + jx, H / 2 + sy + jy) @ m_rotate(-rot) @ m_scale(zoom)
            @ m_translate(-center[0], -center[1]))


def world_matrices(shot, t, step, ctx):
    layers = shot.get("layers", [])
    by_id = {l["id"]: l for l in layers if "id" in l}
    local = {}
    for l in layers:
        st = layer_state(l, t, step, ctx)
        local[id(l)] = st
    world = {}

    def resolve(l):
        if id(l) in world:
            return world[id(l)]
        st = local[id(l)]
        if st is None:
            world[id(l)] = None
            return None
        name, M, asset = st
        parent = l.get("parent")
        if parent:
            pst = resolve(by_id[parent])
            if pst is None:
                world[id(l)] = None
                return None
            # "at": точка крепления в долях вырезки родителя (шея, плечо, линия рта)
            if "at" in l:
                pw, ph = pst[2].src_size
                M = m_translate(l["at"][0] * pw, l["at"][1] * ph) @ M
            M = pst[1] @ M
        world[id(l)] = (name, M, asset)
        return world[id(l)]

    out = []
    for i, l in enumerate(layers):
        r = resolve(l)
        if r is not None:
            out.append((l.get("z", i), l, r))
    out.sort(key=lambda x: x[0])
    return out



# --------------------------------------------------------------------------
# Риги: персонаж = набор деталей, в сцене ставится одной строкой
# --------------------------------------------------------------------------

ROOT_KEYS = ("pos", "scale", "rot", "keys", "flip", "show", "pop", "boil")


def expand_rigs(scene):
    rigs = scene.get("rigs", {})
    for shot in scene["shots"]:
        out = []
        for i, l in enumerate(shot.get("layers", [])):
            if "rig" not in l:
                out.append(l)
                continue
            rig = rigs[l["rig"]]
            iid = l.get("id", f"{l['rig']}{i}")
            z0 = l.get("z", i)
            root = next(p["part"] for p in rig["parts"] if p.get("root"))
            over = dict(l.get("parts", {}))
            if "say" in l:   # [[t0,t1],...] — когда говорит (челюсть хлопает)
                jaw = dict(over.get("jaw", {}))
                talk = dict(rig.get("talk", {}))
                talk["ranges"] = l["say"]
                jaw["talk"] = talk
                over["jaw"] = jaw
            if "face" in l:  # [{"t":1.0,"asset":"x_head_shock"}] — смена эмоции
                head = dict(over.get("head", {}))
                head["swap"] = l["face"]
                over["head"] = head
            for p in rig["parts"]:
                part = {k: v for k, v in p.items() if k not in ("part", "root", "parent", "z")}
                part.update(over.get(p["part"], {}))
                part["z"] = z0 + p.get("z", 0) * 0.01
                if p.get("root"):
                    part["id"] = iid
                    for k in ROOT_KEYS:
                        if k in l:
                            part[k] = l[k]
                else:
                    part["id"] = f"{iid}.{p['part']}"
                    par = p.get("parent", root)
                    part["parent"] = iid if par == root else f"{iid}.{par}"
                out.append(part)
        shot["layers"] = out
    return scene

# --------------------------------------------------------------------------
# Подписи (субтитры ситкома)
# --------------------------------------------------------------------------

@lru_cache(maxsize=16)
def font(path, size):
    return ImageFont.truetype(path, size)


def wrap(draw, text, fnt, max_w):
    words, lines, cur = text.split(), [], ""
    for w in words:
        test = (cur + " " + w).strip()
        if draw.textlength(test, font=fnt) <= max_w:
            cur = test
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def draw_caption(canvas, cap, ctx):
    W, H = ctx.W, ctx.H
    st = ctx.style.get("captions", {})
    size = cap.get("size", st.get("size", 62))
    fnt = font(ctx.font_path, size)
    d = ImageDraw.Draw(canvas)
    lines = wrap(d, cap["text"], fnt, W - 160)
    color = tuple(cap.get("color", st.get("color", [255, 255, 255])))
    y = cap.get("y", st.get("y", int(H * 0.70)))
    lh = int(size * 1.18)
    if cap.get("who"):
        wf = font(ctx.font_path, int(size * 0.55))
        wc = tuple(cap.get("who_color", [255, 214, 0]))
        tw = d.textlength(cap["who"], font=wf)
        d.text(((W - tw) / 2, y - int(size * 0.75)), cap["who"], font=wf, fill=wc,
               stroke_width=4, stroke_fill=(0, 0, 0))
    for i, line in enumerate(lines):
        tw = d.textlength(line, font=fnt)
        d.text(((W - tw) / 2, y + i * lh), line, font=fnt, fill=color,
               stroke_width=st.get("stroke", 7), stroke_fill=(0, 0, 0))


def draw_title_card(canvas, card, ctx, t):
    """Плашка-гэг на весь экран: «3 ЧАСА СПУСТЯ», «ТОКЕНОВ: 0»."""
    W, H = ctx.W, ctx.H
    bg = tuple(card.get("bg", [20, 20, 20])) + (255,)
    over = Image.new("RGBA", (W, H), bg)
    d = ImageDraw.Draw(over)
    size = card.get("size", 120)
    fnt = font(ctx.font_path, size)
    lines = wrap(d, card["text"], fnt, W - 140)
    total = len(lines) * size * 1.2
    for i, line in enumerate(lines):
        tw = d.textlength(line, font=fnt)
        d.text(((W - tw) / 2, (H - total) / 2 + i * size * 1.2), line, font=fnt,
               fill=tuple(card.get("color", [255, 255, 255])))
    canvas.alpha_composite(over)


# --------------------------------------------------------------------------
# Пост-обработка: зерно, виньетка, мерцание
# --------------------------------------------------------------------------

class Post:
    def __init__(self, ctx):
        W, H = ctx.W, ctx.H
        self.ctx = ctx
        rng = np.random.default_rng(3)
        self.grains = []
        for _ in range(4):
            g = rng.normal(0, 1, (H // 2, W // 2)).astype(np.float32)
            g = np.kron(g, np.ones((2, 2), dtype=np.float32))[:H, :W]
            self.grains.append(g)
        yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        r = np.sqrt(((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
        self.vign = np.clip(1 - ctx.style.get("vignette", 0.28) * np.clip(r - 0.35, 0, None) ** 1.6, 0, 1)

    def apply(self, img: Image.Image, step: int) -> Image.Image:
        st = self.ctx.style
        a = np.asarray(img.convert("RGB")).astype(np.float32)
        rnd = random.Random(step * 13)
        flicker = 1 + rnd.uniform(-1, 1) * st.get("flicker", 0.025)
        a *= flicker
        a *= self.vign[..., None]
        a += self.grains[step % 4][..., None] * st.get("grain", 7.0)
        return Image.fromarray(np.clip(a, 0, 255).astype(np.uint8))


# --------------------------------------------------------------------------
# Главный цикл
# --------------------------------------------------------------------------

def render_frame(scene, ctx, post, t_global):
    shots = scene["shots"]
    acc = 0.0
    for shot in shots:
        if t_global < acc + shot["dur"] or shot is shots[-1]:
            break
        acc += shot["dur"]
    t = stepped(t_global - acc, ctx.anim_fps)
    step = int(round(t_global * ctx.anim_fps))
    canvas = Image.new("RGBA", (ctx.W, ctx.H), tuple(shot.get("fill", [30, 30, 30])) + (255,))
    C = camera_matrix(shot, t, ctx, step)
    sh_off = ctx.style.get("shadow_offset", [10, 14])
    for _, layer, (name, M, asset) in world_matrices(shot, t, step, ctx):
        full = C @ M @ m_translate(-asset.pad, -asset.pad)
        if layer.get("shadow", True) and asset.pad:
            blit(canvas, asset.shadow, m_translate(*sh_off) @ full)
        blit(canvas, asset.img, full)
    for cap in shot.get("captions", []):
        if cap["t"][0] <= t < cap["t"][1]:
            draw_caption(canvas, cap, ctx)
    if "card" in shot:
        draw_title_card(canvas, shot["card"], ctx, t)
    return post.apply(canvas, step)


def build_audio_args(scene, root, total):
    audio = scene.get("audio", [])
    if not audio:
        return [], []
    inputs, filters, labels = [], [], []
    for i, a in enumerate(audio):
        inputs += ["-i", os.path.join(root, a["file"])]
        ms = int(a.get("start", 0) * 1000)
        vol = a.get("volume", 1.0)
        filters.append(f"[{i + 1}:a]adelay={ms}|{ms},volume={vol}[a{i}]")
        labels.append(f"[a{i}]")
    filters.append("".join(labels) + f"amix=inputs={len(labels)}:normalize=0,atrim=0:{total}[aout]")
    return inputs, ["-filter_complex", ";".join(filters), "-map", "0:v", "-map", "[aout]",
                    "-c:a", "aac", "-b:a", "192k"]


def main():
    ap = argparse.ArgumentParser(description="Рендер перекладки в вертикальное видео")
    ap.add_argument("scene")
    ap.add_argument("-o", "--out", default="out/render.mp4")
    ap.add_argument("--still", type=float, help="отрендерить один кадр на этой секунде (PNG)")
    ap.add_argument("--fps", type=int, default=None, help="fps видео (по умолчанию из сцены, 24)")
    args = ap.parse_args()

    with open(args.scene, encoding="utf-8") as f:
        scene = expand_rigs(json.load(f))
    root = os.path.dirname(os.path.abspath(args.scene))
    root = os.path.join(root, scene.get("asset_root", "."))
    W, H = scene.get("size", [1080, 1920])
    style = scene.get("style", {})
    font_path = os.path.join(root, style["font"]) if "font" in style else \
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ctx = Ctx(W=W, H=H, anim_fps=scene.get("anim_fps", 12), style=style,
              bank=AssetBank(root, scene["assets"], style), font_path=font_path)
    post = Post(ctx)
    fps = args.fps or scene.get("fps", 24)
    total = sum(s["dur"] for s in scene["shots"])
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)

    if args.still is not None:
        render_frame(scene, ctx, post, args.still).save(args.out)
        print("saved", args.out)
        return

    a_in, a_map = build_audio_args(scene, root, total)
    cmd = ["ffmpeg", "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
           "-s", f"{W}x{H}", "-r", str(fps), "-i", "-", *a_in]
    cmd += a_map if a_map else []
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "18", "-preset", "medium",
            "-movflags", "+faststart", args.out]
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    n = int(round(total * fps))
    last_key, last_bytes = None, None
    for i in range(n):
        tg = i / fps
        key = int(math.floor(tg * ctx.anim_fps + 1e-6))  # одна поза на шаг анимации
        if key != last_key:
            last_bytes = render_frame(scene, ctx, post, tg).tobytes()
            last_key = key
        proc.stdin.write(last_bytes)
        if i % fps == 0:
            print(f"\r{tg:5.1f}/{total:.1f}s", end="", file=sys.stderr)
    proc.stdin.close()
    proc.wait()
    print(f"\nsaved {args.out}", file=sys.stderr)


if __name__ == "__main__":
    main()
