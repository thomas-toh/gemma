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

> **Reality check on the Windows dev box (2026-07-21).** It currently runs *without* a venv,
> straight into Microsoft-Store-Python user-site — so the instructions below describe the
> recommended setup, not the machine you may be sitting at. That works, but it is why two
> workarounds exist: the 138-char Store site-packages path is what made the PySide6 long-path
> install fail (below), and `bridge/audio/listen.py` has to add the CUDA DLL directories to the
> search path by hand because Store Python does not search them. A short-path venv avoids
> both. Details in `NOTES.md`; worth reconciling when you next pay the install cost anyway
> (fresh machine, the Mac, or packaging).

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
python -m bridge.orchestrator          # THE M0 LOOP (step 6): press ctrl+alt+1 (the ask door), ask, hear the answer
python -m bridge.audio.listen          # wake -> listen -> transcribe (step 3); say "hey jarvis" (wake word is opt-in, D23)
python -m bridge.audio.wake            # just the wake-word listener (step 2)
python -m bridge.audio.speak "hello"   # voice out (step 4): TTS; --earcon all auditions earcons
python -m bridge.orchestrator --selfcheck   # no mic/network; each module has a --selfcheck
python -m tests.replay                 # replay harness (step 7): recorded WAVs -> assertions
python -m tests.replay --record key_short  # record one case's WAV (cases in tests/replay/cases.json; all key_* now)
```

`deactivate` to leave the environment. The API key is read from the OS credential
store, never a file (see `spec/50_security.md`).
