"""Contract T — the tool executor (spec/30).

The registry `spec/schemas/tools.json` is the single source of truth for tool names, parameter
schemas and tiers (hard rule 3); this module never hardcodes a tool definition. Two things it
guarantees, both binding:

- **The brain only ever sees a tool this platform actually IMPLEMENTS** (spec/30 rule 3): a tool
  with no backend, above the enabled tier, or whose connector the user has switched off is
  filtered out of the list handed to the adapter, so the model cannot even name it. `execute()`
  re-checks anyway — the allowlist is the defence, not the model (spec/50 rule 1).
- **Every invocation is audited** (spec/30 rule 2 / spec/50 rule 2 / CLAUDE.md hard rule 4):
  run, refused or errored, one JSONL line lands in `logs/audit.jsonl` — the same `logs/` folder a
  user deletes to purge everything (spec/50 rule 3), so no separate purge action.

Tiers (spec/30): 1 = read-only (no gate) · 2 = reversible (earcon announce) · 3 = destructive
(propose-then-tap confirmation, D26). Only Tier 1 has backends today, and the Tier-3 gate renders
on the Teleprompter (a separate surface), so `MAX_TIER` holds the ceiling at 1.

Connectors (D38) are the SECOND, independent gate: a tier answers "may Gemma do this without
asking?" — danger, the designer's judgement — while a connector answers "does this user want
Gemma reaching that at all?" — consent, theirs. A tool passes both or is not offered. Turning a
connector on can never raise a tier.

    python -m bridge.tools --selfcheck     # offline: filtering, dispatch, refusal, audit
"""
from __future__ import annotations

import ctypes
import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from typing import Callable

