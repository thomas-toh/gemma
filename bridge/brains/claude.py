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

from .base import Done, Error, Session, TextDelta, ToolCall, ToolSpec

# Default model per the standing rule; override for the voice loop (latency/cost) via env.
# Sensible alternatives for an always-listening assistant: claude-sonnet-5, claude-haiku-4-5.
DEFAULT_MODEL = os.environ.get("GEMMA_BRAIN_MODEL", "claude-opus-4-8")

# Spoken replies stay short. The ≤2-sentence narration rule is the orchestrator's job
# (step 6); this default just makes the standalone console test sound like the voice loop.
DEFAULT_SYSTEM = (
    "You are Gemma, a voice assistant. Your words are read aloud, so answer in one or "
    "two spoken sentences unless asked for more. No markdown, lists, code, or emoji."
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


def _classify_badrequest(message: str) -> str:
    """A 400 that's really a context overflow vs. any other malformed request."""
    m = message.lower()
    return "context" if ("context" in m or "too long" in m) else "unknown"


def _error_kind(exc: Exception) -> str:
    """Map an SDK exception to a shared Contract B Error kind (spec/20)."""
    import anthropic

    if isinstance(exc, anthropic.AuthenticationError):
        return "auth"
    if isinstance(exc, anthropic.RateLimitError):
        return "rate_limit"
    if isinstance(exc, anthropic.BadRequestError):
        return _classify_badrequest(str(getattr(exc, "message", exc)))
    if isinstance(exc, anthropic.APIConnectionError):
        return "unavailable"
    if isinstance(exc, anthropic.APIStatusError):
        return "unavailable" if exc.status_code >= 500 else "unknown"
    return "unknown"


class ClaudeBrain:
    """B1. `converse` is an async generator, matching the BrainAdapter Protocol."""

    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None):
        self.model = model
        self._api_key = api_key or _get_key()

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

        import anthropic

        client = anthropic.AsyncAnthropic(api_key=self._api_key)
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
    # The non-trivial branch is the 400 -> context/unknown split; the isinstance ladder
    # is a plain lookup. Test the classifier without constructing SDK exceptions.
    assert _classify_badrequest("prompt is too long: 250000 tokens > 200000") == "context"
    assert _classify_badrequest("input length and max_tokens exceed context limit") == "context"
    assert _classify_badrequest("messages.0.role: unexpected value") == "unknown"
    assert DEFAULT_SYSTEM and "voice" in DEFAULT_SYSTEM.lower()
    print("selfcheck OK: error-kind classifier + defaults")


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
