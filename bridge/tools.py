"""Contract T — the tool executor (spec/30).

The registry `spec/schemas/tools.json` is the single source of truth for tool names, parameter
schemas and tiers (hard rule 3); this module never hardcodes a tool definition. Two things it
guarantees, both binding:

- **The brain only ever sees a tool this platform actually IMPLEMENTS** (spec/30 rule 3): a tool
  with no backend, or above the enabled tier, is filtered out of the list handed to the adapter,
  so the model cannot even name it. `execute()` re-checks anyway — the allowlist is the defence,
  not the model (spec/50 rule 1).
- **Every invocation is audited** (spec/30 rule 2 / spec/50 rule 2 / CLAUDE.md hard rule 4):
  run, refused or errored, one JSONL line lands in `logs/audit.jsonl` — the same `logs/` folder a
  user deletes to purge everything (spec/50 rule 3), so no separate purge action.

Tiers (spec/30): 1 = read-only (no gate) · 2 = reversible (earcon announce) · 3 = destructive
(propose-then-tap confirmation, D26). Only Tier 1 has backends today, and the Tier-3 gate renders
on the Teleprompter (a separate surface), so `MAX_TIER` holds the ceiling at 1.

    python -m bridge.tools --selfcheck     # offline: filtering, dispatch, refusal, audit
"""
from __future__ import annotations

import ctypes
import json
import logging
import sys
import time
from datetime import datetime
from typing import Callable

from bridge.brains.base import ToolCall
from bridge.config import load_schemas
from bridge import log as _log

log = logging.getLogger("gemma.tools")

# One line per tool call, appended, never rewritten. Beside gemma.log so "delete logs/" purges
# both in one action (spec/50 rule 3). Resolved through bridge.log so its selfcheck can redirect it.
AUDIT_FILE = _log.LOG_DIR / "audit.jsonl"

# The highest tier `execute()` will run and `tool_specs()` will offer. Raising it is how a tier
# turns on, once its backend AND its gate exist. Tier 2 needs the announce earcon wired; Tier 3
# needs the propose-then-tap confirmation on the Teleprompter (D26) — neither built.
# ponytail: a single ceiling, not per-tier flags — split only if a tier needs enabling alone.
MAX_TIER = 1

CLIP_LIMIT = 2000  # matches the read_clipboard registry description


# --- Tier-1 backends: name -> callable(args) -> str. The tier itself comes from the registry. ---


def _read_clipboard(args: dict) -> str:
    from bridge.paste import get_clipboard_text

    text = get_clipboard_text()
    if not text:
        return "(the clipboard is empty or holds no text)"
    return text[:CLIP_LIMIT]


def _system_status(args: dict) -> str:
    parts = [f"Local time: {datetime.now().strftime('%H:%M on %A %d %B %Y')}"]
    if sys.platform == "win32":
        parts += [p for p in (_win_active_window(), _win_battery()) if p]
    # ponytail: volume level and media playback state (promised by the registry description) need
    # COM (IAudioEndpointVolume) and WinRT (GlobalSystemMediaTransportControls) respectively —
    # real work, deferred. The tool still returns useful status; add the fields when a backend lands.
    return "\n".join(parts)


def _win_active_window() -> str:
    u = ctypes.windll.user32
    hwnd = u.GetForegroundWindow()
    if not hwnd:
        return ""
    length = u.GetWindowTextLengthW(hwnd)
    buf = ctypes.create_unicode_buffer(length + 1)
    u.GetWindowTextW(hwnd, buf, length + 1)
    return f"Active window: {buf.value or '(untitled)'}"


class _PowerStatus(ctypes.Structure):
    _fields_ = [
        ("ACLineStatus", ctypes.c_byte),
        ("BatteryFlag", ctypes.c_byte),
        ("BatteryLifePercent", ctypes.c_byte),
        ("SystemStatusFlag", ctypes.c_byte),
        ("BatteryLifeTime", ctypes.c_ulong),
        ("BatteryFullLifeTime", ctypes.c_ulong),
    ]


def _win_battery() -> str:
    sps = _PowerStatus()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(sps)):
        return ""
    pct = sps.BatteryLifePercent
    if pct == 255:  # 255 = "unknown", which a desktop with no battery reports
        return "Power: AC (no battery)"
    state = "charging" if sps.ACLineStatus == 1 else "on battery"
    return f"Battery: {pct}% ({state})"


_BACKENDS: dict[str, Callable[[dict], str]] = {
    "system_status": _system_status,
    "read_clipboard": _read_clipboard,
}


# --- the registry, the filtered tool list, and dispatch --------------------------------------


def _registry() -> list[dict]:
    """The raw Contract T registry (spec/schemas/tools.json), loaded fresh (hard rule 3)."""
    return load_schemas()["tools"]["tools"]


def _entry(name: str) -> dict | None:
    return next((t for t in _registry() if t.get("name") == name), None)


def tool_specs() -> list[dict]:
    """The tools handed to the brain this turn: only those with a backend on this platform and
    within the enabled tier (spec/30 rule 3 — the model never receives a tool it cannot call)."""
    return [
        t for t in _registry()
        if t.get("name") in _BACKENDS and t.get("tier", 99) <= MAX_TIER
    ]


