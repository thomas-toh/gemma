# Gem — mascot sprite kit · handoff

Gem is the character that represents Gemma while she works: a 20 × 20 pixel
sprite derived from the Gemma mark itself (the 3/4 disc with the hard square
corner). One animation per assistant state, plus one still portrait.

Nothing here is hand-drawn frame by frame. Every frame is generated from a
function of `(state, frame)` in the design source, so the app and the design
sheet stay in sync — see **Regenerating** at the end.

---

## 1. What is in this folder

| file | purpose |
| --- | --- |
| `gem-sprites.json` | **Source of truth.** All states, all frames, palette-indexed. |
| `gem-atlas.png` | 480 × 280 colour atlas. 20 px cells, one row per state. |
| `gem-atlas-4x.png` | Same atlas at 4× (1920 × 1120), for docs, README, store art. |
| `gem-tray-template.png` | Monochrome template: white body, eyes punched out to transparent. |
| `gem_sprites.py` | Pillow loader + a commented pystray tray loop. |
| `gem_sprites.rs` | Rust port; embeds the JSON with `include_str!`. |

---

## 2. The states

Thirteen animations and one still. All loops are seamless: play on repeat, cut
to another state on any frame.

| state | frames | policy | true when |
| --- | --- | --- | --- |
| `idle` | 24 | loop | nothing asked of her |
| `listening` | 6 | loop | mic open, capturing |
| `thinking` | 24 | loop | planning, no tool running |
| `working` | 4 | loop | executing on the machine |
| `speaking` | 12 | loop | TTS playing |
| `done` | 8 | **one-shot** | task finished cleanly |
| `error` | 12 | loop | task could not complete |
| `permission` | 8 | loop | blocked until the user answers |
| `question` | 8 | loop | needs a detail, not blocked |
| `alert` | 8 | loop | destructive step, or an ask left waiting |
| `misheard` | 12 | loop | heard the user, could not parse it |
| `asleep` | 18 | loop | off duty / mic disabled |
| `arriving` | 16 | **one-shot** | wake or summon |
| `portrait.plain` | 1 | static | app icon, About box, empty states |

One-shots play once and fall back to `idle`. Everything else loops until the
app sets another state.

Default playback is **9 fps** (`fps` in the JSON, also per state). Do not run it
faster — the character is designed around a 110 ms beat.

---

## 3. Format

```jsonc
{
  "cell": 20,                    // every frame is 20 x 20 cells
  "fps": 9,
  "palette": { "1": {"role":"ink","hex":"#1B1714"}, ... },
  "atlas": { "file":"gem-atlas.png", "columns":24, "rows":14, "order":[...] },
  "states": {
    "idle": { "fps": 9, "frames": [ ["....11111...", ...20 strings], ... ] }
  }
}
```

Each frame is 20 strings of 20 characters. `.` is transparent; a digit is a
palette role:

| index | role | hex | used for |
| --- | --- | --- | --- |
| `1` | ink | `#1B1714` | the body |
| `2` | eye | `#FBF9F5` | eyes, mouth — knocked out of the body |
| `3` | accent | `#6C4BE8` | badges, the laptop, attention cues |
| `4` | warn | `#D97A28` | reserved second accent |
| `5` | dim | `#9A94A6` | dust, sleep marks, soft detail |

**Ship the indices, not the colours.** Recolouring is a map lookup, so dark
tray, light tray, high contrast and disabled states are all the same frames.

---

## 4. Deploying

### Tray / menubar icon

Use the template palette: body in one colour, eyes mapped to **transparent** so
they are holes in the silhouette. This is what macOS expects from a menubar
icon (it inverts the template itself) and it is what keeps Gem legible at 20 px.
`gem_sprites.py` ships `TRAY_DARK` / `TRAY_LIGHT` for this.

Render at an integer scale only — 20, 40, 60, 80 px. Never a fractional scale;
nearest-neighbour at 1.5× destroys the cells.

Drive it from a single timer:

```python
gem = GemSprites("gem-sprites.json")
icon.icon = gem.frame(current_state, tick, palette=TRAY_DARK)   # tick += 1 every 1/9 s
```

### In-window / larger surfaces

Use the colour palette and any integer scale (`scale=4` → 80 px, `scale=8` →
160 px). Nearest-neighbour resampling, never smooth.

### Static uses

`portrait.plain` is the single frame for the app icon, About box and empty
states. It never animates.

### Rules that keep it coherent

- One state at a time. Badges and props never stack.
- Accent (`3`) appears only in `permission`, `question`, `alert` and the
  `working` laptop. Everything else is ink and eye.
- `done` and `arriving` resolve to `idle`; do not leave them held.
- Anything that lasts under ~400 ms does not deserve its own state.

---

## 5. Wiring it up

### Python

```python
from gem_sprites import GemSprites, COLOR, TRAY_DARK

gem = GemSprites("assets/gem/gem-sprites.json")
img = gem.frame("working", tick, scale=2)      # PIL.Image, RGBA
for frame, delay in gem.loop("speaking"):      # (image, seconds), forever
    ...
gem.gif("arriving", "docs/arriving.gif", scale=4)
```

Requires Pillow. `pystray` only for the tray example at the bottom of the file.

### Rust (for the port)

Drop `gem_sprites.rs` and `gem-sprites.json` in the same module directory; the
JSON is embedded at compile time.

```rust
let gem = GemSprites::load();
let pal = palette_tray([255, 255, 255, 255]);
let rgba = gem.frame("working", tick, 1, &pal);   // Vec<u8>, 20*scale square
```

Feed the buffer to `tray-icon`, `image::RgbaImage`, `softbuffer`, or a texture
upload. No image decoder needed anywhere in the path.

The port changes the loader only. The artwork, the state names, the loop
lengths and the palette are identical across both languages.

---

## 6. Suggested layout in the repo

```
assets/gem/
  gem-sprites.json
  gem-atlas.png
  gem-atlas-4x.png
  gem-tray-template.png
gemma/ui/
  gem_sprites.py          # or src/gem_sprites.rs
```

Placement of individual states in the UI is the app's call — this kit only
guarantees that every state exists, loops cleanly and reads at 20 px.

---

## 7. Regenerating

The sprites are drawn by `buildG(state, frame, palette, 'braced', mouth)` and
`buildPortrait(kind, palette)` in `Gemma Mascot Directions.dc.html`. Change the
art there, re-export, and both the design sheet and the app move together.
Never hand-edit `gem-sprites.json` or repaint the PNGs — the next export would
overwrite it.

Not yet drawn, parked deliberately: the costume portraits (DJ, engineer,
detective, painter, scholar) for settings sections.
