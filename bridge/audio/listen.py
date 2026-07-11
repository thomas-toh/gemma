"""Track G step 3 (docs/04 §8): wake -> listen (VAD) -> transcribe -> console.

Extends step 2. On wake it captures speech, uses Silero VAD to find end-of-speech
(350 ms of silence, spec/40), then transcribes the utterance with faster-whisper
(small.en) and prints the text. A little pre-roll from the ring buffer keeps the start
of the sentence. All audio stays in RAM and is dropped after transcription (spec/50
rule 3) -- nothing is written to disk.

Engine choice A (spec/40): faster-whisper, GPU (CUDA) if present else CPU -- same code
on Windows and macOS. transcribe() is the swap-point: a Mac-GPU engine (whisper.cpp /
MLX) can replace its body later without touching the pipeline.

Run:
    python -m bridge.audio.listen             # say "hey jarvis", then speak
    python -m bridge.audio.listen --selfcheck # no mic/models: end-of-speech logic only
"""
from __future__ import annotations

import argparse
import logging

from bridge.audio.wake import (
    SAMPLE_RATE, BLOCK_MS, BLOCK_SAMPLES, BUFFER_BLOCKS, WAKE_MODEL, THRESHOLD,
)
from bridge.log import setup_logging

log = logging.getLogger("gemma.listen")

# --- listening-window params (all tunable; see spec/40) ---
VAD_CHUNK = 512                                   # Silero VAD needs 512-sample windows @ 16 kHz
VAD_CHUNK_MS = VAD_CHUNK * 1000 // SAMPLE_RATE    # 32 ms
VAD_THRESHOLD = 0.5                               # speech if Silero prob >= this
SILENCE_MS = 350                                  # spec/40: end-of-speech silence (tune live)
MAX_UTTERANCE_S = 30                              # safety cap ONLY; VAD ends normal turns
NOSPEECH_MS = 3000                                # give up if nothing is said after wake
PREROLL_MS = 200                                  # pre-roll from ring buffer (tune: onset vs
                                                  # bleeding the wake word into the transcript)

SILENCE_CHUNKS = (SILENCE_MS + VAD_CHUNK_MS - 1) // VAD_CHUNK_MS   # ceil -> 11 (~352 ms)
MAX_CHUNKS = MAX_UTTERANCE_S * 1000 // VAD_CHUNK_MS                # 937 (~30 s)
NOSPEECH_CHUNKS = NOSPEECH_MS // VAD_CHUNK_MS                      # 93 (~3 s)
PREROLL_BLOCKS = PREROLL_MS // BLOCK_MS                            # 2 (~160 ms)

WHISPER_MODEL = "small.en"                        # spec/40 decision 2


class EndOfSpeech:
    """Decide when one utterance is over, from a stream of per-chunk speech flags.

    Normal turns end on SILENCE_CHUNKS of silence *after* speech starts (any length).
    MAX_CHUNKS is a runaway backstop only. NOSPEECH_CHUNKS gives up if speech never
    starts. Pure logic -> unit-tested in _selfcheck() without a mic or any model.
    """

    def __init__(self, silence_chunks=SILENCE_CHUNKS, max_chunks=MAX_CHUNKS,
                 nospeech_chunks=NOSPEECH_CHUNKS):
        self.silence_chunks = silence_chunks
        self.max_chunks = max_chunks
        self.nospeech_chunks = nospeech_chunks
        self.total = 0
        self.silence_run = 0
        self.speech_started = False

    def update(self, is_speech: bool) -> bool:
        """Feed one chunk's speech flag; return True when the turn should end."""
        self.total += 1
        if is_speech:
            self.speech_started = True
            self.silence_run = 0
        else:
            self.silence_run += 1
        if not self.speech_started:
            return self.total >= self.nospeech_chunks     # nothing said -> give up
        if self.silence_run >= self.silence_chunks:
            return True                                    # end of speech
        return self.total >= self.max_chunks               # safety cap


def _silero_model_path() -> str:
    """Path to the Silero VAD ONNX model that openWakeWord already ships. Reusing it
    lets us run VAD on onnxruntime with **no torch** — which also sidesteps torch failing
    to install on this box (Windows long-path limit). ponytail: reuses a bundled asset;
    vendor the ~2 MB model if that coupling ever breaks."""
    import glob
    import os

    import openwakeword
    base = os.path.dirname(openwakeword.__file__)
    hits = glob.glob(os.path.join(base, "**", "silero_vad*.onnx"), recursive=True)
    if not hits:
        raise FileNotFoundError("silero_vad.onnx not found in the openwakeword package")
    return hits[0]


class SileroVAD:
    """Silero VAD (v4 ONNX) via onnxruntime; no torch. Stateful across chunks — call
    reset() at the start of each utterance to clear the LSTM state."""

    def __init__(self, path: str):
        import numpy as np
        import onnxruntime as ort
        self.sess = ort.InferenceSession(path)
        self.sr = np.array(SAMPLE_RATE, dtype=np.int64)
        self.reset()

    def reset(self) -> None:
        import numpy as np
        self.h = np.zeros((2, 1, 64), dtype=np.float32)
        self.c = np.zeros((2, 1, 64), dtype=np.float32)

    def prob(self, samples_int16) -> float:
        """Speech probability (0–1) for one chunk of int16 samples."""
        x = (samples_int16.astype("float32") / 32768.0).reshape(1, -1)
        out, self.h, self.c = self.sess.run(
            ["output", "hn", "cn"],
            {"input": x, "sr": self.sr, "h": self.h, "c": self.c})
        return float(out[0][0])


