#!/usr/bin/env python3
"""
Черновая озвучка реплик сцены — локально, без ключей (Piper TTS, русские голоса).

    python3 engine/voice.py scenes/ep01_pilot.json          # только недостающие реплики
    python3 engine/voice.py scenes/ep01_pilot.json --force  # переозвучить всё

Для каждой реплики из "dialogue" создаёт audio/<сцена>/sNN_MM_<кто>.wav.
Движок сам подхватит эти файлы: длительность кадра, субтитры и челюсть
подстроятся под звук. Любой файл можно заменить своим дублем (запись голосом,
Gemini TTS, ElevenLabs) — главное сохранить имя.

Голос персонажа задаётся в сцене:
    "cast": { "g": { "name": "ГОША",
                     "voice": { "piper": "dmitri", "speed": 1.12, "pitch": 1.06 } } }
piper: denis | dmitri | irina | ruslan   speed: >1 быстрее   pitch: >1 выше
fx: "robot" — лёгкая «синтетика» для ИИ-агента
Поле реплики "say" — как произнести, если написание сбивает синтезатор
(«дифф» → «диф», «MRR» → «эм-эр-эр»).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from cutout import dialogue_path  # noqa: E402

CACHE = os.path.expanduser("~/.cache/montage/piper")
HF = "https://huggingface.co/rhasspy/piper-voices/resolve/main/ru/ru_RU/{v}/medium/ru_RU-{v}-medium.onnx"
FX = {
    "robot": "aecho=0.8:0.6:14:0.35,highpass=f=180,acrusher=bits=12:mix=0.15",
    "phone": "highpass=f=400,lowpass=f=3200,acompressor",
}


def model(voice: str) -> str:
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, f"ru_RU-{voice}-medium.onnx")
    for url, dst in ((HF.format(v=voice), path), (HF.format(v=voice) + ".json", path + ".json")):
        if not os.path.exists(dst):
            print("↓", os.path.basename(dst), file=sys.stderr)
            urllib.request.urlretrieve(url, dst)
    return path


def synth(text: str, v: dict, out: str):
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        raw = tmp.name
    subprocess.run([sys.executable, "-m", "piper", "-m", model(v.get("piper", "dmitri")),
                    "-f", raw, "--length-scale", str(round(1 / v.get("speed", 1.0), 3))],
                   input=text.encode(), check=True, capture_output=True)
    af = []
    if v.get("pitch", 1.0) != 1.0:
        af.append(f"rubberband=pitch={v['pitch']}")
    if v.get("fx") in FX:
        af.append(FX[v["fx"]])
    af.append("silenceremove=start_periods=1:start_threshold=-45dB,areverse,"
              "silenceremove=start_periods=1:start_threshold=-45dB,areverse")
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", raw, "-af", ",".join(af),
                    "-ar", "44100", "-ac", "1", out], check=True)
    os.unlink(raw)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    with open(args.scene, encoding="utf-8") as f:
        scene = json.load(f)
    cast = scene.get("cast", {})
    n = 0
    for si, shot in enumerate(scene["shots"]):
        for li, line in enumerate(shot.get("dialogue", [])):
            out = dialogue_path(args.scene, scene, si, li, line)
            if os.path.exists(out) and not args.force:
                continue
            v = {**cast.get(line["who"], {}).get("voice", {}), **line.get("voice", {})}
            synth(line.get("say", line["text"]), v, out)
            n += 1
            print(f"♪ {os.path.relpath(out)}  ← {line['who']}: {line['text']}")
    print(f"готово: {n} реплик")


if __name__ == "__main__":
    main()
