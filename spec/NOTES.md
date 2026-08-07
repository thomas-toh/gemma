# NOTES — operational findings

Contract: topic-keyed, edited in place — no session-by-session history · **never
required reading** — no rule, spec, or session workflow may depend on an entry here ·
if an entry becomes load-bearing, promote it (behaviour → spec · run instructions →
README · code rationale → a comment) and delete it here · prune freely; git keeps
history.

## GPU speech-to-text on Windows (RTX 5080)

- `pip install -e ".[gpu-cuda]"` pulls cuBLAS/cuDNN/cudart into the `nvidia` package
  directory, which Windows does not search (Store-Python quirk).
- **Adding the DLL directory is NOT enough, and this cost a silent regression**
  (2026-08-01). `os.add_dll_directory()` is honoured by `ctypes` but **not by
  ctranslate2**, so the directory was right, the DLL was demonstrably loadable, and every
  transcribe still failed with `Library cublas64_12.dll is not found or cannot be loaded`
  and fell back to CPU — 16 times in one log before anyone noticed, because the fallback
  is by design and only logs a warning. Reordering the imports does not help (tested both
  ways). The fix is to **preload each DLL by absolute path** (`ctypes.WinDLL`): Windows
  keys loaded modules by base name, so ctranslate2's later `LoadLibrary` finds the copy
  already in the process and never searches. `listen._load_cuda_dlls()` does both — the
  preload and the directory add, since other loaders do respect the latter.
- The tell that it is on CPU is latency, not an error: ~950 ms per utterance instead of
  ~35 ms. If STT time is suspiciously flat and near a second, check for that warning.
- Measured on `small.en`, 2 s synthetic clip: **CPU 887 ms vs GPU ~33 ms warm (~28×)**.
  Real-speech figures owed from the live mic test (STATE, Track G).
- First GPU run pays a one-time Blackwell kernel JIT (~26 s); cached to disk afterwards.
- macOS stays on CPU; a Metal engine (whisper.cpp / MLX) is added only if measured Mac
  CPU speed disappoints (spec/40).

## Local model runners on Windows (Ollama)

- **Never dial `localhost` — use `127.0.0.1`.** It resolves to IPv6 `::1` first and every
  local runner binds IPv4, so the wasted attempt is paid on *every* call, not just
  failures. Measured: **~2,065 ms to connect via `localhost` against 0.2 ms via
  `127.0.0.1`** — a 10× swing on a whole cleanup turn (2.3 s → 0.2 s). `base_url()`
  rewrites it, deliberately in the URL builder so it also repairs endpoints already
  stored in a profile.
- Even `127.0.0.1` takes ~2 s to report a *refused* connection here, where it should be
  instant — something drops rather than refuses the packet (firewall). Hence local
  providers get `max_retries=0` and a short connect budget: a refused loopback socket is
  not a transient fault, and retrying it three times cost **9.66 s** inside the paste path.
- **Ollama's `/v1` ignores three native fields** that its own API honours: `think`,
  `num_ctx` and `keep_alive` (all tested 2026-08-02, v0.32.5). `reasoning_effort` IS
  supported there and documented with a `none` value meaning thinking-off — that is the
  only route to the thinking toggle from an OpenAI-compatible client. `keep_alive` is
  therefore reachable only as `OLLAMA_KEEP_ALIVE` in the environment at spawn, so it
  governs a server Gemma starts and cannot reach one the user started.
- `num_ctx` sizes the KV cache **at load time** — changing it reloads the model (~3.4 s).
  VRAM scales with it: qwen3:8b is 5.58 GB at 4096, 6.30 at 8192, 7.52 at 16384 and
  ~11.2 GB at 128k. A large context is expensive for nothing when the prompt is ~850
  tokens.
- **Ollama reads GGUF, not ONNX.** An ONNX build of the same model is the wrong artefact twice
  over: wrong format, and it targets ONNX Runtime GenAI, which is a *library* — B2 needs an
  HTTP endpoint, which is what `ollama serve` is. (ONNX is right elsewhere here: wake word,
  Kokoro TTS and the parked Parakeet STT path all use ONNX Runtime. Ears yes, brain no.)
- **The tray icon is `ollama app.exe`; the server is `ollama.exe serve`** and has no GUI.
  Disabling the app's autostart (Task Manager > Startup) leaves no tray and no server.
- **Benchmark one model at a time, fully resident.** Cycling several over 16 GB changes
  scores — partial CPU offload under memory pressure alters the numerics, and a model
  that scores 8/9 isolated scored 7/9 in a combined run.

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
- **Never bind `font.weight` to a state or selection.** A variable font's heavier cut has wider
  advances, so the label visibly RE-SPACES as it changes — carry selection by shade or ink, never
  by weight. Cross-cutting: it applies to any label that can be selected, active or current.

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

## Font tooling (2026-08-01, revised 2026-08-07)

Swapping the icon font used to need `fonttools` (+ `brotli`) to dump a `.ttf`'s cmap. Lucide ships
its own name→codepoint map, so nothing needs to read the font's tables and neither library should
go back into `pyproject.toml`:

    npm pack lucide-static     # package/font/{lucide.ttf,codepoints.json} + package/LICENSE

**The trap that cost time, twice:** icon fonts map the same glyph NAMES to different codepoints.
Material *Symbols* and the older Material *Icons* disagreed (`check` E5CA vs E668, `close` E14C vs
E5CD); Lucide shares nothing with either. Swapping the font means re-mapping every existing glyph,
not just adding the new ones, or known-good icons silently become different pictures rather than
failing. Checked rather than remembered since the Lucide swap: `settings_check` asserts every
codepoint in `Theme.ico` resolves to a real glyph.

## Gem sprite kit — the v2.3 export (2026-08-07)

Design's v2.3 changes exactly one state: `working` goes from `typing` / `laptop-open` /
`laptop-close` to `typewriter` / `typewriter-in` / `typewriter-out`. The other eight states are
frame-identical to the previous export, verified by comparing the frame data rather than trusted,
so the swap is the four asset files plus the clip names in `gem.py`'s self-check. The base loop
grew 32 → 70 frames, which widens the atlas to 70 columns; nothing reads that (the app paints from
the JSON's palette-indexed grid, and the PNGs are reference art).

`look-around` and `jump` are **muted** in the idle rotation (Thomas) — the first a filler, the
second a gag, so one skip list covers both tiers. It lives in `gem.py`'s `MUTED` rather than in
the kit, on the basis that Design's next export overwrites `gem-sprites.json`. `gem.gem` asserts
neither fires across ~74 minutes of simulated idle, which is what catches an export putting them
back.
