# Project Gemma — Bridge Engineering

> Superseded in part: secrets handling by spec/50 §10 (OS credential store — not env vars as §5 says); repo layout, module names and STT model by spec/00 + spec/40 + the `bridge/` tree as built.

**Doc 04 of the project series** · *Status: draft for discussion · July 2026*

The engineering plan for the bridge: the Python daemon that is the whole product until
custom hardware exists. Builds against the contracts in `spec/` (which prevail over
this doc if they ever diverge). Targets milestones **M0 → M2** from spec/00; the T2
transport work lands with Doc 03.

Reference back: [Doc 02 — Architecture & Contracts](../02_architecture/02_system_architecture.md).

---

## 1. Scope and shape

One Python 3.12+ asyncio daemon, headless, started with `python -m gemma_bridge`
(later: launch-at-login). No GUI — a minimal FastAPI status page serves transcript
history, config view, audit log and live state. Runs as a **full peer on Windows 11
and macOS** (D10): same codebase, two thin platform seams (§3).

Explicitly out of scope for M0–M2: T2/T3/T4 transports (Doc 03), B3 agent-CLI adapter
(M4), speaker verification, any UI beyond the status page.

## 2. Repository layout

```
bridge/
  pyproject.toml            # uv/pip installable; pinned deps
  config.example.yaml
  gemma_bridge/
    __main__.py             # entrypoint: load config → build pipeline → run
    config.py               # config.yaml + spec/schemas/* loading & validation
    orchestrator.py         # the state machine (spec/40) — owns everything below
    session.py              # conversation state, history policy, local_only flag
    audio/
      io.py                 # sounddevice capture/playback (portable seam #1)
      ring.py               # ≤3 s pre-trigger ring buffer (spec/50 rule 3)
      wake.py               # openWakeWord wrapper
      vad.py                # Silero VAD wrapper (end-of-speech)
      stt.py                # faster-whisper wrapper (streaming-ish, short-utterance mode)
      tts.py                # Kokoro wrapper, sentence-streamed
      earcons.py            # id → WAV playback (assets/earcons/)
    transports/
      base.py               # Contract H adapter interface
      t0_local.py           # OS endpoints; synthesises HELLO/WAKE internally
    brains/
      base.py               # BrainAdapter protocol + BrainEvent types (spec/20)
      b1_anthropic.py       # Messages API, streaming + tool use
      b2_openai_compat.py   # Ollama / llama-server endpoint + model-quirks layer
    tools/
      registry.py           # loads spec/schemas/tools.json; per-platform filtering
      executor.py           # tier gates, confirmation flow, dispatch, audit hook
      backends/win.py       # pywin32 / UIA / SendInput implementations
      backends/mac.py       # osascript / `open -a` / media-key implementations
    audit.py                # append-only JSONL
    metrics.py              # per-stage timestamps → latency report (spec/40 targets)
    web/app.py              # FastAPI status page
  assets/earcons/*.wav
  tests/
    unit/                   # schema validation, registry filtering, state machine
    replay/                 # recorded-WAV → expected-behaviour harness (§7)
```

Rule of construction: **the orchestrator is the only module that knows the others
exist.** Audio, brains, tools and transports never import each other — they meet only
through the orchestrator and the contract types. This is what keeps every piece
swappable and unit-testable.

## 3. Platform strategy (D10)

**Portable out of the box:** `sounddevice` (WASAPI on Windows, CoreAudio on macOS),
openWakeWord, Silero VAD, faster-whisper (CUDA on the 5080; CPU int8 on Apple Silicon
is amply fast for ≤10 s command utterances — whisper.cpp/Metal is the fallback if it
isn't), Kokoro TTS (CPU/MPS), FastAPI, the Anthropic SDK, Ollama (native Metal on
macOS — an M4/M5 Air runs 4–8B models respectably, so **B2 is available on both
machines**, with the 5080 as the heavyweight).

**The two seams where platform code is allowed:**

1. **Audio endpoint selection** (`audio/io.py`): device enumeration/naming differs;
   config takes a per-platform device name; everything downstream sees 16 kHz frames.
2. **Tool backends** (`tools/backends/`): one implementation file per OS behind the
   registry (spec/30 rule 3). The registry marks each tool's availability per platform;
   the brain's tool list only contains what the running OS implements.

Everything else that varies (paths, autostart, media keys) is confined to a small
`platform_.py` util. CI habit from day one: if it imports `pywin32` outside
`backends/win.py`, the build fails.

## 4. Module behaviours that matter

- **Orchestrator:** one asyncio task owning a state variable (IDLE → LISTENING →
  THINKING → SPEAKING/ACTING → FOLLOW-UP, per spec/40). Barge-in = cancelling the TTS
  task on VAD speech during SPEAKING (target ≤ 250 ms). All transitions logged with
  timestamps into `metrics.py` — the latency targets in spec/40 are *measured by the
  program itself*, not by stopwatch.
- **Audio in:** continuous 20 ms frames → ring buffer (≤ 3 s) → wake detector. On wake:
  ring contents + live frames go to VAD/STT; nothing is ever written to disk (spec/50).
- **STT:** faster-whisper `large-v3-turbo` on the 5080 to start (measure, shrink later
  if pointless); `small`/int8 default on Mac. Single-utterance mode: transcribe on
  end-of-speech; streaming partials are an M1+ refinement, not an M0 requirement.
- **B1 adapter:** Anthropic Messages API, `stream=True`, tools from the registry;
  maps SDK events → BrainEvents; retries once on transient errors; refuses when
  `session.local_only`.
- **B2 adapter:** OpenAI-compatible `/v1/chat/completions` against Ollama/llama-server;
  tolerant tool-call parsing + one reprompt on malformed JSON (the model-quirks layer);
  base URL + model name are config.
