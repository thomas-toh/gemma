# STATE — the jump table

Purpose: make track-hopping free. Thomas works by mood; that is fine **because** the
contracts isolate the tracks. The rules that keep it safe: pick a track by mood, but
within a track always take the next queued action · max one item in flight per track ·
when abandoning mid-task, park it here with a one-line note · read this file at session
start, update it in the same commit as the work.

Last updated: 2026-07-11

## Track G — Bridge (Doc 04 → M0, M1, M2)

- **Works now:** repo committed on `main`. `bridge/` skeleton: `config.py` loads
  `spec/schemas/*` at runtime (hard rule 3), `log.py` logging setup. **Step 2 built:**
  `bridge/audio/wake.py` — mic → ≤3 s in-RAM ring buffer → openWakeWord (`hey_jarvis`,
  ONNX) → console. Cross-platform (sounddevice + onnxruntime, Windows + macOS, D10).
  `--selfcheck` (buffer discipline, no mic) passes. Live mic test passed on Windows and
  macOS — cross-platform (D10) confirmed. **Step 3 built:** `bridge/audio/listen.py` —
  wake → Silero VAD (350 ms end-of-speech) → faster-whisper `small.en` → console.
  Engine A: uses CUDA when loadable, else CPU (one path Win+Mac); `transcribe()` is the
  seam for a Mac-GPU engine later. VAD runs openWakeWord's bundled Silero ONNX via
  onnxruntime — **no torch** (torch won't install here: Windows long-path limit).
  `--selfcheck` (end-of-speech logic + VAD wrapper, no mic) passes; `transcribe()` logs
  real STT latency. **Step 3 live mic test owed** (both OSes). Run instructions in
  `README.md`. Steps 0–3 done.
  - **GPU STT working** on the RTX-5080: `pip install -e ".[gpu-cuda]"` (cuBLAS/cuDNN/
    cudart) + `listen.py` adds their DLL dirs to the search path (Store-Python quirk).
    Measured `small.en`, 2 s clip: **CPU 887 ms vs GPU ~33 ms warm** (~28x); the one-time
    Blackwell kernel JIT (~26 s) is now cached to disk. macOS stays CPU (Metal deferred).
    Numbers are on synthetic audio — real-speech figures come from the live mic test.
- **In flight:** —
- **Next (M0 build order, docs/04 §8):**
  4) earcons + Kokoro TTS out · 5) B1 Claude adapter, streamed to console ·
  6) orchestrator wiring = **M0 acceptance** · 7) metrics + replay harness (5 recordings)

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
  Credential Manager under service `gemma`. First-token measured **1817 ms** — but that
  run had `chunks=1` (whole short reply in one chunk, first≈total), so it's really
  "time to full short response," cold, and well above the 300–900 ms spec/40 expects.
  **Re-measure** with a longer streamed output before trusting it for the latency budget.
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
  docs 01, 02, 04 frozen
- **In flight:** —
- **Next:** Doc 03 (headset engineering) when the hardware mood strikes

## Parked / someday

B3 agent-CLI adapter · H3 (BLE) and H4 (LE Audio) transports · bone-conduction
microphone experiment (Knowles V2S200D) · earcon sound design session · per-request
brain routing · wake-phrase false-accept test protocol · **LiveKit Wakeword** trial as
an openWakeWord replacement (lower false-accept rate; contained swap behind `wake.py`)
