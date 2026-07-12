"""Contract B (spec/20): the one async interface every brain plugs in behind.

Internal message shape is the chat-completions convention (system/user/assistant/tool,
JSON-schema tools). Adapters MUST stream (no buffer-then-return) and MUST surface tool
calls to the orchestrator rather than executing anything themselves (B3 excepted).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, AsyncIterator, Protocol, Union, runtime_checkable

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
        orchestrator drives it with `async for ev in brain.converse(...)`."""
        ...
