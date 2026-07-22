# Spec 70 — Settings & configuration · **STUB (planned)**

**Last reconciled: 2026-07-22** · Build progress: [STATE.md](../STATE.md) (M0-close gate) · Decisions: [spec/00](00_overview.md)

> **This file is a STUB.** The architecture in §2 is decided (2026-07-20); the settings
> **line-item inventory** (§3) and open questions (§4) are being developed in a separate
> effort. Flesh out §3–§4; keep §2 unless a new decision supersedes it.

## 1. What it is

The user-facing configuration surface for Gemma: a **tray icon** (always present) and an
on-demand **settings window**. This is the *"settings surface for tool setup"* named as the
M0-close gate in STATE — the missing piece being a **config source: file → panel**.

## 2. Architecture (decided 2026-07-20)

- **Tray icon** — `QSystemTrayIcon` (PySide6 / QtWidgets), cross-platform: Windows
  notification area · macOS menu bar (D10). Doubles as the always-visible **mic-live
  indicator** (spec/50 truthful-indicator role) for when the overlay is hidden. Menu:
  Open settings · Quit · (Mute).
- **Settings window** — **QML + Qt Quick Controls 2**, hosted in the overlay's UI process
  (D13 — the separate process), **spawned only when opened** (zero idle cost), no Chromium.
  QWebView was considered and rejected: it is Chromium-heavy, the exact weight the overlay
  deliberately avoids.
- **Config flow** — the settings window edits a **config file**; the **bridge reads** that
  file. No control channel back into the voice loop — the UI process stays a clean satellite.
  Reuses the routing config reserved in spec/20.
- **Adapter-aware** — never a flat global form. Knobs group by adapter, and only the active
  adapter's knobs apply (effort/thinking are Claude-only; a local B2 has temperature instead).

## 3. Settings inventory (OWED — the concurrent line-item work)

Seed list (from the STATE M0-close gate + this session) — expand, group, and specify
types / defaults / validation:

- **Brain (Contract B), adapter-aware:** B1 Claude → model · effort · thinking · persona;
  B2 local → model · temperature. *(Now: model via `GEMMA_BRAIN_MODEL`; thinking hardcoded
  off; effort unwired — see the 2026-07-12 adapter-shape note in STATE.)*
- **Speech:** STT model, per-mode (assistant vs dictation) · end-of-speech silence
  (`--silence-ms`) · wake phrase · TTS voice/speed.
- **Assistant:** `--clean-prompts` toggle (D15) · the deterministic word-replacement table
  editing (D15).
- **Triggers:** ask-hotkey and dictation-hotkey bindings (D14 / D16) — combo strings
  (`ctrl+alt+1` / `ctrl+alt+2` today; parsed by `bridge/hotkeys.py`, env
  `GEMMA_HOTKEY_ASK` / `GEMMA_HOTKEY_DICTATE` until this file's config source exists) ·
  **`auto_end`** (default off): end a keyed turn on VAD silence as well, so one tap is
  enough instead of two (`--auto-end`; spec/40 §Triggers).
- *(add more as they surface)*

## 4. Open questions (OWED)

- Config file **format + location** (a schema in `spec/schemas/`? a user config dir?).
- **Validation** + where defaults live.
- **Live-reload** (bridge watches the file) vs restart-to-apply.
- Whether the config **shape** needs a `spec/schemas/*.json` file (hard rule 3) — likely yes.
