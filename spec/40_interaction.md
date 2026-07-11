# Spec 40 — Interaction model

**Status: DESIGNED** (wake + capture/STT front-end PARTIAL — `bridge/audio/{wake,listen}.py`) · Last reconciled: 2026-07-11 · Earcon ids: [schemas/earcons.json](schemas/earcons.json)

## State machine

```
IDLE ──wake──▶ LISTENING ──end-of-speech──▶ THINKING ──┬─▶ SPEAKING ─▶ FOLLOW-UP ─▶ IDLE
                   │                                    └─▶ ACTING(tools) ─▶ earcon ─┘
                   └── timeout 10 s / mute ──▶ IDLE
```

- `LISTENING` opens on WAKE; end-of-speech = VAD silence (initial: 1 s, tune in M0).
- `FOLLOW-UP`: 8 s window accepting speech without re-wake. Mic open, LED `listening`.
- **Barge-in (binding):** user speech during `SPEAKING` stops TTS ≤ 250 ms and routes
  the speech as new input.
- `THINKING` > 1.5 s fires the `working` earcon once.

## Narration rules (agreed 2026-07-10)

- Answers ≤ 2 sentences: spoken automatically.
- Longer answers: play `answer-ready`, hold the text; "read it" (in follow-up window)
  speaks it. Never lecture uninvited.
- Successful Tier 2 actions: earcon only. Failures: earcon + one-sentence explanation.
- Tier 3: `confirm?` earcon + spoken one-line summary of what will happen.

## Latency acceptance criteria (M0/M1 gates, measured not vibes)

| Metric | Target |
|--------|--------|
| Wake detect → `ack` earcon | < 300 ms |
| End of speech → first spoken word (B1) | < 1.5 s |
| End of speech → first spoken word (B2) | < 2.0 s |
| End of speech → Tier 2 action executed | < 1.5 s |
| Barge-in → TTS stopped | < 250 ms |

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

## Open tuning items

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
