# STATE — the jump table

Purpose: make track-hopping free. Thomas works by mood; that is fine **because** the
contracts isolate the tracks. The rules that keep it safe: pick a track by mood, but
within a track always take the next queued action · max one item in flight per track ·
when abandoning mid-task, park it here with a one-line note · read this file at session
start, update it in the same commit as the work · when a step closes, collapse its
entry to one or two lines — durable knowledge moves out (behaviour → spec · run
instructions → README · findings → NOTES.md · decisions → a D-number in spec/00).

Last updated: 2026-07-12

## Track G — Bridge (Doc 04 → M0, M1, M2)

- **Works now:** steps 0–4 built and `--selfcheck`-green. `bridge/`: `config.py`
  (loads `spec/schemas/*`, hard rule 3) + `log.py`; `audio/wake.py` (mic → ≤3 s RAM
  ring → openWakeWord); `audio/listen.py` (wake → Silero VAD → faster-whisper
  `small.en`, GPU when loadable else CPU); `audio/speak.py` (earcons + Kokoro TTS,
  24 kHz). Cross-platform per D10 (step 2 verified live on both OSes). Run
  instructions: `README.md` · GPU setup, benchmarks, quirks: `NOTES.md`.
- **Owed:** live mic test of steps 3–4 on both OSes (real-speech STT figures + earcon/
  TTS audition) — feeds the provisional D11 numbers (spec/00).
- **In flight:** —
- **Next (M0 build order, docs/04 §8):**
  5) B1 Claude adapter, streamed to console · 6) orchestrator wiring, incl. the
  persistent warm output stream (BT onset-buzz fix, spec/40) = **M0 acceptance**
  · 7) metrics + replay harness (5 recordings)

## Track H — Headset (Doc 03 → M3)

- **Works now:** nothing
- **In flight:** Thomas is buying a **used Shokz** (OpenRun/OpenMove class, ~£40–60,
  eBay) — guaranteed-true BC feel test, quality benchmark (docs/01 §4), eventual
  teardown donor. See how it fares before further headset purchases.
- **Next:** 1) **order the Phase 0/1 component basket** (docs/01 §11) — lead-time
  item, do early; delivery time is free cover for Track G work · 2) draft Doc 03
  (headset engineering) · 3) teardown practice on the cheapest available donor
  (LiPo precautions, docs/01 §4.1)
- **Blocked by:** parts delivery once ordered

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
  (B2 groundwork — no commitment to final model; that's the M2 bake-off)

## Track T — Tools (Contract T → M1)

- **Works now:** nothing. M0 runs zero tools; the six starter tools (spec/30) land at M1.
- **In flight:** —
- **Next:** when M0 closes — executor with per-OS backends (spec/30 rule 3), wire
  `schemas/tools.json` into the brain's filtered tool list, Tier 1–2 first.

## Specs — spec & decision docs

- **Works now:** spec/ scaffold v0.2 (Contract H v0.2.0, D10 cross-platform recorded);
  **D11 feedback-first latency posture recorded** (spec/00, 2026-07-12: feedback < 1.5 s
  every turn; no-tool answers bounded; tool turns acknowledged, not bounded;
  generate-then-play stays); `NOTES.md` added for operational findings (routing rule
  in the preamble above); docs 01, 02, 04 frozen
- **In flight:** —
- **Next:** Doc 03 (headset engineering) when the hardware mood strikes

## Parked / someday

B3 agent-CLI adapter · H3 (BLE) and H4 (LE Audio) transports · bone-conduction
microphone experiment (Knowles V2S200D) · earcon sound design session · per-request
brain routing · wake-phrase false-accept test protocol · **LiveKit Wakeword** trial as
an openWakeWord replacement (lower false-accept rate; contained swap behind `wake.py`) ·
**semantic endpointing** (M1) — complete-thought detection so long composed prompts
aren't cut off, the real fix beyond the silence timer (spec/40) · **PC visual overlay**
(Dynamic-Island-style state/text/icons; a supplement to audio, never a replacement) —
designed & deferred, see spec/40 § Visual output + spec/00 inventory ·
**sentence-streamed TTS** — parked per D11 (feedback beats speed); a contained
addition to the TTS path later, reopen only if measured daily use feels slow ·
**long-task interaction pattern** (dispatch-and-notify, heartbeat cadence during long
silence, mid-task status queries by wake, "work on this in the background" phrasing) —
design when B3 or a heavyweight tool lands (D11 discussion, 2026-07-12)
