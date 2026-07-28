# Spec 70 — Settings & configuration

**Last reconciled: 2026-07-28** · Build progress: [STATE.md](../STATE.md) · Decisions: [spec/00](00_overview.md)

> The **window is built** (D29, 2026-07-27) and renders from `spec/schemas/settings.json` — the
> executable truth for panes, defaults and the provider catalogue (hard rule 3). §2's architecture
> holds. §3 still tracks what exists vs. what is owed: the page covers profile, preferences, the
> model roster and triggers; STT / wake phrase / TTS-voice and the word-replacement table are not
> surfaced yet.

## 1. What it is

The user-facing configuration surface for Gemma: a **tray icon** (always present) and an
on-demand **settings window**, over a **config source: file → panel**. *(This was once called the
"M0-close gate"; that gate was retired on 2026-07-28 — it was never part of spec/00's M0 criterion,
and build status belongs in STATE, not here.)*

## 2. Architecture (decided 2026-07-20)

- **Tray icon** — `QSystemTrayIcon` (PySide6 / QtWidgets), cross-platform: Windows
  notification area · macOS menu bar (D10). Doubles as the always-visible **mic-live
  indicator** (spec/50 truthful-indicator role) for when the overlay is hidden. Menu:
  Open settings · Quit · (Mute). Since **D32** the tray icon **is Gem** (the mascot, `teleprompter/gem.py`),
  animated by the live status feed; the settings top-bar carries Gem too, in place of the on-air
  lamp (`arriving` → `idle` → `listening`). The mic-live role is now Gem's `listening`/`idle`.
- **Settings window** — **QML** (Controls.Basic borrowed only for text entry, scrolling and popup
  dismissal; every visible control hand-drawn to match the island — D29), hosted in the UI process
  (D13 — the separate process), **spawned only when opened** (zero idle cost), no Chromium.
  QWebView was considered and rejected: it is Chromium-heavy, the exact weight the overlay
  deliberately avoids.
- **Config flow** — the settings window edits a **config file**; the **bridge reads** that
  file. No *configuration* travels back into the voice loop — the UI process stays a clean
  satellite. *(Amended by D24: this was written as "no control channel back" outright. The UI
  now sends exactly one upstream message, `dismiss`, which can only cancel work in flight and
  can never command — spec/50 rule 12. Settings still travel by file, not by socket.)*
  Reuses the routing config reserved in spec/20.
- **Adapter-aware** — never a flat global form. Knobs group by adapter, and only the active
  adapter's knobs apply (effort/thinking are Claude-only; a local B2 has temperature instead).
- **Bundled assets** — the window ships its own faces in `teleprompter/fonts/`, registered at
  startup (no system-font or icon-pack dependency): Archivo (UI), Martian Mono (machine values),
  Instrument Serif (reserved, gated), and **Material Symbols Outlined** for the icons — drawn as
  font glyphs, not hand-authored paths (D29), and subset to only the glyphs the window uses.

## 3. Settings inventory (OWED — the concurrent line-item work)

Seed list (from the settings-surface sessions) — expand, group, and specify
types / defaults / validation:

- **Output toggles (LANDED 2026-07-24, D28) — the config source's first step:** `tts` (spoken
  replies, default **off** — a capability, D23) and `pings` (the three earcons, default **on**),
  each a checkbox in the tray (spec/40 § Voice out). Persisted by **`bridge/settings.py`** to the
  JSON file named in §4 and read fresh by the daemon each turn. This is the M0-close "config
  source: file → panel", now partway: the file half exists, and the settings **page** now
  renders (D29, 2026-07-27) — profile, preferences, the model roster and triggers, from
  `settings.json`. STT / wake / TTS-voice and the word-replacement table below are not surfaced
  yet; types/validation for those still to spec.
- **Brain (Contract B), adapter-aware:** B1 Claude → model · effort · thinking · persona;
  B2 local → model · temperature. *(Now: model via `GEMMA_BRAIN_MODEL`; thinking hardcoded
  off; effort unwired — see the 2026-07-12 adapter-shape note in STATE.)*
- **Speech:** STT model, per-mode (assistant vs dictation) · end-of-speech silence
  (`--silence-ms`) · wake phrase · TTS voice/speed.
- **Assistant:** `--clean-prompts` toggle (D15) · the deterministic word-replacement table
  editing (D15).
- **Cleanup engine, per-role (S-06, 2026-07-23):** the LLM-cleanup engine is chosen
  **separately for each role** — assistant-path (`--clean-prompts`) and dictation — not one
  global setting. Each picks from the enabled provider/model set (local · Groq · …, keyed by its
  credential-store entry), **default local**. Dictation's current choice is Groq (D19). This is
  a slice of the parked multi-provider **routing** config (spec/20 reserved; STATE Parked): each
  role routes to one enabled provider. Now: hardcoded (dictation = Groq, assistant = local);
  the setting lands with the config source.
- **Triggers:** ask-hotkey and dictation-hotkey bindings (D14 / D16) — combo strings
  (`ctrl+alt+1` / `ctrl+alt+2` today; parsed by `bridge/hotkeys.py`, env
  `GEMMA_HOTKEY_ASK` / `GEMMA_HOTKEY_DICTATE` until this file's config source exists) ·
  **`auto_end`** (default off): end a keyed turn on VAD silence as well, so one tap is
  enough instead of two (`--auto-end`; spec/40 §Triggers).
- **Transport (Contract P):** the status-feed host/port live in `spec/schemas/status.json`
  `transport` (loaded by both the daemon and the overlay, P-01); the port has an env override
  `GEMMA_STATUS_PORT` (both sides honour it) until this config source exists.
- *(add more as they surface)*

## 4. Open questions (OWED)

- Config file **format + location** — **decided (D28):** JSON at `%APPDATA%\gemma\settings.json`
  (`~/.config/gemma/settings.json` off-Windows; `GEMMA_SETTINGS` overrides the path), via
  `bridge/settings.py`. The remaining open questions below still stand.
- **Validation** + where defaults live. *(D28: defaults live in one `DEFAULTS` dict in
  `bridge/settings.py` for now; no validation layer yet.)*
- **Live-reload** vs restart-to-apply — **for the two toggles, live (D28):** the bridge re-reads
  the file each turn, so a tray change applies on the next turn with no watcher and no restart.
- Whether the config **shape** needs a `spec/schemas/*.json` file (hard rule 3) — **yes; resolved
  (D29/D30):** `spec/schemas/settings.json` is that file — the executable truth for panes, groups,
  labels, defaults, `built` flags and the provider catalogue. `bridge/settings.py` derives its
  `DEFAULTS` from it; the window renders from it; neither restates a value.
