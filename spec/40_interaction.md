# Spec 40 — Interaction model

**Last reconciled: 2026-07-21** · Build progress: [STATE.md](../STATE.md) (Tracks G · P) · Earcon ids: [schemas/earcons.json](schemas/earcons.json)

## State machine (orchestrator: `bridge/orchestrator.py`)

```
IDLE ──wake──▶ LISTENING ──end-of-speech──▶ THINKING ──┬─▶ SPEAKING ─▶ FOLLOW-UP ─▶ IDLE
                   │                                    └─▶ ACTING(tools) ─▶ earcon ─┘
                   └── timeout 5 s / mute ──▶ IDLE
```

- `LISTENING` opens on WAKE; end-of-speech = VAD silence (initial: 1 s, tune in M0);
  give-up if speech never starts: 5 s (decided 2026-07-13; was 10 s).
- `FOLLOW-UP`: 8 s window accepting speech without re-wake. Mic open, overlay `listening`.
- **Barge-in (binding):** user speech during `SPEAKING` stops TTS ≤ 250 ms and routes
  the speech as new input.
- `THINKING` that outlives the 1.5 s feedback budget fires the `working` earcon once
  (fired just before the deadline so the sound lands inside it) — this is the D11
  feedback guarantee for any turn that can't answer fast.
- Conversation history threads through one wake-chain (`Session.history`) and dies at
  IDLE; whether it should persist across wakes is an open question (parked — STATE).

## Narration rules (agreed 2026-07-10; enforced by the orchestrator)

- **Register (decided 2026-07-13):** impassive system voice — declaratory or imperative,
  no interjections, exclamations, filler, or performed warmth. A system AI, not a
  companion. Lives in the brain's system prompt (M0: the B1 adapter's placeholder;
  M0.5: the versioned persona). Chosen partly because the M0 TTS cannot act emphasis —
  the script must not demand what the voice can't perform.
- Every answer renders in full on the overlay as it streams (D16) — the spoken channel
  follows the rules below, redundant by design at the desk.
- Answers ≤ 2 sentences: spoken automatically.
- Longer answers: full text on the overlay; the spoken channel plays `answer-ready`
  and speaks on "read it" (unchanged away-from-screen behaviour). Never lecture
  uninvited. M0.5 upgrades this to a model-tagged spoken TL;DR over displayed detail.
- Successful Tier 2 actions: `task-complete` earcon only. Failures: `error` earcon + one-sentence explanation.
- Tier 3: `ask` earcon + spoken one-line summary of what will happen.
- Tool progress (M1, planned — D11): during `ACTING`, the `working` ping then silence
  by default; spoken step narration ("Fetching X…") is a config flag, **default off**.
  The overlay's tool-activity icon is the always-on visual.

> The ≤2-sentence speak/hold split above is an **M0 heuristic**. **M0.5 "It speaks well"
> (spec/00) replaces it** with a model-tagged output contract — the brain marks what to
> speak vs hold, plus TTS-safe formatting and speech normalization — so length isn't
> guessed post-hoc. *(planned, M0.5)*

## Latency acceptance criteria (M0/M1 gates, measured not vibes — spec/00 D11)

| Turn class | Metric | Target |
|------------|--------|--------|
| any | Wake detect → `awake` earcon | < 300 ms |
| any | Ask-hotkey press → listening indication (overlay + earcon) | < 300 ms* |
| any | End of speech → perceptible feedback (first spoken word, `working` earcon, or overlay THINKING — audible alone must satisfy this away from the screen; D16) | < 1.5 s |
| no-tool answer | End of speech → first spoken word (B1) | < 4 s* |
| no-tool answer | End of speech → first spoken word (B2) | < 5 s* |
| tool turn | End of speech → starter-tool (Tier 2) action executed | < 1.5 s |
| tool turn | Completion of longer work | unbounded — ends with `task-complete`/`error` earcon |
| any | Barge-in → TTS stopped | < 250 ms |

*Provisional (D11) — confirm with the owed measurements (STATE: step-3 live mic test,
B1 first-token re-run), then fix or amend with data.