from bridge.brains.base import ToolCall
from bridge.config import load_schemas
from bridge import log as _log
from bridge import settings

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
    # Timezone-AWARE local time: astimezone() attaches the OS's current UTC offset, so the model
    # gets an anchor and can convert to any zone from its own knowledge (Tokyo = UTC+9) — no tool
    # and no web call (rung 1). A naive "22:18" gave it nothing to convert FROM, so it refused.
    now = datetime.now().astimezone()
    z = now.strftime("%z")                        # "+0100"; astimezone() always sets an offset
    offset = f"UTC{z[:3]}:{z[3:]}" if z else "UTC"
    parts = [f"Local time: {now.strftime('%H:%M on %A %d %B %Y')} ({offset})"]
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
    # Win32 SYSTEM_POWER_STATUS: the four status fields are BYTE (unsigned) — c_ubyte, not c_byte.
    # A desktop with no battery reports BatteryLifePercent == 255 ("unknown"); read as a SIGNED
    # byte that is -1, which slipped through the 255 check and printed "Battery: -1%".
    _fields_ = [
        ("ACLineStatus", ctypes.c_ubyte),
        ("BatteryFlag", ctypes.c_ubyte),
        ("BatteryLifePercent", ctypes.c_ubyte),
        ("SystemStatusFlag", ctypes.c_ubyte),
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


# --- find_document: the Windows Search index -------------------------------------------------
#
# The model composes the query from the utterance and this retrieves; nothing here ever opens or
# reads a file, so a wrong guess costs a wasted query, not a directory walk.
#
# ponytail: the index is reached through PowerShell's COM rather than pywin32. Its provider
# (Search.CollatorDSO) is OLE-DB — ADO is the only route, the stdlib has no COM, and pywin32 is
# not a dependency of this project (bridge/paste.py made the same call for the clipboard).
# subprocess is a sanctioned Windows backend (docs/04 §Tools). This is NOT the raw-shell tool
# spec/30 rule 1 forbids: the model supplies search WORDS, never a command, and the finished SQL
# is handed over in an environment variable, so nothing the model wrote is ever parsed as
# PowerShell. Swap to pywin32 if the ~0.5 s process start ever matters.

FIND_LIMIT = 8

_FIND_PS = r"""
[Console]::OutputEncoding = [Text.Encoding]::UTF8
try {
  $c = New-Object -ComObject ADODB.Connection
  $c.Open("Provider=Search.CollatorDSO;Extended Properties='Application=Windows'")
  $rs = $c.Execute($env:GEMMA_SQL)
  while (-not $rs.EOF) {
    $d = $rs.Fields.Item(2).Value
    @($rs.Fields.Item(0).Value,
      $(if ($d) { $d.ToString('yyyy-MM-dd') } else { '?' }),
      $rs.Fields.Item(1).Value) -join "`t"
    $rs.MoveNext()
  }
  $c.Close()
} catch { [Console]::Error.WriteLine($_.Exception.Message); exit 1 }
"""


def _search_terms(q, keep: str = "") -> str:
    """Whatever the model wrote, reduced to plain search words. This is the trust boundary shared
    by every retrieval tool here: the result is spliced into a query string literal, so anything
    that could close it or mean something to the query language is DROPPED rather than escaped —
    quotes, parens, `%` and `_` (LIKE wildcards), `*`, `-` operators. These query languages want
    bare terms anyway, so nothing useful is lost. `keep` re-admits characters a particular field
    genuinely needs (an address needs `@` and `.`); it is never given a quote.
    An absent optional parameter is "", NOT the string "None" — that would search for the word."""
    if q is None:
        return ""
    return " ".join(re.sub(rf"[^\w\s{re.escape(keep)}]", " ", str(q)).split())[:120]


def _iso_date(s) -> str:
    """`since` as a bare YYYY-MM-DD, or "" if the model sent something else (it does not go into
    the query then). Same reason as above: this ends up inside a SQL literal."""
    try:
        return datetime.fromisoformat(str(s)[:10]).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return ""


def _find_document(args: dict) -> str:
    if sys.platform != "win32":
        # ponytail: registered on every platform and degrading here, as read_clipboard does —
        # a per-platform _BACKENDS split earns its keep only when a macOS backend actually exists.
        return "Searching files needs the Windows Search index, which this machine does not have."

    query = _search_terms(args.get("query"))
    if not query:
        return "No usable search terms in that request — I need a word or two from the document."

    # Each term double-quoted and AND-ed: bare multi-word text is a syntax error to CONTAINS, and
    # quoting also demotes a stray AND/OR/NEAR from operator to literal word.
    where = [f"""CONTAINS('{' AND '.join(f'"{t}"' for t in query.split())}')"""]
    # The valid kinds live in the registry, not here (hard rule 3) — read them back off it.
    entry = _entry("find_document") or {}
    kinds = entry.get("parameters", {}).get("properties", {}).get("kind", {}).get("enum", [])
    if args.get("kind") in kinds:
        where.append(f"System.Kind = '{args['kind']}'")
    if since := _iso_date(args.get("since")):
        where.append(f"System.DateModified >= '{since}'")

    # Ranked, not date-sorted: `since` already handles "from this day", and on a real index a
    # date sort floats junk that merely CONTAINS the words (a word-list file matches everything)
    # above the document actually about them. The date rides along in each line regardless.
    sql = (f"SELECT TOP {FIND_LIMIT} System.ItemNameDisplay, System.ItemPathDisplay, "
           f"System.DateModified FROM SystemIndex WHERE {' AND '.join(where)} "
           f"ORDER BY System.Search.Rank DESC")

    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", _FIND_PS],
            env={**os.environ, "GEMMA_SQL": sql},
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20,
            creationflags=subprocess.CREATE_NO_WINDOW,  # no console flash over the overlay
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("find_document: %s", exc)
        return "Windows Search did not answer in time, so I could not look."

    if proc.returncode:
        log.warning("find_document: %s", proc.stderr.strip()[:200])
        return "Windows Search is not available on this machine (the index service may be off)."

    rows = [r.split("\t", 2) for r in proc.stdout.splitlines() if r.strip()]
    hits = [f"{n} · {d} · {p}" for n, d, p in (r for r in rows if len(r) == 3)]
    if not hits:
        return f"Nothing in the Windows Search index matches {query!r}."
    return f"Indexed matches for {query!r} (best first):\n" + "\n".join(hits)


# --- search_email: the desktop Outlook store --------------------------------------------------
#
# find_document's shape, second corpus: the model composes the criteria, the STORE does the
# filtering, and only headers come back — sender, date, subject. Bodies are searched (that is what
# `query` is for) but never returned, and nothing is opened, replied to or sent.
#
# Strictly the LOCAL desktop store over MAPI — no Graph, no cloud API, no credentials (spec/50).
# Same PowerShell-COM subprocess as find_document, and for the same reason: Outlook automation is
# COM-only and pywin32 is not a dependency.

MAIL_LIMIT = 8

_MAIL_PS = r"""
[Console]::OutputEncoding = [Text.Encoding]::UTF8
try {
  $ol = New-Object -ComObject Outlook.Application
  $inbox = $ol.GetNamespace("MAPI").GetDefaultFolder(6)   # olFolderInbox
} catch { [Console]::Error.WriteLine($_.Exception.Message); exit 2 }
try {
  $items = $inbox.Items
  $items.Sort("[ReceivedTime]", $true)                    # newest first, BEFORE restricting
  if ($env:GEMMA_DASL) { $items = $items.Restrict($env:GEMMA_DASL) }
  $n = 0
  foreach ($m in $items) {
    if ($n -ge [int]$env:GEMMA_MAX) { break }             # stop early: never walk a whole mailbox
    if ($m.Class -ne 43) { continue }                     # olMail only — a meeting request has no sender
    $d = $m.ReceivedTime
    @($m.SenderName, $(if ($d) { $d.ToString('yyyy-MM-dd HH:mm') } else { '?' }), $m.Subject) -join "`t"
    $n++
  }
} catch { [Console]::Error.WriteLine($_.Exception.Message); exit 3 }
"""


def _mail_profile_exists() -> bool:
    """Is there a MAPI profile at all? Checked in the REGISTRY, before any COM call: asking
    Outlook for a mailbox when no profile exists can raise a "create a profile" DIALOG on the
    desktop, and a modal prompt behind a voice assistant is a hang with no way to answer it.
    ponytail: Office 16.0 covers 2016 through 365 — add a version if an older Outlook ever
    turns up. A profile existing does not prove it WORKS; the COM path still degrades on its own."""
    import winreg

    for path in (r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Windows Messaging Subsystem\Profiles",
                 r"SOFTWARE\Microsoft\Office\16.0\Outlook\Profiles"):
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, path) as key:
                if winreg.QueryInfoKey(key)[0]:  # at least one profile subkey
                    return True
        except OSError:
            continue
    return False


