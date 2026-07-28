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
import os
import re
import threading
import time
from collections import deque
from dataclasses import replace

from bridge.audio.wake import (
    SAMPLE_RATE, BLOCK_SAMPLES, BUFFER_BLOCKS, WAKE_MODEL, THRESHOLD,
)
from bridge.audio.listen import (
    VAD_CHUNK, VAD_CHUNK_MS, VAD_THRESHOLD, SILENCE_MS, NOSPEECH_MS, PREROLL_BLOCKS,
    MAX_UTTERANCE_S, MAX_CHUNKS, DICTATION_MAX_CHUNKS, EndOfSpeech, SileroVAD,
    _silero_model_path, transcribe,
)
from bridge.audio.speak import VOICE, OutputPump, earcon_samples, synth
from bridge.brains.base import Done, Error, Session, TextDelta, ToolCall, transform
from bridge.brains.claude import ClaudeBrain
from bridge.brains.providers import build_brain
from bridge.brains import router
from bridge.broadcaster import (
    Broadcaster, m_error, m_latency, m_mic, m_response, m_state, m_transcript,
)
from bridge.hotkeys import Hotkeys
from bridge.log import setup_logging
from bridge.paste import paste_text
from bridge.tools import execute as run_tool, tool_specs
from bridge import settings

log = logging.getLogger("gemma.orchestrator")

# --- interaction timings (spec/40) ---
# The answer dwell is NOT here any more (D24). The daemon spent two revisions guessing how
# long an answer needed to stay up — a floor, then a per-word scaling — because it was timing
# a reveal it could not see: the island types at a fixed rate, so the daemon was estimating
# the overlay's own animation. It now publishes `idle` the moment it is free and the island
# decides when to stop showing, which is the only place the reveal state exists.
BARGE_CHUNKS = 4       # sustained speech chunks (~128 ms) to call it a barge-in; with the
                       # low-latency pump the cut lands ≤ 250 ms (spec/40 binding).
                       # ponytail: also the echo-tolerance knob on open speakers (headset
                       # output is the design target); raise it if TTS self-triggers.
MIC_LEVEL_REF = 6000.0  # int16 RMS mapped to a full overlay bar (Contract P 'mic' level).
                        # ponytail: calibration knob — mic-dependent; raise if the bars peg,
                        # lower if they barely move (the physical world needs tuning).

# The daemon's pre-router default brain model. It lives HERE, not in an adapter: the adapters
# carry no model preference (D30 agnosticism pass), so the choice of what to run when nothing
# else says belongs to the caller. Until spec/20's router lands, the orchestrator constructs B1
# directly (see __init__), so this is necessarily a Claude model — a Groq id would fail on B1.
# When the router arrives it reads the primary provider + model from settings and this goes away.
# ponytail: env override until settings-driven selection exists (STATE, M0-close gate).
DAEMON_MODEL = os.environ.get("GEMMA_BRAIN_MODEL", "claude-opus-4-8")

# Dictation cleanup (spec/60, D15/S-06): Groq by default — cloud, fast, cheap, and the key is
# already in the credential store. The cleanup ROLE is meant to be settings-configurable
# (spec/70), but that plumbing is unbuilt (settings.json `cleanup_dictation` is built:false), so
# these are the stopgap, env-overridable like DAEMON_MODEL. Must be an OpenAI-wire provider for
# now — build_brain picks the adapter by wire, so pointing this at Anthropic would work too, but
# a small fast model is the point of cleanup.
# ponytail: replace with the settings-driven cleanup-role selection when spec/70 lands.
CLEANUP_PROVIDER = os.environ.get("GEMMA_CLEANUP_PROVIDER", "groq")
CLEANUP_MODEL = os.environ.get("GEMMA_CLEANUP_MODEL", "llama-3.1-8b-instant")

# The dictation cleanup instruction (spec/60) — the "transform, never answer" task for `transform`
# (D12/D15). The editing rules are adapted from VoiceInk's enhancement prompt (see the 2026-07-18
# review): fix, don't rewrite, and handle the two things a one-line "clean it up" misses — spoken
# self-corrections ("scratch that") and spoken punctuation/layout cues. Context injection (selected
# text / clipboard / screen) is deliberately NOT here — that is the separate #3 lift.
# ponytail: a code constant until the cleanup role is user-configurable (spec/70, VoiceInk lets you
# edit this); the guardrail against answering lives in TRANSFORM_SYSTEM, not here.
DICTATION_CLEANUP = (
    "Clean up this transcript of dictated speech. This is a LIGHT CLEANUP, not a rewrite: stay as "
    "close to the speaker's actual words as you can and change as little as possible.\n"
    "DO:\n"
    "- Fix clear transcription errors, punctuation, capitalisation, grammar and spelling.\n"
    "- Remove filler words (um, uh, like, you know), stutters, repeated words and false starts.\n"
    "- Apply spoken self-corrections: when the speaker abandons wording with a cue like \"scratch "
    "that\", \"no, wait\", \"I mean\" or \"actually\", drop the abandoned words and keep the "
    "correction.\n"
    "- Convert spoken punctuation and layout cues into marks and layout, then remove the cue words "
    "— e.g. \"full stop\"/\"period\", \"comma\", \"question mark\", \"new line\", \"new paragraph\" "
    "— but only when the speaker clearly means the punctuation, not the literal word (\"a period of "
    "rest\", \"a dash of salt\" stay as written).\n"
    "- When the speaker spells a word out letter by letter (\"S. I. L. E.\" or \"S I L E\"), join "
    "the letters into the single intended word or acronym (SILE), not separate tokens.\n"
    "DO NOT (this is cleanup, not rewriting):\n"
    "- Do not add, drop or substitute words beyond the fixes above; never insert words the speaker "
    "did not say. No new qualifiers or intensifiers — \"that's the idea\" must NOT become \"that's "
    "the main idea\".\n"
    "- Do not change the meaning, the emphasis, or how strongly a point is made.\n"
    "- Do not summarise, expand, restyle, reorder, translate, or answer anything.\n"
    "- Keep the speaker's own structure; do not impose paragraphs beyond what their pauses and cues "
    "indicate.\n"
    "- If the dictation is itself a question or request, clean it up as text; never answer or act on it."
)


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
    # B1 no longer emits 'context' (B-02) — kept for other adapters. Door-neutral wording
    # (was "Wake me afresh", wake-word framing for a product whose wake word is off by default).
    "context": "This conversation got too long for me. Start a new turn to reset me.",
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
                 abort=None, tools=None, execute=None) -> tuple[str, str | None]:
    """Run one brain turn, racing it against the dismiss signal. This is THE abort seam:
    without it a dismiss could not interrupt THINKING, which is exactly when you most want
    to bail (a misheard prompt, a question you have thought better of). Cancelling the task
    closes the stream, so the HTTP request is dropped rather than drained."""
    turn = asyncio.create_task(_collect(brain, session, utterance, on_delta, tools, execute))
    if abort is None:
        return await turn
    watch = asyncio.create_task(_wait_flag(abort))
    done, pending = await asyncio.wait({turn, watch}, return_when=asyncio.FIRST_COMPLETED)
    for p in pending:
        p.cancel()
    if turn in done:
        return turn.result()
    # Wait for the cancelled turn to finish unwinding before returning. Its `finally` is what
    # closes the provider's stream (below), and with one long-lived loop nothing else will:
    # `asyncio.run` used to shut down abandoned async generators at turn end, and there is no
    # per-turn `asyncio.run` any more. Without this the abort returns while the HTTP request
    # is still open, and "dismiss drops the request" quietly becomes "dismiss stops reading it".
    await asyncio.gather(turn, return_exceptions=True)
    return "", "aborted"


