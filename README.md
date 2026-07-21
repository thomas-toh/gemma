# Gemma

A **UI-first desk assistant on Windows** (D23): speech and text in through two doors —
**dictate** (words at the caret) and **ask** (the assistant) — with every answer rendered on
the **Teleprompter**, a Dynamic-Island overlay. Two processes: `bridge/` is the headless
daemon, `teleprompter/` is the overlay that subscribes to its status feed. Design lives in
`spec/` (start with `spec/00_overview.md`); current status in `STATE.md`; working rules in
`CLAUDE.md`.

Speech (TTS) and the wake word are supported but **off by default** — flip them on in
settings. The Teleprompter is not optional.

## Running (dev)

Requires **Python 3.12+**. Use an isolated environment (`.venv`) so installs don't
touch the system Python — on macOS/Homebrew a system-wide `pip install` is blocked
outright (PEP 668).

First time — create the environment and install:

```bash
python3.12 -m venv .venv          # Windows: py -3.12 -m venv .venv
source .venv/bin/activate         # Windows: .venv\Scripts\activate
pip install -e .
pip install -e ".[gpu-cuda]"      # optional: NVIDIA GPU speech-to-text (~28x faster)
```

`[gpu-cuda]` is optional and NVIDIA-only (Windows/Linux) — skip it on macOS. Without it,
speech-to-text runs on CPU.

**Windows: enable Long Paths first.** PySide6 (the Teleprompter, a core dependency since D23)
has QML module trees nesting past 260 characters. Without Long Paths the install
**half-completes silently** — `import PySide6` works while QtQuick is missing — so
`python -m teleprompter` checks for this at startup and tells you how to fix it.

Every new terminal — reactivate, then run:

```bash
source .venv/bin/activate         # Windows: .venv\Scripts\activate
python -m bridge.orchestrator          # THE M0 LOOP (step 6): say "hey jarvis", ask, hear the answer
python -m bridge.audio.listen          # wake -> listen -> transcribe (step 3); say "hey jarvis"
python -m bridge.audio.wake            # just the wake-word listener (step 2)
python -m bridge.audio.speak "hello"   # voice out (step 4): TTS; --earcon all auditions earcons
python -m bridge.orchestrator --selfcheck   # no mic/network; each module has a --selfcheck
python -m tests.replay                 # replay harness (step 7): recorded WAVs -> assertions
python -m tests.replay --record wake_short  # record one case's WAV (scripts in tests/replay/cases.json)
```

`deactivate` to leave the environment. The API key is read from the OS credential
store, never a file (see `spec/50_security.md`).
