# STATE — the jump table

Purpose: make track-hopping free. Thomas works by mood; that is fine **because** the
contracts isolate the tracks. The rules that keep it safe: pick a track by mood, but
within a track always take the next queued action · max one item in flight per track ·
when abandoning mid-task, park it here with a one-line note · read this file at session
start, update it in the same commit as the work · when a step closes, collapse its
entry to one or two lines — durable knowledge moves out (behaviour → spec · run
instructions → README · findings → NOTES.md · decisions → a D-number in spec/00).

Last updated: 2026-07-22

## Handoff — start here (2026-07-22)

Track P's island is built and live: real turns render end to end (wake word → STT → B1 →
Teleprompter → TTS). The renderer's defects from the first live run are fixed and guarded by
`python -m teleprompter.overlay_check`. **The agreed next action is the hotkey module.**

| # | Action | Track | Why now |
|---|--------|-------|---------|
| 1 | **Hotkey module — the two doors (D20)** | G ② | On the critical path. Hotkey is now the PRIMARY input (wake word demoted), so the acceptance run cannot test the real input path until this exists. |
| 2 | M0 acceptance run, desk-shaped (D16) | G ③ | ×10 ask-hotkey turns + ×3 wake-word. Blocked by 1. Also unblocks Track D. |
| 3 | M0-close gate — settings surface | G ④ | Thomas's gate, beyond docs/04 §8. |

Parked, not blocking, pick up by mood:

- **Prompt dwell** (owed fix 3 below) — the prompt still flashes for ~1 s. Pairs with the
  **7a/7b dead-air gaps**; same underlying problem, so do them together.