**Clock (binding).** "End of speech" = the moment VAD *declares* the turn over. The
silence timer (1 s) runs before this clock starts — it is a turn-taking cost, tuned
separately (`--silence-ms` now; semantic endpointing at M1), not part of the response
budget.

## Wake detection (M0)

Engine **openWakeWord** on ONNX (spec/00), cross-platform (spec/00 D10). M0 uses the
bundled model **`hey_jarvis`** as the wake phrase — a stand-in; a custom-trained phrase
is a later task. **LiveKit Wakeword** is a noted future alternative (lower false-accept
rate) — a contained swap behind the same audio pipeline, would update spec/00. Capture
blocksize and detection threshold are code-level tuning (`bridge/audio/wake.py`), not
spec constants.

**Triggers — the two doors (D20; planned).** Two hotkeys, bindings in config (spec/70):
- **Dictate** — dumb by contract: capture → word-replace (D15) → `transform` cleanup →
  paste at the caret. Never answers, never routes. Safety rule: invoking dictate while
  text is selected warns on the Teleprompter before pasting over it.
- **Ask** — the assistant: utterance + context (selection · clipboard) to the brain,
  which is the toolpicker (Contract B tool-calling over tools.json). Answers render on
  the Teleprompter and speak (D16). Write-actions (rewrite of the selection, etc.) are
  **propose-then-tap**: proposal on the Teleprompter, second tap of the ask key
  applies — only a user keypress ever pastes (D12). `auto_apply` (spec/70, default
  off) bypasses the tap knowingly.

Each key is hybrid: tap = toggle, hold ≥0.5 s = push-to-talk; the key is the endpoint,
VAD only trims. The ask key opens `LISTENING` directly (wake phrase skipped); the wake
word stays the hands-free entrance to the same door. The hotkey module builds before
the desk-shaped M0 run (D16), shared `bridge/hotkeys/`; the dictate door reuses it.
Rewrite is an ask *outcome*, not a mode (D20, superseding D17's separate slice).

## Speech capture & transcription (M0)

After wake, the bridge opens a listening window (`bridge/audio/listen.py`): **Silero
VAD** marks end-of-speech at **1 s** of silence (`--silence-ms` to tune), then **faster-whisper**
(`small.en`, English-only) transcribes to the console. Engine **choice A** (spec/40
review): faster-whisper on GPU (CUDA) where present, else CPU — one code path on Windows
and macOS. `transcribe()` is the swap-point for a Mac-GPU engine (whisper.cpp / MLX) if
Mac CPU speed disappoints — added only if measured (it would introduce a per-OS STT
seam, extending spec/00 D10). Normal turns end on VAD silence at any length; the **30 s**
cap is a runaway backstop only (on hit: transcribe what we have, warn). Audio is
RAM-only, discarded after transcription (spec/50 rule 3).

**Transcript hygiene (planned, D15).** Every transcript passes the deterministic
word-replacement table (known mishearings; schema-defined) before use — both paths.
The assistant path additionally supports `--clean-prompts` (**default off**): a
per-prompt `transform()` pass ("fix errors and structure only") via a small local
model, added as its own row in the latency table and judged by A/B before ever
becoming default. The overlay shows raw → cleaned when the flag is on.

## Voice out — earcons & TTS (M0)

Two output paths (`bridge/audio/speak.py`), played via sounddevice at the 24 kHz schema
rate:
- **Earcons** — short signal tones, one per `schemas/earcons.json` id (ids read from the
  schema, never hard-coded). M0 uses *generated* placeholder tones kept within each id's
  `maxMs`; designed WAVs (in `bridge/assets/earcons/`) are a later sound-design task.
  Sound-design intent: distinct from each other, pleasant at low volume, ringing out to
  ~1.1 s (`timer` longer). What's latency-bounded is the earcon **onset** (wake →
  `awake` < 300 ms), not its length — the ring-out overlaps the next phase.
- **TTS** — **Kokoro** via `kokoro-onnx` (ONNX runtime, **no torch**; `espeakng-loader`
  bundles the espeak-ng phonemiser, so no manual install). Native 24 kHz. Generate-then-
  play — the accepted M0/M1 design (spec/00 D11); sentence-streamed TTS is parked
  (STATE), reopened only if measured use feels slow. CPU is faster-than-real-time,
  so no GPU needed. Model files fetch once to `~/.cache/gemma/`.