# The tool loop's round ceiling (spec/30): a tool-happy model that never settles on an answer is
# stopped, not looped forever. Five is generous for the Tier-1 tools — most turns take one round
# to call a tool and one to speak the result.
# ponytail: a flat cap; raise it if a legitimate multi-step task ever hits it.
MAX_TOOL_ROUNDS = 5


async def _one_round(brain, session: Session, tools):
    """One Contract-B round: collect the round's text (+ a console dev trace), collect tool calls,
    map errors. Returns (text, calls, error_kind_or_None, malformed). Deliberately does NOT stream
    to the overlay: a tool round's text is the model narrating that it is about to call a tool, and
    only the final answering round should reach the island (the streaming is _collect's job now).
    The utterance is always "" — the turn's input is already in session.history (the real user
    message on the first round, the tool results on later ones), so a round never appends a user
    turn of its own (spec/20 continue path).

    Closes the generator deterministically (spec/20): an abort drops the provider request AT the
    cancel through the adapter's `finally`, rather than leaving it draining tokens nobody sees."""
    parts: list[str] = []
    calls: list[ToolCall] = []
    err: str | None = None
    malformed = False
    stream = brain.converse(session, "", tools)
    try:
        async for ev in stream:
            if isinstance(ev, TextDelta):
                parts.append(ev.text)
                print(ev.text, end="", flush=True)   # console dev trace of every round
            elif isinstance(ev, ToolCall):
                calls.append(ev)
            elif isinstance(ev, Done):
                log.info("brain done: %s", ev.usage)
            elif isinstance(ev, Error):
                if ev.kind == "malformed_tool_call":
                    malformed = True          # spec/20: the tool loop owns the one retry
                else:
                    err = ev.kind
                log.error("brain error/%s: %s", ev.kind, ev.detail)
    finally:
        await stream.aclose()
    if parts:
        print()
    return "".join(parts).strip(), calls, err, malformed


async def _collect(brain, session: Session, utterance: str, on_delta=None,
                   tools=None, execute=None) -> tuple[str, str | None]:
    """Drive one assistant turn to a spoken answer, running the Contract T tool loop in between
    (spec/30): the brain may ask for tools, the orchestrator executes them and feeds the results
    back, and this repeats until the brain answers with no further tool call.

    Returns (reply_text, error_kind_or_None). History is committed to `session.history` ONLY on
    success — a failed or aborted turn leaves it untouched, so the next turn never opens with a
    dangling user message (the invariant the old post-turn append protected).

    Generate-then-play (D11): only the FINAL answering round reaches the overlay (via on_delta) —
    the tool-use preamble rounds stay in history and the console, off the island (spec/40: the
    island shows the answer, not the model working; THINKING already signals "working", D25). The
    returned reply is that same final text.
    """
    tools = tools or []
    working = list(session.history) + [{"role": "user", "content": utterance}]
    turn = replace(session, history=working)          # a copy: uncommitted until success
    retried = False
    for _round in range(MAX_TOOL_ROUNDS + 1):
        text, calls, err, malformed = await _one_round(brain, turn, tools)
        if malformed and not retried:
            retried = True                            # spec/20: retry a malformed tool call once
            log.info("malformed tool call — retrying the round once (spec/20)")
            continue
        if err or malformed:
            return "", (err or "malformed_tool_call")
        if not calls:
            if on_delta and text:
                on_delta(text)                        # only the ANSWER reaches the overlay
            working.append({"role": "assistant", "content": text})
            session.history[:] = working              # commit — success only
            return text, None
        results: dict[str, str] = {}
        for c in calls:
            if execute is None:                       # replay/selfcheck with no executor wired
                log.warning("tool call %r with no executor — refusing", c.name)
                results[c.id] = f"Tool {c.name} is unavailable."
            else:
                content, outcome = execute(c)
                log.info("tool %s -> %s", c.name, outcome)
                results[c.id] = content
        brain.record_tool_round(turn, text, calls, results)  # appends to `working` in wire shape
        retried = False                               # each fresh round gets its own retry budget
    log.warning("tool loop hit the %d-round cap without an answer", MAX_TOOL_ROUNDS)
    return "", "unknown"


