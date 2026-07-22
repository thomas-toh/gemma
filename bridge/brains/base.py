"""Contract B (spec/20): the one async interface every brain plugs in behind.

Internal message shape is the chat-completions convention (system/user/assistant/tool,
JSON-schema tools). Adapters MUST stream (no buffer-then-return) and MUST surface tool
calls to the orchestrator rather than executing anything themselves (B3 excepted).
"""
from __future__ import annotations

import functools
from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol, Union, runtime_checkable


@functools.cache
def ssl_context():
    """The machine's TLS trust store, parsed ONCE for the life of the process.

    Deliberately provider-agnostic and deliberately NOT in an adapter: this describes this
    computer, not Anthropic. Every cloud SDK we are likely to sit behind Contract B —
    Anthropic, Groq (dictation cleanup, D19), OpenAI — is built on httpx, and httpx rebuilds
    this per client with no memoisation of its own. Measured on the PC 2026-07-22: ~190 ms of
    main-thread CPU each time, re-reading the CA bundle from disk, burned on the
    end-of-speech -> first-word path before a single packet moves. Reused, it is ~0.2 ms.

    Any HTTP-based adapter should pass this to its client. A local B2 (Ollama over plain
    HTTP) needs none of it, which is why this is a helper rather than something the contract
    obliges anyone to use.
    """
    import httpx

    return httpx.create_ssl_context()

# A Contract T registry entry — the shape of an item in spec/schemas/tools.json,
# loaded (hard rule 3), never redefined here. M0 passes an empty list.
ToolSpec = dict[str, Any]


@dataclass
class Session:
    """Per-conversation state the adapter needs. `history` is prior chat-completions
    messages the orchestrator threads through (follow-up window, step 6)."""

    id: str
    local_only: bool = False  # spec/20: utterance must not leave the machine -> block B1
    system: str | None = None  # None -> adapter's default voice prompt
    history: list[dict[str, Any]] = field(default_factory=list)
    # ponytail: `prefs` (spec/20) deferred until something reads it.


# --- BrainEvent = TextDelta | ToolCall | ToolResult | Done | Error (spec/20) ---


@dataclass(frozen=True)
class TextDelta:
    text: str


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    input: dict[str, Any]


@dataclass(frozen=True)
class ToolResult:
    # Emitted only by adapters that run their own tools (B3, M4). B1 never emits this;
    # the orchestrator executes ToolCalls through Contract T and feeds results back.
    id: str
    content: Any


@dataclass(frozen=True)
class Done:
    usage: dict[str, int] | None = None


@dataclass(frozen=True)
class Error:
    # kind is one of the shared set (spec/20): auth | rate_limit | context |
    # unavailable | malformed_tool_call | unknown.
    kind: str
    detail: str


BrainEvent = Union[TextDelta, ToolCall, ToolResult, Done, Error]


@runtime_checkable
class BrainAdapter(Protocol):
    def converse(
        self,
        session: Session,
        utterance: str,
        tools: list[ToolSpec],
    ) -> AsyncIterator[BrainEvent]:
        """Stream BrainEvents for one turn. Implemented as an async generator, so the
        orchestrator drives it with `async for ev in brain.converse(...)`.

        ONE LOOP PER ADAPTER (spec/20). Every call for the life of an adapter instance is
        awaited on the same event loop, so an adapter MAY build a client, connection pool or
        session once and keep it across turns. This is a guarantee the orchestrator owes the
        adapter, not the other way round: it used to run each turn in its own `asyncio.run()`,
        and because an HTTP connection pool belongs to the loop that created it, no adapter
        of any provider could reuse a connection even if it tried.

        The orchestrator closes this generator deterministically (`aclose()`) when a turn is
        aborted, so `finally`/`__aexit__` blocks are the right place to release a stream —
        they run at the abort, not whenever the GC gets round to it."""
        ...
