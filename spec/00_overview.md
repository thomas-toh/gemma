# Spec 00 — System overview & status

**Status: DESIGNED (no code)** · Last reconciled: 2026-07-11 · Decisions record: [docs/02](../docs/02_architecture/02_system_architecture.md)

## The system in one paragraph

A head-worn unit (bone-conduction output, microphone, wake-word detection, radio —
deliberately dumb) talks over **Contract H** to the **bridge** (**G**), a Python daemon on the
hub machine (Windows PC or Mac — D10). The bridge transcribes speech, sends it through **Contract B** to a
swappable brain (B1 Claude API → B2 local LLM → B3 agent CLI), executes any requested
PC actions through the **Contract T** tool registry with tiered safety gates, and
replies with earcons (instant pings) or streamed TTS narration.

```mermaid
flowchart LR
    H[Headset] <-- "Contract H" --> G[Bridge]
    G <-- "Contract B" --> B[Brain B1/B2/B3]
    G <-- "Contract T" --> T[Tools / PC]
```

## Legend — naming scheme

One letter per element. The **bridge (G)** is the hub; **H/B/T** are the three things it
connects to, each over the matching Contract.

| Letter | Element | Contract | Component IDs |
|--------|---------|----------|---------------|
| **G** | Bridge — the Gemma daemon (audio, wake, STT, TTS, orchestrator) | — (it *is* the hub) | build steps 0–7 |
| **H** | Headset — hardware + firmware + transport | Contract H | generations **H0–H4** |
| **B** | Brain — swappable LLM | Contract B | **B1** Claude · **B2** local · **B3** CLI |
| **T** | Tools — registry + executor + PC actions | Contract T | safety **Tier 1–3** (spelled out — a "Tier 3" gate is never an "H3" headset) |

Orthogonal axes: **milestones M0–M4** (project-wide stages — see below) and the frozen
**decision records docs 01–04**. Milestone *definitions* live in this file; the live
per-track *sub-steps* live in `STATE.md`; the frozen M0 build order is in docs/04 §8.

> **Terminology note (old → current).** The frozen docs/01–04 use earlier names and are
> not retro-edited (hard rule 2). Current truth: headset generations **T0–T4 → H0–H4**;
> STATE.md tracks relettered **A→G** (Bridge), **B→H** (Headset), **C→B** (Brain), with a
> new **T** (Tools) track — so "Track A's queue" in docs/04 §8 is now Track G's.

## Component inventory

| Component | Spec | Code location (future) | Status |
|-----------|------|------------------------|--------|
| Headset hardware (H0 stock → H2 ESP32) | [10_contract_h](10_contract_h.md) | `firmware/` | DESIGNED — Doc 03 pending |
| Transport adapters | [10_contract_h](10_contract_h.md) §3 | `bridge/transports/` | DESIGNED |
| Audio pipeline (wake, VAD, STT, TTS, earcons) | [40_interaction](40_interaction.md) | `bridge/audio/` | DESIGNED |
| Orchestrator (state machine) | [40_interaction](40_interaction.md) | `bridge/orchestrator.py` | DESIGNED |
| Brain adapters | [20_contract_b](20_contract_b.md) | `bridge/brains/` | DESIGNED |
| Tool registry + executor | [30_contract_t](30_contract_t.md) + [schemas/tools.json](schemas/tools.json) | `bridge/tools/` | DESIGNED |
| Security posture | [50_security](50_security.md) | cross-cutting | BINDING |

## Milestones

| Milestone | Definition (acceptance test) | Status |
|-----------|------------------------------|--------|
| **M0 — Loop closed** | Wake → question → spoken answer < 2 s, ×10 consecutively; stock headset (H0), B1 brain, zero tools | not started |
| **M1 — It acts** | "Open Spotify and play something" → earcon ack; audit log shows the calls; 6 starter tools | not started |
| **M2 — It's local** | M1 script passes with Wi-Fi unplugged (B2 brain) | not started |
| **M3 — On your head** | Full loop on custom ESP32 headset (H2), on-device wake, battery > 4 h | not started |
| **M4 — Experiments** | B3 adapter · bone-conduction mic · H3/H4 · per-request routing | not started |

## Fixed platform decisions

Python 3.12+ / asyncio for the bridge (rationale: docs/02 §6). ESP32-S3 + C++ for the
H2 headset. Audio: 16 kHz 16-bit mono PCM in, 24 kHz mono out (constants in
[schemas/messages.schema.json](schemas/messages.schema.json)). Wake word: user-specified
phrase → trained keyword model (openWakeWord on PC; microWakeWord on ESP32) — never an
LLM, never continuous transcription.

**D10 (2026-07-10): cross-platform hub.** The bridge targets **Windows 11 and macOS as
full peers** (Thomas runs a Windows/RTX-5080 desktop and a Mac laptop; an M4/M5-class
Air can also run B2 locally via Ollama/Metal). Platform-specific code is confined to
exactly two seams: audio endpoint access and the Contract T tool-executor backends
(spec/30 rule 3). Everything else — orchestrator, brains, transports, schemas — is
platform-neutral by construction. Windows is the reference platform (built and tested
first); macOS parity is checked at each milestone, not retrofitted at the end.
Portability design: docs/04 §3.
