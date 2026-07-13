# Gemma bridge

Python daemon for Project Gemma (bone-conduction headset ↔ LLM brains). Design lives
in `spec/` (start with `spec/00_overview.md`); current status in `STATE.md`; working
rules in `CLAUDE.md`.

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

Every new terminal — reactivate, then run:

```bash
source .venv/bin/activate         # Windows: .venv\Scripts\activate
python -m bridge.orchestrator          # THE M0 LOOP (step 6): say "hey jarvis", ask, hear the answer
python -m bridge.audio.listen          # wake -> listen -> transcribe (step 3); say "hey jarvis"
python -m bridge.audio.wake            # just the wake-word listener (step 2)
python -m bridge.audio.speak "hello"   # voice out (step 4): TTS; --earcon all auditions earcons
python -m bridge.orchestrator --selfcheck   # no mic/network; each module has a --selfcheck
```

`deactivate` to leave the environment. The API key is read from the OS credential
store, never a file (see `spec/50_security.md`).
