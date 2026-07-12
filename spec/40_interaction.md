# Spec 40 — Interaction model

**Last reconciled: 2026-07-12** · Build progress: [STATE.md](../STATE.md) (Track G) · Earcon ids: [schemas/earcons.json](schemas/earcons.json)

## State machine *(planned — orchestrator, build step 6)*

```
IDLE ──wake──▶ LISTENING ──end-of-speech──▶ THINKING ──┬─▶ SPEAKING ─▶ FOLLOW-UP ─▶ IDLE
                   │                                    └─▶ ACTING(tools) ─▶ earcon ─┘
                   └── timeout 10 s / mute ──▶ IDLE
```

- `LISTENING` opens on WAKE; end-of-speech = VAD silence (initial: 1 s, tune in M0).
- `FOLLOW-UP`: 8 s window accepting speech without re-wake. Mic open, LED `listening`.
- **Barge-in (binding):** user speech during `SPEAKING` stops TTS ≤ 250 ms and routes
  the speech as new input.
- `THINKING` > 1.5 s fires the `working` earcon once — this is the D11 feedback
  guarantee for any turn that can't answer fast.

## Narration rules (agreed 2026-07-10; enforced by the orchestrator, build step 6)

- Answers ≤ 2 sentences: spoken automatically.
- Longer answers: play `answer-ready`, hold the text; "read it" (in follow-up window)
  speaks it. Never lecture uninvited.
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
| any | End of speech → audible feedback (first spoken word or `working` earcon) | < 1.5 s |
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
(step 6) per the narration rules above — step 4 is only the mechanism.

**Bluetooth output keep-alive (binding for BT devices).** Bluetooth links (H0 stock
headset; H3/H4) idle during silence and glitch on the first audio after silence — a brief
buzz at each earcon/reply onset. Wired output is unaffected. The daemon MUST hold a
**persistent output stream** open, feeding silence between sounds, so the link never idles
(orchestrator, step 6). The step-4 demo opens/closes the device per sound, so it exhibits
the glitch by design — it disappears under the warm stream.

## Visual output — PC overlay (planned, post-M0)

A supplementary on-screen indicator on the hub PC: a Dynamic-Island-style overlay — a
small pill/panel near the top of the screen — showing, at a glance, session **state**
(pulsing dot = awake/listening · spinner = thinking · gone = asleep), the current
**response text**, and small **status icons** (mute, tool activity, error). Component
row in spec/00; `bridge/ui/` when built.

Role and hard boundaries:
- **Supplement, never a replacement.** The system is *eyes-free first* (bone-conduction
  headset); earcons and TTS remain the primary feedback and must fully carry the
  experience on their own. The overlay only helps when the user is at the PC and looking.
- **PC-side, not the headset.** Distinct from spec/10's "no screen on the headset"
  exclusion — this lives on the hub machine's display, not the device. The wearer can't
  see their own headset LED either, so the screen is the only *self*-visible surface.
- **Carries continuous state**, which one-shot earcons can't — so it, not a sound,
  covers the awake→asleep (end-of-session) transition. This is *why* there is no
  `asleep` earcon: falling asleep is passive and a lasting state, better shown than beeped.
- **Out of scope for M0** (close the voice loop first). Overlay tech per platform
  (Windows/macOS always-on-top transparent window) and visual design are TBD when scheduled.

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