def _mail_filter(args: dict) -> tuple[str, list[str]]:
    """Build the DASL restriction, plus a plain-English echo of what it asks for. A DASL filter is
    an injection surface exactly like the SQL one, so every value goes through `_search_terms`
    first and dates through `_iso_date` — a value that sanitises to nothing is simply left out."""
    clauses, said = [], []
    p = "urn:schemas:httpmail:"

    if sender := _search_terms(args.get("sender"), keep="@.-"):
        clauses.append(f"""("{p}fromname" LIKE '%{sender}%' OR "{p}fromemail" LIKE '%{sender}%')""")
        said.append(f"from {sender!r}")
    if subject := _search_terms(args.get("subject")):
        clauses.append(f""""{p}subject" LIKE '%{subject}%'""")
        said.append(f"subject containing {subject!r}")
    if query := _search_terms(args.get("query")):
        # Word by word, not as one phrase: "lease renewal" should still find a mail whose subject
        # says "renewal of the lease". Each word must appear in the subject OR the body.
        for word in query.split():
            clauses.append(f"""("{p}subject" LIKE '%{word}%' OR "{p}textdescription" LIKE '%{word}%')""")
        said.append(f"mentioning {query!r}")
    if since := _iso_date(args.get("since")):
        clauses.append(f""""{p}datereceived" >= '{since}'""")
        said.append(f"on or after {since}")
    if before := _iso_date(args.get("before")):
        clauses.append(f""""{p}datereceived" < '{before}'""")
        said.append(f"before {before}")

    return ("@SQL=" + " AND ".join(clauses) if clauses else ""), said


def _search_email(args: dict) -> str:
    if sys.platform != "win32":
        return "Searching mail needs Outlook on Windows, which this machine does not have."
    if not _mail_profile_exists():
        return ("Outlook has no mail profile set up on this machine, so there is no mailbox to "
                "search.")

    dasl, said = _mail_filter(args)
    asked = ", ".join(said) if said else "the most recent mail"

    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", _MAIL_PS],
            env={**os.environ, "GEMMA_DASL": dasl, "GEMMA_MAX": str(MAIL_LIMIT)},
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30,
            creationflags=subprocess.CREATE_NO_WINDOW,  # no console flash over the overlay
        )
    except (OSError, subprocess.SubprocessError) as exc:
        # ponytail: 30 s covers a cold Outlook start; a warm one answers in well under a second.
        log.warning("search_email: %s", exc)
        return "Outlook did not answer in time, so I could not search your mail."

    if proc.returncode == 2:
        log.warning("search_email: no Outlook (%s)", proc.stderr.strip()[:200])
        return "Outlook is not available on this machine, so I could not search your mail."
    if proc.returncode:
        log.warning("search_email: %s", proc.stderr.strip()[:200])
        return "Outlook could not run that search."

    rows = [r.split("\t", 2) for r in proc.stdout.splitlines() if r.strip()]
    hits = [f"{s} · {d} · {subj}" for s, d, subj in (r for r in rows if len(r) == 3)]
    if not hits:
        return f"No mail in the Outlook inbox matches: {asked}."
    return f"Inbox matches ({asked}), newest first:\n" + "\n".join(hits)