_whisper = None


def _load_whisper(device: str, compute_type: str):
    from faster_whisper import WhisperModel
    log.info("loading faster-whisper %r on %s (first run downloads it)...",
             WHISPER_MODEL, device)
    return WhisperModel(WHISPER_MODEL, device=device, compute_type=compute_type)


def _run(model, audio_f32) -> str:
    # ponytail: beam_size=1 (greedy) for latency; raise it if accuracy needs it.
    segments, _ = model.transcribe(audio_f32, language="en", beam_size=1)
    return "".join(s.text for s in segments).strip()


def transcribe(audio_f32) -> str:
    """STT seam (spec/40 engine choice A). Uses the GPU (CUDA) when it's actually usable,
    else CPU — one code path on Windows and macOS. A Mac-GPU engine (whisper.cpp / MLX)
    could replace this body later, same signature.

    'GPU where present' means present *and loadable*: a CUDA device with missing runtime
    libs (cuBLAS/cuDNN) only fails at inference, so we fall back to CPU on first use."""
    global _whisper
    if _whisper is None:
        import ctranslate2
        gpu = ctranslate2.get_cuda_device_count() > 0
        _whisper = _load_whisper("cuda", "float16") if gpu else _load_whisper("cpu", "int8")
    try:
        return _run(_whisper, audio_f32)
    except RuntimeError as e:
        log.warning("GPU transcribe failed (%s) -- falling back to CPU", e)
        _whisper = _load_whisper("cpu", "int8")
        return _run(_whisper, audio_f32)


def listen() -> None:
    """Full wake -> listen -> transcribe loop on the default mic. Ctrl-C to stop."""
    from collections import deque

    import numpy as np
    import sounddevice as sd
    import openwakeword.utils
    from openwakeword.model import Model

    log.info("loading models (first run downloads them)...")
    openwakeword.utils.download_models([WAKE_MODEL])
    wake_model = Model(wakeword_models=[WAKE_MODEL], inference_framework="onnx")
    vad = SileroVAD(_silero_model_path())

    ring: deque = deque(maxlen=BUFFER_BLOCKS)
    log.info("listening @ %d Hz -- say '%s', then speak (Ctrl-C to stop)",
             SAMPLE_RATE, WAKE_MODEL.replace("_", " "))
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                        blocksize=0) as stream:
        while True:
            # --- wake phase: 80 ms blocks into openWakeWord ---
            block, _ = stream.read(BLOCK_SAMPLES)
            frame = block[:, 0]
            ring.append(frame)
            if not any(s >= THRESHOLD for s in wake_model.predict(frame).values()):
                continue

            # --- listen phase: 512-sample chunks into Silero VAD ---
            print("[wake] listening...")
            vad.reset()
            eos = EndOfSpeech()
            captured = [np.concatenate(list(ring)[-PREROLL_BLOCKS:])]   # pre-roll
            while True:
                chunk, _ = stream.read(VAD_CHUNK)
                samples = chunk[:, 0]
                captured.append(samples)
                if eos.update(vad.prob(samples) >= VAD_THRESHOLD):
                    break

            if eos.total >= MAX_CHUNKS:
                log.warning("hit the %d s utterance cap -- transcribing what we have",
                            MAX_UTTERANCE_S)
            if not eos.speech_started:
                print("[wake] (nothing heard)")
            else:
                audio = np.concatenate(captured).astype("float32") / 32768.0
                text = transcribe(audio)
                print(f"> {text}" if text else "[wake] (no transcript)")
            ring.clear()


def _selfcheck() -> None:
    """No mic/models: prove the end-of-speech state machine (spec/40 timings)."""
    # 1) speech then silence -> ends after exactly SILENCE_CHUNKS of silence
    eos = EndOfSpeech()
    for _ in range(20):
        assert not eos.update(True)
    ended_at = next(i for i in range(1, 500) if eos.update(False))
    assert ended_at == SILENCE_CHUNKS, (ended_at, SILENCE_CHUNKS)
    assert eos.speech_started

    # 2) pure silence -> gives up at NOSPEECH_CHUNKS, no speech ever seen
    eos = EndOfSpeech()
    n = 0
    while not eos.update(False):
        n += 1
    assert n + 1 == NOSPEECH_CHUNKS, (n + 1, NOSPEECH_CHUNKS)
    assert not eos.speech_started

    # 3) unbroken speech -> stops at the MAX_CHUNKS safety cap
    eos = EndOfSpeech()
    n = 0
    while not eos.update(True):
        n += 1
    assert n + 1 == MAX_CHUNKS, (n + 1, MAX_CHUNKS)

    print(f"selfcheck OK: end-of-speech after {SILENCE_CHUNKS} silent chunks "
          f"(~{SILENCE_CHUNKS * VAD_CHUNK_MS} ms), give-up at {NOSPEECH_CHUNKS} "
          f"(~{NOSPEECH_MS} ms), safety cap at {MAX_CHUNKS} (~{MAX_UTTERANCE_S} s)")


def main() -> None:
    setup_logging()
    ap = argparse.ArgumentParser(description="Gemma wake+listen+transcribe (Track G step 3)")
    ap.add_argument("--selfcheck", action="store_true",
                    help="verify end-of-speech logic without a mic or models, then exit")
    args = ap.parse_args()
    if args.selfcheck:
        _selfcheck()
        return
    try:
        listen()
    except KeyboardInterrupt:
        print()  # clean newline after ^C


if __name__ == "__main__":
    main()