def latency_table(trace) -> str:
    """Render per-turn latencies from an event trace against the targets (spec/schemas/
    targets.json — one source, D25). Printed at the end of every live session and every replay
    case (docs/04 §7)."""
    from bridge.config import load_schemas
    tg = load_schemas()["targets"]["targets"]
    # 'word' carries a [measured] tag, not a '<', because first_word is a diagnostic, not a
    # gate (D25): under generate-then-play it is a reply-length proxy, so a fixed ceiling on it
    # would be a length cap wearing a stopwatch's clothes.
    out = [f"{'turn':<6}{'wake->listen':>13}{'eos->feedback':>15}{'eos->word':>11}"
           f"   (wake<{tg['wake_ack']['ms']} / feedback<{tg['feedback']['ms']} / "
           f"word {tg['first_word']['ms']}[measured] ms, targets.json)"]
    wake_t = listen = cur = None
    turns: list[dict] = []
    for t, ev, detail in trace:
        if ev == "wake":
            wake_t, listen = t, None
        elif ev == "earcon" and detail == "listening" and wake_t is not None:
            listen = (t - wake_t) * 1000
        elif ev == "eos":
            cur = {"eos": t, "listen": listen, "fb": None, "word": None}
            turns.append(cur)
            listen = None
        # 'thinking' counts as feedback now (D25): the overlay state change is perceptible
        # feedback (D16) and on a normal turn it is the FIRST of the three, so the column
        # finally reflects the screen instead of only the audio path.
        elif cur is not None and ev in ("thinking", "earcon", "speak"):
            if cur["fb"] is None:
                cur["fb"] = (t - cur["eos"]) * 1000
            if ev == "speak" and cur["word"] is None:
                cur["word"] = (t - cur["eos"]) * 1000
    fmt = lambda v: f"{v:.0f}" if v is not None else "-"  # noqa: E731
    for i, r in enumerate(turns, 1):
        out.append(f"{i:<6}{fmt(r['listen']):>13}{fmt(r['fb']):>15}{fmt(r['word']):>11}")
    return "\n".join(out)