*When* each earcon fires and *whether* to speak vs. stay quiet is the orchestrator's job
per the narration rules above — `speak.py` is only the mechanism.

**Bluetooth output keep-alive (binding for BT devices).** Bluetooth output (AirPods, BT
earbuds) idles during silence and glitches on the first audio after silence — a brief
buzz at each earcon/reply onset. Wired output is unaffected. The daemon MUST hold a
**persistent output stream** open, feeding silence between sounds, so the link never idles
(the orchestrator's `OutputPump`). The standalone `speak.py` CLI opens/closes the device
per sound, so it exhibits the glitch by design — it disappears under the warm stream.

## Visual output — the Teleprompter (component P; D13/D19; v0 planned, pre-M0-run)

A supplementary on-screen indicator on the hub PC: a Dynamic-Island-style overlay — a
small pill/panel near the top of the screen — showing, at a glance, session **state**
(pulsing dot = awake/listening · spinner = thinking · gone = asleep), the current
**response text**, and small **status icons** (mute, tool activity, error). Component
row in spec/00; the top-level `teleprompter/` package (component P, D19).

Role and hard boundaries:
- **First-class at the desk; audio must suffice away (D14).** At the desk the overlay
  is a primary surface — a teleprompter of the transcribed prompt, the streamed
  response, and tool activity, expandable to the current session's turns (**in-memory
  only**; nothing written to disk, spec/50 unchanged). Away from the screen, earcons
  and TTS alone must still fully carry the experience — the demoted-but-binding
  residue of eyes-free-first (it still holds when you step away from the desk). For
  dictation (Track D) the overlay is the *primary* feedback surface *(planned, D2)*.
- **Carries continuous state**, which one-shot earcons can't — so it, not a sound,
  covers the awake→asleep (end-of-session) transition. This is *why* there is no
  `asleep` earcon: falling asleep is passive and a lasting state, better shown than beeped.

Architecture (D13, spec/00):
- **Separate process on a status feed.** The overlay never runs inside the daemon. The
  orchestrator broadcasts JSON status events — state transitions, partial/final
  transcript, mic level, per-turn latency, faults — over a **localhost-only** socket
  (`bridge/broadcaster.py`); the overlay subscribes and renders what arrives. Feed
  message schema: `spec/schemas/status.json` (Contract P, hard rule 3). Renderer:
  **PySide6/Qt (QML)** frameless translucent pill on Windows; a later mac renderer
  consumes the same feed.
- **Never takes focus (BINDING).** The window is non-activating (`WS_EX_NOACTIVATE` /
  Qt `WindowDoesNotAcceptFocus` + `ShowWithoutActivating`). Vital for dictation: focus
  determines where the paste lands — an overlay that steals focus misroutes the transcript.
- **Truthful state (BINDING).** The listening indicator inherits spec/50's truthful-indicator
  rule: it must truthfully reflect whether audio is streaming.
- **Build order:** overlay v0 (state · live transcript · latency readout) lands
  **before the M0 acceptance run** and doubles as its instrument; dictation states
  (recording + mic level · transcribing · transforming · pasted) land at Track D's D2.

## Open tuning items (M0)

Custom wake phrase (replace the `hey_jarvis` stand-in) + false-accept testing (D8) ·
end-of-speech silence threshold (1 s start, `--silence-ms` to tune live) · pre-roll
length · follow-up window length · earcon sound design (synthesise vs buy — genuinely
fun sub-project).

**End-of-speech: semantic endpointing (planned, M1).** A fixed silence timer can't be
both pause-tolerant and snappy — a long tolerance delays *every* reply. The proper fix,
like Siri/Alexa, is **semantic endpointing**: judge from the running transcript whether
the utterance is a complete thought, combined with the timer — so long composed prompts
can pause mid-thought without being cut off, while simple prompts stay fast. Related
levers: higher max-utterance cap, explicit dictation mode. Build when tools/LLM prompting
land (M1).
