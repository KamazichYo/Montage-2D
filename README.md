# Montage-2D — «Навайбкодили»

Мемный ситком в стиле фото-перекладки: вертикальные ролики на 45–75 секунд про двух соседей-вайбкодеров и ИИ-агента Клаву. Герои и квартира — сгенерированные фотографии, вырезанные и переложенные покадрово.

| Документ | Что внутри |
|---|---|
| [`docs/01_show_bible.md`](docs/01_show_bible.md) | Концепция, герои, визуальный язык, структура серии, рубрики, 12 сюжетов, выпуск |
| [`docs/02_prompts.md`](docs/02_prompts.md) | Промты для Nano Banana Pro: герои, эмоции, развёртки, квартира, реквизит |
| [`docs/03_tools_pipeline.md`](docs/03_tools_pipeline.md) | Пайплайн и все инструменты по этапам — что проверено, что нужно подключить |
| [`docs/04_pilot_script.md`](docs/04_pilot_script.md) | Сценарий пилота и список картинок, которые для него нужны |
| [`docs/05_prompt_pack.md`](docs/05_prompt_pack.md) | Готовые промты для первого видео: локации, герои, гости, реквизит |
| [`docs/06_pilot_outside.md`](docs/06_pilot_outside.md) | Новый пилот «Выйти из Матрицы»: сценарий, рамка сериала, список персонажей |
| [`.claude/skills/montage-episode/SKILL.md`](.claude/skills/montage-episode/SKILL.md) | Скилл: как собирать серию и формат сцены |

## Быстрый старт

```bash
pip install pillow numpy scipy rembg onnxruntime piper-tts    # + ffmpeg в системе

python3 engine/make_placeholders.py assets/demo               # болванки
python3 engine/voice.py scenes/ep01_pilot.json                # черновая озвучка (скачает голоса)
python3 engine/cutout.py scenes/ep01_pilot.json -o out/ep01.mp4
```

Вырезать сгенерированные картинки:

```bash
python3 engine/cut.py incoming/gosha/gosha_parts.png -o assets/chars/gosha --split
python3 engine/jaw.py assets/chars/gosha/gosha_head_neutral.png --mouth 0.74
```

Сцена пишется репликами — длительность планов, субтитры и движение челюсти берутся из аудио:

```jsonc
{ "set": "living", "cam": "cu_g",
  "dialogue": [ { "who": "g", "text": "ЗАЧЕМ?!", "face": "gosha_head_shock", "punch": 1.35 } ] }
```