- **Tool executor:** validates the call against the registry schema (reject ≠ crash),
  applies tier gates (T3 → `confirm` earcon + spoken summary + 8 s window), dispatches
  to the platform backend, writes the audit line, returns the result event to the brain.
- **TTS out:** sentence-chunked streaming — first sentence starts playing while the
  brain is still generating. Earcons bypass TTS entirely (pre-loaded WAVs).

## 5. Configuration

`config.yaml` (validated at startup; secrets via environment, never in the file):

```yaml
audio:
  input_device:  { windows: "Headset Microphone", mac: "MacBook Air Microphone" }
  output_device: { windows: "Headset Earphone",  mac: "MacBook Air Speakers" }
wake:
  model_path: models/wake/hey_gemma.onnx     # user-trained (D8)
  threshold: 0.6
stt: { model: large-v3-turbo, device: auto } # auto → cuda | cpu-int8
brains:
  primary: b1
  b1: { model: <claude-model-id> }           # key from ANTHROPIC_API_KEY env
  b2: { base_url: "http://localhost:11434/v1", model: TBD-m2-bakeoff }
session: { local_only_default: false, follow_up_s: 8 }
tools: { enabled: [system_status, read_clipboard, open_app, focus_window, media_control, set_timer] }
web: { port: 8990 }   # localhost only
```

## 6. The six starter tools, per platform

| Tool | Windows | macOS |
|------|---------|-------|
| `system_status` | psutil + `GetForegroundWindow` | psutil + AppleScript frontmost app |
| `read_clipboard` | `pyperclip` | `pyperclip` |
| `open_app` | app-name → path map, `os.startfile` | `open -a "<Name>"` |
| `focus_window` | pywin32 `EnumWindows` + `SetForegroundWindow` | AppleScript `tell app … activate` |
| `media_control` | `SendInput` virtual media keys | media-key events (osascript/Quartz) |
| `set_timer` | internal asyncio timer → `timer` earcon + spoken name | same (platform-free) |

All six are Tier 1–2. The app map for `open_app` lives in config, not code — the tool
description tells the brain to ask for the list on a miss.

## 7. Test strategy

- **Replay harness (the workhorse):** recorded WAV files (wake word, commands,
  questions, silence, barge-in) fed through the real pipeline with a **fake brain**
  (scripted BrainEvents) and fake tool backends. Asserts state transitions, earcon
  choices, and stage latencies. Runs headless in CI on both OSes; no API key, no GPU
  needed. Every real-world misfire later becomes a new replay case (the alfred eval-set
  instinct, applied to audio).
- **Unit tests:** schema validation (every message/tool example validates), registry
  platform-filtering, tier gating incl. the confirmation timeout, audit completeness
  (a refused call still logs).
- **Live smoke script:** `python -m gemma_bridge.smoke` — mic check, wake check, one B1
  round-trip, one earcon — the "is my setup sane" command for a new machine.
- **Latency report:** `metrics.py` prints a per-stage table after every session;
  acceptance = spec/40 numbers on ten consecutive runs.

## 8. M0 build order (becomes Track A's queue in STATE.md)

| # | Step | Done when |
|---|------|-----------|
| 1 | Repo skeleton: pyproject, config loader importing `spec/schemas/*`, logging | `python -m gemma_bridge` starts, validates config + schemas, exits cleanly |
| 2 | Audio in: sounddevice → ring buffer → openWakeWord (stock phrase first) → console | wake word prints WAKE with confidence, 10/10 tries |
| 3 | VAD + STT: wake → capture → end-of-speech → faster-whisper → console transcript | spoken sentence transcribed correctly < 1 s after end of speech |
| 4 | Earcons + TTS out: `ack` on wake; typed text → Kokoro → speakers | audible round-trip; first audio < 300 ms for earcon |
| 5 | B1 adapter: transcript → Claude → streamed text → console | question in, streamed answer out, zero tools |
| 6 | Orchestrator: wire 2–5 into the spec/40 state machine + follow-up + barge-in | **M0 acceptance: wake → question → spoken answer < 2 s, ×10 consecutively** |
| 7 | Metrics + replay harness seeded with 5 recordings | latency table prints; replay passes in CI |

Then **M1** = registry + executor + win.py backends + confirmation + audit (M0 §6
script but with tools), and **M2** = b2 adapter + model bake-off + `local_only` +
mac.py backends + Mac parity check of the whole suite.

Wake-phrase note for step 2: start with a stock openWakeWord model to de-risk the
pipeline; train the custom user phrase (D8) once the loop works, then A/B false-accepts.

## 9. Risks and honest notes

- **Dependency friction is front-loaded:** CUDA/cuDNN for faster-whisper on Windows and
  Metal quirks on Mac are each an evening of setup pain, once. The smoke script exists
  to prove a machine is past it.
- **openWakeWord custom-phrase quality varies** — if "Hey Gemma" false-accepts
  annoyingly, the fallbacks are threshold tuning, a longer phrase, or Porcupine's free
  tier. Budget an evening, not a weekend.
- **Windows audio endpoint naming is chaos** (devices rename on reconnect). The config
  matcher should substring-match and print what it picked at startup.
- **Tool-call reliability floor:** B2 below ~8B will visibly misfire (docs/01 §6.2) —
  the bake-off measures well-formed-call rate on a 20-prompt script before any model
  is trusted with Tier 2.
- **The 5080 is not the constraint; discipline is.** Everything here is glue around
  mature libraries. The risk is scope creep in the tool list — the growth rule
  (spec/30 rule 4) is the guardrail.

*Next actions: agree this doc → seed Track A's queue from §8 → step 1 is an evening's
work with Claude Code in the repo.*
