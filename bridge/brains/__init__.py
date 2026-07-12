"""Brain adapters (Contract B, spec/20). One async interface; every brain plugs in
behind it. B1 (Claude API) is the M0 build (step 5); B2/B3 land at M2/M4."""
from .base import (
    BrainAdapter,
    BrainEvent,
    Done,
    Error,
    Session,
    TextDelta,
    ToolCall,
    ToolResult,
    ToolSpec,
)

__all__ = [
    "BrainAdapter",
    "BrainEvent",
    "Done",
    "Error",
    "Session",
    "TextDelta",
    "ToolCall",
    "ToolResult",
    "ToolSpec",
]
