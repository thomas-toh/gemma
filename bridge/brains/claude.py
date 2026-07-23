"""B1 — Anthropic Messages API adapter (Contract B, spec/20). Build step 5.

Streams a Claude reply as BrainEvents. M0 runs zero tools (utterance in, streamed text
out); the tool_use path is wired for M1 but unexercised until tools land.

    python -m bridge.brains.claude "what time is it in Tokyo?"   # live console round-trip
    python -m bridge.brains.claude --selfcheck                   # no network: error mapping
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import AsyncIterator

from .base import Done, Error, Session, TextDelta, ToolCall, ToolSpec, ssl_context

# Default model per the standing rule; override for the voice loop (latency/cost) via env.
# Sensible alternatives for an always-listening assistant: claude-sonnet-5, claude-haiku-4-5.
DEFAULT_MODEL = os.environ.get("GEMMA_BRAIN_MODEL", "claude-opus-4-8")

# Spoken replies stay short. The ≤2-sentence narration rule is the orchestrator's job
# (step 6); this default just makes the standalone console test sound like the voice loop.
# Register per spec/40 (decided 2026-07-13): impassive system voice. Placeholder until
# M0.5's versioned persona.
# ponytail: the "no tools" claim is static and goes stale the moment tools land (M1) —
# replace with a per-turn capability clause derived from the filtered `tools` list
# (decided 2026-07-13; see STATE, Track B M0.5).
DEFAULT_SYSTEM = (
    "You are Gemma, this machine's system voice. Your words are read aloud: answer in "
    "one or two spoken sentences unless asked for more; no markdown, lists, code, or "
    "emoji. Register: impassive and precise, declaratory or imperative — no "
    "interjections, no exclamations, no filler, no performed warmth. You have no tools "
    "yet: you cannot set timers, control this computer, or act on anything — never "
    "claim an action was performed; state the limitation plainly."
)

# ponytail: short cap — spoken turns are brief and long answers are held, not spoken
# (spec/40). Bump if a legitimate turn ever truncates.
MAX_TOKENS = 1024

# No `thinking` param: on Opus 4.8 that means thinking is OFF, which is what a <4 s
# first-word voice reply wants (adaptive thinking delays the first token). D11 / spec/40.


def _get_key() -> str | None:
    """Credential store first (spec/50 rule 10, service 'gemma'); env var fallback."""
    try:
        import keyring

        key = keyring.get_password("gemma", "anthropic")
        if key:
            return key
    except ImportError:
        pass
    return os.environ.get("ANTHROPIC_API_KEY")


def _error_kind(exc: Exception) -> str:
    """Map an SDK exception to a shared Contract B Error kind (spec/20) by its TYPE and status
    code — never by matching the message prose (B-02).

    No `context` case: a context overflow and any other malformed request are BOTH
    `BadRequestError` / `type == "invalid_request_error"` (verified, anthropic 0.116.0) — the
    provider gives no distinct code to switch on, so the only in-band signal is the message
    text, and heuristics over prose mis-narrate (a 400 about a bad field said "conversation too
    long"). A 400 therefore maps to `unknown` (the generic apology), which is what the API is
    actually telling us. Detecting context overflow *properly* means counting tokens against the
    model's window BEFORE the call — a proactive check, not an error heuristic — and that only
    earns its keep once conversations persist across wakes (parked; STATE)."""
    import anthropic

    if isinstance(exc, anthropic.AuthenticationError):
        return "auth"
    if isinstance(exc, anthropic.RateLimitError):
        return "rate_limit"
    if isinstance(exc, anthropic.APIConnectionError):
        return "unavailable"
    if isinstance(exc, anthropic.APIStatusError):   # covers BadRequestError (400) -> unknown
        return "unavailable" if exc.status_code >= 500 else "unknown"
    return "unknown"


class ClaudeBrain:
    """B1. `converse` is an async generator, matching the BrainAdapter Protocol."""

    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None):
        self.model = model
        self._api_key = api_key or _get_key()
        self._client = None          # built on first use, then kept — see _client_once()

    def _client_once(self):
        """One client for this adapter's life, resting on Contract B's one-loop guarantee
        (spec/20). It used to be rebuilt per turn, which cost two separate things on the
        end-of-speech -> first-word path: a fresh TCP+TLS handshake (unavoidable then, since
        an httpx pool belongs to the loop that made it and the loop died with the turn), and
        ~190 ms of plain CPU re-reading this machine's CA bundle. Only the second is fixed
        here; the first is fixed by there being one loop at all.

        `DefaultAsyncHttpxClient`, NOT a bare `httpx.AsyncClient`: the SDK passes a supplied
        client through verbatim, and a bare one silently swaps the SDK's 600 s read timeout
        for httpx's 5 s default — which would abort exactly the slow-first-token turns this
        is meant to make faster (this repo has already recorded a 9.1 s cold turn).
        """
        import anthropic

        if self._client is None:
            self._client = anthropic.AsyncAnthropic(
                api_key=self._api_key,
                http_client=anthropic.DefaultAsyncHttpxClient(verify=ssl_context()),
            )
        return self._client

    async def converse(
        self,
        session: Session,
        utterance: str,
        tools: list[ToolSpec],
    ) -> AsyncIterator:
        if session.local_only:
            yield Error("unavailable", "B1 (Claude API) blocked: session is local_only")
            return
        if not self._api_key:
            yield Error("auth", "no API key (keyring service 'gemma' or ANTHROPIC_API_KEY)")
            return

        client = self._client_once()
        messages = list(session.history) + [{"role": "user", "content": utterance}]
        kwargs = dict(
            model=self.model,
            max_tokens=MAX_TOKENS,
            system=session.system or DEFAULT_SYSTEM,
            messages=messages,
        )
        if tools:
            kwargs["tools"] = tools

        try:
            async with client.messages.stream(**kwargs) as stream:
                async for text in stream.text_stream:
                    yield TextDelta(text)
                final = await stream.get_final_message()
            # Tool calls (M1): a turn either speaks or calls tools; surface them after
            # the text so the orchestrator can execute through Contract T.
            for block in final.content:
                if block.type == "tool_use":
                    yield ToolCall(block.id, block.name, block.input)
            yield Done(
                usage={
                    "input_tokens": final.usage.input_tokens,
                    "output_tokens": final.usage.output_tokens,
                }
            )
        except Exception as exc:  # noqa: BLE001 - map every provider error to Error
            yield Error(_error_kind(exc), str(getattr(exc, "message", exc)))


async def _run(question: str, model: str) -> int:
    brain = ClaudeBrain(model=model)
    session = Session(id="cli")
    status = 0
    async for ev in brain.converse(session, question, []):
        if isinstance(ev, TextDelta):
            print(ev.text, end="", flush=True)
        elif isinstance(ev, ToolCall):
            print(f"\n[tool_call {ev.name} {ev.input}]", flush=True)
        elif isinstance(ev, Done):
            print(f"\n[done: {ev.usage}]")
        elif isinstance(ev, Error):
            print(f"\n[error/{ev.kind}: {ev.detail}]", file=sys.stderr)
            status = 1
    return status


def _selfcheck() -> None:
    # Error mapping is by exception TYPE and status code, never message prose (B-02). Build real
    # SDK exception instances via __new__ (isinstance passes; no httpx.Response to fake), set
    # only the status_code the ladder reads. A 400 maps to `unknown` — the generic apology —
    # because Anthropic collapses context-overflow and other bad requests into one type.
    import anthropic

    def _exc(cls, status=None):
        e = cls.__new__(cls)
        if status is not None:
            e.status_code = status
        return e

    assert _error_kind(_exc(anthropic.AuthenticationError)) == "auth"
    assert _error_kind(_exc(anthropic.RateLimitError)) == "rate_limit"
    assert _error_kind(_exc(anthropic.APIConnectionError)) == "unavailable"
    assert _error_kind(_exc(anthropic.InternalServerError, 500)) == "unavailable"
    assert _error_kind(_exc(anthropic.BadRequestError, 400)) == "unknown", \
        "a 400 must map to the generic apology — no prose-guessing at 'context' (B-02)"
    assert _error_kind(RuntimeError("boom")) == "unknown"
    assert DEFAULT_SYSTEM and "voice" in DEFAULT_SYSTEM.lower()

    # Client lifetime (spec/20 adapter lifetime). No network: every cost here is local CPU.
    import time

    assert ssl_context() is ssl_context(), "the CA bundle must be parsed once per process"
    brain = ClaudeBrain(api_key="x")
    first = brain._client_once()                    # also warms `import anthropic` (~600 ms,
    assert brain._client_once() is first, \
        "the client must be built once and kept"    # ...paid once at startup, not per turn)
    # Time a genuinely FRESH build, imports warm — this is the per-turn cost that used to be
    # paid on every question. ~190 ms unmemoised vs ~0.2 ms memoised (measured 2026-07-22),
    # so 50 ms sits ~4x under the failure and ~250x over the pass.
    t0 = time.perf_counter()
    ClaudeBrain(api_key="x")._client_once()
    build_ms = (time.perf_counter() - t0) * 1000
    assert build_ms < 50, f"building the client took {build_ms:.0f} ms — CA bundle reloaded?"
    # A supplied http_client is used VERBATIM by the SDK, so a bare httpx.AsyncClient would
    # silently swap the SDK's 600 s read timeout for httpx's 5 s default and start killing
    # slow first tokens — the exact turns this whole change exists to speed up.
    assert first.timeout.read >= 60, f"custom client dropped the SDK read timeout: {first.timeout}"

    print("selfcheck OK: error mapping by type/status (no prose), defaults, client built once "
          "with the trust store memoised and the SDK's long read timeout intact")


def main() -> None:
    ap = argparse.ArgumentParser(description="Gemma B1 Claude adapter (Track G step 5)")
    ap.add_argument("question", nargs="?", help="prompt to send to Claude")
    ap.add_argument("--model", default=DEFAULT_MODEL, help=f"model id (default {DEFAULT_MODEL})")
    ap.add_argument("--selfcheck", action="store_true", help="offline logic check, no network")
    args = ap.parse_args()

    if args.selfcheck:
        _selfcheck()
        return
    if not args.question:
        ap.error("provide a question, or --selfcheck")
    sys.exit(asyncio.run(_run(args.question, args.model)))


if __name__ == "__main__":
    main()
