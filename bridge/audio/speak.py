"""Track G step 4 (docs/04 §8): voice out — earcons + text-to-speech.

Two ways for the bridge to make sound:
- earcon(id): play a short signal tone for one of the earcons defined in
  spec/schemas/earcons.json (ids come from the schema — never hard-coded here).
  M0 uses simple *generated* tones as placeholders; real designed WAVs (living in
  bridge/assets/earcons/) are a later sound-design task.
- speak(text): synthesise speech with Kokoro (via kokoro-onnx, ONNX runtime, no torch)
  and play it. Output is 24 kHz (schema outbound rate), which is Kokoro's native rate.

Playback uses sounddevice (same lib as the mic, output side). Generate-then-play for now;
streaming TTS is a later latency optimisation.

Run:
    python -m bridge.audio.speak "hello, I am Gemma"   # speak text
    python -m bridge.audio.speak --earcon awake        # play one earcon
    python -m bridge.audio.speak --earcon all          # audition every earcon
    python -m bridge.audio.speak --selfcheck           # no audio/model: check tone gen
"""
from __future__ import annotations

import argparse
import logging
import threading
import time
from collections import deque
from pathlib import Path

from bridge.config import load_schemas
from bridge.log import setup_logging

log = logging.getLogger("gemma.speak")

# Output rate is a Contract-H schema constant -- load it, never hardcode (hard rule 3).
SAMPLE_RATE_OUT = load_schemas()["messages"]["audioConstants"]["outbound"]["sampleRateHz"]

VOICE = "af_sarah"          # a Kokoro en-us voice; --voice to try others

RING_MS = 900      # each struck note rings this long, overlapping into the next -> fuller

# Earcon motifs: id -> [(freq_hz, step_ms), ...]. Notes are STRUCK at cumulative step
# offsets and ring/overlap (see _tone), like a real notification arpeggio (modelled on the
# reference notification's warm D-major D-F#-A). freq 0 = a rest. Distinct + pleasant;
# durations are checked against schema maxMs in _selfcheck. Real WAVs still an option later.
TONES: dict[str, list[tuple[int, int]]] = {
    "awake":         [(587, 95), (880, 95)],                 # D5->A5 quick rise: heard you, listening
    "working":       [(494, 0)],                             # single soft B4: thinking
    "task-complete": [(587, 85), (740, 85), (880, 90)],      # D-F#-A rising major: success
    "ask":           [(740, 95), (988, 100)],                # F#5->B5 up-question: confirm?
    "answer-ready":  [(880, 110), (1175, 110)],              # A5->D6 up double: ready
    "timer":         [(1175, 150), (0, 70), (880, 150), (0, 70), (1175, 160)],  # music-box
    "error":         [(440, 110), (330, 130)],               # A4->E4 low fall: something wrong
}
DEFAULT_TONE = [(740, 100)]        # for any schema id without a bespoke motif


def _earcon_ids() -> set[str]:
    return {e["id"] for e in load_schemas()["earcons"]["earcons"]}


def _note(freq: float, n: int, rate: int):
    """One struck tonal note: fundamental + gentle harmonics under an exponential ring
    (warm/mallet-like, not metallic). Attack ramp avoids a click."""
    import numpy as np
    t = np.arange(n) / rate
    wave = (np.sin(2 * np.pi * freq * t)
            + 0.30 * np.sin(2 * np.pi * 2 * freq * t)
            + 0.12 * np.sin(2 * np.pi * 3 * freq * t)
            + 0.05 * np.sin(2 * np.pi * 4 * freq * t))
    env = np.exp(-t * 3.4)                                  # rings out (slower = longer tail)
    atk = int(rate * 0.005)
    if atk < n:
        env[:atk] *= np.linspace(0, 1, atk)
    return (wave * env).astype(np.float32)


def _tone(notes, rate: int):
    """Render a notification-style motif: notes struck at cumulative step offsets, each
    ringing for RING_MS and OVERLAPPING (summed), so it sounds full rather than a thin
    sequence of beeps. Warm tonal timbre. notes = [(freq_hz, step_ms), ...]; freq 0 = rest."""
    import numpy as np
    ring_n = int(rate * RING_MS / 1000)
    onset, span, events = 0, 0, []
    for freq, step_ms in notes:
        if freq > 0:
            events.append((onset, freq))
            span = max(span, onset + ring_n)
        onset += int(rate * step_ms / 1000)
    if not events:
        return np.zeros(0, dtype=np.float32)
    buf = np.zeros(span + int(rate * 0.008), dtype=np.float32)
    for start, freq in events:
        note = _note(freq, ring_n, rate)
        buf[start:start + len(note)] += note
    peak = float(np.abs(buf).max())
    if peak > 0:
        buf *= 0.55 / peak                                 # consistent loudness, no overlap clip
    rel = int(rate * 0.150)                                # long, smooth fade so the tail tapers
    if rel < len(buf):                                     # to silence (no audible truncation)
        buf[-rel:] *= 0.5 * (1 + np.cos(np.linspace(0, np.pi, rel)))   # raised cosine: 1 -> 0
    return buf


