#!/usr/bin/env python3
"""Собирает scenes/demo_gosha_reel.json — три коротких гэга на кукле Гоши (походка, двойной взгляд, отваливается рука)."""
import json
import os

REPO = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
base = json.load(open(os.path.join(REPO, "assets", "chars", "gosha", "rig.json")))
look = {"sat": 0.94, "contrast": 1.05, "noise": 3, "fibre": 0.012, "edge_darken": 0.08}
sc = {"title": "Примеры анимации Гоши", "size": [1080, 1920], "fps": 24, "anim_fps": 12, "asset_root": "../assets",
      "style": {"edge": 6, "boil": 1.2, "camera_boil": 1.0, "shadow_blur": 10, "shadow_offset": [10, 14],
                "shadow_opacity": 0.45, "grain": 6, "flicker": 0.03, "vignette": 0.3, "photo_look": look,
                "captions": {"size": 58, "y": 1560, "stroke": 7}},
      "cast": {"g": {"name": "", "color": [255, 160, 60], "voice": {"piper": "dmitri", "speed": 1.12, "pitch": 1.05}}},
      "assets": base["assets"], "rigs": {"gosha": base["rig"]}, "shots": []}
label = lambda text: [{"t": [0.1, 3.0], "who": "", "text": text, "color": [255, 255, 255], "y": 110, "size": 52}]

# A. походка вразвалочку
kr, ka, kb = [], [], []
for i in range(13):
    t = i * 0.25
    kr.append({"t": t, "pos": [200 + 680 * t / 3.0, 1850 if i % 2 == 0 else 1826], "rot": -4 if i % 2 == 0 else 4, "ease": "linear"})
    ka.append({"t": t, "rot": 24 if i % 2 == 0 else -24, "ease": "linear"})
    kb.append({"t": t, "rot": -24 if i % 2 == 0 else 24, "ease": "linear"})
A = {"dur": 3.0, "fill": [221, 203, 168], "captions": label("1. ПОХОДКА ВРАЗВАЛОЧКУ"),
     "layers": [{"id": "g", "rig": "gosha", "scale": 0.9, "pos": [200, 1850], "keys": kr, "boil": 1.5,
                 "face": [{"t": 0, "asset": "gosha_head_proud"}],
                 "parts": {"sleeve_a": {"keys": ka}, "sleeve_b": {"keys": kb}}}]}

# B. двойной взгляд: резкий наезд, тряска, шок, руки вверх с перелётом
B = {"dur": 3.0, "fill": [186, 206, 214], "captions": label("2. ДВОЙНОЙ ВЗГЛЯД"),
     "camera": {"keys": [{"t": 0, "zoom": 1.0, "center": [540, 960]}, {"t": 1.0, "zoom": 1.0, "center": [540, 960]},
                         {"t": 1.0001, "zoom": 1.9, "center": [540, 760], "ease": "step"},
                         {"t": 3.0, "zoom": 2.1, "center": [540, 780], "ease": "linear"}],
                "shake": [{"t": 1.0, "dur": 0.5, "amp": 34}]},
     "layers": [{"id": "g", "rig": "gosha", "scale": 0.9, "pos": [540, 1840],
                 "keys": [{"t": 0, "scale": [1, 1]}, {"t": 1.0, "scale": [1, 1]}, {"t": 1.25, "scale": [0.97, 1.05], "ease": "spring"}],
                 "face": [{"t": 0, "asset": "gosha_head_smug"}, {"t": 1.0, "asset": "gosha_head_shock"}, {"t": 1.9, "asset": "gosha_head_shout"}],
                 "parts": {"sleeve_a": {"keys": [{"t": 0, "rot": 2}, {"t": 1.0, "rot": 2}, {"t": 1.45, "rot": 165, "ease": "spring"}]},
                           "sleeve_b": {"keys": [{"t": 0, "rot": -2}, {"t": 1.0, "rot": -2}, {"t": 1.45, "rot": -165, "ease": "spring"}]},
                           "hand_a": {"swap": [{"t": 1.35, "asset": "gosha_hand_wave_a"}]},
                           "hand_b": {"swap": [{"t": 1.35, "asset": "gosha_hand_wave_b"}]}}}]}

# C. «Кажется, у меня отпала рука»
C = {"fill": [214, 190, 170], "lead": 0.4, "tail": 1.0, "captions": label("3. ОТВАЛИЛАСЬ РУКА")[:1],
     "dialogue": [{"who": "g", "text": "Ой. Кажется, у меня отпала рука."}],
     "layers": [{"id": "g", "rig": "gosha", "scale": 0.9, "pos": [540, 1840],
                 "face": [{"t": 0, "asset": "gosha_head_proud"}, {"t": 1.5, "asset": "gosha_head_panic"}],
                 "parts": {"hand_a": {"keys": [{"t": 0, "pos": [0, 0], "rot": 0}, {"t": 1.5, "pos": [0, 0], "rot": 0},
                                               {"t": 1.95, "pos": [-10, 500], "rot": -30, "ease": "in"},
                                               {"t": 2.15, "pos": [-25, 430], "rot": -60, "ease": "out"},
                                               {"t": 2.4, "pos": [-35, 505], "rot": -95, "ease": "in"}]},
                           "sleeve_b": {"keys": [{"t": 0, "rot": -2}, {"t": 1.5, "rot": -2}, {"t": 1.9, "rot": -150, "ease": "spring"}]},
                           "hand_b": {"swap": [{"t": 1.8, "asset": "gosha_hand_claw_b"}]}}}]}
C["captions"][0]["t"] = [0.1, 1.0]
sc["shots"] = [A, B, C]
json.dump(sc, open(os.path.join(REPO, "scenes", "demo_gosha_reel.json"), "w"), ensure_ascii=False, indent=1)
print("scenes/demo_gosha_reel.json")
