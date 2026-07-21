# STATE — the jump table

Purpose: make track-hopping free. Thomas works by mood; that is fine **because** the
contracts isolate the tracks. The rules that keep it safe: pick a track by mood, but
within a track always take the next queued action · max one item in flight per track ·
when abandoning mid-task, park it here with a one-line note · read this file at session
start, update it in the same commit as the work · when a step closes, collapse its
entry to one or two lines — durable knowledge moves out (behaviour → spec · run
instructions → README · findings → NOTES.md · decisions → a D-number in spec/00).

Last updated: 2026-07-21

## Track G — Bridge (Doc 04 → M0, M1, M2)

- **Works now:** steps 0–6 built and `--selfcheck`-green. `bridge/`: `config.py`
  (loads `spec/schemas/*`, hard rule 3) + `log.py`; `audio/wake.py` (mic → ≤3 s RAM
  ring → openWakeWord); `audio/listen.py` (wake → Silero VAD → faster-whisper
  `small.en`, GPU when loadable else CPU); `audio/speak.py` (earcons + Kokoro TTS,
  24 kHz; `OutputPump` = the persistent warm output stream, spec/40 BT keep-alive);
  `brains/` (Contract B): `base.py` + `claude.py` (B1 Anthropic adapter — async
  streaming, zero tools; no `thinking` = fast first token; model via
  `GEMMA_BRAIN_MODEL`, default `claude-opus-4-8`, drop to sonnet-5/haiku-4-5 for the
  voice loop); `orchestrator.py` (step 6: spec/40 state machine — wake→listen→think→
  speak, follow-up window, barge-in, working-earcon timer, ≤2-sentence speak/hold
  heuristic, per-turn latency logs). Cross-platform per D10 (step 2 verified live on
  both OSes). Run instructions: `README.md` · GPU setup, benchmarks, quirks: `NOTES.md`.
- **Owed:** live full-loop test (both OSes) = **the M0 acceptance run** (spec/00: ×10,
  feedback < 1.5 s, first word < 4 s — per-turn latency lines print) + real-speech STT
  figures for the provisional D11 numbers (spec/00). Watch items for that run: earcon
  ring-out bleeding into VAD on open speakers · BT A2DP↔HFP duplex behaviour (a BT
  earbud's mic use may degrade its output) · barge-in false-trigger rate on speakers (knob:
  `BARGE_CHUNKS` in `orchestrator.py`).
- **Works now (step 7):** replay harness (`tests/replay.py`) — recorded WAVs through
  the real wake/VAD/STT pipeline driving the real orchestrator with fake mic/pump/
  brain/TTS; 5 cases defined in `tests/replay/cases.json`; per-turn latency table
  (also printed when a live session ends). Selfcheck CI on GitHub Actions
  (windows-latest) — **deviation from docs/04 §7:** replay does NOT run in CI because
  the WAVs (Thomas's voice) are deliberately untracked (`tests/replay/wav/`,
  gitignored; copy the folder to the Mac clone by hand).
- **Owed:** ① record the 5 case WAVs (`python -m tests.replay --record <name>`,
  scripts in cases.json) and run 5/5 green on the PC, later on the Mac (D10 parity) ·
  ② the **M0 acceptance run** — ×10 consecutive live turns, latency table vs spec/00
  targets · ③ real-speech STT figures for the provisional D11 numbers.
- **Open question:** should conversation history persist across wakes? (Now: dies at
  IDLE, one wake-chain.) Parked — Thomas is ideating this in a separate Fable session.
