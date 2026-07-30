# STATE — the jump table

Purpose: make track-hopping free. Thomas works by mood; that is fine **because** the
contracts isolate the tracks. The rules that keep it safe: pick a track by mood, but
within a track always take the next queued action · max one item in flight per track ·
when abandoning mid-task, park it here with a one-line note · read this file at session
start, update it in the same commit as the work · when a step closes, collapse its
entry to one or two lines — durable knowledge moves out (behaviour → spec · run
instructions → README · findings → NOTES.md · decisions → a D-number in spec/00).

Last updated: 2026-07-28

## Handoff — start here (2026-07-28)

**M0 IS CLOSED.** Its criterion (ask-hotkey → the reply streams to the Teleprompter, perceptible
feedback < 1.5 s, ×10 consecutively, B1, zero tools) passed and was measured on 2026-07-22, 10/10.
The **"M0-close gate" is RETIRED** (Thomas, 2026-07-28): it was bolted on after the fact, was never
part of spec/00's M0 criterion, and "the settings window is up to par" is not a testable bar. The
quality it stood for is real and now has its own section — **Config & routing**, below.

**Build sequence (Thomas) — do in this order:**
1. **Config & routing** — the router v1 landed (D33); what remains is the settings window being
   below par, plus the router's Layer 2. Its own section below.
2. **Conversation / memory model** — the parked "chats vs dump-everything, want something in
   between" design. Unblocks the proactive context-overflow guard (B-02).
3. **M0.5 "It speaks well"** — sentence-streamed TTS forces the speak/hold decision (a
   model-tagged split replaces the ≤ 2-sentence heuristic) and carries the persona prompt, speech
   normalization, and the read-all-when-TTS-on direction. *(The earcon half of this item shipped
   separately as D28.)*
4. **Tools + dictation** — **Track T** Tier 2/3, and **Track D**'s deepening + the D3 rewrite.
   Tier 1 (D31) and dictation D1/D2 are done, so both tracks are live, not blocked.
5. **Mac parity (D10)** — last: the full-loop Mac test + macOS hotkeys (Carbon
   `RegisterEventHotKey`).

**Parked, not in the sequence:**
- **Local B2 brain (Ollama)** — deferred. M2 "it's local" and the *local* cleanup-engine option
  (S-06) both wait on it. B2's adapter already exists (D30) and speaks to any OpenAI-compatible
  endpoint, and the router (D33) can already point a role at one — so this is now "stand a local
  server up and pick it", not new adapter work.
- **Launcher / packaging** — tray autostart, launcher option **C2** (Job Object lifetime tie),
  daemon-death made visible in the tray, and the **true single-process merge** (one thing to
  launch, one crash to restart everything). Wants its own D-number; it amends D13/D19's isolation
  rationale and D10's two-seam limit. *A dev launcher `run.py` starts both procs from one command;
  two procs stay deliberate for dev — restart only the component you changed. The merge belongs
  with packaging, not the dev launcher.*
- **Rename `bridge/` → `daemon/`** (S-07). The package is named for the cancelled headset it
  bridged to the brains (D18); it is now just the daemon. Prose is already de-headseted; the
  rename itself is churn (imports · `pyproject` · `checks.yml` · README · spec/00's legend) and
  wants a naturally-churny moment. Frozen docs stay per hard rule 2. The letter **G** survives
  either way — it is "Gemma", not "bridge".

**Owed designs — pick up by mood:**
- **"Listen to me" / the always-open mic.** Reviving any always-open-mic mode must answer spec/50
  rule 4 truthfully. Thomas' view: a config-time warning that the mic is always on may do the same
  job as a live indicator. Pushback on record: consent to a *capability* is not the same as
  signalling *current* capture — a checkbox cannot reveal a window that failed to close. spec/50
  already separates the always-on wake ring (rule 3, ≤ 3 s RAM, discarded) from triggered capture
  (rule 4), so the argument may hold for the former and not the latter. If rule 4 should change,
  that wants a D-number and a written rationale, not a quiet edit.
- **Partial replies on a brain error.** A failed or blocked stream discards everything received and
  shows a generic apology. Keeping the partial with a fault marker needs a rendering decision (what
  a half-answer plus a fault looks like) — which is why it is parked rather than patched.
- **The conversation / memory model** (surfaced by B-02). History dies at IDLE, one chain. The
  poles are Claude's named persistent **chats** and Siri's **dump-everything-on-close**; Gemma
  wants something between, and it is undecided. It gates the *proper* overflow guard — a proactive
  token count against the model's context window before the call (Anthropic gives no distinct 400
  code for overflow, so an error heuristic cannot do it) — which only earns its keep once
  conversations persist. It also gates the overlay's cross-turn scroll-back (D27).
- **Read-all-when-TTS-on + the wake-phrase config ("listen for me")** — both land at M0.5. The
  `tts` toggle exists (default off); the read-all behaviour behind it does not. D23's "listen for
  me" switch (off = hotkeys only, no wake word and no barge-in; on = both live) is recorded but
  still unbuilt — the config source now exists, so this is buildable whenever it is wanted.
- **The two dead-air gaps (7a/7b).** The island shows the morphing status word until the transcript
  lands, then sits motionless. **(7a) before the transcript appears**: STT latency, plus whether
  LLM cleanup gates the display. Thomas' asymmetry: cleanup latency is invisible in *dictation*
  (you wait for the paste anyway) but visible in the *assistant* path. Contract P already allows
  both ways — `transcript.final:false` is reserved for partials, so raw text can show instantly and
  be replaced by the cleaned version; a verbal slip flashes then resolves, and the brain ignores it
  either way. This is the real reason **Parakeet** matters to Track P: whether it streams partials,
  not its cleanup. Blocked on the Parakeet + `--clean-prompts` (D15) decisions. **(7b) while the
  brain composes**: the longer wait, independent of the above, solvable any time; needs a cue that
  coexists with displayed text, since the status word's slot is taken by then.
