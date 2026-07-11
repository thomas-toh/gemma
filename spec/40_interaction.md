# Spec 40 — Interaction model

**Status: DESIGNED** (wake front-end PARTIAL — `bridge/audio/wake.py`) · Last reconciled: 2026-07-11 · Earcon ids: [schemas/earcons.json](schemas/earcons.json)

## State machine

```
IDLE ──wake──▶ LISTENING ──end-of-speech──▶ THINKING ──┬─▶ SPEAKING ─▶ FOLLOW-UP ─▶ IDLE
                   │                                    └─▶ ACTING(tools) ─▶ earcon ─┘
                   └── timeout 10 s / mute ──▶ IDLE
```

- `LISTENING` opens on WAKE; end-of-speech = VAD silence (initial: 350 ms, tune in M0).
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

## Open tuning items

Custom wake phrase (replace the `hey_jarvis` stand-in) + false-accept testing (D8) ·
VAD silence threshold · follow-up window length · earcon sound design (synthesise vs
buy — genuinely fun sub-project).