_BACKENDS: dict[str, Callable[[dict], str]] = {
    "system_status": _system_status,
    "read_clipboard": _read_clipboard,
    "find_document": _find_document,
    "search_email": _search_email,
}


# --- the registry, the filtered tool list, and dispatch --------------------------------------


def _registry() -> list[dict]:
    """The raw Contract T registry (spec/schemas/tools.json), loaded fresh (hard rule 3)."""
    return load_schemas()["tools"]["tools"]


def _entry(name: str) -> dict | None:
    return next((t for t in _registry() if t.get("name") == name), None)


def _connectors() -> dict[str, bool]:
    """`{connector id: is it switched on}`, read FRESH from the user's settings (D38). Derived
    from the schema's `connector_*` entries rather than a list here, so adding a connector is a
    JSON edit (hard rule 3). Settings are re-read every turn, which is why a toggle applies to
    the next utterance with no restart and no watcher."""
    now = settings.load()
    return {s["connector"]: bool(now.get(key))
            for key, s in settings.schema()["settings"].items() if "connector" in s}


def _connected(entry: dict, on: dict[str, bool]) -> bool:
    """Has the user consented to this tool's connector? A tool naming a connector that has no
    setting is treated as OFF, not on: an unrecognised id must fail closed, or a typo in the
    registry would quietly hand the brain a tool nobody agreed to."""
    return on.get(entry.get("connector"), False)


def label_of(name: str) -> str:
    """A tool said in a sentence a person would use, from the registry's `label` — or the bare
    tool name if it has none. What the island shows while the tool runs and what the connector
    card lists (D38); one wording, read from the schema by both (hard rule 3)."""
    return (_entry(name) or {}).get("label", "") or name


def implemented(entry: dict) -> bool:
    """Could this tool run AT ALL on this machine — is there a backend, and is it within the tier
    ceiling? Deliberately the designer's half of the question only; whether the user WANTS it is
    the connector's, asked separately. The settings window calls this so a connector card can show
    which of its tools are real today rather than promising what the tier still forbids."""
    return entry.get("name") in _BACKENDS and entry.get("tier", 99) <= MAX_TIER


def tool_specs() -> list[dict]:
    """The tools handed to the brain this turn: only those with a backend on this platform,
    within the enabled tier, AND whose connector the user has switched on (spec/30 rule 3 — the
    model never receives a tool it cannot call). Tier and connector are independent: either one
    alone is enough to withhold a tool."""
    on = _connectors()
    return [t for t in _registry() if implemented(t) and _connected(t, on)]


