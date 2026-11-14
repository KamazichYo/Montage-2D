# Промты для генерации (Google: Nano Banana Pro / Gemini 3 Pro Image)

Где генерировать: **Gemini app** (режим изображений, «Thinking»/Pro-модель), **Google Flow** или **AI Studio** — везде, где есть Nano Banana Pro. Промты на английском: модель так точнее держит детали. Пояснения — на русском.

> **Актуальный набор для первого видео — [`05_prompt_pack.md`](05_prompt_pack.md).** Этот файл — запас: развёртки по частям, кисти, дополнительные ракурсы.
>
> **Для пилота нужно всего 11 картинок** — список в [`04_pilot_script.md`](04_pilot_script.md). Остальное в этом файле — на вырост.

## Порядок работы (важно для одинаковых лиц)

1. **Сначала — лист-референс (turnaround)** каждого героя. Выбираем лучший вариант. Это «паспорт» персонажа.
2. Все следующие генерации делаем, **прикрепляя этот лист как референс** и начиная промт со слов *«Using the attached character sheet as the exact reference for face, hair, body and clothing…»*.
3. Потом лист эмоций (головы), потом «развёртка» (части тела), потом руки.
4. Квартира: сначала мастер-план, потом остальные ракурсы с ним как референсом.

## Технические требования к картинкам для вырезки

