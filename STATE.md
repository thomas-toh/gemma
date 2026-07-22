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
`python -m teleprompter.overlay_check`. **The hotkey module is now built too** (`ctrl+alt+1`
opens the ask door), so the acceptance run is unblocked.

**In progress (2026-07-22): the adversarial review**
(`docs/01_scoping/Reviews/2026-07-22_2129_Review-adversarial-code-and-spec.md`) — 26 numbered
findings across `bridge/`, `teleprompter/` and `spec/`, being worked item by item. **D24 landed
first** (below) and discharged **G-01 · G-02 · G-04 · S-01** and Track P's owed fix 3 — by
deleting the code they lived in rather than patching it. G-08 was adjudicated *keep as-is*
(Thomas): the 5 s no-speech give-up stays on keyed turns. Selfchecks green across hotkeys ·
broadcaster · orchestrator · decode · overlay_check; **replay 4/4 on the PC**, transcripts
verbatim; **D24 verified live** (2026-07-22) — prompt gate, Esc on a displayed answer, Esc
mid-thought, and Esc handed back to other apps when the island is hidden.
**B-01 done (2026-07-22), API-agnostically** (Thomas's constraint: Gemma will run several
providers, so the fix had to be one). The daemon now keeps **one event loop for the process**
(`Orchestrator._run_async`) instead of an `asyncio.run()` per turn — a per-turn loop made
connection reuse impossible for *every* provider, since an HTTP pool belongs to the loop that
made it. That, plus deterministic `aclose()` on abort, is written into **spec/20 as an adapter
lifetime guarantee the orchestrator owes**, not as B1 behaviour. `base.py::ssl_context()`
memoises the machine's CA bundle for any HTTP adapter (Anthropic · Groq · OpenAI all sit on
httpx, which rebuilds it per client): **measured 187 ms per turn of main-thread CPU, recovered**
— guarded by a timing assertion, verified to fail at 187 ms when reverted. `serve()` stays
synchronous on purpose: mic, wake model, VAD, whisper and Kokoro are all blocking C calls, so
an async `serve()` would starve the loop unless every one moved to an executor.
**D25 done (2026-07-22): latency gates audited + made a single source.** Thomas's call — the
D11 numbers were headset-era (2026-07-12) and never re-derived after D18/D23. `first_word`
(4 s/5 s) demoted from pass/fail **gate** to **measured** diagnostic (under generate-then-play
it is a reply-length proxy, ~45 ms/token; and the streaming text, not the first word, is the
first feedback since D23). The `feedback` instrument now credits the overlay's flip to THINKING
(D16) instead of only audio, so the replay table's `eos->feedback` column dropped from ~1400 ms
(our own working-timer) to **0–1 ms** (the screen). All numbers consolidated into
`spec/schemas/targets.json` (they had drifted across four files); the overlay readout + latency
table load it, and the `kind` reclassification is data both obey — guarded in decode, overlay
and orchestrator selfchecks, each verified to fail when first_word is flipped back to a gate.
**G-07 folded in** (stale derived-constant comments in `listen.py`, deleted).
**Remaining review items:** G-03 · G-05 · G-06 · P-01–P-04 · U-01 · U-02 · B-02 · S-02–S-09 · X-01.
**Next (Thomas's sequencing):** sentence-streamed TTS — start speaking the moment Claude starts
writing, cut at sentence terminators (`synth()` is already per-sentence). Forces the speak/hold
decision (M0.5's model-tagged split, or drop the heuristic) because the length is no longer
known before speech starts.

| # | Action | Track | Why now |
|---|--------|-------|---------|
| 1 | **Finish the review's findings** | G · P | 26 items, in severity order; the S-items are spec reconciliation and group into three commits. B-01 (a fresh API client + event loop per turn) is the one remaining *class* fix. |
| 2 | Live-verify Esc + the upstream verb | P | D24 moved dismissal into the overlay. The whole path — native event filter → socket → brain-call cancellation — is proven offline and in selfchecks, never once on a real keypress. |
| 3 | M0-close gate — settings surface | G ④ | Thomas's gate, beyond docs/04 §8. The last thing between here and M0 closed — the acceptance test itself has PASSED. |
| 4 | 7a/7b dead-air gaps | P | The *three timing bugs* are closed by D24; what remains of 7a/7b is the genuinely separate question of what to show while STT and the brain are working. |

**M0's acceptance test has PASSED** (2026-07-22, details under Track G). M0 is not *closed* —
Thomas's settings-surface gate stands — but the loop is proven. **Track D is unblocked**
(D12 sequencing, 2026-07-18: validate the shared capture path live before building on it).

**CLOSED 2026-07-22 by D24 — the whole answer-display saga.** Four days of bugs (held-answer
wipe → dwell too short → dwell measured from the wrong clock → prompt truncated mid-reveal)
were one root: **the daemon deciding things only the overlay can see.** D24 moves the display
decisions to the overlay, `idle` is demoted to "the daemon is free", the turn-clear rides on
`listening`, and Contract P gains one upstream verb (`dismiss`). Detail: spec/00 D24 · spec/40
§State machine · spec/50 rule 12. Deleted with it: `answer_dwell()` and its two constants,
`self.shown`, `blank_at`, and the whole transient-door arming protocol in `bridge/hotkeys.py`.
Residue of the earlier fixes still standing: the follow-up window stays **removed**, and
**"read it" readback is retired** — whether anything speaks a long answer on request folds into
the TTS switch (spec/70, with "listen to me"); the hold survives and means SHOWN, not spoken.
**Still owed from the dismissal design: an on-island close affordance** — Esc now exists
(overlay-owned, D24), but a *click* target needs `WM_NCHITTEST` → `HTTRANSPARENT` per-region
hit-testing, still unproven here and shared with the expanded view. Build once, serve both.
"Click *outside*" remains ruled out: the window never takes focus, so it would need a
system-wide low-level mouse hook — heavy, and against spec/50's posture.

**Fixed 2026-07-22 (live, during acceptance-run setup) — bars drawn over a stale answer.**
Symptom (Thomas): press the ask key while a reply is showing and the wave appears *alongside*
the old text instead of dismissing it. **Not the hotkey.** Reproduced against a recorded turn:
the trigger is **barge-in** — pressing then speaking over the reply trips it, and barge-in
opens its capture from inside `_speak()`, publishing `listening` with no `idle` first. The
turn-clear lived in `serve()`, so only the two entrances *there* got it; the two that open
from `_speak()` skipped it. Root cause was structural, so the fix is a **refactor: the clear
moved into `_capture()`** — the one place capture windows actually open — and is now a binding
invariant in spec/40 (`state` sequence `speaking → idle → listening`). Guarded by an
orchestrator selfcheck, verified to FAIL when the line is removed.
**Second half, same report:** a press *during* a reply used to sit queued until the turn
finished playing, so it looked like nothing happened. `_speak()` now polls the ask key and
treats it as a deliberate barge-in — cut TTS, clear, open the mic. **Still queued:** a press
while the *brain is streaming*, because `_collect()` owns that window inside asyncio; needs
cancellation there, noted in code.
**Coverage gap this exposed:** removing the wake cases (above) took `wake_barge` with them —
so barge-in, where this bug lived, now has **no replay case at all**, and the new
key-interrupt path has none either. Both want a case; the key-interrupt one *can* be a keyed
case (unlike barge-in) if the harness can script a second press mid-reply.

**BUILT 2026-07-22 — the dismiss key and the abort seam (D24).** Decided as three items and
delivered as one decision, because the first two could not be built where they were.
① **Esc dismisses the Teleprompter**, registered only while the island shows — but *not* by the
daemon. Doing it daemon-side needed `PostThreadMessage` marshalling against a blocking
`GetMessageW`, raced across two threads on an `_armed` set, and could only arm against the
daemon's *guess* at what was displayed; that guess held Esc hostage from every other app for
the entire answer dwell while nothing polled for it. **The overlay owns Esc instead** — it is
the window, so "is it showing" is a fact. `bridge/hotkeys.py` loses the transient-door protocol
entirely and `parse_binding` loses its modifier-less exemption.
② **Dismiss = full abort of the turn**, not just a blank: LISTENING drops the capture, SPEAKING
cuts TTS, **THINKING cancels the in-flight brain call**. The asyncio cancellation seam in
`_drive()`/`_collect()` is load-bearing and built; only the *source* of the signal moved, so
the single `Dismissed` handler still unwinds every state. Guarded end to end: a `dismiss` line
off the wire must cancel a hanging brain call, verified to FAIL when the wiring is cut.
③ **The dwell** was estimating **reveal** time (90 ms/word) plus reading time from the wrong
clock. It is now the overlay's, measured from the moment the text finishes appearing —
`Theme.durationAnswerDwell`, a flat 20 s, because from the right clock a constant is enough.
**Still queued:** a press while the *brain is streaming* — `_collect()` owns that window inside
asyncio, and the ask key (unlike Esc) is not yet polled there.

**Fixed 2026-07-22 — the stuck ask door (found by Thomas within minutes of Esc landing).**
Press `ctrl+alt+1`, then Esc: the next `ctrl+alt+1` logged `ask: closed (tap)` and opened
nothing, so it took two presses to get going again. Cause: `Door.open` is the module's
tap-toggle flag, Esc aborted the turn in the *orchestrator*, and the module never heard — so
the next press was read as the closing tap. **Wider than the symptom:** it bit every capture
ending without a second press — the no-speech give-up, the 30 s cap, and **`--auto-end`, which
was therefore comprehensively broken** (VAD ends the capture, `open` stays set, every other
press swallowed). Fix: `Door.close()`, called from `_capture()`'s `finally` so no exit path
can skip it, plus `Hotkeys.reset()` on the dismiss unwind. Guarded; verified to FAIL when
reverted.

**THE PATTERN — three bugs, one root, all on 2026-07-22.** ① barge-in opened a capture without
clearing the turn · ② key-interrupt opened a turn without the entrance ritual (no `wake` trace,
no `awake` earcon — it silently cost 60% of the acceptance run's press-latency readings) ·
③ a capture could end without the door that opened it being told. Every one is **the same
shape: a fact that lives in two places either side of a seam, and one side not being told.**
Each fix moved the fact to the single place that owns it — the clear into `_capture()`, the
entrance into `_enter()`, the toggle into `Door.close()`. **This is the brief for the refactor
session:** hunt remaining duplicated state across the daemon/module/overlay seams rather than
individual misbehaviours.
**Candidates discharged by D24 (2026-07-22):** `self.shown` and `blank_at` are *deleted* — the
daemon no longer guesses what the island shows or times a reveal it cannot see; the clear moved
off a caller and onto the `listening` state itself; and the `_armed` set that the arming
protocol raced across two threads went with the protocol.
**Still open on this brief:** `Door.open` vs orchestrator capture state (fixed once via
`Door.close()`, but the two-Events-plus-a-flag shape remains — a monotonic press counter owned
by the module would make lost updates impossible by construction; review G-06) · the daemon
building a fresh API client and event loop per turn (review B-01) · no snapshot for a
reconnecting overlay, so a mid-turn restart renders nothing (review P-02).

Parked, not blocking, pick up by mood:

- **"Listen to me" / the follow-up question (owed design).** Reviving any always-open-mic mode
  must answer spec/50 rule 4 truthfully. Thomas' view: a config-time warning that the mic is
  always on may do the same job as a live indicator. Pushback on record: consent to a
  *capability* is not the same as signalling *current* capture — a config checkbox cannot
  reveal a window that failed to close. Note spec/50 already separates the always-on wake ring
  (rule 3, ≤3 s RAM, discarded) from triggered capture (rule 4), so the argument may hold for
  the former and not the latter. If the conclusion is that rule 4 should change, that wants a
  D-number and a written rationale — not a quiet edit.
- **Partial replies on a brain error (owed design).** A blocked or failed stream currently
  discards everything received and shows a generic apology. Keeping the partial with a fault
  marker would have made the anthem case self-explanatory. Needs a rendering decision (what a
  half-answer plus a fault looks like), which is why it is parked rather than patched.

- **Prompt dwell** (owed fix 3 below) — the prompt still flashes for ~1 s. Pairs with the
  **7a/7b dead-air gaps**; same underlying problem, so do them together.
- **Expanded view** — design session first, and it **wants its own D-number** (it widens D14).
- **Latency readout styling** (owed fix 4) — deferred to a static-screens design pass.
- **Contract P gap (D20)** — dictate overwrite-warning + propose-then-tap messages, unbuilt.
- **Launcher option C2** — Job Object lifetime tie; **wants its own D-number** (amends D13/D19's
  isolation rationale and D10's two-seam limit), and daemon-death must become visible in the
  tray. *(This line used to reserve "D24"; D24 was allocated to the display-ownership decision
  on 2026-07-22. Reserve numbers by taking them, not by naming them in advance — the D18/D19
  collision came from exactly this.)*

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
- **M0 ACCEPTANCE RUN — PASSED, 2026-07-22 (PC).** ×10 consecutive ask-hotkey turns, answers
  streaming to the Teleprompter, B1, zero tools. **spec/00's M0 criterion — perceptible
  feedback < 1.5 s ×10 — is met 10/10: 1403–1413 ms.**
  **Read that column honestly:** every reading is 1403–1413 because `WORKING_AFTER_S` is 1.4 s.
  The brain produced nothing audible before the earcon on ANY turn, so the metric passes *by
  construction* — raise the constant to 1.6 and it fails. It measures our timer, not Gemma's
  speed. D11 designed exactly this (feedback beats speed), but the number is not evidence of
  latency and should not be quoted as if it were.
  **First spoken word** (measured, not pass/fail post-D23): 7/10 under the 4 s target · median
  ≈ 3320 ms · min 2704 · max 5992. Breaches: turn 1 **4681** (cold-start artefact — but a big
  improvement on the 9142 ms of the previous run), turn 4 **4631**, turn 10 **5992**.
  **~~Turns 4 and 10 are NOT cold and are unexplained.~~ EXPLAINED 2026-07-22 — and the answer
  is uncomfortable.** Pairing `brain done` usage lines with `first spoken word` lines in
  `logs/gemma.log` for that run, by output tokens: 19→2704 · 29→2910 · 33→3215 · 30→3299 ·
  45→3321 · 56→3575 · 49→4631 · 72→4875 · 80→5992. The two "outliers" are simply **the two
  longest replies**, and the run fits ≈ **2100 ms + 45 ms per output token**. That is exactly
  what D11's generate-then-play guarantees: first word = STT + the WHOLE reply generated + the
  WHOLE reply synthesised, so first-word latency is a function of reply length by construction.
  Nothing was anomalous. **The real consequence: the 4 s first-word target is not a latency
  target at all under generate-then-play — it is a reply-length cap** (~42 output tokens). Any
  serious attempt to hold it wants sentence-streamed TTS, which is parked under D11
  ("feedback beats speed") and should be reopened *with this number*, not on feel.
  **Press → `awake` earcon: 1 ms** against a 300 ms target.
  **Instrument defect found by the run and fixed the same day:** only 4 of 10 turns recorded a
  press→indication figure. Six turns were deliberate **key-interrupts** (Thomas pressing the
  ask key mid-reply), and that path opened its capture from `_speak()` without the entrance
  ritual — no `wake` trace event, and no `awake` earcon either, so a key-interrupt was also
  silently unacknowledged. **Second bug from one root** (the first being barge-in skipping the
  turn-clear): capture-opening paths diverging from the common entrance. Fixed structurally —
  `_enter()` now carries the entrance for `serve()` and the key-interrupt alike.
- **Owed:** live full-loop test on the **Mac** (D10 parity); the PC run is done (spec/00: ×10,
  feedback < 1.5 s, first word < 4 s — per-turn latency lines print) + real-speech STT
  figures for the provisional D11 numbers (spec/00). Watch items for that run: earcon
  ring-out bleeding into VAD on open speakers · BT A2DP↔HFP duplex behaviour (a BT
  earbud's mic use may degrade its output) · barge-in false-trigger rate on speakers (knob:
  `BARGE_CHUNKS` in `orchestrator.py`).
- **Works now (step 7):** replay harness (`tests/replay.py`) — recorded WAVs through
  the real wake/VAD/STT pipeline driving the real orchestrator with fake mic/pump/
  brain/TTS; **6 cases, redesigned 2026-07-22 for the two doors** (below); per-turn latency table
  (also printed when a live session ends). Selfcheck CI on GitHub Actions
  (windows-latest) — **deviation from docs/04 §7:** replay does NOT run in CI because
  the WAVs (Thomas's voice) are deliberately untracked (`tests/replay/wav/`,
  gitignored; copy the folder to the Mac clone by hand).
- **Works now (step ②, this commit): the hotkey module — the two doors (D20).**
  `bridge/hotkeys.py` (a module, not the package spec/40 named): combo-string parser
  (`ctrl+alt+1` ask · `ctrl+alt+2` dictate; env `GEMMA_HOTKEY_ASK`/`_DICTATE` until spec/70's
  config source exists — a binding with no modifier is rejected, it would be swallowed
  everywhere you type) → Win32 `RegisterHotKey` + a `GetMessageW` pump on a daemon thread →
  per-door `start`/`end` events. Hybrid per key: tap-toggle, or hold ≥ 0.5 s for push-to-talk
  with the release as the endpoint. **Narrow registration, no keyboard hook** — the reason is
  now spec/50 rule 11; the cost is a per-OS seam and **macOS is unbuilt** (Carbon
  `RegisterEventHotKey`), where the wake word stays the only entrance.
  Orchestrator: `_pressed()` makes the ask key a second entrance to the same door in the IDLE
  loop (same earcon, same dwell-supersede, ~80 ms poll — inside the 300 ms target), and
  `capture_over()` implements the endpoint rule — **the key ends a keyed turn, not the 1 s
  silence cut**; nothing-said and the 30 s cap still do. `--auto-end` (spec/70, default off)
  puts the silence cut back for one-tap use. The **dictate door is registered but unwired** —
  a press logs and does nothing; its pipeline is Track D's.
  Proven: selfcheck (parsing, tap-toggle, hold-PTT, stale-end clearing — CI-wired) plus a
  live run driving `ctrl+alt+1` through `SendInput`, confirming the OS actually delivers.
- **Replay cases rebuilt for the two doors (2026-07-22, Thomas).** The old suite was 4/5
  wake-first — designed when the wake word was primary. D16 demoted it, so the suite now
  mirrors the desk shape: cases carry a **`trigger`** (`key` · `wake` · `none`) and the keyed
  ones drive the real `Door` objects — no Win32, no keyboard, because a Door is two Events and
  that is the whole interface. **A keyed case's WAV is recorded between two real presses**
  (`_record_keyed`, which dogfoods `bridge/hotkeys.py`), so the clip *is* the capture window
  and its end *is* the endpoint — no invented per-case timestamp. New: **`key_long_pause`**,
  the case that only exists post-D20 — a deliberate 2–3 s pause mid-question, which the wake
  word would cut and the key must not; it is the only real-speech test of `capture_over`.
  Dropped `wake_long` (superseded). **The three wake-word cases were then removed entirely**
  (Thomas, same day): D23 makes "listen for me" default OFF, and off means no wake word *and*
  no barge-in — so all three tested an opt-in config, `ambient` included (a false-accept test
  is meaningless when nothing is listening). The always-on-mic regression story gets designed
  *with* the switch rather than kept alive around it; barge-in returns as a **wake** case then,
  since it needs speech after the endpoint. Old definitions are in git; the WAVs are already
  recorded and left on disk (gitignored) so a revisit costs no re-recording.
  Suite is now 4 keyed cases: `key_short` · `key_long_pause` · `key_hold` · `key_silence`.
- **RESULT (2026-07-22): 4/4 green on the PC, all four transcripts verbatim.** Both endpoint
  modes are now proven on real speech: **`key_long_pause`** (deliberate 2–3 s pause, 12.75 s
  captured in one turn) validates `capture_over` — under the wake word the 1 s silence cut
  would have truncated it — and **`key_hold`** exercises push-to-talk, which had never run on
  real speech before. (Replay latency figures are harness figures — cold STT load, fake brain,
  fake TTS — not acceptance-run numbers.)
- **Owed:** ① ~~record the case WAVs and run green on the PC~~ **DONE**; Mac parity (D10) owed (`python -m tests.replay --record <name>`,
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
  · ② ~~**hotkey module — the two doors (D20)**~~ **DONE** (above) — ask key wired, dictate
  key registered but unwired (Track D), macOS unbuilt · ③ the owed acceptance run, now
  **desk-shaped**: ×10 ask-hotkey turns (overlay streaming + speech), latency table vs
  spec/40 targets · ④ the M0-close gate below. **No wake-word turns** (Thomas,
  2026-07-22) — this line had gone stale against spec/00: D23 already superseded D16(2),
  making the wake word a conditional clause ("with 'listen for me' enabled", default off)
  rather than a ×3 pass/fail variant. Same reasoning that removed the wake replay cases.
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
- **Built (D24, 2026-07-22) — the island owns the display.** `Overlay.qml`: the prompt hands
  over to the reply only once it has finished revealing (`promptShown` +
  `Theme.durationPromptHold`), and the island hides *itself* `Theme.durationAnswerDwell` after
  the text finishes appearing — replacing a daemon-side timer that was estimating this file's
  own typing speed. `showing` deliberately lets a dismiss outrank `busy`, so Esc takes the
  island away instantly rather than waiting for the daemon's abort to come back.
  `teleprompter/__main__.py`: `DismissKey`, a `QAbstractNativeEventFilter` holding bare Esc via
  `RegisterHotKey` for exactly as long as the window is visible (armed off the same
  `visibleChanged` signal as the NOACTIVATE re-stamp). `feed.py` gained `send()` — the one
  upstream verb — and `feed_lost()`, because `idle` can no longer double as "show nothing".
  `decode.py` now *loads* `clearsTurn` and `upstream` from `status.json` instead of restating
  them. Guarded in `overlay_check` (prompt gate · dwell start/stop · dismiss) and in
  `decode --selfcheck`; every assertion verified to FAIL when its fix is reverted.
  **Unproven live:** the native event filter has only ever run on Qt's `offscreen` platform.
- **OWED — fixes from the first live run (2026-07-22).** First real turns ever rendered
  (wake word → STT → B1 → Teleprompter → TTS). It works end to end; these are the defects:
  1. ~~**The reply appears as a block, not typed.**~~ **FIXED.** Prompt *and* reply now reveal
     through one paced typewriter, so it no longer matters how a brain chunks its stream. One
     WORD per tick (`Theme.durationWord`), not one character: character pacing read as a chat
     stream being skimmed rather than a teleprompter to be read.
  2. ~~**The pill snaps into existence on wake.**~~ **FIXED.** `entrance` fades the window in
     and out, bound to the state rather than toggled by hand.
  3. ~~**The prompt flashes for ~1 s / is cut off mid-typing.**~~ **FIXED by D24.** `bodyText`
     was `reply !== "" ? reply : transcript`, so the FIRST brain delta flipped it and the prefix
     test reset the typewriter to zero — at 90 ms/word against a ~1 s warm first token, any
     prompt past **~11 words** lost its tail (cold turns completed, which is why it read as
     inconsistent). A minimum *time* dwell could never have fixed it: any dwell shorter than the
     reveal truncates identically. The invariant is *finish revealing → hold → swap*, and it is
     now enforced overlay-side (`promptShown`, `Theme.durationPromptHold`), guarded by
     `overlay_check` and verified to FAIL when the gate is removed.
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
- **UNBLOCKED 2026-07-22:** the M0 acceptance run passed, discharging the 2026-07-18 condition
  (validate the shared capture path live before building on it). The dictate key is already
  registered (`ctrl+alt+2`) and logs on press; only its pipeline is missing.
  (The D17 review gate cleared 2026-07-21 → **D20**, the two-door model.)
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
  triggers + anti-relitigation clause (D21)**; **D24 — Teleprompter owns the display; Contract P
  gains the `dismiss` upstream verb; `status.json` → v0.3.0 (`clearsTurn`/`upstream` promoted to
  loaded data); spec/50 rule 12; spec/20 adapter-lifetime guarantees (one loop, deterministic
  close)**; **D25 — latency gates re-derived for the desk: `first_word` demoted to `measured`,
  `feedback` credits the screen, all numbers consolidated into `spec/schemas/targets.json`**;
  docs 01, 02, 04 frozen
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
