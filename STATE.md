# STATE — the jump table

Purpose: make track-hopping free. Thomas works by mood; that is fine **because** the
contracts isolate the tracks. The rules that keep it safe: pick a track by mood, but
within a track always take the next queued action · max one item in flight per track ·
when abandoning mid-task, park it here with a one-line note · read this file at session
start, update it in the same commit as the work.

Last updated: 2026-07-10

## Track A — Bridge software (Doc 04 → M0, M1, M2)

- **Works now:** repo committed on `main`. `bridge/` skeleton: `config.py` loads
  `spec/schemas/*` at runtime (hard rule 3, self-check passes), `log.py` logging setup;
  `pyproject.toml` pins `anthropic`+`keyring` only. Steps 0–1 done.
- **In flight:** —
- **Next (M0 build order, docs/04 §8):**
  2) audio in → ring buffer → openWakeWord (stock phrase) → console ·
  3) VAD + faster-whisper → console transcripts · 4) earcons + Kokoro TTS out ·
  5) B1 Claude adapter, streamed to console · 6) orchestrator wiring = **M0 acceptance**
  · 7) metrics + replay harness (5 recordings)

## Track B — Headset hardware (Doc 03 → M3)

- **Works now:** nothing
- **In flight:** Thomas is buying a **used Shokz** (OpenRun/OpenMove class, ~£40–60,
  eBay) — guaranteed-true BC feel test, quality benchmark (docs/01 §4), eventual
  teardown donor. See how it fares before further headset purchases.
- **Next:** 1) **order the Phase 0/1 component basket** (docs/01 §11) — lead-time
  item, do early; delivery time is free cover for Track A work · 2) draft Doc 03
  (headset engineering) · 3) teardown practice on the cheapest available donor
  (LiPo precautions, docs/01 §4.1)
- **Blocked by:** parts delivery once ordered

## Track C — Brains & models (M0 needs B1; M2 needs B2)

- **Works now:** B1 smoke test (`scripts/b1_smoke.py`) green on Windows — auth, streaming,
  tool-call/tool-loop all PASS. Dedicated "gemma" key (spend-capped) lives in Windows
  Credential Manager under service `gemma`. First-token measured **1817 ms** — but that
  run had `chunks=1` (whole short reply in one chunk, first≈total), so it's really
  "time to full short response," cold, and well above the 300–900 ms spec/40 expects.
  **Re-measure** with a longer streamed output before trusting it for the latency budget.
- **In flight:** —
- **Next:** 1) install Ollama on the 5080, pull one small model, sanity-check tokens/sec
  (B2 groundwork — no commitment to final model; that's the M2 bake-off)

## Track D — Spec & decision docs

- **Works now:** spec/ scaffold v0.2 (Contract H v0.2.0, D10 cross-platform recorded);
  docs 01, 02, 04 frozen
- **In flight:** —
- **Next:** Doc 03 (headset engineering) when the hardware mood strikes

## Parked / someday

B3 agent-CLI adapter · T3 (BLE) and T4 (LE Audio) transports · bone-conduction
microphone experiment (Knowles V2S200D) · earcon sound design session · per-request
brain routing · wake-phrase false-accept test protocol