- **Фон ровный, однотонный, светло-серый (#B0B0B0) или белый, без теней и градиентов.** Тогда вырезаю либо нейросетью, либо просто ключом по цвету.
- **Свет мягкий, ровный, студийный, спереди** — одинаковый на всех листах, иначе детали не склеятся.
- **Детали не касаются друг друга**, между ними воздух. Ничего не обрезано краем кадра.
- Максимальное разрешение (2K/4K). Вертикаль для полного роста, горизонталь для листов.
- Если модель склеила детали или нарисовала лишний палец — не беда, переделаю/подрежу; главное — лицо и одежда одинаковые.

---

## A. Гоша — лист-референс (turnaround)

```
Photorealistic character reference sheet of one young man for a cut-out photo
collage animation. Same person shown 4 times side by side, full body, standing in
a relaxed A-pose with arms slightly away from the body: front view, 3/4 view,
side profile, back view.

Character "Gosha", 25 years old, tall and very skinny with long arms, cheerful
goofy face, huge confident grin, thin teenage mustache, messy dark hair under a
black baseball cap worn backwards, big headphones around his neck, oversized
bright orange hoodie with white drawstrings, loose light-grey sweatpants, chunky
white sneakers. Slightly exaggerated proportions: head a bit large, like a
sitcom caricature, but still a real photo.

Flat even soft studio lighting, no harsh shadows, plain uniform light-grey seamless
background, every figure fully in frame with space between them, sharp focus,
high detail skin and fabric texture, 35mm photo look. No text, no labels.
```

## B. Лёва — лист-референс

```
Photorealistic character reference sheet of one young man for a cut-out photo
collage animation. Same person shown 4 times side by side, full body, standing in
a relaxed A-pose with arms slightly away from the body: front view, 3/4 view,
side profile, back view.

Character "Lyova", 27 years old, short and stocky, round soft face, curly
chestnut hair, round thin-rimmed glasses, tired skeptical eyes with dark circles,
slight frown, short stubble. Wears an olive-green knitted cardigan over a faded
black t-shirt with a worn retro computer logo, dark jeans, grey slippers worn
over socks. Slightly exaggerated proportions like a sitcom caricature, but still
a real photo.

Flat even soft studio lighting, no harsh shadows, plain uniform light-grey seamless
background, every figure fully in frame with space between them, sharp focus,
high detail skin and fabric texture, 35mm photo look. No text, no labels.
```

> Хочется, чтобы герои были похожи на реальных людей (вас/друзей)? Прикрепите их фото к промту и добавьте: *«Use the attached photo for the face likeness»*. Только с согласия этих людей.

---

## C. Лист эмоций — сменные головы (для каждого героя)

Это главный инструмент актёрской игры в перекладке: в нужный момент голова «подменяется».

```
Using the attached character sheet as the exact reference for the face, hair and
accessories, create an expression sheet: a 3x3 grid of separate head-and-neck
cut-outs of the same man, all strictly front-facing, same size, same head
position, same flat soft studio lighting, plain uniform light-grey background,
generous empty space between heads, nothing cropped.

Expressions:
1 neutral, mouth closed
2 smug half-smile, eyes half-closed
3 total shock, eyes wide, eyebrows up, mouth closed
4 panic, sweating, eyes darting
5 dead inside, empty stare, mouth closed
6 laughing hysterically, mouth wide open
7 angry, frown, teeth clenched
8 proud, chin up, big grin
9 crying with joy, tears

Photorealistic, high detail, no text, no labels, no grid lines.
```

Вариант для **3/4 ракурса** (для реверс-шотов, когда герои смотрят друг на друга): замените *«strictly front-facing»* на *«all heads turned in 3/4 view to the left»*.

### C2. Рот для речи

Почти все эмоции просим **с закрытым ртом** — речь делаю «челюстью-хлопушкой»: режу голову по линии рта (`engine/jaw.py`), нижняя часть опускается, когда персонаж говорит. Это классический приём фото-коллажа, смотрится смешно и очень «перекладочно».

Если хочется аккуратнее — сгенерируйте пару «рот закрыт / рот открыт»:

```
Using the attached character sheet as the exact reference, two identical
front-facing head cut-outs of the same man side by side, identical pose, lighting
and expression, the ONLY difference: left — mouth closed, right — mouth open
mid-word as if saying "ah". Plain uniform light-grey background, space between
them, flat soft studio lighting, photorealistic.
```

---

## D. «Развёртка» — кукла-перекладка по частям

```
Using the attached character sheet as the exact reference for face, body and
clothing, create a cut-out puppet parts sheet of the same man, photographed as
separate pieces laid out flat for a paper cut-out animation, each piece isolated
with large empty gaps, nothing overlapping, nothing cropped:

- head with neck, front view (mouth closed)
- head with neck, 3/4 view (mouth closed)
- torso in the hoodie WITHOUT head and WITHOUT arms (with clean shoulder and
  neck openings)
- left arm in hoodie sleeve, from shoulder to wrist, straight
- right arm in hoodie sleeve, from shoulder to wrist, straight
- left hand open palm, right hand open palm
- pelvis and both legs in sweatpants with sneakers, standing
- the same legs in sitting position (bent at the knees, side view)

Plain uniform light-grey background, flat soft even studio lighting, no shadows,
photorealistic, high detail, top-down product-photo style, no text, no labels.
```

> Если модель путается с отделёнными конечностями — ничего страшного. Достаточно хорошего фото в полный рост в А-позе (лист A) — руки и голову я отрежу сам по линиям плеч и шеи и прикрою стыки «шарнирами» (так и делают в классической перекладке).

## E. Руки-позы (сменные кисти — много шуток держится на руках)

```
Using the attached character sheet as the exact reference for skin tone and the
orange hoodie cuff, a sheet of 8 separate right hands with a short piece of
sleeve, each isolated with space around: pointing finger, thumbs up, facepalm
palm, holding a smartphone, holding an energy drink can, typing claw, middle of a
clap, OK sign. Plain uniform light-grey background, flat soft studio lighting,
photorealistic, no text.
```

(Для Лёвы: «olive-green cardigan cuff», вместо банки — кружка чая.)

## F. Позы целиком (быстрый путь)

Когда нужна сложная поза для одного кадра (упал на диван, обнял ноутбук, лежит лицом в клавиатуре) — проще сгенерировать целую фигуру и переложить её как одну вырезку:

```
Using the attached character sheet as the exact reference, the same man
[lying face down on the floor in despair, arms spread], full body, entirely in
frame, plain uniform light-grey background, flat soft studio lighting,
photorealistic, no text.
```

---

## G. Квартира — «Хата»

### G0. Мастер-план (генерировать первым)

```
Photorealistic interior photo, vertical 9:16, wide shot of a cramped rented
two-room flat in an old Soviet-era panel apartment building, converted by two
young programmers into a chaotic "startup office". Front-facing straight-on
view like a sitcom set, camera at chest height.

In the centre: a worn grey-blue fabric sofa with a crocheted blanket, a low
coffee table with pizza boxes and empty energy drink cans. Left side: a messy
desk with two monitors on pizza boxes, a gaming chair, a tall tower of empty
energy drink cans. Right side: a neat desk with one monitor, a yellow rubber
duck on top, a mug of tea, a plant. Back wall: faded 90s wallpaper, a
whiteboard with a scribbled cloud and arrows, an RGB LED strip glowing purple,
a window showing other panel buildings at night with lit windows. Old radiator,
a carpet hanging on the wall, laminate floor.

Warm evening practical lighting plus monitor glow, slightly lived-in and funny,
NO people, sharp focus throughout, high detail, 35mm photo look, no text.
```

### G1–G9. Остальные ракурсы (прикрепить мастер-план как референс)

Начало каждого промта:
```
Using the attached photo as the exact reference for this same room, same
furniture, same objects, same lighting and time of day, NO people, vertical
9:16, photorealistic:
```
и дальше одно из:

| # | Добавка к промту |
|---|---|
| G1 | `reverse angle: view from the window towards the entrance door and the hallway, the back of the sofa in the foreground` |
| G2 | `medium shot of the messy left desk: two monitors with code, gaming chair, tower of energy drink cans, tangled cables, sticky notes` |
| G3 | `medium shot of the neat right desk: one monitor, yellow rubber duck, mug of tea, small plant, a C++ book` |
| G4 | `medium close shot of the sofa from the front, coffee table with pizza boxes in the foreground` |
| G5 | `the small kitchen corner: old fridge covered with magnets and a sticker "НЕ ДЕПЛОИТЬ В ПЯТНИЦУ" crossed out, a kettle, a window` — это фон для конфессионалов |
| G6 | `the narrow hallway with the front door, a coat rack, a pile of sneakers and delivery bags` |
| G7 | `close-up of the laptop screen on the desk, the screen is plain dark grey and empty` — фон для чата с Клавой; сам текст рисует движок |
| G8 | `view out of the window: Soviet panel buildings, [night with lit windows / early morning sunrise]` |

### G-ext. Экстерьер (заставка серии)

```
Photorealistic vertical 9:16 photo of a typical 9-storey Soviet panel apartment
building at dusk, a few windows lit warmly, one window on the 4th floor glowing
purple from an RGB LED strip, snowy/autumn courtyard, playground, parked old
cars, cinematic, establishing shot of a sitcom, no text.
```

> **Хитрость:** для каждого фона генерируйте **версию без людей**. Людей всегда добавляю вырезками — так их можно двигать, менять эмоции и переставлять между планами.

---

## H. Реквизит (вырезается так же)

```
Photorealistic product photos, separated with space on plain uniform light-grey
background, flat soft studio lighting, no text: an open silver laptop seen
from the front, a black energy drink can with a neon-green band, a pizza box,
a yellow rubber duck, a smartphone in a cracked case, a mug of tea with a tea bag
string, a dead potted ficus, a delivery food bag.
```

---

## Чек-лист перед тем, как отдавать мне картинки

- [ ] Лицо и одежда совпадают с листом-референсом.
- [ ] Ровный однотонный фон, ничего не обрезано.
- [ ] Свет на всех листах одного героя одинаковый.
- [ ] Файлы названы по шаблону: `gosha_sheet.png`, `gosha_faces_front.png`, `gosha_parts.png`, `room_master.png`, `room_g2_desk_gosha.png` и т. д.
- [ ] Кладите в `incoming/` в репозитории или в папку на Google Drive — я подключён к Drive и заберу оттуда.
