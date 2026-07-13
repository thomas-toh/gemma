"""Track G step 6 (docs/04 §8): the orchestrator — the spec/40 state machine as one daemon.

    IDLE ──wake──▶ LISTENING ──end-of-speech──▶ THINKING ──▶ SPEAKING ─▶ FOLLOW-UP ─▶ IDLE

Wires steps 2–5 together: wake (openWakeWord) → listen (Silero VAD + faster-whisper) →
think (Contract B brain) → speak (earcons + Kokoro through a persistent warm output
stream — the spec/40 BT keep-alive). Barge-in (binding): speech during SPEAKING cuts TTS
and becomes the next utterance. This is the only module that knows the others exist
(docs/04 §2) — audio and brains meet here through the contract types.

Run:
    python -m bridge.orchestrator              # the M0 loop, live (mic + speakers)
    python -m bridge.orchestrator --selfcheck  # no mic/models/network: decision logic only
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import re
import threading
import time
from collections import deque

from bridge.audio.wake import (
    SAMPLE_RATE, BLOCK_SAMPLES, BUFFER_BLOCKS, WAKE_MODEL, THRESHOLD,
)
from bridge.audio.listen import (
    VAD_CHUNK, VAD_CHUNK_MS, VAD_THRESHOLD, SILENCE_MS, NOSPEECH_MS, PREROLL_BLOCKS,
    MAX_UTTERANCE_S, EndOfSpeech, SileroVAD, _silero_model_path, transcribe,
)
from bridge.audio.speak import VOICE, OutputPump, synth, tone_samples
from bridge.brains.base import Done, Error, Session, TextDelta, ToolCall
from bridge.brains.claude import DEFAULT_MODEL, ClaudeBrain
from bridge.log import setup_logging

log = logging.getLogger("gemma.orchestrator")

# --- interaction timings (spec/40) ---
FOLLOWUP_MS = 8000     # follow-up window: speech accepted without re-wake
WORKING_AFTER_S = 1.4  # 'working' earcon if nothing audible yet — just inside D11's 1.5 s
BARGE_CHUNKS = 4       # sustained speech chunks (~128 ms) to call it a barge-in; with the
                       # low-latency pump the cut lands ≤ 250 ms (spec/40 binding).
                       # ponytail: also the echo-tolerance knob on open speakers (headset
                       # output is the design target); raise it if TTS self-triggers.


def sentences(text: str) -> int:
    """Count sentences for the speak/hold split. ponytail: M0 heuristic (spec/40) —
    terminator runs; 'Dr.' overcounts. Retired at M0.5 when the model tags spoken/held."""
    return len(re.findall(r"[.!?]+(?=\s|$)", text.strip()))


def wants_readback(text: str) -> bool:
    """'read it' in the follow-up window speaks a held answer (spec/40).
    ponytail: keyword match — STT renders the phrase many ways."""
    return bool(re.search(r"\bread\b", text, re.IGNORECASE))


# Error.kind (spec/20) -> one spoken sentence (spec/40 narration rules).
SPOKEN_ERRORS = {
    "auth": "I can't reach my brain: the API key is missing or rejected.",
    "rate_limit": "I'm being rate limited. Give me a moment and try again.",
    "context": "This conversation got too long for me. Wake me afresh to reset it.",
    "unavailable": "My brain is unreachable right now.",
}


def spoken_error(kind: str) -> str:
    return SPOKEN_ERRORS.get(kind, "Something went wrong on my end.")


class BargeIn:
    """Sustained-speech detector for interrupting TTS: N consecutive speech chunks mean
    the user is talking over us — one cough or echo blip must not cut the reply."""

    def __init__(self, chunks: int = BARGE_CHUNKS):
        self.chunks = chunks
        self.run = 0

    def update(self, is_speech: bool) -> bool:
        self.run = self.run + 1 if is_speech else 0
        return self.run >= self.chunks


async def _collect(brain, session: Session, utterance: str) -> tuple[str, str | None]:
    """Drive one Contract-B turn; return (reply_text, error_kind_or_None).
    Generate-then-play (D11): the full reply is needed before TTS, so deltas are
    only streamed to the console."""
    parts: list[str] = []
    err: str | None = None
    async for ev in brain.converse(session, utterance, []):   # M0: zero tools
        if isinstance(ev, TextDelta):
            parts.append(ev.text)
            print(ev.text, end="", flush=True)
        elif isinstance(ev, ToolCall):   # impossible with zero tools; loud if it happens
            log.warning("ignoring tool call %r at M0", ev.name)
        elif isinstance(ev, Done):
            log.info("brain done: %s", ev.usage)
        elif isinstance(ev, Error):
            err = ev.kind
            log.error("brain error/%s: %s", ev.kind, ev.detail)
    if parts:
        print()
    return "".join(parts).strip(), err


class Orchestrator:
    def __init__(self, silence_ms: int = SILENCE_MS, voice: str = VOICE,
                 model: str = DEFAULT_MODEL):
        self.silence_chunks = (silence_ms + VAD_CHUNK_MS - 1) // VAD_CHUNK_MS
        self.voice = voice
        self.brain = ClaudeBrain(model=model)
        self.session = Session(id="boot")
        self.held: str | None = None            # long answer awaiting "read it"
        self.audible = True                     # has this turn produced sound yet?
        self.working = threading.Timer(0, lambda: None)
        self.t_eos = time.perf_counter()        # spec/40 clock: VAD declared the turn over
        self.pump: OutputPump | None = None
        self.mic = None
        self.vad: SileroVAD | None = None

    # --- feedback bookkeeping (D11: something audible < 1.5 s after end of speech) ---

    def _mark_audible(self, what: str) -> None:
        self.working.cancel()                   # no-op if it already fired
        if not self.audible:
            self.audible = True
            log.info("audible feedback (%s) %.0f ms after end of speech",
                     what, (time.perf_counter() - self.t_eos) * 1000)

    def _working_ping(self) -> None:
        # Timer thread — pump.play is thread-safe. THINKING outlived the feedback
        # budget, so the earcon IS the feedback.
        self.pump.play(tone_samples("working"))
        self._mark_audible("'working' earcon")

    def _ping(self, name: str) -> None:
        self.pump.play(tone_samples(name))
        self._mark_audible(f"'{name}' earcon")

    # --- mic helpers ---

    def _flush_mic(self) -> None:
        """Drop mic audio buffered while we weren't reading (THINKING) — stale sound
        must not register as barge-in or follow-up speech."""
        n = self.mic.read_available
        if n:
            self.mic.read(n)

    def _capture(self, preroll=None, nospeech_ms: int = NOSPEECH_MS, seed=None):
        """One utterance by VAD. Returns float32 mono audio, or None if nothing said.
        seed = chunks already heard (a barge-in trigger) — the turn starts mid-speech,
        so the VAD keeps its warm state."""
        import numpy as np

        if seed is None:
            self.vad.reset()
        eos = EndOfSpeech(silence_chunks=self.silence_chunks,
                          nospeech_chunks=max(1, nospeech_ms // VAD_CHUNK_MS))
        captured: list = []
        if preroll:
            captured.append(np.concatenate(preroll))
        for s in seed or []:
            captured.append(s)
            eos.update(True)
        while True:
            chunk, _ = self.mic.read(VAD_CHUNK)
            samples = chunk[:, 0]
            captured.append(samples)
            if eos.update(self.vad.prob(samples) >= VAD_THRESHOLD):
                break
        if eos.total >= eos.max_chunks:
            log.warning("hit the %d s utterance cap — transcribing what we have",
                        MAX_UTTERANCE_S)
        if not eos.speech_started:
            return None
        self.t_eos = time.perf_counter()
        return np.concatenate(captured).astype("float32") / 32768.0

    # --- the states ---

    def _turn(self, audio):
        """THINKING → SPEAKING/held → FOLLOW-UP for one utterance. Returns the next
        utterance's audio (from follow-up or barge-in), or None — the chain ends."""
        print("[thinking]")
        self.audible = False
        self.working = threading.Timer(WORKING_AFTER_S, self._working_ping)
        self.working.daemon = True
        self.working.start()

        text = transcribe(audio)
        if not text:
            self._ping("error")                 # narration rules: the pipeline broke
            print("(no transcript)")
            return self._followup()
        print(f"> {text}")

        if self.held and wants_readback(text):
            held, self.held = self.held, None
            return self._speak(synth(held, self.voice))

        reply, err = asyncio.run(_collect(self.brain, self.session, text))
        if err or not reply:
            self._ping("error")
            return self._speak(synth(spoken_error(err or "unknown"), self.voice))

        self.session.history += [{"role": "user", "content": text},
                                 {"role": "assistant", "content": reply}]
        self.held = None
        if sentences(reply) > 2:                # spec/40: long answers held, never lectured
            self._ping("answer-ready")
            self.held = reply
            print("[answer held — say 'read it']")
            return self._followup()
        return self._speak(synth(reply, self.voice))

    def _speak(self, samples):
        """SPEAKING: play via the pump while watching the mic — user speech cuts TTS
        ≤ 250 ms and becomes the next utterance (spec/40, binding)."""
        self._flush_mic()
        self.vad.reset()
        self.pump.play(samples)
        self._mark_audible("speech")
        log.info("first spoken word %.0f ms after end of speech",
                 (time.perf_counter() - self.t_eos) * 1000)
        barge = BargeIn()
        recent: deque = deque(maxlen=barge.chunks)
        while self.pump.playing():
            chunk, _ = self.mic.read(VAD_CHUNK)
            samples_in = chunk[:, 0]
            recent.append(samples_in)
            if barge.update(self.vad.prob(samples_in) >= VAD_THRESHOLD):
                self.pump.cut()
                print("[barge-in]")
                return self._capture(seed=list(recent))
        return self._followup()

    def _followup(self):
        """FOLLOW-UP: 8 s window, mic open, no re-wake (spec/40). None ends the chain."""
        print("[follow-up window]")
        self._flush_mic()
        return self._capture(nospeech_ms=FOLLOWUP_MS)

    # --- the daemon ---

    @staticmethod
    def _flush_wake(wake_model) -> None:
        """openWakeWord keeps a ~2 s feature window. Once wake fires we stop feeding it
        (turns read the mic for VAD instead), so the trigger phrase would still sit in
        that window when IDLE resumes — and re-fire, forever. Push silence through the
        window and clear the score buffer before watching for wake again."""
        import numpy as np
        zero = np.zeros(BLOCK_SAMPLES, dtype=np.int16)
        for _ in range(BUFFER_BLOCKS):          # ~3 s of silence: full window turnover
            wake_model.predict(zero)
        wake_model.reset()

    def run(self) -> None:
        import numpy as np
        import sounddevice as sd
        import openwakeword.utils
        from openwakeword.model import Model

        t0 = time.perf_counter()
        log.info("warm-up: loading wake, VAD, STT and TTS models...")
        openwakeword.utils.download_models([WAKE_MODEL])
        wake_model = Model(wakeword_models=[WAKE_MODEL], inference_framework="onnx")
        self.vad = SileroVAD(_silero_model_path())
        transcribe(np.zeros(SAMPLE_RATE // 2, dtype=np.float32))  # loads whisper + GPU warm-up
        synth("ready")                                            # loads Kokoro; discarded
        log.info("warm-up done in %.1f s", time.perf_counter() - t0)

        ring: deque = deque(maxlen=BUFFER_BLOCKS)   # ≤3 s pre-trigger audio, RAM only (spec/50)
        with OutputPump() as pump, \
             sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                            blocksize=0) as mic:
            self.pump, self.mic = pump, mic
            log.info("ready — say '%s' (Ctrl-C to stop)", WAKE_MODEL.replace("_", " "))
            while True:
                # IDLE: wake watch
                block, _ = mic.read(BLOCK_SAMPLES)
                frame = block[:, 0]
                ring.append(frame)
                if not any(s >= THRESHOLD for s in wake_model.predict(frame).values()):
                    continue
                t_wake = time.perf_counter()
                pump.play(tone_samples("awake"))    # < 300 ms: enqueued immediately
                log.info("awake earcon %.0f ms after wake detect",
                         (time.perf_counter() - t_wake) * 1000)
                print("[wake] listening...")
                # ponytail: fresh history each wake-chain — whether it should persist
                # across wakes is an open question (parked; STATE), so it dies at IDLE.
                self.session = Session(id=time.strftime("%H%M%S"))
                self.held = None

                utt = self._capture(preroll=list(ring)[-PREROLL_BLOCKS:])
                ring.clear()
                if utt is None:
                    print("[nothing heard]")
                while utt is not None:              # the turn chain: follow-ups, barge-ins
                    utt = self._turn(utt)
                self._flush_wake(wake_model)        # else the old phrase re-triggers
                print("[idle]")


def _selfcheck() -> None:
    """No mic/models/network: the orchestrator's pure decision logic. (End-of-speech
    timing is listen.py's selfcheck; pump buffer discipline is speak.py's.)"""
    # speak/hold split (spec/40 narration heuristic)
    assert sentences("Yes.") == 1
    assert sentences("It is 3 pm. Tokyo is nine hours ahead.") == 2
    assert sentences("One. Two! Three?") == 3
    assert sentences("no terminator") == 0            # still spoken: 0 <= 2
    assert sentences("Wait... sure.") == 2            # a '...' run counts once

    # readback matcher
    assert wants_readback("read it")
    assert wants_readback("Please read it out.")
    assert wants_readback("Read that back to me")
    assert not wants_readback("what's the weather")
    assert not wants_readback("I'm ready")            # \b: no match inside 'ready'

    # barge-in: only sustained speech triggers
    b = BargeIn(chunks=4)
    assert not any(b.update(x) for x in [True, True, False, True, True, True])
    assert b.update(True)                             # 4th consecutive chunk fires

    # every shared Contract-B error kind has a short spoken line
    for kind in ("auth", "rate_limit", "context", "unavailable",
                 "malformed_tool_call", "unknown"):
        line = spoken_error(kind)
        assert line and sentences(line) <= 2, kind

    print("selfcheck OK: speak/hold split, readback match, barge-in counter, error lines")


def main() -> None:
    setup_logging()
    ap = argparse.ArgumentParser(description="Gemma orchestrator — the M0 loop (Track G step 6)")
    ap.add_argument("--selfcheck", action="store_true",
                    help="verify decision logic without mic, models or network, then exit")
    ap.add_argument("--silence-ms", type=int, default=SILENCE_MS,
                    help=f"end-of-speech silence in ms (default {SILENCE_MS}); tune by ear")
    ap.add_argument("--voice", default=VOICE, help=f"Kokoro voice (default {VOICE})")
    ap.add_argument("--model", default=DEFAULT_MODEL,
                    help=f"brain model id (default {DEFAULT_MODEL}; env GEMMA_BRAIN_MODEL)")
    args = ap.parse_args()
    if args.selfcheck:
        _selfcheck()
        return
    try:
        Orchestrator(args.silence_ms, args.voice, args.model).run()
    except KeyboardInterrupt:
        print()  # clean newline after ^C


if __name__ == "__main__":
    main()
