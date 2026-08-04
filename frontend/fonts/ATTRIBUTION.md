# Bundled fonts — provenance and licences

The Teleprompter ships its typefaces rather than relying on what a machine happens to have
installed (`Theme.qml` names them by role). Redistributing them means carrying their licences,
which is what this folder does. Copyright lines below are the ones embedded in each file's
`name` table — read them out with any font inspector to check this file has not drifted.

| File | Project | Copyright | Licence |
|---|---|---|---|
| `Inter-Variable.ttf` | [Inter](https://github.com/rsms/inter) (Rasmus Andersson) | Copyright 2020 The Inter Project Authors | SIL OFL 1.1 — [`OFL.txt`](OFL.txt) |
| `InstrumentSerif-Regular.ttf`<br>`InstrumentSerif-Italic.ttf` | [Instrument Serif](https://github.com/Instrument/instrument-serif) (Instrument) | Copyright 2022 The Instrument Serif Project Authors | SIL OFL 1.1 — [`OFL.txt`](OFL.txt) |
| `MartianMono-Variable.ttf` | [Martian Mono](https://github.com/evilmartians/mono) (Evil Martians) | Copyright 2020 The Martian Mono Project Authors | SIL OFL 1.1 — [`OFL.txt`](OFL.txt) |
| `MaterialSymbolsOutlined.ttf` | [Material Symbols](https://github.com/google/material-design-icons) (Google) | Copyright 2026 Google LLC | Apache 2.0 — [`LICENSE-Apache-2.0.txt`](LICENSE-Apache-2.0.txt) |

Two obligations ride along, both already satisfied by keeping this folder intact:

- **OFL 1.1** — the licence and copyright notice must travel with the font, and the fonts may
  not be sold on their own. It also forbids shipping a *modified* font under the original name;
  these are unmodified, so nothing to do unless one is ever subset or patched.
- **Apache 2.0** — the licence must accompany the file and modifications must be marked.
  Material Symbols is used unmodified, for the single glyph the island's body face lacks
  (the `check` in the latched "Pasted ✓" beat).

`frontend/icons/*.svg` are **not** from any of these projects — `check.svg`,
`content_copy.svg` and `save.svg` are hand-drawn in the Material Symbols *idiom* and borrow its
glyph names, so the resemblance is deliberate but the paths are ours. `gemma-mark.svg` is the
project's own mark. No attribution is owed for any of them.