- **In flight:** —
- **Next:** M0 build order (docs/04 §8) complete — remaining before M0 is called done,
  in order: ① **Teleprompter (D13/D19) — its own Track P** (front/back split): the
  Contract-P feed schema (`status.json`) and the orchestrator-side **broadcaster**
  (`bridge/broadcaster.py`) are built (Track P C1); remaining is the `teleprompter/` app
  (front-end, Track P C2/C3) · ② **hotkey module + ask-Gemma path (D14/D16)** —
  shared `bridge/hotkeys/` (hybrid tap-toggle / hold-PTT logic, later reused by Track
  D's D1); ask key opens LISTENING directly · ③ the owed acceptance run, now
  **desk-shaped (D16)**: ×10 ask-hotkey turns (overlay streaming + speech) + ×3
  wake-word variant, latency table vs spec/40 targets · ④ the M0-close gate below.
  The acceptance run also unblocks Track D (D12 sequencing, 2026-07-18).
- **Post-M0 (D14/D15):** overlay expandable session view (in-memory only) ·
  word-replacement layer wired into the assistant path · `--clean-prompts` experiment
  (after Track B's Ollama groundwork; A/B ~20 real transcripts + latency row).
- **M0-close gate (Thomas; beyond docs/04 §8):** settings surface for tool setup —
  per-adapter tunables, exposed to the user before M0 is called done. Claude knobs:
  model · effort · thinking. Must be **adapter-aware** (effort/thinking are
  Claude-only; a local B2 model has temperature instead), not a flat global form.
  Now: model via env `GEMMA_BRAIN_MODEL`; thinking hardcoded off; effort unwired.
  Missing piece is a config source (file → panel); reuses the routing config already
  reserved in spec/20. Adapter code shape (~8 lines to promote the knobs to params)
  noted in the 2026-07-12 discussion.

## Track P — Teleprompter (Contract P) — **back-end built (C1); front-end next**

- **Decided (2026-07-20):** the visual front-end is the **Teleprompter** (component **P**),
  a separate **PySide6 + QML** process on the **Contract P** status feed
  (`spec/schemas/status.json`, committed). Front/back split: back-end = `bridge/` (headless
  daemon — broadcasts the feed + reads config/keys); front-end = a new top-level
  `teleprompter/` package, a dumb subscriber. QML chosen over QWebView/Electron — the only
  lightweight non-Chromium cross-platform option, stays in Python, cleanest non-activation
  (research this session).
- **Design locked** (blueprint: `sandbox/teleprompter-mockup.html`, gitignored): a solid-black
  Dynamic-Island **fused to the top screen edge** — bottom corners rounded, top corners flare
  **outward** into the edge (concave, drawn as a filled path); **white on black**; a **bars**
  indicator driven by the real **mic** level (audio-reactive, not decorative); typewriter text
  (your prompt, then Gemma's reply replaces it — never stacked); **⌄ handle** expands prior
  prompts this session (in-memory, D14). No state labels.
- **Window proven on the Windows box** (`sandbox/qml_spike/`): frameless + translucent +
  always-on-top + **non-activating** renders correctly. Windows gotchas captured in NOTES
  (long-path venv · QML-plugin PATH fix · `WS_EX_NOACTIVATE` fallback · concave-corner path).
- **Built (C1, this commit):** the back-end. `bridge/broadcaster.py` — crash-isolated
  localhost NDJSON publisher on Contract P (`publish()` never blocks/raises; a busy port
  disables it; overlay = reconnecting client, daemon = always-up server) + a scripted
  `--fake` driver (drives the whole overlay with **no audio/mic/models**) + `--selfcheck`
  (validates the wire against `status.json`; CI-wired — the first Gemma test to exercise
  its full wire path in CI). Orchestrator seam: state/transcript/response-delta/mic-RMS/
  latency/error mirrored off `_ev`, broadcaster started in `run()`; unstarted (inert) under
  replay. Contract P gained an **`error`** message (`kind` + `message`). **D19** recorded
  (spec/00) — Teleprompter = P · Contract P · front/back split. Selfchecks green; socket
  wire + crash-isolation verified live.
- **In flight:** —
- **Next — the `teleprompter/` front-end:** **C2** — Python host (non-activating window
  ported from `sandbox/qml_spike/`) + QML island (all states, bars from the `mic` feed,
  transcript/reply typewriter) rendering the `--fake` feed with no audio/models · **C3** —
  `QSystemTrayIcon` tray (alive-icon + Quit + Groq key field → `keyring` `("gemma","groq")`)
  + ⌄ expand/history (in-memory, D14). PySide6 becomes an optional `[ui]` dep and
  `teleprompter` joins `[tool.setuptools] packages` at C2. Full settings surface still
  deferred (`spec/70`, M0-close gate).
- **Owed (decision, from the C1 review 2026-07-21):** barge-in mic vs spec/50's truthful
  indicator. During SPEAKING the mic is hot (barge-in) but the feed emits `mic` only during
  `_capture`, so `status.json`'s absolute "present ⇔ audio is being captured" overstates the
  code. Resolve either by **narrowing the schema wording** (treat barge-in monitoring like
  the already-accepted always-on wake-watch, keeping the locked design's no-mic-during-
  speaking) or by **emitting `mic` in `_speak`** (strictest reading — then C2 owes a "mic
  live" cue beyond the mockup). Not a functional bug; doc-vs-code precision.

## Track B — Brain (M0 needs B1; M2 needs B2)

- **Works now:** B1 smoke test (`scripts/b1_smoke.py`) green on Windows — auth, streaming,
  tool-call/tool-loop all PASS. Dedicated "gemma" key (spend-capped) lives in Windows
  Credential Manager under service `gemma`.
- **Owed:** first-token re-measure — the recorded **1817 ms** ran with `chunks=1`
  (whole short reply in one chunk, first≈total), so it's really "time to full short
  response," cold; well above the ~300–900 ms ballpark noted in `b1_smoke.py`.
  Re-run with a longer streamed output — feeds the provisional D11 numbers (spec/00).
- **In flight:** —
- **Next:** 1) install Ollama on the 5080, pull one small model, sanity-check tokens/sec
  (B2 groundwork — no commitment to final model; that's the M2 bake-off · also the
  engine for the D15 `--clean-prompts` experiment) ·
  2) **M0.5 "It speaks well" (spec/00):** voice output contract — model-tagged
  spoken/held split (retires spec/40's sentence-count heuristic), versioned persona
  prompt (retires the `claude.py` placeholder; decided 2026-07-13: persona = template
  + capability clause derived per turn from the filtered tool list — never a static
  capability claim, which goes stale at M1), speech normalization, B2-tolerant
  parse. Consumed by the orchestrator (Track G).

## Track D — Dictation (spec/00 D12 → MD)

- **Works now:** nothing. Design settled 2026-07-18 (D12; study:
  `docs/01_scoping/Reviews/2026-07-18_1643_Review-gemma-voiceink-codebases.md`):
  **trigger-is-the-mode** — wake word =
  assistant, global hotkey = dictation (hybrid: tap = toggle, hold ≥0.5 s =
  push-to-talk; **the key is the endpoint** — release/second-press stops capture, VAD
  only trims edges, never the assistant loop's 1 s silence cut) · cleanup via a new
  Contract-B verb **`transform(text, instructions)`** ("rewrite, never answer" — port
  VoiceInk's enhancement prompt). Cleanup engine chosen this session = **Groq** (cloud,
  fast/cheap; Groq API key → credential store; revises D15's local-model note); STT/TTS
  stay local ·
  delivery = clipboard + synthetic Ctrl+V, deterministic and user-initiated, never a
  Contract-T tool · capture stays in RAM (spec/50 rule 3) · STT model is per-mode
  config — dictation is the stricter quality test · shared deterministic
  word-replacement layer (D15) runs before `transform` here and before the brain in
  the assistant path · **rewrite mode in principle (D17):** selection + spoken
  instruction → `transform` → paste-over; slice D3.
- **Blocked by:** ① the M0 acceptance run (Track G) — decided 2026-07-18: validate
  the shared capture path live before building on it · ② the **D17
  interaction-consolidation review** — the trigger scheme (wake word + how many
  keys, mapped how) must be settled before spec/60 encodes it. No Track D code
  before both clear.
- **In flight:** —
- **Next (when unblocked):** ⓪ the D17 interaction-consolidation review (design
  session, no code — output is a D-number + the trigger scheme) · ① draft
  `spec/60_dictation.md` + add `transform` to spec/20 (Contract B), encoding the
  review's scheme · ② D1 build slice: trigger → capture → whisper → transform →
  paste, cleanup included from day one (decided 2026-07-18; reuses Track G's
  `bridge/hotkeys/` module — D16) · ③ measure `large-v3-turbo` vs `small.en` vs
  **Parakeet** (sherpa-onnx = torch-free ONNX path; **gated** — adopt only if a real win,
  discuss first) on the 5080 (latency + error rate on dictated text) for the per-mode
  model default · ④ D2: overlay dictation states (recording + mic
  level · transcribing · transforming · pasted) on the D13 status feed · ⑤ D3:
  rewrite mode (D17).
- **Deferred at design time:** voice-switch into dictation ("take dictation") ·
  per-app modes (foreground-window detection) · streaming partials ·
  browser-URL / screen-OCR context blocks.

## Track T — Tools (Contract T → M1)

- **Works now:** nothing. M0 runs zero tools; the six starter tools (spec/30) land at M1.
- **In flight:** —
- **Next:** when M0 closes — executor with per-OS backends (spec/30 rule 3), wire
  `schemas/tools.json` into the brain's filtered tool list, Tier 1–2 first.

## Specs — spec & decision docs

- **Works now:** spec/ scaffold v0.2 (D10 cross-platform recorded); **Contract H excised (D18) — custom headset cancelled**;
  **D11 feedback-first latency posture recorded** (spec/00, 2026-07-12: feedback < 1.5 s
  every turn; no-tool answers bounded; tool turns acknowledged, not bounded;
  generate-then-play stays); `NOTES.md` added for operational findings (routing rule
  in the preamble above); **Teleprompter formalised (D19): component P · Contract P ·
  front/back split; `status.json` → v0.2.0 (+`error` message)**; docs 01, 02, 04 frozen
- **In flight:** —
- **Next:** —

## Parked / someday

B3 agent-CLI adapter · earcon sound design session · **multi-provider brain registry +
per-role routing** — config exposes an *enabled* provider/model set (user picks which of
Groq / OpenAI / Anthropic / … to make available, each keyed by its credential-store
entry); every role — assistant brain · dictation cleanup · rewrite — routes to one enabled
provider, per-task sub-routing possible (short → Groq, long → Haiku); credentials stay
provider-scoped (one key each), routing lives in spec/20's reserved routing config +
spec/70 settings; first slice = the M0-close settings gate (2026-07-21) ·
wake-phrase false-accept test protocol · **LiveKit Wakeword** trial as
an openWakeWord replacement (lower false-accept rate; contained swap behind `wake.py`) ·
**semantic endpointing** (M1) — complete-thought detection so long composed prompts
aren't cut off, the real fix beyond the silence timer (spec/40) ·
**sentence-streamed TTS** — parked per D11 (feedback beats speed); `synth()` already
works per sentence, so streaming = play-each-piece-as-ready; reopen only if measured
daily use feels slow ·
**long-task interaction pattern** (dispatch-and-notify, heartbeat cadence during long
silence, mid-task status queries by wake, "work on this in the background" phrasing) —
design when B3 or a heavyweight tool lands (D11 discussion, 2026-07-12)