- **Expanded view** — design session first, and it **wants its own D-number** (it widens D14).
- **Latency readout styling** (owed fix 4) — deferred to a static-screens design pass.
- **Contract P gap (D20)** — dictate overwrite-warning + propose-then-tap messages, unbuilt.
- **Launcher option C2** — Job Object lifetime tie; **needs D24** (amends D13/D19's isolation
  rationale and D10's two-seam limit), and daemon-death must become visible in the tray.

Two open questions owed a decision:

- **Earcons** — gated by the speech switch, or always on? (see D23 note under Track P)
- **CI and the renderer** — `overlay_check` is NOT wired in. PySide6 is a core dependency
  (D23) but `checks.yml` still calls it an optional `[ui]` extra and claims QML "needs a
  display", which is **wrong**: it runs headless under `QT_QPA_PLATFORM=offscreen`. Decide
  whether CI carries it. Recommended yes — every bug this week was in the renderer.

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
  in order: ① ~~**Teleprompter (D13/D19) — its own Track P**~~ **DONE** — C1 (feed schema +
  broadcaster), C2 (the island) and C3 (tray, instrument) are all built and proven against
  live turns; remaining Teleprompter work is polish and is parked under Track P, not blocking
  · ② **hotkey module — the two doors (D20)** —
  shared `bridge/hotkeys/` (hybrid tap-toggle / hold-PTT; dictate + ask keys, bindings
  in spec/70 config); ask key opens LISTENING directly · ③ the owed acceptance run, now
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
  (your prompt, then Gemma's reply replaces it — never stacked). No state labels.
  **The ⌄ handle is CUT (2026-07-21, overrides D14):** built, seen in place, and rejected — the
  nub hanging under the pill spoiled the sleek line. Prior prompts move into the expanded view
  instead, so the island stays a pure display surface with no controls at all.
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
- **Built (C2, this commit) — the front-end renders live.** `teleprompter/`: `decode.py`
  (Qt-free NDJSON framing + reducer; `--selfcheck`, now CI-wired) · `model.py` (thin QObject
  over it) · `feed.py` (QTcpSocket + reconnect + a mic watchdog, so the bars follow live `mic`
  frames rather than inferred state) · `Overlay.qml` (island silhouette from the spike;
  mic-driven bars; prompt typewriter; morphing status word; 3-line cap with glide-scroll and a
  top fade) · `Theme.qml` + `qmldir` (**design tokens** — a `pragma Singleton`: colour,
  opacity-by-role, type, motion; island geometry stays local) · `__main__.py` (QApplication
  host, non-activating re-stamp on every show, bundled-font registration). **Inter is bundled**
  (`fonts/Inter-Variable.ttf`, ~0.83 MB) and registered at run time — no system install, and
  the Mac gets the same face (D10). PySide6 is a **core dependency** (D23 — the UI is the
  spine, no longer an `[ui]` extra); `teleprompter` joins
  `[tool.setuptools] packages` with package-data for the QML + font.
  **Verified against `--fake` with no audio/mic/models**: every state renders, the 3-line cap
  scrolls, and all 8 CI selfchecks pass.
- **Built (C3, `299fc46`):** tray (painted alive-icon · Quit · Groq key → `keyring`
  `("gemma","groq")` · latency toggle) · latency readout · reduced motion · multi-monitor fix.
  The ⌄ was built and then **cut** (D22). Focus question **answered**: a non-activating window
  *can* take clicks without taking focus, and `WS_EX_TRANSPARENT` makes the island fully
  click-through while still painting — `setMask()` must NOT be used, it clips painting too.
- **OWED — fixes from the first live run (2026-07-22).** First real turns ever rendered
  (wake word → STT → B1 → Teleprompter → TTS). It works end to end; these are the defects:
  1. ~~**The reply appears as a block, not typed.**~~ **FIXED.** Prompt *and* reply now reveal
     through one paced typewriter, so it no longer matters how a brain chunks its stream. One
     WORD per tick (`Theme.durationWord`), not one character: character pacing read as a chat
     stream being skimmed rather than a teleprompter to be read.
  2. ~~**The pill snaps into existence on wake.**~~ **FIXED.** `entrance` fades the window in
     and out, bound to the state rather than toggled by hand.
  3. **The prompt flashes for ~1 s and is gone** — ugly and janky. *Measured:* the brain takes
     ~1 s warm but **6 s cold**, so the dwell is wildly inconsistent. **Fix:** a minimum dwell
     before the reply may replace the prompt (keeps the locked design's "never stacked").
     Same family as the 7a/7b gaps below.
  4. **The latency readout is ugly.** Styling — folds into the static-screens pass, but now a
     confirmed complaint rather than a hypothetical.
- **First real latency figures (2026-07-22)** — partially discharges the owed D11 numbers:
  real-speech STT on GPU **273–603 ms** (vs 33 ms on the synthetic clip) · perceptible feedback
  **1404–1417 ms** every turn (always the `working` earcon — the brain never beats the 1.4 s
  timer) · first spoken word **2787 / 3328 / 3563 ms** warm, but **9142 ms on the first
  (cold-connection) turn**, the only breach of D11's 4 s and a cold-start artefact · warm-up
  22.1 s with the CUDA JIT cached.
- **Renderer hardening (2026-07-22).** The silhouette moved from `Canvas` to `Shape`
  (`CurveRenderer`): Canvas repainted *asynchronously*, so a freshly wrapped line rendered over
  the desktop until the black caught up. An adversarial pass over the result then found two
  more, both now fixed: the reveal gated on the island's **growth but not its scroll**, so past
  three lines words landed while the text was still sliding; and the latency readout reserved a
  guessed 96px gutter for a reading that measures **140px**, so the instrument would have sat
  on the reply during the acceptance run — it is now measured from the font.
- **The window no longer animates (2026-07-22).** Live symptom: after an animation the right
  edge finished rendering visibly later than the left. Cause: the *window itself* was resizing,
  and a native resize lands a frame apart from the scene graph, so newly exposed area painted
  late; separately the silhouette was drawn at its TARGET height while the window animated
  toward it, clipping its own bottom corners mid-growth. The window is now a **fixed
  transparent frame** and the island animates inside it. Depends on `WS_EX_TRANSPARENT` — the
  frame is mostly empty space and would otherwise swallow clicks across all of it.
  The silhouette is now a **Rectangle plus two flares** rather than one eight-segment path:
  the flares never change size, so nothing re-tessellates during an animation. Verified
  pixel-identical to the old path bar 0.22% of pixels, all on the two bottom radii, where
  Rectangle antialiases slightly smoother.
  New: `python -m teleprompter.overlay_check` — the renderer's offline check, on Qt's
  `offscreen` platform so it needs no display. Every assertion in it was verified to FAIL when
  its bug is reintroduced. **Not yet in CI:** PySide6 is an optional `[ui]` extra and CI does
  not install it; `checks.yml`'s note that "QML needs a display" is now wrong. Decide whether
  the pipeline should carry the UI extra.
- **Open question raised by D23:** are **earcons** gated by the speech switch, or always on?
  They are not TTS, and the `working` earcon is currently the only thing meeting D11's 1.5 s
  budget on the audio side — with speech off, the overlay's `thinking` state carries it alone
  (which it does, per D16's "perceptible"). Decide when the switch is built.
- **Owed (design, 2026-07-21) — the two dead-air gaps.** The island shows the morphing status
  word only until the transcript lands, then sits *motionless*. Two distinct problems:
  **(7a) before the transcript appears** — STT latency, plus whether LLM cleanup gates the
  display. Note the asymmetry Thomas drew: cleanup latency is invisible in *dictation* (you
  wait for the paste anyway) but visible in the *assistant* path, where it delays on-screen
  feedback. Contract P already allows having it both ways: `transcript.final:false` is
  reserved for partials, so the raw text can show instantly and be *replaced* by the cleaned
  version — a verbal slip ("…scratch that, 10:30") flashes then resolves, and the brain
  ignores it either way. This is also the real reason **Parakeet** matters to Track P: whether
  it streams partials, not its cleanup. Blocked on the Parakeet + `--clean-prompts` (D15)
  decisions. **(7b) while the brain composes**, after the transcript is settled — the longer
  wait, and independent of all of the above. Solvable any time; needs a cue that coexists with
  displayed text (the status word's slot is taken by then).
- **Settled (2026-07-21) — how the island handles the mouse.** The island is **display-only**
  and carries no controls, so its window is stamped `WS_EX_TRANSPARENT` (plus NOACTIVATE and
  TOPMOST): it paints in full yet is invisible to the mouse, and never intercepts a click meant
  for the app beneath — it sits over a maximised browser's tab strip. Measured: 81% of the
  island painted, and the pixel under it reports the window behind. **Do NOT use
  `QWindow.setMask()` for this.** Qt documents it as an input hint, but on Windows it is
  `SetWindowRgn`, which clips *painting* too — it clipped the island down to the ⌄ nub (70% →
  10% painted). Both proven on this box: a window can be click-through, and a window can take
  clicks *without* taking focus. Only *per-region* click-through in ONE window is unproven; it
  needs `WM_NCHITTEST` → `HTTRANSPARENT` via a native event filter — and the expanded view
  wants its own window anyway, so it may never be needed.
- **Owed (design, from 2026-07-21; overrides D14, wants a D-number):** an **expanded view** —
  now the single home for everything the island deliberately does not carry: **prior prompts**
  (moved here when the ⌄ was cut), the full text of a long reply, and copy / save / export.
  Past ~3–4 lines the island stops
  being glanceable, so a second surface shows the full turn with copy/save actions. Resolves
  spec/40's "longer answers: full text on the overlay" honestly, and gives the ⌄ handle a
  better job than history alone (so it widens D14's scope → wants its own D-number). Scope
  caution: copy is safe; save/export must reuse spec/50's transcript-logging mechanism rather
  than invent a second one; "send" is an integration and belongs behind Contract T (M1+), not
  a button the overlay owns. `maxLines` is already a single knob, config-bound at spec/70.
- **Resolved (2026-07-21, from the C1 review):** barge-in detection is the **same species as
  the wake-word watch** — "always-on mic", not a capture window. `status.json`'s `mic` wording
  narrowed to match (v0.2.1): a `mic` message means a capture window (LISTENING/FOLLOW-UP) is
  open; wake-watch and barge-in deliberately emit none. The locked design stands — no mic cue
  while Gemma speaks.
- **Settled by D23 (was owed):** the **"listen for me"** switch groups the always-on-mic
  behaviours — **off = hotkeys only** (mic opens solely on a keypress: no wake word, no
  barge-in), **on = both live**. Default off. Recorded in D23 alongside the speech switch;
  still needs *building*, which waits on a config source (spec/70, M0-close gate). spec/40
  stays accurate meanwhile because the built code is unconditional.
- **Owed (Contract P gap, from D20):** the two Teleprompter surfaces D20 introduces have no
  message type — the dictate-door **overwrite warning** (dictate invoked while text is
  selected) and the ask-door **propose-then-tap proposal** (a write-action pending a
  confirming keypress). Neither fits `response` (a streamed reply, not something pending),
  `error` (a fault), or the `state` enum. Add each when its producer lands — hotkey module
  (Track G ②) and dictate/rewrite (Track D) — deliberately **not** built speculatively at C2.

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
  the assistant path · **rewrite (D20):** an *ask-door
  outcome*, not a mode — propose-then-tap on the Teleprompter; `auto_apply` (spec/70,
  default off); slice D3.
- **Blocked by:** the M0 acceptance run (Track G) — decided 2026-07-18: validate
  the shared capture path live before building on it. (The D17 review gate cleared
  2026-07-21 → **D20**, the two-door model.)
- **In flight:** —
- **Next (when unblocked):** ① draft
  `spec/60_dictation.md` + add `transform` to spec/20 (Contract B), encoding D20's
  two-door scheme · ② D1 build slice: trigger → capture → whisper → transform →
  paste, cleanup included from day one (decided 2026-07-18; reuses Track G's
  `bridge/hotkeys/` module — D16) · ③ measure `large-v3-turbo` vs `small.en` vs
  **Parakeet** (sherpa-onnx = torch-free ONNX path; **gated** — adopt only if a real win,
  discuss first) on the 5080 (latency + error rate on dictated text) for the per-mode
  model default · ④ D2: overlay dictation states (recording + mic
  level · transcribing · transforming · pasted) on the D13 status feed · ⑤ D3: ask-door
  rewrite (D20, propose-then-tap).
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
  front/back split; `status.json` → v0.2.0 (+`error` message)**; **two-door
  interaction model recorded (D20)**; **Rust port evaluated & deferred with re-open
  triggers + anti-relitigation clause (D21)**; docs 01, 02, 04 frozen
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
