"""Track G step 6 (docs/04 §8): the orchestrator — the spec/40 state machine as one daemon.

    IDLE ──wake──▶ LISTENING ──end-of-speech──▶ THINKING ──▶ SPEAKING ─▶ dwell ─▶ IDLE

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
from bridge.broadcaster import (
    Broadcaster, m_error, m_latency, m_mic, m_response, m_state, m_transcript,
)
from bridge.hotkeys import Hotkeys
from bridge.log import setup_logging

log = logging.getLogger("gemma.orchestrator")

# --- interaction timings (spec/40) ---
ANSWER_DWELL_S = 8.0   # FLOOR for how long the answer stays on the island after a turn ends.
                       # The mic is CLOSED throughout — this replaced the old 8 s follow-up
                       # window, which held the mic open and so had to publish `listening`,
                       # wiping the very answer it existed to let you respond to.
ANSWER_DWELL_PER_WORD_S = 0.45  # ...and the per-word scaling on top of that floor. 8 s was
                       # inherited from a SPEECH window and blanked long answers mid-reveal:
                       # the island types at 90 ms/word, so a 200-word answer needs ~20 s
                       # before it has even finished appearing. 0.45 = that reveal cost plus
                       # room to actually read it. Deliberately generous — this is only the
                       # walked-away backstop; a keypress dismisses (STATE, Track P).
WORKING_AFTER_S = 1.4  # 'working' earcon if nothing audible yet — just inside D11's 1.5 s
BARGE_CHUNKS = 4       # sustained speech chunks (~128 ms) to call it a barge-in; with the
                       # low-latency pump the cut lands ≤ 250 ms (spec/40 binding).
                       # ponytail: also the echo-tolerance knob on open speakers (headset
                       # output is the design target); raise it if TTS self-triggers.
MIC_LEVEL_REF = 6000.0  # int16 RMS mapped to a full overlay bar (Contract P 'mic' level).
                        # ponytail: calibration knob — mic-dependent; raise if the bars peg,
                        # lower if they barely move (the physical world needs tuning).


def answer_dwell(reply: str) -> float:
    """How long an answer stays on the island once the turn ends. Scales with length
    because the island *reveals* at a fixed rate — a flat timer blanks a long answer
    while it is still typing itself out (STATE, Track P)."""
    return max(ANSWER_DWELL_S, len(reply.split()) * ANSWER_DWELL_PER_WORD_S)


def capture_over(fired: bool, eos: EndOfSpeech, keyed: bool, auto_end: bool) -> bool:
    """Should a capture stop, given what the VAD just decided? (D20)

    On a keyed turn **the key is the endpoint**: the 1 s silence cut no longer ends the
    turn, so you can pause mid-thought and the mic stays yours until you tap or release.
    Two of `EndOfSpeech`'s three exits survive a key endpoint — "you never said anything"
    and the 30 s runaway cap — and its bare `fired` flag cannot tell the three apart, so
    they are re-read off `eos` here. `auto_end` (spec/70) puts the silence cut back for
    people who would rather not tap twice.
    """
    if not fired:
        return False
    if not keyed or auto_end:
        return True
    return not eos.speech_started or eos.total >= eos.max_chunks


def sentences(text: str) -> int:
    """Count sentences for the speak/hold split. ponytail: M0 heuristic (spec/40) —
    terminator runs; 'Dr.' overcounts. Retired at M0.5 when the model tags spoken/held."""
    return len(re.findall(r"[.!?]+(?=\s|$)", text.strip()))


# Error.kind (spec/20) -> one spoken sentence (spec/40 narration rules).
SPOKEN_ERRORS = {
    "auth": "I can't reach my brain: the API key is missing or rejected.",
    "rate_limit": "I'm being rate limited. Give me a moment and try again.",
    "context": "This conversation got too long for me. Wake me afresh to reset it.",
    "unavailable": "My brain is unreachable right now.",
}


def spoken_error(kind: str) -> str:
    return SPOKEN_ERRORS.get(kind, "Something went wrong on my end.")


class Dismissed(Exception):
    """The dismiss key was pressed — unwind the turn from wherever we are. Raised by any
    state that waits (capture, speaking) and by a brain call the abort seam cut short; the
    single handler in serve() does the tidying, so no state has to know how to clean up
    after the others."""


class BargeIn:
    """Sustained-speech detector for interrupting TTS: N consecutive speech chunks mean
    the user is talking over us — one cough or echo blip must not cut the reply."""

    def __init__(self, chunks: int = BARGE_CHUNKS):
        self.chunks = chunks
        self.run = 0

    def update(self, is_speech: bool) -> bool:
        self.run = self.run + 1 if is_speech else 0
        return self.run >= self.chunks


async def _wait_flag(flag) -> None:
    """Bridge a threading.Event into asyncio. ponytail: a 50 ms poll, not a proper
    loop-aware primitive — the flag is set from the hotkey pump thread, and 50 ms is far
    inside human reaction time for a dismiss."""
    while not flag.is_set():
        await asyncio.sleep(0.05)


async def _drive(brain, session: Session, utterance: str, on_delta=None,
                 abort=None) -> tuple[str, str | None]:
    """Run one brain turn, racing it against the dismiss signal. This is THE abort seam:
    without it a dismiss could not interrupt THINKING, which is exactly when you most want
    to bail (a misheard prompt, a question you have thought better of). Cancelling the task
    closes the stream, so the HTTP request is dropped rather than drained."""
    turn = asyncio.create_task(_collect(brain, session, utterance, on_delta))
    if abort is None:
        return await turn
    watch = asyncio.create_task(_wait_flag(abort))
    done, pending = await asyncio.wait({turn, watch}, return_when=asyncio.FIRST_COMPLETED)
    for p in pending:
        p.cancel()
    if turn in done:
        return turn.result()
    return "", "aborted"


async def _collect(brain, session: Session, utterance: str,
                   on_delta=None) -> tuple[str, str | None]:
    """Drive one Contract-B turn; return (reply_text, error_kind_or_None).
    Generate-then-play (D11): the full reply is needed before TTS, so deltas are only
    streamed to the console and, via on_delta, to the overlay teleprompter (D14)."""
    parts: list[str] = []
    err: str | None = None
    async for ev in brain.converse(session, utterance, []):   # M0: zero tools
        if isinstance(ev, TextDelta):
            parts.append(ev.text)
            if on_delta:
                on_delta(ev.text)
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


def latency_table(trace) -> str:
    """Render per-turn latencies from an event trace against the spec/40 targets.
    Printed at the end of every live session and every replay case (docs/04 §7)."""
    out = [f"{'turn':<6}{'wake->awake':>12}{'eos->feedback':>15}{'eos->word':>11}"
           "   (targets <300 / <1500 / <4000 ms, spec/40)"]
    wake_t = awake = cur = None
    turns: list[dict] = []
    for t, ev, detail in trace:
        if ev == "wake":
            wake_t, awake = t, None
        elif ev == "earcon" and detail == "awake" and wake_t is not None:
            awake = (t - wake_t) * 1000
        elif ev == "eos":
            cur = {"eos": t, "awake": awake, "fb": None, "word": None}
            turns.append(cur)
            awake = None
        elif cur is not None and ev in ("earcon", "speak"):
            if cur["fb"] is None:
                cur["fb"] = (t - cur["eos"]) * 1000
            if ev == "speak" and cur["word"] is None:
                cur["word"] = (t - cur["eos"]) * 1000
    fmt = lambda v: f"{v:.0f}" if v is not None else "-"  # noqa: E731
    for i, r in enumerate(turns, 1):
        out.append(f"{i:<6}{fmt(r['awake']):>12}{fmt(r['fb']):>15}{fmt(r['word']):>11}")
    return "\n".join(out)


class Orchestrator:
    def __init__(self, silence_ms: int = SILENCE_MS, voice: str = VOICE,
                 model: str = DEFAULT_MODEL, brain=None, broadcaster=None,
                 auto_end: bool = False, hotkeys=None):
        self.silence_chunks = (silence_ms + VAD_CHUNK_MS - 1) // VAD_CHUNK_MS
        self.voice = voice
        self.auto_end = auto_end                 # spec/70: end a keyed turn on VAD silence too
        self.hk = hotkeys                        # None under replay/selfcheck: wake word only
        self.brain = brain or ClaudeBrain(model=model)   # injectable: replay's fake brain
        self.synth = synth                               # injectable: replay fakes TTS
        self.bc = broadcaster or Broadcaster()           # Contract P feed; unstarted in replay
        self.trace: list[tuple[float, str, str]] = []    # (t, event, detail) — latency_table
        self.session = Session(id="boot")
        self.shown = ""                         # last thing left on the island -> its dwell
        self.audible = True                     # has this turn produced sound yet?
        self.working = threading.Timer(0, lambda: None)
        self.t_eos = time.perf_counter()        # spec/40 clock: VAD declared the turn over
        self.pump: OutputPump | None = None
        self.mic = None
        self.vad: SileroVAD | None = None

    # orchestrator event -> Contract P 'state' (bridge/broadcaster.py, spec/schemas/status.json).
    # 'listening' is emitted by _capture (mic open); 'speaking'/'error' by _speak (its `state`
    # arg — so an error apology dwells in fault mode, not a bare reply view). 'speak' is
    # trace-only here.
    # 'dismissed' maps to idle: it blanks the island and, through _publish_state, hands the
    # bare Esc binding back to the rest of the system.
    _EVENT_STATE = {"thinking": "thinking", "idle": "idle", "dismissed": "idle"}

    def _ev(self, event: str, detail: str = "", show: str | None = None) -> None:
        """Trace an event (the harness asserts on these), mirror it to the overlay feed
        (Contract P), and print its console line."""
        self.trace.append((time.perf_counter(), event, detail))
        self._broadcast(event, detail)
        if show is not None:
            print(show)

    def _broadcast(self, event: str, detail: str) -> None:
        """Best-effort overlay mirror of a traced event. publish() never blocks/raises."""
        state = self._EVENT_STATE.get(event)
        if state:
            self._publish_state(state)
        elif event == "transcript":
            self.bc.publish(m_transcript(detail))

    def _publish_state(self, name: str) -> None:
        """Publish a Contract P state — and keep the dismiss key armed in step with it.

        Esc is a BARE binding, so it is taken from the rest of the system only while the
        island is on screen and handed straight back at `idle`. Routing every state change
        through here is what makes that automatic: there is no state that can show the
        island without arming Esc, or hide it while still holding the key hostage."""
        self.bc.publish(m_state(name))
        if self.hk is not None:
            self.hk.arm("dismiss", name != "idle")

    def _dismissed(self) -> bool:
        """Has dismiss been pressed since we last looked? Consumes the signal."""
        flag = self._abort_flag()
        if flag is not None and flag.is_set():
            flag.clear()
            return True
        return False

    def _abort_flag(self):
        """The dismiss door's Event, or None when there are no hotkeys (replay, tests)."""
        if self.hk is None:
            return None
        door = self.hk.doors.get("dismiss")
        return door.start if door is not None else None

    # --- feedback bookkeeping (D11: something audible < 1.5 s after end of speech) ---

    def _mark_audible(self, what: str) -> None:
        # ponytail: this check-then-set races the working-timer thread — worst case a
        # duplicate 'feedback' latency line (debug-only, spec/40); not worth a lock for an
        # instrument reading, and the pre-existing double-log is equally benign.
        self.working.cancel()                   # no-op if it already fired
        if not self.audible:
            self.audible = True
            ms = (time.perf_counter() - self.t_eos) * 1000
            self.bc.publish(m_latency("feedback", ms))
            log.info("audible feedback (%s) %.0f ms after end of speech", what, ms)

    def _working_ping(self) -> None:
        # Timer thread — pump.play is thread-safe. THINKING outlived the feedback
        # budget, so the earcon IS the feedback.
        self.pump.play(tone_samples("working"))
        self._ev("earcon", "working")
        self._mark_audible("'working' earcon")

    def _ping(self, name: str) -> None:
        self.pump.play(tone_samples(name))
        self._ev("earcon", name)
        self._mark_audible(f"'{name}' earcon")

    # --- mic helpers ---

    def _flush_mic(self) -> None:
        """Drop mic audio buffered while we weren't reading (THINKING) — stale sound
        must not register as barge-in or follow-up speech."""
        n = self.mic.read_available
        if n:
            self.mic.read(n)

    @staticmethod
    def _mic_level(samples) -> float:
        """RMS of an int16 mic chunk mapped to [0,1] — drives the overlay bars while a
        capture window is open (spec/50 truthful indicator). Whether barge-in monitoring
        during SPEAKING should emit it too is an open decision (STATE, Track P)."""
        import numpy as np
        rms = float(np.sqrt(np.mean(samples.astype(np.float32) ** 2)))
        return min(1.0, rms / MIC_LEVEL_REF)

    def _capture(self, preroll=None, nospeech_ms: int = NOSPEECH_MS, seed=None, door=None):
        """One utterance by VAD. Returns float32 mono audio, or None if nothing said.
        seed = chunks already heard (a barge-in trigger) — the turn starts mid-speech,
        so the VAD keeps its warm state. door = the hotkey that opened this capture, which
        then owns the endpoint (D20, `capture_over`); None on a wake-word turn."""
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
        # BINDING INVARIANT: opening a capture window clears the previous turn first — the
        # island must never show bars over a stale answer. This lives HERE, not in the
        # callers, because capture windows open from two places: serve() (wake or ask key)
        # and _speak() (barge-in, and a keypress mid-reply). The barge-in path used to skip
        # it, which is exactly how bars ended up drawn over the last reply.
        # Redundant when already idle — the reducer treats idle->idle as a no-op.
        self._ev("idle")                            # CLEARS_TURN (teleprompter/decode.py)
        self._dismissed()                           # drop a stale press from a past turn
        self._publish_state("listening")            # island -> bars (mic open)
        try:
            return self._capture_loop(eos, captured, door)
        finally:
            # However this capture ended, the door that opened it is no longer open — the
            # orchestrator is the authority on that, not the press counter (Door.close()).
            if door is not None:
                door.close()

    def _capture_loop(self, eos, captured: list, door):
        """The mic loop itself. Split out only so _capture() can guarantee door.close()
        on every exit — including the Dismissed unwind."""
        import numpy as np

        while True:
            chunk, _ = self.mic.read(VAD_CHUNK)
            samples = chunk[:, 0]
            captured.append(samples)
            if self.bc.started:                     # skip the RMS work when the feed is disabled
                self.bc.publish(m_mic(self._mic_level(samples)))
            if self._dismissed():
                raise Dismissed
            fired = eos.update(self.vad.prob(samples) >= VAD_THRESHOLD)
            if door is not None and door.end.is_set():
                break                               # the key is the endpoint (D20)
            if capture_over(fired, eos, door is not None, self.auto_end):
                break
        if eos.total >= eos.max_chunks:
            log.warning("hit the %d s utterance cap — transcribing what we have",
                        MAX_UTTERANCE_S)
        if not eos.speech_started:
            return None
        self.t_eos = time.perf_counter()
        self._ev("eos")
        return np.concatenate(captured).astype("float32") / 32768.0

    # --- the states ---

    def _turn(self, audio):
        """THINKING → SPEAKING, or held (shown, not spoken), for one utterance. Returns the
        next utterance's audio — only a barge-in produces one now — or None to end the chain,
        after which the answer dwells on the island until IDLE blanks it."""
        self._ev("thinking", show="[thinking]")
        self.audible = False
        self.working = threading.Timer(WORKING_AFTER_S, self._working_ping)
        self.working.daemon = True
        self.working.start()

        text = transcribe(audio)
        if not text:
            self.bc.publish(m_error("I didn't catch that.", "no_transcript"))
            self._ping("error")                 # narration rules: the pipeline broke
            self._ev("no-transcript", show="(no transcript)")
            self.shown = ""                     # nothing to read: the dwell floor is enough
            return None                         # ends the chain; the wake watch resumes
        self._ev("transcript", text, show=f"> {text}")

        reply, err = asyncio.run(_drive(
            self.brain, self.session, text,
            on_delta=lambda d: self.bc.publish(m_response(delta=d)),
            abort=self._abort_flag(),
        ))
        if err == "aborted":
            self._dismissed()                   # consume the signal the race saw
            raise Dismissed
        if err or not reply:
            kind = err or "unknown"
            self.bc.publish(m_error(spoken_error(kind), kind))
            self._ping("error")
            self.shown = spoken_error(kind)     # the apology is what dwells
            return self._speak(self.synth(spoken_error(kind), self.voice), state="error")
        self.bc.publish(m_response(done=True))  # reply text complete on the overlay
        self.shown = reply                      # what the island is displaying -> its dwell

        self.session.history += [{"role": "user", "content": text},
                                 {"role": "assistant", "content": reply}]
        # The hold survives; the "say 'read it'" escape hatch does not. Holding is what stops
        # a long answer being read AT you (spec/40, never lecture uninvited) — it now means
        # SHOWN, not spoken. Whether anything speaks a long answer on request folds into the
        # TTS switch (spec/70), decided with "listen to me".
        if sentences(reply) > 2:
            self._ping("answer-ready")
            self._ev("held", show="[answer shown, not spoken]")
            return None
        return self._speak(self.synth(reply, self.voice))

    def _speak(self, samples, state: str = "speaking"):
        """SPEAKING: play via the pump while watching the mic — user speech cuts TTS
        ≤ 250 ms and becomes the next utterance (spec/40, binding). `state` is the overlay
        mode shown while playing — 'speaking' normally, 'error' while reading an apology so
        the island dwells in fault mode instead of a bare reply view."""
        self._flush_mic()
        self.vad.reset()
        self._publish_state(state)
        self.pump.play(samples)
        self._ev("speak")
        self._mark_audible("speech")
        first_word_ms = (time.perf_counter() - self.t_eos) * 1000
        self.bc.publish(m_latency("first_word", first_word_ms))
        log.info("first spoken word %.0f ms after end of speech", first_word_ms)
        barge = BargeIn()
        recent: deque = deque(maxlen=barge.chunks)
        while self.pump.playing():
            chunk, _ = self.mic.read(VAD_CHUNK)
            samples_in = chunk[:, 0]
            recent.append(samples_in)
            # The ask key is the deliberate version of a barge-in: it cuts the reply and
            # takes the floor immediately. Without this the press only landed once the turn
            # had finished playing, so pressing it to dismiss an answer appeared to do
            # nothing. ponytail: covers SPEAKING only — a press while the brain is still
            # streaming still waits, because _collect() owns that window inside asyncio.
            # Add cancellation there if the wait is felt.
            if self._dismissed():
                raise Dismissed                 # stop talking; serve() cuts the pump
            keyed = self._pressed()
            if keyed is not None:
                t0 = time.perf_counter()
                self.pump.cut()
                self._enter(keyed, t0)          # same entrance as serve(): traced + earcon
                return self._capture(door=keyed)
            if barge.update(self.vad.prob(samples_in) >= VAD_THRESHOLD):
                self.pump.cut()
                self._ev("barge-in", show="[barge-in]")
                return self._capture(seed=list(recent))
        return None

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

    def _enter(self, door, t0: float) -> None:
        """The entrance ritual, wherever a turn is opened from: trace the entrance so the
        latency table can measure press/wake -> indication (spec/40), and sound the `awake`
        earcon so the press is audibly acknowledged.

        Every path that opens a turn goes through here. The two that did NOT are how the
        barge-in path came to draw bars over a stale answer, and how key-interrupt turns
        came to have no press-latency reading at all — 60% of the first acceptance run."""
        self._ev("wake", "key" if door else "phrase",
                 show=f"[{'ask key' if door else 'wake'}] listening...")
        self.pump.play(tone_samples("awake"))    # < 300 ms: enqueued immediately
        self._ev("earcon", "awake")
        log.info("awake earcon %.0f ms after %s", (time.perf_counter() - t0) * 1000,
                 "keypress" if door else "wake detect")

    def _pressed(self):
        """The ask door if its hotkey just opened a capture, else None. Also drains the
        dictate door: it is registered so the binding is proven end to end, but its
        pipeline is Track D's and does not exist yet."""
        if self.hk is None:
            return None
        d = self.hk.doors.get("dictate")
        if d is not None and d.start.is_set():
            d.start.clear()
            d.end.clear()
            log.info("dictate hotkey pressed — that door is not built yet (Track D)")
        ask = self.hk.doors.get("ask")
        if ask is not None and ask.start.is_set():
            ask.start.clear()           # `end` is the module's to clear, on the next press
            return ask
        return None

    def serve(self, mic, pump, wake_model) -> None:
        """The IDLE→wake→turn-chain loop against a mic, pump and wake model — real
        devices from run(), fakes from the replay harness (tests/replay.py)."""
        self.pump, self.mic = pump, mic
        ring: deque = deque(maxlen=BUFFER_BLOCKS)   # ≤3 s pre-trigger audio, RAM only (spec/50)
        # When the last turn's answer should stop being shown. `idle` both clears the turn and
        # hides the island, so publishing it the moment a turn ends would blank the answer as
        # it finished arriving. The wake watch below runs THROUGHOUT the dwell — this delays
        # the blanking, never Gemma's readiness.
        blank_at: float | None = None
        while True:
            # IDLE: wake watch
            block, _ = mic.read(BLOCK_SAMPLES)
            frame = block[:, 0]
            ring.append(frame)
            if blank_at is not None and time.perf_counter() >= blank_at:
                blank_at = None
                self._ev("idle", show="[idle]")
            # Two entrances to the same door (D20): the ask hotkey and the wake phrase.
            door = self._pressed()
            if door is None and not any(s >= THRESHOLD
                                        for s in wake_model.predict(frame).values()):
                continue
            t_wake = time.perf_counter()
            blank_at = None                     # a new turn supersedes the dwell; _capture()
                                                # does the clearing, for every entrance alike
            self._enter(door, t_wake)
            # ponytail: fresh history each wake-chain — whether it should persist
            # across wakes is an open question (parked; STATE), so it dies at IDLE.
            self.session = Session(id=time.strftime("%H%M%S"))

            try:
                utt = self._capture(preroll=list(ring)[-PREROLL_BLOCKS:], door=door)
                ring.clear()
                if utt is None:
                    self._ev("nothing-heard", show="[nothing heard]")
                while utt is not None:          # the turn chain: barge-ins
                    utt = self._turn(utt)
            except Dismissed:
                # One handler for every state (spec/40): whatever was in flight — an open
                # mic, a streaming brain call, TTS mid-sentence — stops here.
                self.working.cancel()
                pump.cut()
                self.shown = ""
                if self.hk is not None:
                    self.hk.reset()             # no door left mid-toggle by the abandon
                self._ev("dismissed", show="[dismissed]")
                self._flush_wake(wake_model)
                blank_at = None                 # nothing left on the island to dwell
                continue
            self._flush_wake(wake_model)        # else the old phrase re-triggers
            # Leave the answer up long enough to reveal AND read (a keypress cuts it short).
            blank_at = time.perf_counter() + answer_dwell(self.shown)

    def run(self) -> None:
        import numpy as np
        import sounddevice as sd
        import openwakeword.utils
        from openwakeword.model import Model

        self.bc.start()                          # Contract P feed up (crash-isolated; a busy
                                                 # port just disables it — never fatal)
        t0 = time.perf_counter()
        log.info("warm-up: loading wake, VAD, STT and TTS models...")
        openwakeword.utils.download_models([WAKE_MODEL])
        wake_model = Model(wakeword_models=[WAKE_MODEL], inference_framework="onnx")
        self.vad = SileroVAD(_silero_model_path())
        transcribe(np.zeros(SAMPLE_RATE // 2, dtype=np.float32))  # loads whisper + GPU warm-up
        synth("ready")                                            # loads Kokoro; discarded
        log.info("warm-up done in %.1f s", time.perf_counter() - t0)

        with OutputPump() as pump, \
             sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16",
                            blocksize=0) as mic:
            # After warm-up, so a press during the 22 s model load cannot queue a turn
            # that fires the instant we start serving.
            self.hk = self.hk or Hotkeys()
            self.hk.start()
            log.info("ready — press %s or say '%s' (Ctrl-C to stop)",
                     self.hk.doors["ask"].combo, WAKE_MODEL.replace("_", " "))
            self.serve(mic, pump, wake_model)


class FakeReply:
    """A Contract-B brain that answers instantly — selfcheck only."""

    def __init__(self, text: str):
        self.text = text

    async def converse(self, session, utterance, tools):
        yield TextDelta(self.text)
        yield Done()


def _selfcheck() -> None:
    """No mic/models/network: the orchestrator's pure decision logic. (End-of-speech
    timing is listen.py's selfcheck; pump buffer discipline is speak.py's.)"""
    # speak/hold split (spec/40 narration heuristic)
    assert sentences("Yes.") == 1
    assert sentences("It is 3 pm. Tokyo is nine hours ahead.") == 2
    assert sentences("One. Two! Three?") == 3
    assert sentences("no terminator") == 0            # still spoken: 0 <= 2
    assert sentences("Wait... sure.") == 2            # a '...' run counts once


    # capture endpoint (D20): the key owns a keyed turn; the wake path is unchanged
    spoke = EndOfSpeech(silence_chunks=2, max_chunks=100, nospeech_chunks=3)
    for f in (True, False):                           # speech, then a silence run
        spoke.update(f)
    assert capture_over(True, spoke, keyed=False, auto_end=False)   # wake: silence ends it
    assert not capture_over(True, spoke, keyed=True, auto_end=False)  # keyed: it does not
    assert capture_over(True, spoke, keyed=True, auto_end=True)     # unless auto_end is on
    assert not capture_over(False, spoke, keyed=False, auto_end=False)  # VAD hasn't fired

    quiet = EndOfSpeech(silence_chunks=2, max_chunks=100, nospeech_chunks=3)
    assert not any(quiet.update(False) for _ in range(2))
    assert quiet.update(False)                        # nothing said at all -> give up,
    assert capture_over(True, quiet, keyed=True, auto_end=False)     # even on a keyed turn

    capped = EndOfSpeech(silence_chunks=99, max_chunks=4, nospeech_chunks=99)
    assert not any(capped.update(True) for _ in range(3))
    assert capped.update(True)                        # 30 s runaway cap survives a key
    assert capture_over(True, capped, keyed=True, auto_end=False)

    # answer dwell scales with what is on screen, and never dips under the floor
    assert answer_dwell("") == ANSWER_DWELL_S
    assert answer_dwell("Yes.") == ANSWER_DWELL_S                  # short: floor wins
    assert answer_dwell("word " * 200) > 20                        # must outlast the reveal
    assert answer_dwell("word " * 200) > answer_dwell("word " * 50)

    # BINDING INVARIANT: a capture window clears the previous turn BEFORE the mic opens,
    # whichever entrance opened it. Regressing this draws the mic bars over the last reply
    # (it did: the barge-in path skipped the clear, which lived in serve()).
    import numpy as np

    class _Rec:                                       # stands in for the Contract P feed
        started = False
        def __init__(self): self.states = []
        def publish(self, m):
            if m.get("type") == "state":
                self.states.append(m["state"])

    class _SilentMic:
        read_available = 0
        def read(self, n): return np.zeros((n, 1), dtype=np.int16), False

    class _QuietVad:
        def reset(self): pass
        def prob(self, s): return 0.0

    probe = Orchestrator(brain=object(), broadcaster=_Rec())
    probe.mic, probe.vad = _SilentMic(), _QuietVad()
    assert probe._capture(nospeech_ms=64) is None      # silence -> gives up, no transcript
    assert probe.bc.states[:2] == ["idle", "listening"], probe.bc.states

    # the abort seam: a dismiss must cut a brain call that is still streaming, not wait it
    # out. A brain that never yields stands in for "slow first token" — the hardest case.
    class _Hanging:
        async def converse(self, session, utterance, tools):
            await asyncio.sleep(30)
            yield TextDelta("should never arrive")   # pragma: no cover

    flag = threading.Event()
    threading.Timer(0.15, flag.set).start()
    t0 = time.perf_counter()
    reply, err = asyncio.run(_drive(_Hanging(), Session(id="t"), "hi", abort=flag))
    assert (reply, err) == ("", "aborted"), (reply, err)
    assert time.perf_counter() - t0 < 5, "abort must not wait for the brain"

    # with no abort flag the same call runs normally (replay/selfcheck path)
    reply, err = asyncio.run(_drive(FakeReply("Fine."), Session(id="t"), "hi"))
    assert (reply, err) == ("Fine.", None), (reply, err)

    # barge-in: only sustained speech triggers
    b = BargeIn(chunks=4)
    assert not any(b.update(x) for x in [True, True, False, True, True, True])
    assert b.update(True)                             # 4th consecutive chunk fires

    # every shared Contract-B error kind has a short spoken line
    for kind in ("auth", "rate_limit", "context", "unavailable",
                 "malformed_tool_call", "unknown"):
        line = spoken_error(kind)
        assert line and sentences(line) <= 2, kind

    # latency table: two turns — one with wake+working+speak, one speak-only
    tbl = latency_table([(0.0, "wake", ""), (0.1, "earcon", "awake"), (1.0, "eos", ""),
                         (2.2, "earcon", "working"), (3.5, "speak", ""),
                         (10.0, "eos", ""), (10.8, "speak", "")])
    lines = tbl.splitlines()
    assert len(lines) == 3, tbl
    assert "100" in lines[1] and "1200" in lines[1] and "2500" in lines[1], lines[1]
    assert lines[2].count("800") == 2 and "-" in lines[2], lines[2]

    print("selfcheck OK: speak/hold split, capture endpoint, barge-in counter, "
          "error lines, latency table")


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
    ap.add_argument("--auto-end", action="store_true",
                    help="end a hotkey turn on VAD silence too, instead of a second tap (spec/70)")
    args = ap.parse_args()
    if args.selfcheck:
        _selfcheck()
        return
    orch = Orchestrator(args.silence_ms, args.voice, args.model, auto_end=args.auto_end)
    try:
        orch.run()
    except KeyboardInterrupt:
        print()  # clean newline after ^C
        if orch.trace:
            print(latency_table(orch.trace))   # the session's metrics (docs/04 §7)


if __name__ == "__main__":
    main()