def disabled_note() -> str:
    """One sentence for the system prompt naming what the user has switched OFF, or "" if
    nothing is (D38). Without it a hidden tool is simply absent, and a model asked to find a file
    improvises instead of saying it cannot — the can't-rendered-as-didn't failure D36 found in
    `search_email`, which is a lie about what happened, not merely an unhelpful answer.

    Only connectors that would OTHERWISE be usable are named — a connector with no implemented,
    in-tier tool behind it is left unmentioned, because telling the brain "Web is off" implies
    switching it on would work. Labels come from the schema, so this text follows the pane."""
    on = _connectors()
    live = {t["connector"] for t in _registry() if implemented(t)}
    off = [s["label"] for s in settings.schema()["settings"].values()
           if s.get("connector") in live and not on.get(s["connector"])]
    if not off:
        return ""
    return (f" Switched off in this user's settings, so you have no way to reach them: "
            f"{', '.join(off)}. If one of those is what a request needs, say plainly that it is "
            f"switched off in Gemma's settings — never imply you looked and found nothing.")


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
    elif not _connected(entry, _connectors()):
        # The consent gate, checked again here and not only in the filter (D38): a tool the user
        # switched off must be dead even if something else calls it — history from before the
        # toggle, a resampled round, a future caller that skips tool_specs().
        content = f"Tool {name!r} is switched off in this user's settings."
        outcome = f"refused:connector_{entry.get('connector')}"
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
    # No network, no real audio: the logic worth guarding is the two GATES (a tool the model must
    # not see), dispatch, the refusal backstop, and that every path audits.
    from pathlib import Path
    import tempfile

    global AUDIT_FILE

    reg = _registry()
    assert reg, "spec/schemas/tools.json must carry the starter tools"
    assert all(t.get("connector") for t in reg), "every tool declares a connector (D38)"

    # Both gates read the USER's settings, so pointing them at an empty file is what makes this
    # check deterministic — otherwise it would pass or fail with whatever is toggled on this box.
    # No try/finally: this runs as a one-shot script, so a leaked env var in a process that is
    # either about to print OK or about to die on a traceback buys nothing.
    settings_dir = tempfile.TemporaryDirectory()
    os.environ["GEMMA_SETTINGS"] = str(Path(settings_dir.name) / "settings.json")
    keys = [k for k, s in settings.schema()["settings"].items() if "connector" in s]
    assert keys, "the connectors pane must declare its settings (schemas/settings.json)"

    # A fresh install: System only. Files, Email and Clipboard are consent, not danger, and stay
    # off until they are asked for (D38) — so Gemma answers and dictates and reaches nothing.
    assert {t["name"] for t in tool_specs()} == {"system_status"}, tool_specs()

    # Every connector on. The four Tier-1 tools appear — and not one Tier-2 tool does, which is
    # the point: consent cannot raise a tier, so the two gates are genuinely independent.
    for k in keys:
        settings.set(k, True)
    offered = {t["name"] for t in tool_specs()}
    assert offered == {"system_status", "read_clipboard", "find_document", "search_email"}, offered
    for t in reg:
        if t["tier"] > MAX_TIER:
            assert t["name"] not in offered, f"{t['name']}: tier {t['tier']} must not be offered"
    assert all("tier" in t for t in tool_specs()), "specs carry the tier for the loop to read"
    # ...and with everything on there is nothing to warn the brain about.
    assert disabled_note() == "", disabled_note()

    # The connector alone is also sufficient to exclude: switching Files off removes exactly
    # find_document and leaves every other tool where it was.
    settings.set("connector_files", False)
    assert {t["name"] for t in tool_specs()} == offered - {"find_document"}, tool_specs()

    # ...and the brain is TOLD, in prose. A hidden tool is merely absent, which reads as "no such
    # capability exists" and gets improvised around — the can't-rendered-as-didn't failure of D36.
    # Only connectors with a usable tool behind them are named: saying "Web is off" would imply
    # switching it on would work, and there is no web tool at all.
    note = disabled_note()
    assert "Files" in note and "switched off" in note, note
    for absent in ("Web", "Apps & media", "MCP"):
        assert absent not in note, f"a connector with no live tool must not be named: {note}"
    settings.set("connector_files", True)

    # find_document's trust boundary: the model's words end up inside a SQL string literal, so
    # everything that could close it or steer the query is dropped, and a bad date never lands.
    assert _search_terms("bob's ' OR 1=1 --") == "bob s OR 1 1", _search_terms("bob's ' OR 1=1 --")
    assert "'" not in _search_terms("a'b\"c;d`e$f(g)") and "$" not in _search_terms("a$b")
    assert _search_terms("café über") == "café über", "real words survive, only punctuation goes"
    # An OMITTED optional parameter must vanish, not become a search for the word "None".
    assert _search_terms("!!!") == "" and _search_terms(None) == ""
    # `keep` re-admits what an address needs, and not one character more.
    assert _search_terms("sarah.jones@example.com", keep="@.-") == "sarah.jones@example.com"
    assert "'" not in _search_terms("o'brien@x.com", keep="@.-")
    assert _iso_date("2026-01-31") == "2026-01-31"
    assert _iso_date("last tuesday") == "" and _iso_date(None) == "" and _iso_date(7) == ""

    # search_email's DASL is built from the same sanitised parts. Nothing the model wrote can
    # close the string literal or smuggle in a LIKE wildcard, and an omitted param adds no clause.
    dasl, said = _mail_filter({"sender": "sarah", "since": "2026-05-01"})
    assert dasl.startswith("@SQL=") and "fromname" in dasl and "datereceived" in dasl, dasl
    assert "subject\" LIKE" not in dasl, "an omitted parameter must not add a clause"
    assert said == ["from 'sarah'", "on or after 2026-05-01"], said
    hostile = _mail_filter({"subject": "x%' OR '1'='1"})[0]
    assert hostile.count("'") == 2, f"the value must stay inside ONE literal: {hostile}"
    assert "x OR 1 1" in hostile, f"...as its declawed self: {hostile}"
    assert _mail_filter({})[0] == "", "no criteria means no restriction, not a malformed one"
    # Each free-text word gets its own subject-OR-body clause, so word order never matters.
    assert _mail_filter({"query": "lease renewal"})[0].count("textdescription") == 2

    with tempfile.TemporaryDirectory() as tmp:
        AUDIT_FILE = Path(tmp) / "audit.jsonl"

        # An unknown tool is refused, not executed — the allowlist backstop behind the filter.
        content, outcome = execute(ToolCall("1", "no_such_tool", {}), session="s", transcript="hi")
        assert outcome == "refused:unknown_tool" and "not available" in content, (content, outcome)

        # A Tier-2 tool that IS in the registry but has no backend is refused too (defence in
        # depth: even if the filter were bypassed, execute() still says no).
        content, outcome = execute(ToolCall("2", "open_app", {"app": "spotify"}))
        assert outcome == "refused:unknown_tool", (content, outcome)

        # A real Tier-1 tool runs and returns something the brain can read — including a UTC
        # offset, so a "what time in <city>" question is arithmetic the model does itself (rung 1).
        content, outcome = execute(ToolCall("3", "system_status", {}), session="s")
        assert outcome == "ok" and "time" in content.lower(), (content, outcome)
        assert "utc" in content.lower(), f"time needs a UTC anchor for zone conversion: {content!r}"

        # read_clipboard runs; on a headless runner with no clipboard it degrades to a string
        # rather than raising (like paste.py's own selfcheck).
        content, outcome = execute(ToolCall("4", "read_clipboard", {}))
        assert outcome in ("ok", "error"), (content, outcome)

        # find_document dispatches and ALWAYS answers in prose, whatever the machine offers: a
        # real hit list on an indexed box, "not available" off Windows or with the index service
        # off (a CI runner). A nonsense term keeps it deterministic — the point is the round trip,
        # not the corpus, so no live index is required here.
        content, outcome = execute(ToolCall("5", "find_document", {"query": "zzqx nosuch term"}))
        assert outcome == "ok" and content.strip(), (content, outcome)

        # ...including when the model sends junk in the optional params: an unknown `kind` and an
        # unparseable `since` are dropped, not passed through to the query.
        content, outcome = execute(
            ToolCall("6", "find_document", {"query": "zzqx", "kind": "spaceship", "since": "soon"})
        )
        assert outcome == "ok" and content.strip(), (content, outcome)

        # search_email dispatches and answers in prose on every machine: real headers where
        # Outlook has a profile, "not available" where it does not (a CI runner, and this box —
        # Outlook is installed here but no profile exists). No live mailbox is required.
        content, outcome = execute(ToolCall("7", "search_email", {"sender": "zzqx", "since": "2026-01-01"}))
        assert outcome == "ok" and content.strip(), (content, outcome)

        # ...and with NO criteria at all, which is legal here (every parameter is optional) and
        # must mean "the most recent mail", not a malformed restriction.
        content, outcome = execute(ToolCall("8", "search_email", {}))
        assert outcome == "ok" and content.strip(), (content, outcome)

        # A tool whose connector the user switched off is REFUSED even when called directly, not
        # merely hidden (D38): the filter is convenience, the allowlist is the defence. This is
        # the path a stale round or a caller that skips tool_specs() would take.
        settings.set("connector_clipboard", False)
        content, outcome = execute(ToolCall("9", "read_clipboard", {}))
        assert outcome == "refused:connector_clipboard", (content, outcome)
        assert "switched off" in content, content
        settings.set("connector_clipboard", True)

        # Every one of those nine calls left exactly one audit line, with the required fields —
        # a refused call is audited exactly as a run one is (spec/30 rule 2).
        lines = AUDIT_FILE.read_text(encoding="utf-8").splitlines()
        assert len(lines) == 9, f"every call must audit once, got {len(lines)}"
        rec = json.loads(lines[0])
        assert set(rec) == {"ts", "session", "transcript_snippet", "tool", "args",
                            "outcome", "duration_ms"}, sorted(rec)
        assert rec["tool"] == "no_such_tool" and rec["session"] == "s"
        assert rec["transcript_snippet"] == "hi", "the triggering transcript is recorded"

    os.environ.pop("GEMMA_SETTINGS", None)
    print(f"tools selfcheck OK: {len(offered)} Tier-{MAX_TIER} tools offered with every "
          f"connector on ({', '.join(sorted(offered))}); tier, connector and the allowlist each "
          f"refuse on their own, and every call is audited")


if __name__ == "__main__":
    _selfcheck()
