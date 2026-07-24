# NOTES — operational findings

Contract: topic-keyed, edited in place — no session-by-session history · **never
required reading** — no rule, spec, or session workflow may depend on an entry here ·
if an entry becomes load-bearing, promote it (behaviour → spec · run instructions →
README · code rationale → a comment) and delete it here · prune freely; git keeps
history.

## GPU speech-to-text on Windows (RTX 5080)

- `pip install -e ".[gpu-cuda]"` pulls cuBLAS/cuDNN/cudart; `listen.py` adds their DLL
  directories to the search path at runtime — the pip `nvidia-*` packages drop DLLs
  inside the `nvidia` package directory, which Windows does not search (Store-Python
  quirk).
- Measured on `small.en`, 2 s synthetic clip: **CPU 887 ms vs GPU ~33 ms warm (~28×)**.
  Real-speech figures owed from the live mic test (STATE, Track G).
- First GPU run pays a one-time Blackwell kernel JIT (~26 s); cached to disk afterwards.
- macOS stays on CPU; a Metal engine (whisper.cpp / MLX) is added only if measured Mac
  CPU speed disappoints (spec/40).

## torch does not install on this box

- The Windows long-path limit breaks the torch install. Everything runs on onnxruntime
  instead (wake word, VAD, TTS) — worth keeping even if the limit is ever lifted: one
  inference runtime, smaller install.

## Earcon design

- Three designed WAVs (`listening`/`success`/`failure`) in `bridge/assets/earcons/`, pre-rendered
  to 24 kHz mono and loaded via the stdlib `wave` module (D28). They replaced the earlier generated
  placeholder tones. The mp3 → 24 kHz-mono-WAV conversion is a one-off (PyAV), so the runtime needs
  no audio-codec dependency.

## TTS (Kokoro) timings

- Synthesis ≈ 1.26 s for a one-line test on CPU (roughly 0.3–0.4× real-time). Feeds the
  D11 no-tool answer budget; re-check with real reply lengths at step 6.

## Concurrency — why Python's GIL is not the bottleneck

- The GIL serialises only *pure-Python bytecode running in threads*; it is **released**
  during native/C/GPU work and while blocked on I/O. Every heavy part of Gemma runs
  outside it: STT (CUDA / CTranslate2), wake·VAD·TTS (ONNX Runtime, C++), the brain
  (network I/O, async), audio capture/playback (PortAudio's own callback thread — see
  `speak.py` `OutputPump`). Python is the microsecond glue between them, so the moving
  parts already run concurrently.
- It would only bite CPU-bound *pure-Python* parallelism — which Gemma never does; the
  maths lives in numpy / ONNX / CUDA (all GIL-releasing). This is the standard
  ML-orchestration pattern, not a special case — hence Python for the bridge (spec/00
  platform decisions, docs/02 §6). Not a reason to change language.
- The one genuine concurrency refinement is Python-internal: the per-turn `asyncio.run`
  loop → a single long-lived async daemon (docs/02 async design; flagged in the
  2026-07-18 VoiceInk review), due before tools/streaming land. If real parallel
  pure-Python compute ever appears, Python 3.13+ has an optional free-threaded (no-GIL)
  build — not needed here.

## PySide6 (Teleprompter front-end) on this box

- **Install hits the Windows long-path limit** (same wall as torch): PySide6_Addons has
  deeply-nested Qt paths > 260 chars. Sidestep with a **short-path venv** — the spike uses
  `sandbox/.venv`. It otherwise falls back to **Store Python 3.13 user-site** (no project
  `.venv` exists), whose base path is already ~140 chars, which is why the limit bites.
  Thomas is enabling Windows Long Paths (registry + reboot); after that a normal project
  venv installs fine and PySide6 can become an optional `[ui]` dep.
- **QML plugin DLL search:** Qt's plugin loader does NOT search the PySide6 package dir, so
  `qtquick2plugin.dll` fails with "module could not be found." Fix (same class as the CUDA-DLL
  quirk): add `os.path.dirname(PySide6.__file__)` to `PATH` before importing the Qt
  submodules — see `sandbox/qml_spike/overlay.py`.
- **Window recipe (proven on this box):** frameless + translucent + always-on-top +
  non-activating = flags `FramelessWindowHint | WindowStaysOnTopHint | Tool |
  WindowDoesNotAcceptFocus` + transparent `Window` color, plus a native `WS_EX_NOACTIVATE`
  ctypes fallback on the HWND (the pure Qt flag is spotty on Windows).
- The concave top-corner "flare" is a filled `Canvas` path (QML `border-radius` only rounds
  inward); bottom corners use normal radius. Reference shape: `sandbox/qml_spike/Overlay.qml`.

## Claude API content filtering (Track B, seen live 2026-07-22)

- **Song lyrics get blocked at the END of a stream, not the start.** "State the first stanza
  of the US national anthem" streamed the whole stanza as normal `TextDelta`s, then closed
  with `invalid_request_error: Output blocked by content filtering policy`. Reproduced 4×.
  Nothing to fix in Gemma — the API will not return that text — but it is the clearest live
  example of the shape: a *usable partial reply plus a terminal error*. `_collect()` returns
  `(partial, err)` and the orchestrator throws the partial away for a generic apology, which
  is why the overlay showed the anthem and then replaced it with a fault. See STATE (Track P)
  for the parked design question about rendering partials.
- Diagnosing this needed the daemon's console, which at the time went only to stderr — in a
  Claude Code background-task file nobody would ever find. Hence `logs/gemma.log`.