def _play(samples, rate: int = SAMPLE_RATE_OUT) -> None:
    import numpy as np
    import sounddevice as sd
    # latency="high" = bigger buffer -> no underrun buzz; contiguous float32 for a clean feed.
    sd.play(np.ascontiguousarray(samples, dtype=np.float32), rate, latency="high")
    sd.wait()


def tone_samples(name: str):
    """Samples for one earcon by its schema id (no playback — the orchestrator feeds
    these into the OutputPump; the CLI plays them via earcon())."""
    if name not in _earcon_ids():
        raise ValueError(f"unknown earcon {name!r}; valid: {sorted(_earcon_ids())}")
    return _tone(TONES.get(name, DEFAULT_TONE), SAMPLE_RATE_OUT)


def earcon(name: str) -> None:
    """Play one earcon by its schema id."""
    _play(tone_samples(name))


class OutputPump:
    """Persistent warm output stream (spec/40, binding for BT devices): one OutputStream
    held open for the daemon's life, fed silence between sounds so a Bluetooth link never
    idles — the onset-buzz fix. play() enqueues without blocking; cut() drops all queued
    audio (the barge-in stop, ≤ 250 ms); the callback runs on PortAudio's thread, so the
    main loop stays free to read the mic while sound plays."""

    def __init__(self, rate: int = SAMPLE_RATE_OUT):
        self.rate = rate
        self._lock = threading.Lock()
        self._queue: deque = deque()    # pending float32 arrays; head may be part-played
        self._stream = None

    def __enter__(self) -> "OutputPump":
        import sounddevice as sd
        # ponytail: latency="low" keeps barge-in cuts inside the 250 ms budget; the
        # callback is a memcpy so underruns shouldn't happen — raise it if a device crackles.
        self._stream = sd.OutputStream(samplerate=self.rate, channels=1, dtype="float32",
                                       latency="low", callback=self._callback)
        self._stream.start()
        return self

    def __exit__(self, *exc) -> None:
        self._stream.stop()
        self._stream.close()
        self._stream = None

    def _callback(self, outdata, frames, time_info, status) -> None:
        outdata.fill(0)                 # silence baseline — this line IS the BT keep-alive
        filled = 0
        with self._lock:
            while filled < frames and self._queue:
                chunk = self._queue[0]
                n = min(frames - filled, len(chunk))
                outdata[filled:filled + n, 0] = chunk[:n]
                if n == len(chunk):
                    self._queue.popleft()
                else:
                    self._queue[0] = chunk[n:]
                filled += n

    def play(self, samples) -> None:
        """Enqueue samples (float32 mono at self.rate). Returns immediately."""
        import numpy as np
        with self._lock:
            self._queue.append(np.ascontiguousarray(samples, dtype=np.float32))

    def cut(self) -> None:
        """Drop everything queued — output goes silent within one callback block."""
        with self._lock:
            self._queue.clear()

    def playing(self) -> bool:
        """True while queued audio remains (the device buffer adds ~latency ms after)."""
        with self._lock:
            return bool(self._queue)


# --- text-to-speech (Kokoro via kokoro-onnx) ---
# Model files aren't bundled (too big); fetched once to a local cache on first use.
_KOKORO_BASE = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0"
_KOKORO_FILES = {"kokoro-v1.0.onnx": _KOKORO_BASE + "/kokoro-v1.0.onnx",
                 "voices-v1.0.bin": _KOKORO_BASE + "/voices-v1.0.bin"}
_kokoro = None


def _kokoro_model_paths() -> tuple[Path, Path]:
    import urllib.request
    cache = Path.home() / ".cache" / "gemma"
    cache.mkdir(parents=True, exist_ok=True)
    paths = {}
    for name, url in _KOKORO_FILES.items():
        p = cache / name
        if not p.exists():
            log.info("downloading %s (first run only)...", name)
            urllib.request.urlretrieve(url, p)
        paths[name] = p
    return paths["kokoro-v1.0.onnx"], paths["voices-v1.0.bin"]