class Orchestrator:
    def __init__(self, silence_ms: int = SILENCE_MS, voice: str = VOICE,
                 model: str = DAEMON_MODEL, brain=None, broadcaster=None,
                 auto_end: bool = False, hotkeys=None):
        self.silence_chunks = (silence_ms + VAD_CHUNK_MS - 1) // VAD_CHUNK_MS
        self.voice = voice
        self.auto_end = auto_end                 # spec/70: end a keyed turn on VAD silence too
        self.hk = hotkeys                        # None under replay/selfcheck: wake word only
        # The assistant brain. An INJECTED brain (replay/selfcheck) is used as-is; otherwise the
        # router resolves it from the user's model picker each turn (see _assistant_brain), falling
        # back to this default. The two `_sig` fields cache which routed config the current brain /
        # cleanup brain was built for, so the adapter is rebuilt only when the pick changes.
        self._injected_brain = brain is not None
        self.brain = brain or ClaudeBrain(model=model)   # injectable: replay's fake brain
        self._brain_sig = None
        self._cleanup = None                             # dictation cleanup brain, built on first use
        self._cleanup_sig = None
        self.synth = synth                               # injectable: replay fakes TTS
        # D24: dismissal arrives from the Teleprompter, which owns bare Esc because it alone
        # knows when it is on screen. Set from the broadcaster's receive thread; every waiting
        # state polls it, and the single Dismissed handler in serve() does the unwinding — the
        # plumbing is unchanged from when the daemon owned the key, only the source moved.
        self._dismiss = threading.Event()
        self.bc = broadcaster or Broadcaster(on_dismiss=self._dismiss.set)
        self.trace: list[tuple[float, str, str]] = []    # (t, event, detail) — latency_table
        self.session = Session(id="boot")
        self.fed_back = True                    # has this turn recorded perceptible feedback?
                                                # True at rest so a stray mark before any turn
                                                # cannot publish; reset to False per turn.
        self.t_eos = time.perf_counter()        # spec/40 clock: VAD declared the turn over
        self._loop: asyncio.AbstractEventLoop | None = None   # see _run_async()
        self.pump: OutputPump | None = None
        self.mic = None
        self.vad: SileroVAD | None = None

    # orchestrator event -> Contract P 'state' (bridge/broadcaster.py, spec/schemas/status.json).
    # 'listening' is emitted by _capture (mic open); 'speaking'/'error' by _speak (its `state`
    # arg — so an error apology dwells in fault mode, not a bare reply view). 'speak' is
    # trace-only here.
    # 'idle'/'dismissed' both mean "the daemon is free again" — NOT "blank the island" (D24).
    # The island is already gone on a dismiss (it hid itself the instant Esc was pressed, which
    # is why it, not the daemon, sends the verb), and after a normal turn it stays up until it
    # has finished revealing the answer plus its own dwell.
    # Dictation adds three of its own (D2, spec/60): the STT and cleanup phases the assistant
    # collapses into one 'thinking', plus a paste confirmation. `pasted` only reaches the wire
    # because it is here — otherwise `_ev("pasted")` would be trace-only.
    _EVENT_STATE = {"thinking": "thinking", "idle": "idle", "dismissed": "idle",
                    "transcribing": "transcribing", "transforming": "transforming",
                    "pasted": "pasted"}

    def _ev(self, event: str, detail: str = "", show: str | None = None,
            mirror: bool = True) -> None:
        """Trace an event (the harness asserts on these), mirror it to the overlay feed
        (Contract P), and print its console line. `mirror=False` keeps an event in the trace
        but off the wire — dictation traces its transcript for the harness but must NOT show it
        on the island (it pastes elsewhere) or let it join the assistant's prompt history."""
        self.trace.append((time.perf_counter(), event, detail))
        if mirror:
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
        """Publish a Contract P state. `listening` is load-bearing beyond showing the bars:
        it is also what CLEARS the previous turn (status.json `clearsTurn`), so a capture
        window can never open over a stale answer — the invariant lives in the state itself
        rather than in whichever caller remembered to blank first."""
        self.bc.publish(m_state(name))

    def _run_async(self, coro):
        """Run a coroutine on the daemon's ONE long-lived event loop, and block until it is
        done. This is the sync loop's only door into asyncio.

        Every turn used to get a fresh `asyncio.run()`, which quietly made connection reuse
        impossible for **every** provider rather than just B1: an HTTP connection pool belongs
        to the loop that created it, and that loop died with the turn. So each turn paid a new
        TCP+TLS handshake on the end-of-speech -> first-word path, and no adapter could have
        avoided it however well written. One loop for the process's life is the fix, and it is
        the orchestrator's to give — hence Contract B's one-loop guarantee (spec/20); what an
        adapter keeps across turns is then its own business.

        `serve()` deliberately stays synchronous. Making it a coroutine looks tempting and is
        a trap: mic reads, the wake model, the VAD, whisper and Kokoro are all blocking C
        calls, so an async `serve()` would starve the loop unless every one of them were
        pushed to an executor — a rewrite of the daemon to save a thread.
        """
        if self._loop is None:
            self._loop = asyncio.new_event_loop()
            threading.Thread(target=self._loop.run_forever, name="gemma-brain",
                             daemon=True).start()
        return asyncio.run_coroutine_threadsafe(coro, self._loop).result()

    def _dismissed(self) -> bool:
        """Has the overlay reported a dismiss since we last looked? Consumes the signal."""
        if self._dismiss.is_set():
            self._dismiss.clear()
            return True
        return False

    def _abort_flag(self):
        """The Event a streaming brain call races against (the abort seam in `_drive`)."""
        return self._dismiss

    # --- feedback bookkeeping (D11: something PERCEPTIBLE < 1.5 s after end of speech) ---

    def _feedback(self, what: str) -> None:
        """Record time-to-first-perceptible-feedback, ONCE per turn (D11/D16/D25).
        Perceptible = the overlay's flip to THINKING, an earcon, or the first spoken word —
        whichever lands first. Since D23 the screen is the primary surface, so on a normal
        turn the near-instant THINKING state IS the feedback; the 'working' earcon is the
        speech-mode audio fallback. The instrument used to credit only AUDIO, so it reported
        our own 1.4 s working-timer every turn and gave the screen zero credit — a headset-era
        measurement outliving the headset (D25)."""
        # ponytail: the check-then-set can race the working deadline firing on the loop thread
        # — worst case a duplicate latency line, not worth a lock for an instrument reading.
        if not self.fed_back:
            self.fed_back = True
            ms = (time.perf_counter() - self.t_eos) * 1000
            self.bc.publish(m_latency("feedback", ms))
            log.info("perceptible feedback (%s) %.0f ms after end of speech", what, ms)

    def _ping(self, name: str) -> None:
        """Play one earcon by schema id — gated on the 'pings' setting (default on). Silent when
        off: this is a visual-first app and the screen carries the turn (D28)."""
        if not settings.get("pings"):
            return
        self.pump.play(earcon_samples(name))
        self._ev("earcon", name)
        self._feedback(f"'{name}' earcon")

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
        # Dictation's endpoint is the key, not the clock (D20): a long dictation would otherwise
        # hit the assistant's 30 s runaway cap and truncate mid-sentence. Give the dictate door a
        # far larger backstop; the assistant keeps the tight cap (a spoken question is short).
        max_chunks = DICTATION_MAX_CHUNKS if (door is not None and door.name == "dictate") else MAX_CHUNKS
        eos = EndOfSpeech(silence_chunks=self.silence_chunks, max_chunks=max_chunks,
                          nospeech_chunks=max(1, nospeech_ms // VAD_CHUNK_MS))
        captured: list = []
        if preroll:
            captured.append(np.concatenate(preroll))
        for s in seed or []:
            captured.append(s)
            eos.update(True)
        # BINDING INVARIANT: opening a capture window clears the previous turn — the island
        # must never show the mic bars over a stale answer. Since D24 that clearing IS
        # `listening` (status.json `clearsTurn`), so no caller can skip it: it used to be a
        # separate `idle` published here, and before that a blank in serve() alone, which the
        # barge-in entrance bypassed — that is precisely how bars came to be drawn over the
        # last reply. One message, one owner, no path that can forget.
        self._dismissed()                           # drop a stale dismiss from a past turn
        self._publish_state("listening")            # clears the turn AND opens the bars
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
        after which the answer stays on the island until the overlay hides it (D24)."""
        self.fed_back = False
        self._ev("thinking", show="[thinking]")
        self._feedback("overlay thinking")      # D25: the screen is the feedback now (D23) —
                                                # near-instant, and finally credited

        text = transcribe(audio)
        if not text:
            self.bc.publish(m_error("I didn't catch that.", "no_transcript"))
            self._ping("failure")               # narration rules: the pipeline broke
            self._ev("no-transcript", show="(no transcript)")
            return None                         # ends the chain; the wake watch resumes
        self._ev("transcript", text, show=f"> {text}")

        # The 'working' earcon is retired (D28): since D23/D25 the overlay's THINKING state IS
        # the feedback, so nothing pings while the brain runs — the screen carries it.
        reply, err = self._run_async(_drive(
            self._assistant_brain(), self.session, text,
            on_delta=lambda d: self.bc.publish(m_response(delta=d)),
            abort=self._abort_flag(),
            tools=tool_specs(),                 # Contract T: only implemented, in-tier tools (spec/30)
            execute=lambda c: run_tool(c, session=self.session.id, transcript=text),
        ))
        if err == "aborted":
            self._dismissed()                   # consume the signal the race saw
            raise Dismissed
        if err or not reply:
            kind = err or "unknown"
            self.bc.publish(m_error(spoken_error(kind), kind))
            self._ping("failure")
            if settings.get("tts"):
                return self._speak(self.synth(spoken_error(kind), self.voice), state="error")
            return None      # TTS off: the fault MESSAGE shows on the overlay (as no_transcript does)
        self.bc.publish(m_response(done=True))  # reply text complete on the overlay
        # History is committed inside _collect now (it must persist tool rounds mid-turn, and only
        # on success), so there is no post-turn append here any more.
        # The hold survives; the "say 'read it'" escape hatch does not. Holding is what stops
        # a long answer being read AT you (spec/40, never lecture uninvited) — it means SHOWN,
        # not spoken, and pings `success` (D28) so a long answer you may have glanced away from
        # gets one soft "it's ready". (Read-all-when-TTS-on is parked for M0.5, spec/40.)
        if sentences(reply) > 2:
            self._ping("success")
            self._ev("held", show="[answer shown, not spoken]")
            return None
        if settings.get("tts"):
            return self._speak(self.synth(reply, self.voice))
        log.info("answer shown, not spoken (TTS off)")
        return None

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
        self._feedback("speech")
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
                captured = self._capture(door=keyed)
                # A dictate press mid-reply must NOT be fed to the brain: it cuts TTS, delivers
                # the dictation, and ends the chain (returning None). Only an ask key-interrupt
                # feeds the assistant chain. (This is the seam the review flagged — _pressed has
                # two callers, and routing on only the serve() one would misroute this path.)
                if keyed.name == "dictate":
                    if captured is not None:
                        self._dictate(captured)
                    return None
                return captured
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
        latency table can measure press/wake -> indication (spec/40), and sound the `listening`
        earcon (gated on 'pings') so the press is audibly acknowledged.

        Every path that opens a turn goes through here. The two that did NOT are how the
        barge-in path came to draw bars over a stale answer, and how key-interrupt turns
        came to have no press-latency reading at all — 60% of the first acceptance run."""
        self._ev("wake", "key" if door else "phrase",
                 show=f"[{door.name if door else 'wake'}] listening...")
        if settings.get("pings"):
            self.pump.play(earcon_samples("listening"))    # < 300 ms: enqueued immediately
            self._ev("earcon", "listening")
            log.info("listening earcon %.0f ms after %s", (time.perf_counter() - t0) * 1000,
                     "keypress" if door else "wake detect")

    def _pressed(self):
        """The door whose hotkey just opened a capture — the **ask** door or the **dictate**
        door — else None (a wake-word turn). The caller routes on `door.name`: 'ask' runs the
        assistant turn, 'dictate' runs the dictation pipeline (spec/60).

        `start` is cleared here (we are taking the turn); `end` is the module's to clear on the
        next press, and `_capture()`'s finally calls `door.close()` when the capture really ends.
        Ask is checked first so that if both somehow fired at once, the assistant wins."""
        if self.hk is None:
            return None
        for name in ("ask", "dictate"):
            d = self.hk.doors.get(name)
            if d is not None and d.start.is_set():
                d.start.clear()
                return d
        return None

    def _assistant_brain(self):
        """The answer brain for this turn. An injected brain (replay/selfcheck) is used unchanged;
        otherwise the router resolves it from the user's model picker (spec/20 §Routing), falling
        back to the daemon default when no primary is configured. Cached across turns while the
        routed config is unchanged, so the client is kept (spec/20 adapter lifetime) but a change
        in the picker lands on the next turn with no restart."""
        if self._injected_brain:
            return self.brain
        sig = router.signature("assistant")
        if sig != self._brain_sig:
            self.brain = router.build_for_role("assistant") or ClaudeBrain(model=DAEMON_MODEL)
            self._brain_sig = sig
            log.info("router: assistant brain -> %s", sig or f"default ({DAEMON_MODEL})")
        return self.brain

    def _cleanup_brain(self):
        """The dictation cleanup brain: the router's `cleanup_dictation` role (spec/20 §Routing),
        or the Groq default (D15/S-06) when unconfigured. Cached across turns while its config is
        unchanged (spec/20 adapter lifetime), yet a picker change lands on the next dictation. Lazy:
        dictation may never be used in a session, and building it reads the credential store."""
        sig = router.signature("cleanup_dictation")
        if self._cleanup is None or sig != self._cleanup_sig:
            self._cleanup = (router.build_for_role("cleanup_dictation")
                             or build_brain(CLEANUP_PROVIDER, CLEANUP_MODEL))
            self._cleanup_sig = sig
        return self._cleanup

    def _dictate(self, audio) -> None:
        """A dictation turn (spec/60): transcribe → clean up → paste at the caret. No brain
        answer and no follow-up chain — the key was the endpoint and the text goes to whatever
        app has focus. Cleanup is an ENHANCEMENT, not a gate: if it is unavailable the raw
        transcript is delivered, so dictation still works with no cleanup key and, in that case,
        nothing leaves the machine."""
        self.fed_back = False                       # a fresh turn: let it record feedback once
        self._ev("transcribing", show="[dictation: transcribing]")   # own state, not 'thinking' (D2)
        self._feedback("overlay thinking")          # D25: the screen is the feedback

        text = transcribe(audio)
        if not text:
            self.bc.publish(m_error("I didn't catch that.", "no_transcript"))
            self._ping("failure")
            self._ev("no-transcript", show="(no transcript)")
            self._publish_state("idle")
            return
        # mirror=False: the transcript is traced for the harness but pastes at the caret — it is
        # never shown on the island and must not join the assistant's prompt history (D2).
        self._ev("transcript", text, show=f"> {text}", mirror=False)

        self._ev("transforming", show="[dictation: cleaning up]")    # own state (D2)
        cleaned, err = self._run_async(
            transform(self._cleanup_brain(), text, DICTATION_CLEANUP))
        if err or not cleaned:
            log.warning("dictation cleanup unavailable (%s) — pasting the raw transcript",
                        err.kind if err else "empty result")
            cleaned = text
        else:
            self._ev("transcript", cleaned, show=f"> {cleaned}", mirror=False)

        if paste_text(cleaned):
            self._ping("success")
            self._ev("pasted", show="[pasted]")
        else:
            self.bc.publish(m_error("Couldn't paste the text.", "paste_failed"))
            self._ping("failure")
            self._ev("paste-failed", show="(paste failed)")
        self._publish_state("idle")

    def serve(self, mic, pump, wake_model) -> None:
        """The IDLE→wake→turn-chain loop against a mic, pump and wake model — real
        devices from run(), fakes from the replay harness (tests/replay.py)."""
        self.pump, self.mic = pump, mic
        ring: deque = deque(maxlen=BUFFER_BLOCKS)   # ≤3 s pre-trigger audio, RAM only (spec/50)
        while True:
            # IDLE: wake watch
            block, _ = mic.read(BLOCK_SAMPLES)
            frame = block[:, 0]
            ring.append(frame)
            # Two entrances to the same door (D20): the ask hotkey and the wake phrase.
            door = self._pressed()
            if door is None and not any(s >= THRESHOLD
                                        for s in wake_model.predict(frame).values()):
                continue
            t_wake = time.perf_counter()
            self._enter(door, t_wake)
            # ponytail: fresh history each wake-chain — whether it should persist
            # across wakes is an open question (parked; STATE), so it dies at IDLE.
            self.session = Session(id=time.strftime("%H%M%S"))

            try:
                utt = self._capture(preroll=list(ring)[-PREROLL_BLOCKS:], door=door)
                ring.clear()
                if utt is None:
                    self._ev("nothing-heard", show="[nothing heard]")
                elif door is not None and door.name == "dictate":
                    self._dictate(utt)          # spec/60: standalone, no assistant chain
                else:
                    while utt is not None:      # the turn chain: barge-ins
                        utt = self._turn(utt)
            except Dismissed:
                # One handler for every state (spec/40): whatever was in flight — an open
                # mic, a streaming brain call, TTS mid-sentence — stops here. The island is
                # already gone; it hid itself the instant Esc landed and told us afterwards.
                # The working-earcon deadline needs no cancel here: it lives inside _drive and
                # was already cancelled when the aborted turn returned (G-03).
                pump.cut()
                if self.hk is not None:
                    self.hk.reset()             # no door left mid-toggle by the abandon
                self._ev("dismissed", show="[dismissed]")
                self._flush_wake(wake_model)
                continue
            # Published BEFORE the wake flush (37 model calls) so the island's dwell clock
            # starts when the turn actually ended. `idle` says the DAEMON is free — it no
            # longer blanks anything, because how long the answer stays up is a fact about
            # the reveal, which only the island can see (D24).
            self._ev("idle", show="[idle]")
            self._flush_wake(wake_model)        # else the old phrase re-triggers

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

    # BINDING INVARIANT: a capture window clears the previous turn BEFORE the mic opens,
    # whichever entrance opened it. Regressing this draws the mic bars over the last reply
    # (it did: the barge-in path skipped the clear, which lived in serve()).
    # Since D24 the clear IS `listening`, so the guarantee no longer depends on a caller
    # remembering to blank first — but only while the contract agrees, hence the cross-check.
    from bridge.config import load_schemas
    assert "listening" in load_schemas()["status"]["clearsTurn"], \
        "Contract P no longer clears on `listening` — opening a capture would leave the "\
        "previous answer on the island under the mic bars"

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
    assert probe.bc.states == ["listening"], probe.bc.states

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

    # The Contract T tool loop (spec/30): a round that asks for a tool must run the tool, feed the
    # result back into history, and drive a SECOND round that answers with it — and the whole turn
    # commits to history only on success. This is the new logic in _collect; the fakes below stand
    # in for a real brain's ToolCall/record_tool_round surface.
    class _ToolThenAnswer:
        def __init__(self): self.rounds, self.saw_result = 0, False
        async def converse(self, session, utterance, tools):
            self.rounds += 1
            if self.rounds == 1:
                yield TextDelta("let me check.")           # preamble — must NOT reach the overlay
                yield ToolCall("t1", "system_status", {}); yield Done()
            else:                                          # the result must be in history by now
                self.saw_result = any("noon" in str(m) for m in session.history)
                yield TextDelta("It is noon."); yield Done()
        @staticmethod
        def record_tool_round(session, text, calls, results):
            session.history.append({"role": "assistant", "tool": [c.name for c in calls]})
            session.history.append({"role": "tool", "content": results.get("t1", "")})

    sess = Session(id="tool")
    brain = _ToolThenAnswer()
    overlay: list[str] = []
    reply, err = asyncio.run(_drive(brain, sess, "what time is it?", on_delta=overlay.append,
                                    tools=tool_specs(), execute=lambda c: ("It is noon.", "ok")))
    assert (reply, err) == ("It is noon.", None), (reply, err)
    assert brain.rounds == 2, "a tool call must drive a second, answering round"
    assert brain.saw_result, "the tool result must be in history for the answering round"
    assert "".join(overlay) == "It is noon.", \
        f"only the answer may reach the overlay, not the tool-use preamble: {overlay}"
    assert sess.history[0] == {"role": "user", "content": "what time is it?"}, sess.history
    assert sess.history[-1] == {"role": "assistant", "content": "It is noon."}, sess.history

    # spec/20: exactly one retry on a malformed tool call, then recover.
    class _MalformedOnce:
        def __init__(self): self.n = 0
        @staticmethod
        def record_tool_round(*a): pass                    # never reached
        async def converse(self, session, utterance, tools):
            self.n += 1
            if self.n == 1:
                yield Error("malformed_tool_call", "args not JSON")
            else:
                yield TextDelta("recovered."); yield Done()
    mo = _MalformedOnce()
    reply, err = asyncio.run(_drive(mo, Session(id="m"), "q",
                                    tools=tool_specs(), execute=lambda c: ("", "ok")))
    assert (reply, err) == ("recovered.", None) and mo.n == 2, (reply, err, mo.n)

    # A model that never stops calling tools is capped, not looped forever (spec/30).
    class _AlwaysTool:
        @staticmethod
        def record_tool_round(*a): pass
        async def converse(self, session, utterance, tools):
            yield ToolCall("x", "system_status", {}); yield Done()
    reply, err = asyncio.run(_drive(_AlwaysTool(), Session(id="c"), "loop",
                                    tools=tool_specs(), execute=lambda c: ("ok", "ok")))
    assert (reply, err) == ("", "unknown"), (reply, err)

    # ONE event loop for the process, not one per turn (spec/20 adapter lifetime). A per-turn
    # loop made connection reuse impossible for EVERY provider, not just B1 — an HTTP pool
    # belongs to the loop that built it, and that loop died with the turn.
    loops = Orchestrator(brain=object(), broadcaster=_Rec())

    async def _which():
        return asyncio.get_running_loop()

    first_loop = loops._run_async(_which())
    assert loops._run_async(_which()) is first_loop, "each turn built a fresh event loop"
    assert first_loop.is_running(), \
        "the brain loop must still be alive BETWEEN turns — that is the whole point of it"

    # ...and an aborted turn must CLOSE the brain's stream, not merely stop reading it. Driven
    # through _run_async deliberately: on the long-lived loop there is no per-turn
    # `shutdown_asyncgens` to close an abandoned generator, so only the explicit aclose() in
    # _one_round (and _drive waiting for the unwind) can do it. Left open, a dismissed turn goes
    # on generating tokens nobody will ever see.
    closed: list[str] = []

    class _HangingWatched:
        async def converse(self, session, utterance, tools):
            try:
                await asyncio.sleep(30)
                yield TextDelta("should never arrive")   # pragma: no cover
            finally:
                # Tearing down a real HTTPS stream is not instantaneous. Without the delay
                # this check passes by winning a race rather than by the fix being present.
                await asyncio.sleep(0.05)
                closed.append("closed")

    flag2 = threading.Event()
    threading.Timer(0.15, flag2.set).start()
    reply, err = loops._run_async(
        _drive(_HangingWatched(), Session(id="t"), "hi", abort=flag2))
    assert (reply, err) == ("", "aborted"), (reply, err)
    assert closed == ["closed"], \
        "an aborted turn must close the brain's stream before _drive returns"

    # D24: the dismiss signal is no longer a key this process owns — it arrives as a Contract P
    # line from the Teleprompter, which holds bare Esc because it alone knows when it is on
    # screen. Drive the WHOLE seam: a line off the wire must cancel a streaming brain call
    # exactly as the old keypress did. Breaking any link (broadcaster allowlist, the on_dismiss
    # wiring, _abort_flag) fails here rather than silently costing the user their dismiss key.
    wired = Orchestrator(brain=object())               # a real Broadcaster, never started
    assert not wired._dismissed()
    wired.bc._upstream(b'{"type":"dismiss"}')          # exactly what _read_client hands it
    assert wired._dismissed(), "an upstream dismiss must reach the orchestrator"
    assert not wired._dismissed(), "the signal is consumed once, not latched"
    wired.bc._upstream(b'{"type":"state","state":"idle"}')
    assert not wired._dismissed(), "only 'dismiss' may cross upstream (spec/50 rule 12)"

    threading.Timer(0.15, lambda: wired.bc._upstream(b'{"type":"dismiss"}')).start()
    t0 = time.perf_counter()
    reply, err = asyncio.run(_drive(_Hanging(), Session(id="t"), "hi",
                                    abort=wired._abort_flag()))
    assert (reply, err) == ("", "aborted"), (reply, err)
    assert time.perf_counter() - t0 < 5, "an overlay dismiss must cut the brain call"

    # barge-in: only sustained speech triggers
    b = BargeIn(chunks=4)
    assert not any(b.update(x) for x in [True, True, False, True, True, True])
    assert b.update(True)                             # 4th consecutive chunk fires

    # every shared Contract-B error kind has a short spoken line
    for kind in ("auth", "rate_limit", "context", "unavailable",
                 "malformed_tool_call", "unknown"):
        line = spoken_error(kind)
        assert line and sentences(line) <= 2, kind

    # latency table: two turns — one full (wake->listen, thinking feedback, speak), one speak-only
    tbl = latency_table([(0.0, "wake", ""), (0.1, "earcon", "listening"), (1.0, "eos", ""),
                         (1.05, "thinking", ""), (3.5, "speak", ""),
                         (10.0, "eos", ""), (10.8, "speak", "")])
    lines = tbl.splitlines()
    assert len(lines) == 3, tbl
    assert "100" in lines[1] and "50" in lines[1] and "2500" in lines[1], lines[1]
    assert lines[2].count("800") == 2 and "-" in lines[2], lines[2]
    # The header quotes targets.json, not four hardcoded copies (D25), and first_word is a
    # measured diagnostic, not a gate — so it is tagged, never a "<".
    assert "targets.json" in lines[0] and "[measured]" in lines[0], lines[0]

    # D25 reframe: the overlay's flip to THINKING is perceptible feedback (D16), and on a
    # normal turn it lands FIRST — so the feedback column must credit it, not a later earcon.
    # Without 'thinking' in the crediting set the instrument credited only audio (the headset-era
    # measurement it replaces).
    tbl2 = latency_table([(0.0, "eos", ""), (0.05, "thinking", ""),
                          (1.4, "earcon", "success"), (3.0, "speak", "")])
    assert "50" in tbl2.splitlines()[1], tbl2   # feedback = 50 ms (thinking), not 1400

    # ...and the runtime recorder agrees: _feedback publishes ONCE, at the earliest event, and
    # a later audible event does not double-count. Guards the fed_back once-only flag.
    class _Lat:
        started = False
        def __init__(self): self.fb = []
        def publish(self, m):
            if m.get("type") == "latency" and m["metric"] == "feedback":
                self.fb.append(m["ms"])

    fb = Orchestrator(brain=object(), broadcaster=_Lat())
    fb.fed_back = False
    fb.t_eos = time.perf_counter()
    fb._feedback("overlay thinking")            # screen feedback, near-instant
    fb._feedback("'success' earcon")            # a later audio event must NOT re-publish
    assert len(fb.bc.fb) == 1, f"feedback recorded {len(fb.bc.fb)} times, must be once"

    # D28: earcons obey the 'pings' setting (default on) — a visual-first quiet mode is one toggle
    # away. Point settings at a throwaway file so the real config is untouched; a stub pump counts
    # plays without a device.
    import os
    import tempfile

    class _Pump:
        def __init__(self): self.n = 0
        def play(self, s): self.n += 1

    with tempfile.TemporaryDirectory() as d:
        os.environ["GEMMA_SETTINGS"] = os.path.join(d, "s.json")
        pg = Orchestrator(brain=object(), broadcaster=_Rec())
        pg.pump = _Pump()
        pg.fed_back = True                      # keep this micro-test off the feedback recorder
        settings.set("pings", False)
        pg._ping("failure")
        assert pg.pump.n == 0, "pings off must silence earcons"
        settings.set("pings", True)
        pg._ping("failure")
        assert pg.pump.n == 1, "pings on must play the earcon"
    os.environ.pop("GEMMA_SETTINGS", None)

    # --- dictation (Track D, spec/60): dispatch by door, and the cleanup-fallback pipeline ---
    # _pressed distinguishes the two doors by name; the caller routes on it. A dictate press must
    # never be fed to the brain — the seam the adversarial review flagged (_pressed has two
    # callers). Ask wins a simultaneous press.
    class _FakeDoor:
        def __init__(self, name):
            self.name = name
            self.start = threading.Event()
            self.end = threading.Event()

        def close(self):
            self.start.clear()
            self.end.clear()

    class _FakeHK:
        def __init__(self):
            self.doors = {"ask": _FakeDoor("ask"), "dictate": _FakeDoor("dictate")}

    disp = Orchestrator(brain=object(), broadcaster=_Rec(), hotkeys=_FakeHK())
    assert disp._pressed() is None, "no press is a wake turn"
    disp.hk.doors["dictate"].start.set()
    got = disp._pressed()
    assert got is not None and got.name == "dictate" and not got.start.is_set()
    disp.hk.doors["ask"].start.set()
    disp.hk.doors["dictate"].start.set()
    assert disp._pressed().name == "ask", "the assistant wins a simultaneous press"

    # _dictate: transcribe -> clean -> paste, with the whole pipeline faked (no whisper, no
    # network, no Win32). The load-bearing behaviours: the cleaned text is delivered; a cleanup
    # failure falls back to the RAW transcript (dictation must work with no cleanup key); and an
    # empty transcript is a fault with no paste.
    # Patch via globals(), NOT `import bridge.orchestrator`: under `-m` the running module is
    # `__main__` and the import gives a SECOND copy, so patching the import would miss the names
    # `_dictate` actually reads. globals() is this module's own namespace either way.
    g = globals()
    _orig = {n: g[n] for n in ("transcribe", "transform", "paste_text")}
    try:
        pasted: list = []
        g["paste_text"] = lambda text, restore=True: (pasted.append(text) or True)
        g["transcribe"] = lambda audio: "um so like hello there"

        async def _clean_ok(brain, text, instr):
            return "Hello there.", None

        g["transform"] = _clean_ok
        di = Orchestrator(brain=object(), broadcaster=_Rec())
        di.pump, di._cleanup = _Pump(), object()      # object() skips build_brain (keyring/net)
        di._dictate(object())
        assert pasted == ["Hello there."], pasted
        # D2: dictation drives its own states, not the assistant's 'thinking'. The transcript is
        # mirror=False, so it never appears in the broadcast — only these four states do.
        assert di.bc.states == ["transcribing", "transforming", "pasted", "idle"], di.bc.states

        pasted.clear()

        async def _clean_fail(brain, text, instr):
            return "", Error("auth", "no key")

        g["transform"] = _clean_fail
        dr = Orchestrator(brain=object(), broadcaster=_Rec())
        dr.pump, dr._cleanup = _Pump(), object()
        dr._dictate(object())
        assert pasted == ["um so like hello there"], \
            f"cleanup failure must deliver the raw transcript, got {pasted}"
        # Cleanup failed but the paste still succeeded, so the state run is unchanged: the
        # confirmation is about the paste, not the tidy-up.
        assert dr.bc.states == ["transcribing", "transforming", "pasted", "idle"], dr.bc.states

        pasted.clear()
        g["transcribe"] = lambda audio: ""
        dn = Orchestrator(brain=object(), broadcaster=_Rec())
        dn.pump, dn._cleanup = _Pump(), object()
        dn._dictate(object())
        # Empty STT stops at transcribing -> fault -> idle: no transforming, no pasted, no paste.
        assert pasted == [] and dn.bc.states == ["transcribing", "idle"], \
            f"no transcript -> transcribing then fault: {dn.bc.states}"
    finally:
        g.update(_orig)

    print("selfcheck OK: speak/hold split, capture endpoint, barge-in counter, error lines, "
          "latency table + targets, feedback credits the screen (D25), pings toggle gates earcons, "
          "dictation dispatch + cleanup-fallback-to-raw (spec/60)")


def main() -> None:
    setup_logging()
    ap = argparse.ArgumentParser(description="Gemma orchestrator — the M0 loop (Track G step 6)")
    ap.add_argument("--selfcheck", action="store_true",
                    help="verify decision logic without mic, models or network, then exit")
    ap.add_argument("--silence-ms", type=int, default=SILENCE_MS,
                    help=f"end-of-speech silence in ms (default {SILENCE_MS}); tune by ear")
    ap.add_argument("--voice", default=VOICE, help=f"Kokoro voice (default {VOICE})")
    ap.add_argument("--model", default=DAEMON_MODEL,
                    help=f"brain model id (default {DAEMON_MODEL}; env GEMMA_BRAIN_MODEL)")
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
