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

## Earcon design (step-4 placeholders)

- Generated tones: warm overlapping-ring tonal chimes — notes struck at step offsets
  with a ~900 ms ring-out, D-major-leaning motifs — tuned by ear against reference
  notification sounds. Designed WAV files remain a later sound-design task (spec/40).

## TTS (Kokoro) timings

- Synthesis ≈ 1.26 s for a one-line test on CPU (roughly 0.3–0.4× real-time). Feeds the
  D11 no-tool answer budget; re-check with real reply lengths at step 6.
