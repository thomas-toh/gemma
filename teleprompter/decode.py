"""Contract P (spec/schemas/status.json) — the wire half of the Teleprompter, Qt-free.

NDJSON framing plus the reducer that turns a message stream into what the island shows.
This module deliberately imports nothing from `bridge/` and nothing from Qt: the front-end
depends on the *wire*, never on the daemon, so a future non-Python back-end drops in
unchanged (spec/00 D21) — and the fiddly logic stays testable in CI, where PySide6 isn't
installed.

Run:
    python -m teleprompter.decode --selfcheck   # no Qt, no sockets: framing + reducer
"""
from __future__ import annotations

import argparse
import json
import logging
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

log = logging.getLogger("gemma.teleprompter")

# Contract P transport (spec/00 D19; the docs/04 §5 reserved port). Mirrored here rather
# than imported from bridge/broadcaster.py — keeping the front/back split honest (D21).
HOST = "127.0.0.1"
PORT = 8990


@lru_cache(maxsize=1)
def status_schema() -> dict:
    """spec/schemas/status.json — the executable contract (hard rule 3), read straight from
    the repo rather than via bridge.config, so the front-end stays decoupled from the daemon."""
    root = Path(__file__).resolve().parent.parent
    return json.loads((root / "spec" / "schemas" / "status.json").read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def known_types() -> frozenset[str]:
    """The 'type' consts the schema defines. Anything else is ignored (protocol: log once)."""
    return frozenset(d["properties"]["type"]["const"]
                     for d in status_schema()["$defs"].values())


class Decoder:
    """Bytes -> Contract-P messages. Holds the partial trailing line between reads, and
    drops malformed lines / unknown types, logging each kind once (status.json protocol)."""

    def __init__(self) -> None:
        self._buf = b""
        self._warned: set[str] = set()

    def feed(self, data: bytes) -> list[dict]:
        self._buf += data
        out: list[dict] = []
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            if not line.strip():
                continue
            try:
                msg = json.loads(line)
            except (ValueError, UnicodeDecodeError):
                self._warn("malformed", "ignoring malformed feed line")
                continue
            if not isinstance(msg, dict):
                self._warn("nonobject", "ignoring non-object feed message")
                continue
            if msg.get("type") not in known_types():
                self._warn(f"type:{msg.get('type')}",
                           f"ignoring unknown message type {msg.get('type')!r}")
                continue
            out.append(msg)
        return out

    def _warn(self, key: str, message: str) -> None:
        if key not in self._warned:
            self._warned.add(key)
            log.warning(message)


# A 'state' that starts a new turn — or ends the session — clears the previous turn's reply
# and fault. 'speaking'/'error' must NOT clear: the reply streams in during THINKING and the
# island flips to SPEAKING while it is read, so clearing there would blank the text exactly
# as the user starts reading it.
CLEARS_TURN = frozenset({"listening", "thinking", "idle"})


# Prior prompts. RAM only — spec/50 forbids writing any of this to disk.
# NOTHING RENDERS THIS TODAY, deliberately: the ⌄ handle that used to show it was cut (D22),
# and its replacement — the expanded view — is not built yet. Kept because that view is the
# agreed home for prior prompts, and because collecting them is ~4 lines with a test, whereas
# reconstructing a session's prompts after the fact is impossible (nothing is on disk).
# ponytail: a flat cap, not a ring buffer; the process is short-lived.
HISTORY_MAX = 50


@dataclass
class OverlayState:
    """What the island is currently showing. Fed by apply(); rendered by the QML layer."""

    state: str = "idle"
    transcript: str = ""
    reply: str = ""
    done: bool = False
    mic: float = 0.0
    error: str = ""
    kind: str = ""
    # Per-turn instrument readings (spec/40 targets: feedback < 1500 ms, first word < 4000 ms).
    # status.json calls these "not user-facing chrome by default", so the overlay only shows
    # them behind a toggle — but D13 wants them on screen for the M0 acceptance run.
    feedback_ms: float = 0.0
    first_word_ms: float = 0.0
    # Survives CLEARS_TURN deliberately: the turn ends, the session's prompts do not.
    history: list = field(default_factory=list)

    def apply(self, msg: dict) -> None:
        t = msg["type"]
        if t == "state":
            self.state = msg["state"]
            if self.state in CLEARS_TURN:
                self.transcript = self.reply = self.error = self.kind = ""
                self.done = False
                self.feedback_ms = self.first_word_ms = 0.0
            if self.state != "listening":
                self.mic = 0.0          # bars fall the moment the capture window closes
        elif t == "transcript":
            self.transcript = msg["text"]
            # Only settled prompts join the history; partials (streaming STT, deferred) would
            # otherwise pile up one entry per keystroke-equivalent.
            if msg.get("final", True) and msg["text"]:
                self.history.append(msg["text"])
                del self.history[:-HISTORY_MAX]
        elif t == "response":
            self.reply += msg.get("delta", "")
            self.done = bool(msg.get("done", False))
        elif t == "mic":
            self.mic = float(msg["level"])
        elif t == "error":
            self.error = msg["message"]
            self.kind = msg.get("kind", "unknown")
        elif t == "latency":
            if msg["metric"] == "feedback":
                self.feedback_ms = float(msg["ms"])
            elif msg["metric"] == "first_word":
                self.first_word_ms = float(msg["ms"])


def _selfcheck() -> None:
    """No Qt, no sockets: prove the framing survives arbitrary chunking and that the reducer
    keeps the reply on screen while it is spoken."""
    assert known_types() == {"state", "transcript", "response", "mic", "latency", "error"}, \
        sorted(known_types())

    # --- framing ---
    d = Decoder()
    assert d.feed(b'{"type":"state","state":"idle"}\n') == [{"type": "state", "state": "idle"}]
    assert d.feed(b'{"type":"mic","level":0.5}') == []            # partial line: held back
    assert d.feed(b'\n') == [{"type": "mic", "level": 0.5}]       # ...completed by the next read
    two = d.feed(b'{"type":"mic","level":0.1}\n{"type":"mic","level":0.2}\n')
    assert [m["level"] for m in two] == [0.1, 0.2]                # several per chunk
    # a message split mid-token across three reads still arrives intact
    assert d.feed(b'{"type":"transc') == [] and d.feed(b'ript","text":"hi"') == []
    assert d.feed(b'}\n') == [{"type": "transcript", "text": "hi"}]
    # junk is dropped, and never wedges the stream
    assert d.feed(b'not json\n') == []
    assert d.feed(b'[1,2]\n') == []                               # valid JSON, not an object
    assert d.feed(b'{"type":"future_thing","x":1}\n') == []       # unknown type: ignored
    assert d.feed(b'\n\n') == []                                  # blank lines
    assert d.feed(b'{"type":"state","state":"idle"}\n') == [{"type": "state", "state": "idle"}]

    # --- reducer ---
    s = OverlayState()
    s.apply({"type": "state", "state": "listening"})
    s.apply({"type": "mic", "level": 0.7})
    assert s.state == "listening" and s.mic == 0.7
    s.apply({"type": "state", "state": "thinking"})
    assert s.mic == 0.0, "bars must fall when the capture window closes"
    s.apply({"type": "transcript", "text": "what's the weather"})
    for word in ("It's ", "clear ", "in ", "Tokyo."):
        s.apply({"type": "response", "delta": word})
    assert s.reply == "It's clear in Tokyo." and not s.done
    # the reply must SURVIVE the flip to speaking — this is the whole point of CLEARS_TURN
    s.apply({"type": "state", "state": "speaking"})
    assert s.reply == "It's clear in Tokyo.", "speaking must not clear the reply"
    assert s.transcript == "what's the weather", "speaking must not clear the prompt"
    s.apply({"type": "response", "done": True})
    assert s.done
    # a new turn clears the last one — but NOT the session's prompt history
    s.apply({"type": "state", "state": "listening"})
    assert s.reply == "" and s.transcript == "" and not s.done
    assert s.history == ["what's the weather"], s.history
    s.apply({"type": "state", "state": "thinking"})
    s.apply({"type": "transcript", "text": "set a timer"})
    s.apply({"type": "transcript", "text": "partial", "final": False})   # partials excluded
    s.apply({"type": "state", "state": "idle"})
    assert s.history == ["what's the weather", "set a timer"], s.history
    for i in range(HISTORY_MAX + 10):                                    # cap holds
        s.apply({"type": "transcript", "text": f"prompt {i}"})
    assert len(s.history) == HISTORY_MAX and s.history[-1] == f"prompt {HISTORY_MAX + 9}"

    # faults: the message carries the reason, and state:error must not wipe it
    s.apply({"type": "error", "message": "I can't reach my brain right now.", "kind": "unavailable"})
    s.apply({"type": "state", "state": "error"})
    assert s.error == "I can't reach my brain right now." and s.kind == "unavailable"
    s.apply({"type": "error", "message": "no kind given"})
    assert s.kind == "unknown"                                    # schema default
    # latency: captured for the acceptance-run readout, and reset with the turn
    s.apply({"type": "latency", "metric": "feedback", "ms": 900})
    s.apply({"type": "latency", "metric": "first_word", "ms": 3400})
    assert (s.feedback_ms, s.first_word_ms) == (900.0, 3400.0)
    s.apply({"type": "state", "state": "idle"})
    assert s.error == "" and s.state == "idle"
    assert (s.feedback_ms, s.first_word_ms) == (0.0, 0.0), "latency must reset with the turn"

    print("selfcheck OK: framing survives arbitrary chunking, junk/unknown types ignored, "
          "reducer keeps the reply through SPEAKING and clears it on a new turn")


def main() -> None:
    ap = argparse.ArgumentParser(description="Teleprompter wire decoder — Contract P (Track P)")
    ap.add_argument("--selfcheck", action="store_true",
                    help="verify framing + reducer without Qt or sockets, then exit")
    args = ap.parse_args()
    if args.selfcheck:
        logging.basicConfig(level=logging.WARNING)
        _selfcheck()
        return
    ap.error("nothing to do: pass --selfcheck (the renderer lives in `python -m teleprompter`)")


if __name__ == "__main__":
    main()
