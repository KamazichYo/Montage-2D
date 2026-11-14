# Montage-2D — мемный ситком в стиле фото-перекладки

Вертикальные рилсы на 60–90 секунд про двух корешей-вайбкодеров. Персонажи и квартира — сгенерированные фотографии, вырезанные и переложенные покадрово (cutout / photo-collage stop-motion).

- [`docs/01_show_bible.md`](docs/01_show_bible.md) — концепция, персонажи, квартира, структура серии, 12 сюжетов
- [`docs/02_prompts.md`](docs/02_prompts.md) — промты Nano Banana Pro: листы-референсы, эмоции, развёртки, фоны, реквизит
- [`docs/03_tools_pipeline.md`](docs/03_tools_pipeline.md) — пайплайн, скиллы, инструменты, как передавать материалы

## Быстрый старт

```bash
pip install pillow numpy scipy rembg onnxruntime   # + ffmpeg в системе
python3 engine/make_placeholders.py assets/demo    # болванки для теста
python3 engine/cutout.py scenes/demo.json -o out/demo.mp4
```

Вырезать сгенерированные картинки:

```bash
python3 engine/cut.py incoming/gosha/gosha_parts.png -o assets/chars/gosha --split
python3 engine/jaw.py assets/chars/gosha/gosha_head_neutral.png --mouth 0.74
```

## Формат сцены (коротко)

```jsonc
{
  "assets": { "bg_living": {"file": "bg.png", "bg": true}, "gosha_body": "gosha_body.png" },
  "rigs":   { "gosha": { "parts": [ {"part": "body", "root": true, ...}, {"part": "head", "at": [0.5, 0.02], ...} ] } },
  "shots": [
    { "dur": 2.4,
      "camera": { "keys": [{"t": 0, "zoom": 1.9, "center": [320, 1060]}, {"t": 1.0, "zoom": 2.6, "ease": "step"}],
                  "shake": [{"t": 1.0, "dur": 0.4, "amp": 22}] },
      "layers": [
        { "asset": "bg_living", "pos": [540, 960], "scale": 0.82, "boil": 0 },
        { "rig": "gosha", "pos": [320, 1600], "scale": 0.72,
          "face": [{"t": 1.0, "asset": "gosha_head_shock"}],   // смена эмоции
          "say":  [[1.1, 2.1]] }                                // челюсть хлопает
      ],
      "captions": [{ "t": [1.1, 2.4], "who": "ГОША", "text": "...какие тесты?" }] }
  ],
  "audio": [{ "file": "audio/line1.wav", "start": 1.1 }]
}
```