def execute(call: ToolCall, *, session: str = "", transcript: str = "") -> tuple[str, str]:
    """Run one tool call through Contract T. Returns `(content, outcome)` and NEVER raises: a
    tool fault becomes a string the brain reads and narrates, not an exception that kills the
    turn. Every path — run, refused, errored — is audited before returning (spec/30 rule 2)."""
    name = call.name
    args = dict(call.input or {})
    t0 = time.perf_counter()

    entry = _entry(name)
    backend = _BACKENDS.get(name)
    if entry is None or backend is None:
        # Not in the registry, or no backend on this platform. The allowlist is the defence.
        content, outcome = f"Tool {name!r} is not available.", "refused:unknown_tool"
    elif entry.get("tier", 99) > MAX_TIER:
        content = f"Tool {name!r} needs a confirmation step that is not built yet."
        outcome = f"refused:tier_{entry.get('tier')}"
    else:
        try:
            content, outcome = backend(args), "ok"
        except Exception as exc:  # noqa: BLE001 — a tool fault is data for the brain, not a crash
            content, outcome = f"Tool {name!r} failed: {exc}", "error"
            log.warning("tool %s failed: %s", name, exc)

    _audit(session, transcript, name, args, outcome, round((time.perf_counter() - t0) * 1000, 1))
    return content, outcome


def _audit(session, transcript, tool, args, outcome, duration_ms) -> None:
    """Append one audit record (spec/30 rule 2 shape). Best-effort on the WRITE: a full disk must
    not take the daemon down mid-turn, so a failed write is logged loudly and the call proceeds —
    the same degrade-don't-crash posture bridge.log takes.
    ponytail: warn-and-proceed rather than refuse-if-unloggable; harden to refuse only if the
    audit trail ever has to be provably complete on this prototype."""
    record = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "session": session,
        "transcript_snippet": (transcript or "")[:200],
        "tool": tool,
        "args": args,
        "outcome": outcome,
        "duration_ms": duration_ms,
    }
    try:
        AUDIT_FILE.parent.mkdir(exist_ok=True)
        with AUDIT_FILE.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        log.error("AUDIT WRITE FAILED for %s (%s) — call ran unlogged", tool, exc)


def _selfcheck() -> None:
    # No network, no real audio: the logic worth guarding is the tool FILTER (a tool the model
    # must not see), dispatch, the refusal backstop, and that every path audits.
    from pathlib import Path
    import tempfile

    global AUDIT_FILE

    reg = _registry()
    assert reg, "spec/schemas/tools.json must carry the starter tools"

    # The filter is the security boundary: the brain must be offered ONLY implemented, in-tier
    # tools. Every Tier-2/3 starter tool (open_app, set_timer, …) must be absent, because a tool
    # the model cannot see is a tool it cannot call (spec/30 rule 3).
    offered = {t["name"] for t in tool_specs()}
    assert offered == {"system_status", "read_clipboard"}, offered
    for t in reg:
        if t["tier"] > MAX_TIER:
            assert t["name"] not in offered, f"{t['name']}: tier {t['tier']} must not be offered"
    assert all("tier" in t for t in tool_specs()), "specs carry the tier for the loop to read"

    with tempfile.TemporaryDirectory() as tmp:
        AUDIT_FILE = Path(tmp) / "audit.jsonl"

        # An unknown tool is refused, not executed — the allowlist backstop behind the filter.
        content, outcome = execute(ToolCall("1", "no_such_tool", {}), session="s", transcript="hi")
        assert outcome == "refused:unknown_tool" and "not available" in content, (content, outcome)

        # A Tier-2 tool that IS in the registry but has no backend is refused too (defence in
        # depth: even if the filter were bypassed, execute() still says no).
        content, outcome = execute(ToolCall("2", "open_app", {"app": "spotify"}))
        assert outcome == "refused:unknown_tool", (content, outcome)

        # A real Tier-1 tool runs and returns something the brain can read.
        content, outcome = execute(ToolCall("3", "system_status", {}), session="s")
        assert outcome == "ok" and "time" in content.lower(), (content, outcome)

        # read_clipboard runs; on a headless runner with no clipboard it degrades to a string
        # rather than raising (like paste.py's own selfcheck).
        content, outcome = execute(ToolCall("4", "read_clipboard", {}))
        assert outcome in ("ok", "error"), (content, outcome)

        # Every one of those four calls left exactly one audit line, with the required fields.
        lines = AUDIT_FILE.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 4, f"every call must audit once, got {len(lines)}"
        rec = json.loads(lines[0])
        assert set(rec) == {"ts", "session", "transcript_snippet", "tool", "args",
                            "outcome", "duration_ms"}, sorted(rec)
        assert rec["tool"] == "no_such_tool" and rec["session"] == "s"
        assert rec["transcript_snippet"] == "hi", "the triggering transcript is recorded"

    print(f"tools selfcheck OK: {len(offered)} Tier-{MAX_TIER} tools offered "
          f"({', '.join(sorted(offered))}), unknown/out-of-tier refused, every call audited")


if __name__ == "__main__":
    _selfcheck()
