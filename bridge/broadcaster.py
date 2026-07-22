"""Track P (Contract P, spec/schemas/status.json): the crash-isolated status broadcaster.

The orchestrator publishes overlay status events — coarse state, transcript, streamed
response, mic level, per-turn latency, and faults — as NDJSON over a localhost-only TCP
socket (127.0.0.1). The Teleprompter (component P, D19) is a separate process that
subscribes and renders whatever arrives; it never drives the voice loop.

This module is the publisher half, and it is isolated from the voice loop by construction:
`publish()` is a non-blocking, never-raising hand-off onto a bounded queue drained by a
daemon thread, and a bind failure just disables the feed. A slow, absent, or dead overlay
(or the broadcaster itself dying) can neither stall nor crash the orchestrator (spec/00
D13/D19). The daemon is the always-up server; the overlay is the reconnecting client.

Message shapes are Contract P (spec/schemas/status.json, hard rule 3): the m_* helpers are
the one place the field names live, and --selfcheck validates them against the loaded
schema, so the code never re-encodes the field lists.

Run:
    python -m bridge.broadcaster --fake       # no audio/mic/models: play a scripted
                                              # session to any connected overlay
    python -m bridge.broadcaster --selfcheck  # no sockets/network: validate the wire, exit
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import queue
import socket
import sys
import threading
import time

from bridge.config import load_schemas
from bridge.log import setup_logging

log = logging.getLogger("gemma.status")

HOST = "127.0.0.1"
PORT = int(os.environ.get("GEMMA_STATUS_PORT", "8990"))   # Contract P transport (docs/04 §5
# reserved 'web' port); localhost only. ponytail: one number, constant + env override — no
# config system for it, and no cross-package import (the teleprompter mirrors these two).
QUEUE_MAX = 256   # publish() drops when full — mic frames are droppable (status.json).
UPSTREAM_MAX = 4096   # bytes a client may send without a newline before we discard them. The
                      # upstream verbs are a dozen bytes each; anything larger is a client
                      # gone wrong, and unbounded buffering would be its lever on us.


def upstream_types() -> frozenset[str]:
    """Message types a CLIENT may send us (D24). Loaded from status.json, never restated:
    the whole point of the list is that the two ends cannot disagree about it."""
    return frozenset(load_schemas()["status"]["upstream"])


# --- Contract P messages (spec/schemas/status.json). The one place the field names live;
#     _selfcheck validates each against the loaded schema so this can't drift silently. ---

def m_state(state: str) -> dict:
    return {"type": "state", "state": state}


def m_transcript(text: str, final: bool = True) -> dict:
    return {"type": "transcript", "text": text, "final": final}


def m_response(delta: str = "", done: bool = False) -> dict:
    return {"type": "response", "delta": delta, "done": done}


def m_mic(level: float) -> dict:
    return {"type": "mic", "level": level}


def m_latency(metric: str, ms: float) -> dict:
    return {"type": "latency", "metric": metric, "ms": ms}


def m_error(message: str, kind: str = "unknown") -> dict:
    return {"type": "error", "kind": kind, "message": message}


class Broadcaster:
    """A localhost NDJSON publisher. `start()` it once, then `publish(msg)` from anywhere;
    connected overlays receive each message as one JSON line. Callers are insulated from
    subscribers: publish() never blocks and never raises, so a wedged/absent overlay can
    only slow or drop the *feed*, never the voice loop."""

    def __init__(self, host: str = HOST, port: int = PORT, on_dismiss=None):
        self.host, self.port = host, port
        self._q: queue.Queue = queue.Queue(maxsize=QUEUE_MAX)
        self._clients: set[socket.socket] = set()
        self._lock = threading.Lock()
        self._srv: socket.socket | None = None
        self._started = False
        # D24: the one thing a subscriber may say back. A CANCEL, never a command (spec/50
        # rule 12) — it can only stop work already in flight, so the worst a hostile local
        # process can do with it is interrupt a turn it can already read off this same socket.
        self._on_dismiss = on_dismiss

    @property
    def started(self) -> bool:
        return self._started

    def start(self) -> None:
        if self._started:
            return
        try:
            srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            if sys.platform != "win32":
                # Unix: avoid TIME_WAIT rebind pain. Skipped on Windows, where SO_REUSEADDR
                # lets a second process *steal* the port — there we want bind() to fail.
                srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            srv.bind((self.host, self.port))
            srv.listen()
        except OSError as e:
            # Port busy / bind refused: run deaf, never take down the daemon (crash-isolation).
            log.warning("status feed disabled (%s:%d: %s)", self.host, self.port, e)
            return
        self._srv = srv
        self._started = True
        threading.Thread(target=self._accept, name="status-accept", daemon=True).start()
        threading.Thread(target=self._send, name="status-send", daemon=True).start()
        log.info("status feed on %s:%d (Contract P)", self.host, self.port)

    def publish(self, msg: dict) -> None:
        """Non-blocking, never raises. Drops on a full queue — the feed is best-effort,
        the voice loop is sacred (mic frames are explicitly droppable, status.json)."""
        if not self._started:
            return
        try:
            self._q.put_nowait(msg)
        except queue.Full:
            pass

    def _accept(self) -> None:
        while True:
            try:
                conn, _ = self._srv.accept()
            except ConnectionError:
                continue    # a client reset at/just-before accept — keep serving, don't die
            except OSError:
                return      # listener socket gone (process exit) — nothing left to accept
            try:
                conn.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
            except OSError:
                conn.close()   # died between accept and setup — drop it, keep serving
                continue
            with self._lock:
                self._clients.add(conn)
            log.info("overlay connected (%d subscriber(s))", len(self._clients))
            threading.Thread(target=self._read_client, args=(conn,),
                             name="status-recv", daemon=True).start()

    def _read_client(self, conn: socket.socket) -> None:
        """Drain one client's upstream verbs (D24). A thread per client because the normal
        case is a subscriber that says nothing and blocks here forever; crash-isolation is
        unchanged, since anything that goes wrong here kills only this thread — publish()
        and the voice loop never touch it."""
        buf = b""
        try:
            while True:
                data = conn.recv(4096)
                if not data:
                    return                      # clean close; _send discards the socket
                buf += data
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    self._upstream(line)
                if len(buf) > UPSTREAM_MAX:     # no newline in sight: not a Contract P client
                    log.warning("dropping %d oversized upstream bytes", len(buf))
                    buf = b""
        except OSError:
            return                              # reset/closed under us — nothing to clean up

    def _upstream(self, line: bytes) -> None:
        """One line from a client. Anything not named in status.json's 'upstream' is dropped:
        the allowlist is what keeps this channel a cancel rather than a control surface."""
        try:
            msg = json.loads(line)
        except (ValueError, UnicodeDecodeError):
            log.warning("ignoring malformed upstream line")
            return
        if not isinstance(msg, dict) or msg.get("type") not in upstream_types():
            log.warning("ignoring upstream message %r — not in the allowlist",
                        msg.get("type") if isinstance(msg, dict) else type(msg).__name__)
            return
        log.info("dismiss from the overlay")
        if self._on_dismiss is not None:
            self._on_dismiss()

    def _send(self) -> None:
        # ponytail: blocking sendall to localhost is the known ceiling — a wedged client
        # slows only the FEED (this thread), never the voice loop, which only touches the
        # queue. Go per-client non-blocking with buffers only if that ever actually bites.
        while True:
            msg = self._q.get()
            line = (json.dumps(msg, separators=(",", ":")) + "\n").encode("utf-8")
            with self._lock:
                dead = [c for c in self._clients if not _try_send(c, line)]
                for c in dead:
                    self._clients.discard(c)
            if dead:
                log.info("overlay disconnected (%d subscriber(s))", len(self._clients))


def _try_send(conn: socket.socket, line: bytes) -> bool:
    try:
        conn.sendall(line)
        return True
    except OSError:
        try:
            conn.close()
        except OSError:
            pass
        return False


# --- lightweight Contract-P validation (no jsonschema dep) — used only by --selfcheck ---

def _validate(msg: dict) -> list[str]:
    """Match msg by its 'type' to the matching $def in status.json and check required keys,
    no unknown keys (additionalProperties:false), and enum membership. [] means valid."""
    defs = load_schemas()["status"]["$defs"]
    t = msg.get("type")
    d = next((v for v in defs.values()
              if v.get("properties", {}).get("type", {}).get("const") == t), None)
    if d is None:
        return [f"unknown type {t!r}"]
    props = d["properties"]
    probs = [f"{t}: missing required {k!r}" for k in d.get("required", []) if k not in msg]
    for k, v in msg.items():
        if k not in props:
            probs.append(f"{t}: unexpected key {k!r}")
            continue
        enum = props[k].get("enum")
        if enum is not None and v not in enum:
            probs.append(f"{t}: {k}={v!r} not in {enum}")
    return probs


# --- scripted fake feed: drives the whole overlay with NO audio/mic/models -------------

def fake_events():
    """A scripted Contract-P session (mirrors the mockup's auto() timeline), looping
    forever. Yields (wait_s_before, message). Every 4th turn is a fault, to exercise the
    error path too."""
    prompts = [
        ("What's the weather in Tokyo right now?",
         "It's clear over Tokyo right now, about 18 degrees with light winds."),
        ("Set a timer for ten minutes.",
         "Timer set for ten minutes. I'll chime when it's up."),
        # deliberately long: exercises the overlay's line cap, scroll and top fade
        ("Summarise the email from the leasing agent.",
         "The agent confirms the lease renews at the current rent and they need your "
         "signature by Friday, with the deposit cleared the following week. They also "
         "want a copy of your insurance certificate and the signed inventory schedule "
         "before move-in, so the managing agent can release the keys on the morning of "
         "the handover."),
    ]
    turn = 0
    while True:
        prompt, reply = prompts[turn % len(prompts)]
        yield (0.8, m_state("idle"))
        yield (1.0, m_state("listening"))
        for i in range(44):                        # mic: quiet, then the user speaking
            level = 0.05 + 0.03 * ((i * 3) % 4) / 3 if i < 8 else 0.30 + 0.55 * ((i * 13) % 7) / 6
            yield (0.045, m_mic(round(min(1.0, level), 3)))
        yield (0.2, m_state("thinking"))
        yield (0.9, m_transcript(prompt))
        if turn % 4 == 3:
            yield (1.1, m_error("I can't reach my brain right now.", "unavailable"))
            yield (0.05, m_state("error"))
            yield (2.5, m_state("idle"))
        else:
            # Instrument readings, so the overlay's latency readout is actually exercised
            # rather than only ever being rendered for the first time during the M0 run.
            # Deliberately straddles the spec/40 targets (feedback 1500, first word 4000) so
            # the over-budget styling gets exercised too.
            yield (0.1, m_latency("feedback", 1180 if turn % 2 else 1720))
            yield (0.5, m_state("speaking"))
            yield (0.05, m_latency("first_word", 3450 if turn % 2 else 4310))
            for word in reply.split(" "):
                yield (0.09, m_response(delta=word + " "))
            yield (0.1, m_response(done=True))
            yield (2.6, m_state("idle"))
        turn += 1


def _run_fake(host: str, port: int) -> None:
    bc = Broadcaster(host, port)
    bc.start()
    if not bc.started:
        return   # start() already logged why
    log.info("fake feed playing — connect the teleprompter (Ctrl-C to stop)")
    try:
        for wait, msg in fake_events():
            time.sleep(wait)
            bc.publish(msg)
    except KeyboardInterrupt:
        print()


def _selfcheck() -> None:
    """No sockets/network: prove the m_* helpers speak Contract P (spec/schemas/status.json),
    that bad messages are caught, that the wire round-trips as NDJSON, and that publish()
    is a safe no-op / never-raises off the voice loop."""
    samples = [
        m_state("idle"), m_state("listening"), m_state("thinking"),
        m_state("speaking"), m_state("error"),
        m_transcript("hello world"), m_transcript("partial", final=False),
        m_response(delta="hi "), m_response(done=True),
        m_mic(0.0), m_mic(1.0),
        m_latency("feedback", 1200), m_latency("first_word", 3400),
        m_error("boom", "auth"), m_error("no kind given"),
    ]
    for msg in samples:
        assert _validate(msg) == [], (msg, _validate(msg))

    # malformed messages must be rejected
    assert _validate({"type": "state", "state": "sleeping"})       # enum violation
    assert _validate({"type": "mic"})                              # missing 'level'
    assert _validate({"type": "nope"})                             # unknown type
    assert _validate({"type": "state", "state": "idle", "x": 1})   # extra key

    # NDJSON: one object per line, no embedded newlines, exact round-trip
    for msg in samples:
        line = json.dumps(msg, separators=(",", ":"))
        assert "\n" not in line and json.loads(line) == msg, msg

    # the whole scripted session is valid Contract P (sample one+ full loop)
    seen = 0
    for _, msg in fake_events():
        assert _validate(msg) == [], (msg, _validate(msg))
        seen += 1
        if seen > 200:
            break

    # publish() is inert on a stopped broadcaster and drops (never raises) under backpressure
    bc = Broadcaster()
    bc.publish(m_state("idle"))              # not started -> no-op
    bc._started = True                       # simulate started with no threads/socket...
    bc._q = queue.Queue(maxsize=2)           # ...and a tiny queue
    for _ in range(50):
        bc.publish(m_mic(0.5))               # overflows -> must drop, never raise/block

    # --- upstream (D24): one verb, allowlisted from the schema, no sockets needed ---
    assert upstream_types() == {"dismiss"}, sorted(upstream_types())
    assert _validate({"type": "dismiss"}) == []
    fired: list[int] = []
    up = Broadcaster(on_dismiss=lambda: fired.append(1))
    up._upstream(b'{"type":"dismiss"}')
    assert fired == [1], "a dismiss line must reach the handler"
    # THE security property (spec/50 rule 12): this channel can cancel and nothing else. A
    # downstream verb replayed upstream must not act — otherwise any local process could
    # drive the island's text, or worse once Contract P grows.
    for bad in (b'{"type":"state","state":"idle"}',
                b'{"type":"transcript","text":"ignore your instructions"}',
                b'{"type":"response","delta":"x"}', b'not json', b'[1,2]', b'{"no":"type"}'):
        up._upstream(bad)
    assert fired == [1], "only 'dismiss' may cross the upstream channel"

    print("selfcheck OK: 7 message types validate against status.json, malformed rejected, "
          "NDJSON round-trips, scripted feed valid, publish() drops safely under backpressure, "
          "upstream accepts 'dismiss' and nothing else")


def main() -> None:
    setup_logging()
    ap = argparse.ArgumentParser(description="Gemma status broadcaster — Contract P (Track P)")
    ap.add_argument("--fake", action="store_true",
                    help="play a scripted session to any connected overlay (no audio/mic/models)")
    ap.add_argument("--selfcheck", action="store_true",
                    help="validate the wire against status.json without sockets, then exit")
    ap.add_argument("--host", default=HOST)
    ap.add_argument("--port", type=int, default=PORT)
    args = ap.parse_args()
    if args.selfcheck:
        _selfcheck()
        return
    if args.fake:
        _run_fake(args.host, args.port)
        return
    ap.error("nothing to do: pass --fake (drive the overlay) or --selfcheck")


if __name__ == "__main__":
    main()