def synth(text: str, voice: str = VOICE):
    """Synthesise `text` to samples at SAMPLE_RATE_OUT (no playback — the orchestrator
    feeds these into the OutputPump). Kokoro's native rate is the schema's 24 kHz."""
    global _kokoro
    if _kokoro is None:
        from kokoro_onnx import Kokoro
        model, voices = _kokoro_model_paths()
        log.info("loading Kokoro TTS...")
        _kokoro = Kokoro(str(model), str(voices))
    t0 = time.perf_counter()
    samples, rate = _kokoro.create(text, voice=voice, speed=1.0, lang="en-us")
    log.info("TTS %.0f ms for %d chars", (time.perf_counter() - t0) * 1000, len(text))
    if rate != SAMPLE_RATE_OUT:     # never happens with Kokoro v1; loud if a swap breaks it
        log.warning("TTS rate %d != schema outbound %d", rate, SAMPLE_RATE_OUT)
    return samples


def speak(text: str, voice: str = VOICE) -> float:
    """Synthesise `text` and play it. Returns the spoken duration in seconds."""
    samples = synth(text, voice)
    _play(samples, SAMPLE_RATE_OUT)
    return len(samples) / SAMPLE_RATE_OUT


def _selfcheck() -> None:
    """No audio/model: every schema earcon generates a non-empty tone within its maxMs."""
    maxms = {e["id"]: e["maxMs"] for e in load_schemas()["earcons"]["earcons"]}
    stray = set(TONES) - set(maxms)          # a motif whose id left the schema would
    assert not stray, f"TONES has motifs for ids not in the schema: {sorted(stray)}"  # otherwise die silently
    for name in sorted(_earcon_ids()):
        samples = _tone(TONES.get(name, DEFAULT_TONE), SAMPLE_RATE_OUT)
        dur_ms = len(samples) / SAMPLE_RATE_OUT * 1000
        assert len(samples) > 0, f"{name}: empty tone"
        assert dur_ms <= maxms[name] + 1, f"{name}: {dur_ms:.0f} ms exceeds schema maxMs {maxms[name]}"

    # OutputPump buffer discipline, no device: drive the callback by hand.
    import numpy as np
    pump = OutputPump()
    out = np.ones((8, 1), dtype=np.float32)
    pump._callback(out, 8, None, None)
    assert not out.any(), "empty pump must emit pure silence (BT keep-alive)"
    pump.play(np.arange(1, 11, dtype=np.float32))          # 10 samples: 1..10
    pump.play(np.full(4, 99, dtype=np.float32))
    pump._callback(out, 8, None, None)
    assert list(out[:, 0]) == [1, 2, 3, 4, 5, 6, 7, 8], "callback must drain in order"
    assert pump.playing()
    pump._callback(out, 8, None, None)
    assert list(out[:, 0]) == [9, 10, 99, 99, 99, 99, 0, 0], "must cross chunks, then pad silence"
    assert not pump.playing()
    pump.play(np.ones(100, dtype=np.float32))
    pump.cut()
    assert not pump.playing(), "cut() must empty the queue"
    pump._callback(out, 8, None, None)
    assert not out.any(), "after cut(), silence"

    print(f"selfcheck OK: tones for {len(_earcon_ids())} earcons within schema maxMs; "
          f"pump drains in order, pads silence, cut() empties")


def main() -> None:
    setup_logging()
    ap = argparse.ArgumentParser(description="Gemma voice out: earcons + TTS (Track G step 4)")
    ap.add_argument("text", nargs="?", help="text to speak")
    ap.add_argument("--earcon", help="play an earcon id (or 'all' to audition every one)")
    ap.add_argument("--voice", default=VOICE, help=f"Kokoro voice (default {VOICE})")
    ap.add_argument("--selfcheck", action="store_true",
                    help="verify tone generation without audio or the TTS model, then exit")
    args = ap.parse_args()
    if args.selfcheck:
        _selfcheck()
        return
    if args.earcon == "all":
        for name in sorted(_earcon_ids()):
            print(f"earcon: {name}")
            earcon(name)
            time.sleep(0.4)
    elif args.earcon:
        earcon(args.earcon)
    if args.text:
        speak(args.text, voice=args.voice)


if __name__ == "__main__":
    main()