- **The `Door` interface split** (review G-06) — the last item on the "duplicated state across
  seams" brief. The Door does two jobs: reporting raw key up/down events AND deciding tap-vs-hold →
  open/close. Job two duplicates the capture lifecycle the *orchestrator* already owns, so
  `close()` has to reach across the thread seam and clear shared flags — the G-06 race and the D24
  "stuck door" bug both lived there. The fix is to **split mechanism from policy**: the Door emits
  only raw key events (a `queue.Queue` of presses/releases — each consumed exactly once, no shared
  flag to clear), and the orchestrator's state machine turns those into open/close. Then
  `Door.open`/`close()` cease to exist and neither race can recur.
- **Latency readout styling** — a confirmed complaint, deferred to a static-screens design pass.
- **Amber limit-warning** (Track D; held on the Design session's sprites) — as a capture nears its
  cap (dictation's 300 s) the overlay should warn. Proposed: the daemon sends seconds-remaining on
  the `mic` message in the last ~30 s; listening bars go amber with a countdown. Choices pending —
  form (countdown / amber-only / word-cue) and threshold.

**Closed sagas, for the record.** Full accounts live in spec/00's D-numbers and in
`docs/01_scoping/Reviews/2026-07-22_2129_Review-adversarial-code-and-spec.md`: the **26-finding
adversarial review** (closed 2026-07-23; produced D24 · D25 · D26 · CLAUDE.md's Rule 0) · the
four-day **answer-display saga** (closed by **D24** — one root cause: the daemon deciding things
only the overlay can see) · the **three same-shape bugs** of 2026-07-22, each "a fact living on
both sides of a seam with one side not told" (closed; the surviving item is the `Door` split
above) · the **M0 acceptance run** (passed; its durable finding — first word ≈ 2100 ms + 45 ms per
output token under generate-then-play, making the old 4 s "gate" a ~42-token reply-length cap — is
recorded in spec/00 §D25 and `spec/schemas/targets.json`).

---

## Config & routing — the settings window + the router

Spans Track B (the router) and Track P (the window). Deliberately **not** a new component letter;
it is the unfinished half of D29/D30/D33.

- **Built — the settings window (D29):** a schema-driven QML window off `spec/schemas/settings.json`
  (defaults, `built` flags and the provider catalogue all live there, so a knob is a JSON edit).
  **Models** = the provider roster, an editor card per model (the model well/picker, the dials that
  provider actually offers, on/off, primary, a key-status footer, and a gear opening the Add/Edit
  sheet). **Config** = profile · preferences · triggers. Guarded by `settings_check` (CI-wired,
  fails on any QML warning).
- **Built — the router v1 (D33):** `bridge/brains/router.py` resolves a role to the configured
  provider+model from settings, read fresh each turn — `assistant` ← `primary`,
  `cleanup_dictation`/`cleanup_prompts` ← their keys, each via `models[<provider>]`. The
  orchestrator (`_assistant_brain`, `_cleanup_brain`) rebuilds the adapter only when
  `router.signature(role)` changes, so the client is kept (spec/20 adapter lifetime) yet a picker
  change lands next turn with no restart. An unconfigured role falls back to the daemon default
  (`DAEMON_MODEL` / Groq cleanup); an injected brain (replay) bypasses the router entirely. **The
  model picker now drives the daemon** — all of D30's adapter work is reachable by the assistant,
  not just by dictation cleanup.
- **Built — the config source:** `%APPDATA%\gemma\settings.json` via `bridge/settings.py`, written
  by the tray/window and re-read by the daemon each turn. Started at D28 with the `tts` and `Pings`
  toggles.
- **Owed — the window is below par** (Thomas, 2026-07-28). Named gaps: the AddCard dashed border
  (Qt), roster reorder, and the settings not surfaced at all yet — **STT model · wake phrase · TTS
  voice · word-replacement** (spec/70 §3).
- **Owed — router Layer 2** (explicitly out of v1): several instances per provider + the
  roles/routes redesign (spec/70) · per-task-type routing and its classifier (short → Groq, long →
  Haiku) · a `local_only` policy. B1's `effort`/`thinking` stay unwired until M0.5, so `effort`
  currently reaches only B2.
- **Built 2026-07-28 — the dictation Engine card is live.** Both its controls now do something:
  the **Engine dropdown** was already resolved by the router (D33), and the **"Tidy dictation"
  toggle** is now read by `_dictate` — off skips the transform entirely and pastes the raw
  transcript, reusing the delivery path that already existed for cleanup failure, and it skips
  the `transforming` state too, since showing "Tidying…" while nothing tidies would be a lie.
  `built: true` on both keys. Found during the reconciliation pass: flipping the flag alone would
  have shipped a toggle that appeared to control tidying and did nothing. Guarded in the
  orchestrator selfcheck (toggle-off pastes raw, and the state run is
  `["transcribing","pasted","idle"]`), verified to FAIL when the gate is reverted.

## Track G — Bridge (Doc 04 → **M0 ✅**, M1, M2)

- **Works now:** steps 0–7 built and `--selfcheck`-green. `bridge/`: `config.py` (loads
  `spec/schemas/*`, hard rule 3) + `log.py`; `audio/wake.py` (mic → ≤ 3 s RAM ring →
  openWakeWord); `audio/listen.py` (wake → Silero VAD → faster-whisper `small.en`, GPU when
  loadable else CPU); `audio/speak.py` (earcons + Kokoro TTS, 24 kHz; `OutputPump` = the
  persistent warm output stream, spec/40's BT keep-alive); `brains/` (Contract B — see Track B);
  `tools.py` (Contract T — see Track T); `orchestrator.py` (the spec/40 state machine —
  listen → think → speak, barge-in, the ≤ 2-sentence speak/hold heuristic (`sentences()`, retired
  at M0.5), the dictation branch, the Tier-1 tool loop, per-turn latency logs). The daemon keeps
  **one event loop for the process** (`_run_async`), not one per turn — recorded in spec/20 as an
  adapter-lifetime guarantee the orchestrator owes. `serve()` stays synchronous on purpose: mic,
  wake model, VAD, whisper and Kokoro are all blocking C calls, so an async `serve()` would starve
  the loop unless every one moved to an executor. Cross-platform per D10. Run instructions:
  `README.md` · GPU setup, benchmarks, quirks: `NOTES.md`.
- **Works now — the two doors (D20).** `bridge/hotkeys.py`: a combo-string parser (`ctrl+alt+1`
  ask · `ctrl+alt+2` dictate; env `GEMMA_HOTKEY_ASK`/`_DICTATE` until the settings window surfaces
  them — a modifier-less binding is rejected, it would be swallowed everywhere you type) → Win32
  `RegisterHotKey` + a `GetMessageW` pump on a daemon thread → per-door `start`/`end` events.
  Hybrid per key: tap-toggle, or hold ≥ 0.5 s for push-to-talk with the release as the endpoint.
  **Narrow registration, no keyboard hook** (spec/50 rule 11); the cost is a per-OS seam, and
  **macOS is unbuilt** (Carbon `RegisterEventHotKey`), where the wake word stays the only entrance.
  `capture_over()` implements the endpoint rule — **the key ends a keyed turn, not the 1 s silence
  cut**; nothing-said and the runaway cap still do. `--auto-end` (default off) puts the silence cut
  back for one-tap use. Proven live: `ctrl+alt+1` driven through `SendInput`, confirming the OS
  actually delivers.
- **Works now — the replay harness** (`tests/replay.py`): recorded WAVs through the real wake/VAD/
  STT pipeline driving the real orchestrator with fake mic/pump/brain/TTS, plus a per-turn latency
  table. Four keyed cases — `key_short` · `key_long_pause` · `key_hold` · `key_silence` — **4/4
  green on the PC, all four transcripts verbatim**. `key_long_pause` (a deliberate 2–3 s pause,
  12.75 s captured in one turn) is the only real-speech test of `capture_over`, which the wake
  word's 1 s silence cut would have truncated; `key_hold` exercises push-to-talk. A keyed case's WAV
  is recorded between two real presses (`_record_keyed`, which dogfoods `bridge/hotkeys.py`), so the
  clip *is* the capture window and its end *is* the endpoint. The three wake-word cases were removed
  when D23 made the wake word default-off (an opt-in config, and a false-accept test is meaningless
  when nothing is listening); barge-in returns as a **wake** case if that switch is ever built. Old
  definitions are in git and the WAVs are still on disk, so a revisit costs no re-recording.
  **Deviation from docs/04 §7:** replay does NOT run in CI — the WAVs are Thomas's voice and
  deliberately untracked (`tests/replay/wav/`, gitignored; copy the folder to the Mac clone by hand).
  Replay latency figures are harness figures (cold STT load, fake brain, fake TTS), never acceptance
  numbers.
- **Owed — replay coverage gap.** Removing the wake cases took `wake_barge` with them, so
  **barge-in has no replay case at all**, and the **key-interrupt** path (pressing the ask key
  mid-reply) has none either. Both want one; the key-interrupt case *can* be keyed, if the harness
  can script a second press mid-reply.
- **Owed — a press while the brain is streaming** is still queued rather than acted on:
  `_collect()` owns that window inside asyncio and the ask key is not polled there (Esc is, via
  D24's cancellation seam). Noted in code. *Re-check against D31's tool loop, which reshaped
  `_collect`.*
- **Owed — Mac parity (D10):** the full-loop live test and a 4/4 replay run, plus real-speech STT
  figures for the provisional D11 numbers. Watch items for that run: earcon ring-out bleeding into
  VAD on open speakers · BT A2DP↔HFP duplex behaviour (a BT earbud's mic use may degrade its
  output) · barge-in false-trigger rate on speakers (knob: `BARGE_CHUNKS` in `orchestrator.py`).
- **Post-M0 (D14/D15):** the word-replacement layer wired into the assistant path · the
  `--clean-prompts` experiment (after the Ollama groundwork; A/B ~20 real transcripts + a latency
  row). *(The overlay session view shipped as D27 for the current turn; cross-turn scroll-back waits
  on the conversation/memory model.)*
- **In flight:** —

## Track P — Teleprompter (Contract P) — built and live; in polish

- **DONE 2026-07-28 (D34) — model + token count in the peek footer.** The peek names the model that
  answered + the turn's total tokens (`claude-opus-4-8 • 1847 tokens`, mono, bottom-left — variant A).
  Contract P: `response` gains optional `model`+`tokens` (`status.json` → v0.5.0), stamped on the `done`
  message (model from the router-resolved brain's `.model`; tokens summed from each round's
  `Done(usage)`, input+output); `decode`/`OverlayModel`/`PeekPanel` carry and render it. Guarded in
  `broadcaster` + `decode` selfchecks; overlay/settings checks green. Owed: live on the box (peek a
  real answer and read the footer).
- **Works now:** the island renders real turns end to end (key → STT → brain → Teleprompter → TTS).
  `teleprompter/`: `decode.py` (Qt-free NDJSON framing + reducer, loading `clearsTurn`/`upstream`
  from `status.json` rather than restating them) · `model.py` · `feed.py` (QTcpSocket + reconnect +
  a mic watchdog + `send()`, the one upstream verb) · `Overlay.qml` · `PeekPanel.qml` · `Theme.qml`
  (design tokens, a `pragma Singleton`) · `SettingsWindow.qml` + `KeyRecorder.qml` · `tray.py` ·
  `gem.py` · `settings_model.py` · `__main__.py`. Back end: `bridge/broadcaster.py`, a
  crash-isolated localhost NDJSON publisher (`publish()` never blocks or raises; a busy port
  disables it; the daemon is an always-up server, the overlay a reconnecting client) with a
  `--fake` driver that drives the whole overlay with **no audio, mic or models**. It retains the
  current turn and replays it to a client that reconnects mid-turn (P-02). PySide6 is a **core**
  dependency (D23). Fonts are bundled and registered at run time — Inter · Archivo · Martian Mono,
  with Instrument Serif bundled but deployed nowhere — so there is no system install and the Mac
  gets the same faces (D10). Guarded by `teleprompter.overlay_check` (headless, software RHI),
  `decode --selfcheck`, `settings_check` and `teleprompter.gem`, all CI-wired.
- **The locked design** lives in spec/40 §Visual output: the island fused to the top screen edge,
  mic-driven bars, typewriter text, no controls (D22 — the ⌄ handle was built, seen in place, and
  **cut**). Windows gotchas are in NOTES.md. Three hard-won facts worth not relearning: a
  non-activating window *can* take clicks without taking focus · **`QWindow.setMask()` must NOT be
  used** for click-through — Qt documents it as an input hint, but on Windows it is `SetWindowRgn`,
  which clips *painting* too · and the **window itself never animates** (a native resize lands a
  frame apart from the scene graph, so newly exposed area paints late) — it is a fixed transparent
  frame and the island animates inside it, which is why `WS_EX_TRANSPARENT` is load-bearing.
- **Built (D24) — the island owns the display.** The prompt hands over to the reply only once it has
  finished revealing (`promptShown` + `Theme.durationPromptHold`), and the island hides *itself*
  `Theme.durationAnswerDwell` after the text finishes appearing, replacing a daemon-side timer that
  was estimating the overlay's own typing speed. `DismissKey`, a `QAbstractNativeEventFilter`, holds
  bare Esc via `RegisterHotKey` for exactly as long as the window is visible. **Verified live
  2026-07-22** — the prompt gate, Esc on a displayed answer, Esc mid-thought, and Esc handed back to
  other apps when the island is hidden.
- **Built (D27) — the expanded view / "peek".** Hover a shown answer → hint; click → the island
  grows *in place* into the current turn read in full (prompt pinned and collapsible past 2 lines ·
  reply scroll under a top/bottom fade · **Copy** + **Save**-to-file). Content-clamped height, then
  scroll; Esc collapses before dismissing; the dwell pauses while open. The island takes input over
  its silhouette when peekable, via per-region `WM_NCHITTEST` — **amends D22**. Action icons are
  hand-drawn SVGs; exact Material Symbols can drop in. **Unproven live:** the hover → click → peek
  path and the per-region hit-test have only run offscreen, with no real mouse (the `WM_NCHITTEST`
  mechanism itself is proven in the spike). "Send" stays a Contract-T integration (M1+), never an
  overlay button.
- **Built (D32) — Gem the mascot, first surfaces.** The commissioned ghost sprite kit
  (`teleprompter/gem/`, its own source of truth — never hand-edit) renders in three places through
  one renderer, `teleprompter/gem.py`: the **Windows taskbar / app icon** (`portrait.plain` on a
  rounded chip), the **tray** (status-driven off the live feed), and the **settings top bar**
  (replacing the on-air lamp — `arriving` on open → `idle` → `listening` while capturing). QML draws
  it through a `QQuickImageProvider` (`image://gem/<state>/<frame>`). Native purple/orange accents
  are kept; the **body flips light** on dark surfaces — a palette MAP over the kit's indices, never
  a repaint or a second export. Truthful by construction (spec/50 rule 4): every surface is driven
  by real Contract-P state. The overlay island is deliberately left alone for now. Parked kit extra:
  the costume portraits (DJ/engineer/…) for settings sections.
  - **Refined 2026-07-28 (`d468005`):** the tray follows the **taskbar** theme
    (`SystemUsesLightTheme`), not the app theme (`AppsUseLightTheme`) — the two differ on a common
    Windows 11 combo (light apps + dark taskbar), which rendered Gem's dark body invisible; and the
    tray now **animates idle** too (every multi-frame state animates; only a genuinely single-frame
    state rests). The settings top bar was simplified in the same commit: the orange brand Mark and
    the "Gemma" wordmark removed, Models/Config centred, Gem moved to the **top-LEFT** as the page's
    only mark and its mic indicator.
  - **Superseded 2026-07-29 by D35 (below).** The tray is no longer a Gem surface, and the kit is
    v3. Read D35 for what is true; the paragraph above is kept as the record of what D32 shipped.
    *(This also closes the "spec/00 D32 not updated with `d468005`" debt — D35 restates the tray.)*
- **Built (D35, 2026-07-29) — sprite kit v3 + the tray's mic ring.** Design shipped v2 then v2.2/v3
  in a day; neither is drop-in over v1. States hold named **clips** with
  policies (loop / oneshot / hold), and the kit carries its own **timing script**. `idle/rest` is a
  single frame, so `gem.py` now runs that script — `GemPlayer` (a Qt-free port of the kit's own
  player) plus `QmlGem`, which hands QML one bindable URL, so the settings window sets a state and
  stops counting frames. Both palettes are read **from the JSON** (a light + a dark hex per role,
  plus a `shade`); only body and eye are overridden — this amends D32's "the accents don't
  flip", which predates the kit having ground-specific accents (Thomas). Gem's surfaces are now two:
  the **taskbar / app icon** (`idle/rest`, cropped to the frame's own ink) and the **settings top
  bar at 52px** (2× the cell — the whole cell fits the 58px bar, so nothing is cropped; 3×/78px was
  tried and is too tall, and there is no integer step between). `idle` with its own fidgets →
  `listening` while capturing. The **tray drops Gem**
  for a **mic-level ring** — hollow ink while the mic is closed, a coral core with a halo that grows
  and brightens with the real RMS while open; no timer (mic frames are the clock), repaint gated on
  a 12-step quantisation. Thomas is commissioning a separate tray set. Gone with v1: `portrait.plain`,
  `arriving`, `question`, `alert`, and `gem.gem_state()` (the tray was its only consumer).
  Guarded: `teleprompter.gem` + a new `teleprompter.tray` selfcheck, both CI-wired.
  - **We ship Design's 26px build**, not their 32 — same art, tighter cell, Gem 54% of the width
    instead of 44%. Checked on arrival: 462 frames / 24 clips, every frame 26 × 26 legal chars,
    both atlases compared to the JSON pixel-for-pixel (a 26-cell JSON beside a 32-cell atlas throws
    nothing and renders garbage). Our earlier self-recrop and its `recrop_26.py` are superseded by
    Design's own export and removed.
  - **The idle script is two-tier now** — `filler` (blink, look-around) on a fast beat, a **gag**
    (`jump` `skip-rope` `guitar` `phone` `basketball` `disguise`) every `gagEvery` fillers. The trap:
    a v2 loader *runs* a v3 kit and just plays gags where fillers belong, so Gem performs constantly
    — no crash, no warning. `GemPlayer` was ported to the two-tier shape and the selfcheck asserts
    the tiers stay separate over ~74 simulated minutes. Eyes are 2px wide as of this kit.
  - **Owed — the sprite lab:** `needs-permission/granted` f5 (the falling lock) loses 5px off the
    bottom to the 26px crop. Design says flag it and leave it — it wants a human pass, not invented
    pixels.
  - **Gem mimes the turn (settings bar):** `listening` → `working` while the brain composes →
    `speaking` for as long as the ISLAND's typewriter is still laying the answer down → `done` →
    `idle`. Driven by `overlay.revealing`, a new UI-side field on `OverlayModel` that `Overlay.qml`
    publishes — the daemon's `speaking` state never fires with TTS off, and its stream finishes
    seconds before the reveal does. It needed its own notify signal — published through the model's
    blanket `changed` it invalidated its own inputs and QML spun a binding loop.
  - **Gem is on the island too, behind `gem_in_island`** (preferences, default on — Thomas).
    52px inside the pill on the left, `gemLeft` 4 / `gemGap` 6 over a cell that carries ~12px of
    its own margin; the waveform used to be centred in the whole pill and ran 30px under her, so it
    now starts after her column and the Gem theme narrows to 14 bars / 10px fade (from 20 / 22).
    Compact pill 230 → 238px. Off restores the pre-Gem island **exactly**, which `overlay_check`
    proves by re-deriving the original formulas rather than trusting the branch. Her x/y are
    rounded to whole pixels (an odd pill width would land a nearest-neighbour sprite on a half
    pixel), CI-guarded. The phase ladder moved out of QML into `QmlGem` now two windows drive one
    player, and gained `error` (which outranks a pending reply) plus dictation's
    `transcribing`/`transforming` → `working` and `pasted` → `done`. **No Gem on the peek** — a
    `search` clip for it is commissioned.
  - **Owed — live on the box:** the tray ring against a real mic, the taskbar icon, and Gem
    miming a real turn on both surfaces. Headless cannot show them.
  - **Open (Thomas):** whether Gem stays on the island at all — "more professional" without her.
    The switch already carries either answer; only its **default** would change.
- **Settled (2026-07-21) — mic cues.** Barge-in detection is the **same species as the wake-word
  watch** — "always-on mic", not a capture window. `status.json`'s `mic` message means a capture
  window is open; wake-watch and barge-in deliberately emit none. No mic cue while Gemma speaks.
- **Owed — the Contract P gap (from D20).** Two surfaces D20 introduces still have no message type:
  the dictate-door **overwrite warning** (dictate invoked while text is selected) and the ask-door
  **propose-then-tap proposal** (a write action pending a confirming keypress). Neither fits
  `response` (a streamed reply, not something pending), `error` (a fault), or the `state` enum. Add
  each when its producer lands — deliberately not built speculatively.
- **In flight:** —

## Track B — Brain (Contract B)

- **Works now — B1** (`brains/claude.py`): the Anthropic adapter — async streaming, tool
  translation, and error mapping **by exception type + status code, never message prose** (B-02;
  a 400 → generic apology, because Anthropic gives no distinct code for context overflow — both are
  `invalid_request_error`). Smoke test green on Windows (auth, streaming, tool-call, tool-loop).
- **Works now — B2** (`brains/compat.py`, D30): **one adapter for any OpenAI-compatible endpoint,
  cloud or local** — which is every provider the settings window offers except Anthropic, since the
  only differences are a base URL and a credential. spec/20's B2 row was widened rather than a
  fourth row added, so **M2 "it's local" is now a question of which endpoint it points at**.
  Reachability is schema truth (`settings.json` `wire`/`api`/`env`/`adapter`, read by
  `brains/providers.py`): no adapter hardcodes a host, key name or model id. Live model lists come
  from `GET {api}/models` off a worker thread, with a schema `not_chat` list dropping ids that
  cannot serve a turn (Groq returns 15, of which 7 are speech/TTS/safety; OpenAI 129, including
  embeddings and images). Fetching the list *is* the key test, so `probe()` returns `(ids, status)`
  over a closed set (`ok · nokey · auth · unreachable · empty · error`) — otherwise a wrong key and
  a dead network are the same empty picker — and it tests the **typed** key, not the stored one.
  **Verified live: Anthropic (11) · OpenAI (108) · Groq (8)**, plus a wrong key reading `auth` and
  an absent key `nokey`; the remaining providers share the exact code path, untested for want of
  keys. Keys are spend-capped and live in the OS credential store (spec/50 rule 10).
- **Works now — `transform`** (dictation cleanup, D12's "transform, never answer"): a **free
  function over any adapter's `converse`** (`brains/base.py`), not a per-adapter method. A transform
  is a constrained conversation (guardrail system prompt, no tools, no history, buffered), so it
  reuses every adapter's streaming, error taxonomy and lifetime, and works on Groq, Claude or local
  identically. Returns `(text, Error|None)`. Two per-call overrides ride on `Session`:
  `max_tokens`, so a long dictation isn't truncated at the 1024 spoken cap, and `temperature`, so
  cleanup runs deterministic.
- **Model-agnostic by rule** (2026-07-25): neither adapter carries a default model, and a modelless
  turn yields a clean `Error("unknown", "no model chosen…")`. The daemon's fallback lives in
  `orchestrator.DAEMON_MODEL` (env-overridable), not in an adapter. spec/20 records the rule. Model
  choice is now the router's job (D33 — see Config & routing).
- **Owed — the first-token re-measure.** The recorded **1817 ms** ran with `chunks=1` (the whole
  short reply in one chunk, so first ≈ total) — really "time to full short response", cold, and well
  above the ~300–900 ms ballpark in `b1_smoke.py`. Re-run with a longer streamed output; it feeds
  the provisional D11 numbers.
- **In flight:** —
- **Next:** ① install Ollama on the 5080, pull one small model, sanity-check tokens/sec — B2
  groundwork, with no commitment to a final model (that is the M2 bake-off, and the engine for the
  D15 `--clean-prompts` experiment) · ② **M0.5 "It speaks well"**: the voice output contract —
  a model-tagged spoken/held split (retiring spec/40's sentence-count heuristic), a versioned
  persona prompt (persona = template + a capability clause derived per turn from the filtered tool
  list, never a static claim, which would go stale at M1), speech normalization, and a B2-tolerant
  parse. Consumed by the orchestrator.

## Track D — Dictation (spec/00 D12 → MD)

- **Works now (D1, 2026-07-25) — the dictate door, end to end.** Dictate key → `_capture` (shared
  with the assistant, key endpoint) → `transcribe` → `transform` cleanup → **paste at the caret**
  (`bridge/paste.py`: clipboard + synthetic Ctrl+V via stdlib ctypes, daemon-issued because the
  overlay never holds focus; the prior clipboard text is restored). Dispatch is by **`door.name`**
  in `_pressed()`, which has two callers (`serve` and `_speak`), so a dictate press mid-reply cuts
  TTS and dictates rather than being fed to the brain. Cleanup is an **enhancement, not a gate**: on
  failure the RAW transcript is pasted, so dictation works with no key and nothing leaves the
  machine. Verified end to end on the recorded WAVs. Behaviour spec: `spec/60_dictation.md`.
- **Works now (D2, 2026-07-27) — the overlay states, both sides.** Contract P gained
  `transcribing` · `transforming` · `pasted` (`status.json` → v0.4.0) and the overlay renders them:
  a steady status word, then a latched **"Pasted ✓"** beat that dwells `Theme.durationPasteDwell`
  and hides itself. `bodyText` is forced empty during dictation so a stray transcript cannot leak
  into the prompt slot, and the transcript is broadcast `mirror=False` (trace only), so dictation
  text never shows on the island nor joins the assistant's prompt history.
- **Cleanup quality (2026-07-28, committed in `13d60f5`).** `DICTATION_CLEANUP` was rebuilt from a
  one-liner to VoiceInk's structured editing rules (self-corrections like "scratch that"; spoken
  punctuation and layout cues, open-ended with a false-positive guard), then **tightened to
  CLEANUP-NOT-REWRITING** (Thomas: it was adding words and could shift emphasis — "that's the idea"
  → "the main idea"). It is now a DO / DO NOT split: never insert words the speaker didn't say, no
  new qualifiers or intensifiers, don't change meaning, emphasis or strength, keep the speaker's
  structure — plus an **acronym-join** rule (spelled "S I L E" → SILE). Groq
  `llama-3.1-8b-instant`, temperature 0. Study: VoiceInk's cleanup — **ONE call, the whole
  transcript, no chunking**. Dictation's runaway cap is 300 s (`DICTATION_MAX_CHUNKS`), not the
  assistant's 30 s (fixed in `c091a65`).
  **⚠ Committed but UNTESTED against live speech** — restart the daemon, dictate, and confirm it
  stopped adding words.
- **Works now (D15 word-replacement, 2026-07-28).** The deterministic find-and-replace seam is
  filled: `spec/schemas/word_replacements.json` (whole-word, case-insensitive, literal `to`),
  applied by `bridge/replace.py`, hooked in `_dictate()` right after STT — so it runs BEFORE
  cleanup and applies even when cleanup is off (deterministic fixes are never skipped). Empty table
  = no-op; ships one entry (`gemma`→`Gemma`). Selfchecked + CI-wired (`python -m bridge.replace`).
  A curating UI is a later lift (spec/70 §3); the fuzzy `<CUSTOM_VOCABULARY>` prompt half of #2 is
  still parked.
- **Owed — the live keypress test.** The whole dictate path (D1 + D2) has been verified against
  recorded WAVs and selfchecks, but never once by Thomas pressing the key and speaking. Every
  hotkey path is like this; `RegisterHotKey` is proven live separately.
- **Parked deepening (VoiceInk-derived), in rough value order:**
  - **#2 custom vocabulary** — the deterministic word-replace seam (D15) is **done** (see the
    Works-now note above). What remains is the fuzzy `<CUSTOM_VOCABULARY>` block — a prompt-side
    spelling authority for names/acronyms Whisper mis-hears in ways the exact table can't predict.
    Still the highest-value prompt-side lift.
  - **#3 live context** — inject clipboard / selected text as context blocks (VoiceInk's Power
    Modes). Both are cheap on Windows; screen-OCR is the high-effort, low-reliability piece,
    deferred per the design-time "skip screen-OCR" call.
  - **Formatting settings** — a deterministic typography layer AFTER cleanup (double space after a
    full stop [Thomas's], em/en dashes, curly quotes — regexes, not prompt lines), plus a
    user-editable cleanup prompt.
  - **Chunking long dictation — RESOLVED: don't.** A single call is correct at our lengths (~1k
    tokens, Groq ~1–2 s) and higher quality (no boundary artefacts); VoiceInk agrees. Revisit ONLY
    if dictations reach thousands of words → split at PARAGRAPH boundaries, never mid-thought. Live
    per-sentence cleanup is parked with the same trigger.
- **Design settled 2026-07-18 (D12; study:
  `docs/01_scoping/Reviews/2026-07-18_1643_Review-gemma-voiceink-codebases.md`).**
  **Trigger-is-the-mode** — hotkey = dictation, wake word = assistant · cleanup via the Contract-B
  `transform` verb · cleanup engine = **Groq** (cloud, fast and cheap; revises D15's local-model
  note) · STT and TTS stay local · delivery = clipboard + synthetic Ctrl+V, deterministic and
  user-initiated, never a Contract-T tool · capture stays in RAM (spec/50 rule 3) · the STT model is
  per-mode config, dictation being the stricter quality test · the shared deterministic
  word-replacement layer (D15) runs before `transform` here and before the brain in the assistant
  path · **rewrite (D20)** is an *ask-door outcome*, not a mode — propose-then-tap on the
  Teleprompter, `auto_apply` default off, slice D3.
- **In flight:** —
- **Next:** ① **test the tightened cleanup prompt live** (committed, above) · ② the parked deepening
  (#2 vocabulary first) · ③ measure `large-v3-turbo` vs `small.en` vs **Parakeet** (sherpa-onnx =
  a torch-free ONNX path; **gated** — adopt only if a real win, discuss first) on the 5080 for the
  per-mode STT default; a parallel session is on Parakeet · ④ **D3**: the ask-door rewrite (D20,
  propose-then-tap). *(D15 word-replacement — done 2026-07-28, above.)*
- **Deferred at design time:** voice-switch into dictation ("take dictation") · per-app modes
  (foreground-window detection) · streaming partials · browser-URL and screen-OCR context blocks.

## Track T — Tools (Contract T → M1)

- **Works now (D31, 2026-07-27) — the Tier-1 executor, and the brain loops over it.**
  `bridge/tools.py` executes Contract T, and the assistant turn (`orchestrator._collect`) is a
  multi-round tool loop. Two read-only tools have backends: `system_status` (time · active window ·
  battery; volume and media playback need COM/WinRT, deferred) and `read_clipboard` (reusing
  `bridge/paste.py`). The brain is handed only implemented, in-tier tools (`tool_specs()`,
  `MAX_TIER=1`), so it cannot name a tool that isn't wired; `execute()` re-checks the allowlist as
  the defence (spec/50 rule 1). Every call — run, refused or errored — is one JSONL line in
  `logs/audit.jsonl` (spec/30 rule 2), purged with `logs/`. The loop: `converse` surfaces
  `ToolCall`s and never executes them, the orchestrator runs them, and each adapter's
  `record_tool_round` serialises the round into history in its own wire shape (Anthropic blocks /
  OpenAI `tool` messages), re-entered with an empty utterance until the brain answers; one retry on
  `malformed_tool_call`, a 5-round cap, history committed only on success.
- **Works now (2026-07-28) — `find_document`, the third Tier-1 tool** (ROADMAP #11, first slice).
  "Find the document about X [from this day]" → one query against the **Windows Search index**
  (`SystemIndex`), back as up to eight ranked hits, `name · date · path`. The model composes
  `query` (+ optional `kind`, `since`) from the utterance; the tool retrieves and opens nothing.
  Ranked rather than date-sorted — a date sort floats anything that merely *contains* the words
  (a word-list file matches everything) above the document actually about them; `since` covers
  "from this day". Verified live on the box against real documents.
  Implementation: the index's provider (`Search.CollatorDSO`) is OLE-DB, so ADO is the only route
  and the stdlib has no COM — reached via **PowerShell COM in a subprocess** rather than adding
  pywin32, which is *not* a project dependency (the handoff assumed it was; `pywin32-ctypes` is
  present but is a keyring shim with no COM). Not the raw shell spec/30 rule 1 forbids: the model
  gives words, never a command; terms are stripped to bare `\w` before they reach the query and
  each is quoted and AND-ed (which also demotes a stray `OR`/`NEAR` to a literal word); the SQL is
  handed to the subprocess in an env var, so nothing the model wrote is parsed as PowerShell. Off
  Windows, or with the Search service off, it answers "not available" instead of raising — so CI
  needs no live index. Selfcheck covers the sanitiser directly plus both dispatch paths.
- **Works now (2026-07-28) — `search_email`, the fourth Tier-1 tool** (ROADMAP #11, second slice;
  closes #11). "The email from Sarah about the lease" → one restriction against the **desktop
  Outlook inbox** over MAPI, back as up to eight headers, `sender · date · subject`. All five
  params (`sender`, `subject`, `query`, `since`, `before`) are optional and AND-ed; the store does
  the filtering (`Items.Restrict` with a DASL query, sorted newest-first before restricting, and
  the loop breaks at eight) so a mailbox is never enumerated. Bodies are *searched* — that is what
  `query` is for — but only headers are returned; free text goes word-by-word over subject OR body
  so "lease renewal" still finds "renewal of the lease". Local desktop store only: no Graph, no
  cloud, no credentials (spec/50).
  **Not verified live — Outlook is installed on this box but has NO mail profile**, so every call
  here degrades to "no mail profile". The DASL property names and date literals are therefore
  written-not-proven; first run against a real mailbox is the test. Before any COM call the backend
  checks the profile registry keys, because asking Outlook for a mailbox with no profile can raise
  a modal *create-a-profile* dialog — a hang with no way to answer it behind a voice assistant. A
  false "no profile" is the failure mode to watch if an older Outlook (pre-16.0) ever turns up.
- **The tool ledger (spec/30 rule 4).** Growth is tracked, not gated: nothing waits on a clock, but
  no tool is assumed good until it has misfired-free invocations in real use behind it. Evidence is
  `logs/audit.jsonl` (rule 2 already logs every call's outcome); this table is the human read of it,
  and a tool that keeps misfiring is a candidate for removal.

  | Tool | Tier | Built | Proven in real use |
  |------|------|-------|--------------------|
  | `system_status` | 1 | 2026-07-27 (D31) | **not yet** — no live tool turn on the box |
  | `read_clipboard` | 1 | 2026-07-27 (D31) | **not yet** — same |
  | `find_document` | 1 | 2026-07-28 | **not yet** — backend verified live against real documents, but never through a brain turn |
  | `search_email` | 1 | 2026-07-28 | **no** — cannot be: no Outlook mail profile on this box, so the retrieval path has never run at all |

  *Update the right-hand column when a tool has been invoked by the brain, in a real turn, several
  times without misfiring — that is the column the rule exists for.*
- **Not built:** Tier 2 (`open_app` · `focus_window` · `media_control` · `set_timer` — need backends
  plus the announce earcon) and Tier 3 (propose-then-tap confirmation, D26, on the Teleprompter). No
  raw shell below Tier 3 (spec/30 rule 1).
- **In flight:** —
- **Next:** live-verify a tool turn end to end (Claude asks `system_status`, then answers) — no tool
  has yet been driven by a brain, which is what the ledger's right-hand column is waiting on. Then
  `search_email` against a real mailbox the first time a mail profile exists. Tier 2 backends when
  a tool is genuinely wanted.

## Specs — spec & decision docs

- **Works now:** the spec/ scaffold; Contract H excised (D18, the custom headset cancelled); docs
  01, 02 and 04 frozen. Decisions D10–D33 are recorded in spec/00 — most recently **D27** (the
  expanded view / peek) · **D28** (earcon vocabulary cut to three WAVs; `tts` and `Pings` as
  separate toggles) · **D29** (the settings window) · **D30** (B2 = any OpenAI-compatible endpoint;
  reachability as schema truth) · **D31** (the Tier-1 tool executor and the brain's tool loop) ·
  **D32** (Gem the mascot, first surfaces) · **D33** (the per-role router v1). Schemas current:
  `status.json` v0.4.0 · `settings.json` v0.2.0 · `earcons.json` v0.4.0 · `targets.json` v1.0.0.
- **Reconciled 2026-07-28** (a sweep against what had actually shipped): **spec/00 D32** corrected
  on two points the tray had outgrown — the theme source is `SystemUsesLightTheme` (the taskbar),
  not the app setting, and idle no longer rests on a single frame; both carry an inline amendment
  note rather than a silent overwrite. **spec/00 D15** no longer says the cleanup plumbing waits on
  a config source — D28 and D33 built it. **spec/70 §1 + §3** no longer call the settings window
  "the M0-close gate" (retired; build status belongs in STATE anyway).
  **`spec/schemas/settings.json`** Engine card flipped to `built: true` — see Config & routing.
- **In flight:** —
- **Parked — rename `bridge/` → `daemon/`** (S-07): see the handoff's parked list.

## Parked / someday

B3 agent-CLI adapter · earcon sound design session · wake-phrase false-accept test protocol ·
**LiveKit Wakeword** trialled as an openWakeWord replacement (lower false-accept rate; a contained
swap behind `wake.py`) · **semantic endpointing** (M1) — complete-thought detection so long
composed prompts aren't cut off, the real fix beyond the silence timer (spec/40) · **long-task
interaction pattern** (dispatch-and-notify, heartbeat cadence during long silence, mid-task status
queries, "work on this in the background" phrasing) — design it when B3 or a heavyweight tool
lands · **usage/cost ledger** (2026-07-28) — record per-turn API usage and cost for **Ask and
Dictate** to a small store (JSONL/SQLite in `%APPDATA%\gemma`):
`{ts, role, provider, model, in/out tokens, cost}`. The data already exists (adapters normalise
`usage`); it is simply not persisted. RECORDING can start now — cheap, backend, router-independent —
so the parked **data page** inherits history instead of starting empty. Cost needs a `$/token`
table, whose home is the `settings.json` catalogue; splits by role, and dovetails with the router's
per-instance view.
