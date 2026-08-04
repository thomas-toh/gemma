"""Contract T tool-choice eval (was backend.orchestrator --check-tools). — Run:  python -m eval.tool_check   |   python -m eval.tool_check --selfcheck"""
from backend.orchestrator import (
    tool_specs, _start_local_servers, router, build_model, DAEMON_MODEL,
    DEFAULT_SYSTEM, disabled_note, Session, _one_round,
)

# Contract T, LIVE: does the MODEL pick the right tool for a plain request? That is the one thing
# no offline check can reach — `backend.tools --selfcheck` proves the executor, and the backends were
# driven by hand, but "a model decided to call this" is the empty column in STATE's tool ledger.
#
# `want_arg` is (parameter, substring), matched case-insensitively, because a model may reasonably
# say "Spotify" or "spotify" and either is right. `want_tool = ""` means NO tool should be called —
# over-eager tool use is a real failure mode and needs a case, not an assumption.
_TOOL_CASES = [
    ("open Spotify",                  "open_app",      ("app", "spotify"),      "the plain case"),
    ("launch Notepad for me",         "open_app",      ("app", "notepad"),      "a different verb"),
    ("bring File Explorer to the front", "focus_window", ("title_query", "explorer"),
     "switching to something already open is NOT open_app"),
    ("pause the music",               "media_control", ("action", "play_pause"), "a media key"),
    ("turn the volume up",            "media_control", ("action", "volume_up"),  "...and a volume key"),
    ("mute the sound",                "media_control", ("action", "mute_toggle"), "...and mute"),
    ("what time is it",               "system_status", None,
     "a READ must stay a read — asking the time must never open or move anything"),
    ("what did I just copy",          "read_clipboard", None,   "the other read"),
    ("how are you today",             "",              None,
     "no tool fits, so none should be called (the over-eager failure)"),
]


def _check_tools() -> None:
    """Contract T, LIVE: put each `_TOOL_CASES` utterance to the real assistant model with the
    real tool list and check WHICH tool it asks for.

    Nothing is executed. `_one_round` surfaces the tool calls and never runs them, which is what
    makes this safe to run repeatedly — it will not open nine apps or change your volume.

    Connectors are read, never written: a case whose tool the user has switched off is SKIPPED and
    said so. Consent is the user's, and a test that flips it to make itself pass is worse than a
    test that admits it could not run.
    """
    import asyncio

    offered = {t["name"] for t in tool_specs()}
    print(f"tools offered to the model: {', '.join(sorted(offered)) or '(none)'}")
    missing = {c[1] for c in _TOOL_CASES if c[1]} - offered
    if missing:
        print(f"NOT offered, so their cases will skip: {', '.join(sorted(missing))}\n"
              f"  (turn the matching connector on in Settings > Connectors — Apps & media is off "
              f"by default)")

    _start_local_servers()          # so this runs without the daemon up, if the role is local
    model = router.build_for_role("assistant") or build_model(None, DAEMON_MODEL)
    system = DEFAULT_SYSTEM + disabled_note()
    rows, failures, skipped = [], 0, 0

    # Printed as each case LANDS, not batched at the end: every case is a full model round, so a
    # silent run looks hung for a minute or two on a local model (seen 2026-08-03).
    for n, (said, want_tool, want_arg, why) in enumerate(_TOOL_CASES, start=1):
        head = f"[{n}/{len(_TOOL_CASES)}] {said!r}"
        if want_tool and want_tool not in offered:
            print(f"skip {head}\n       {want_tool} is not switched on", flush=True)
            rows.append(("skip", said, f"{want_tool} is not switched on", why))
            skipped += 1
            continue
        print(f"...  {head}", end="\r", flush=True)      # overwritten by the verdict below
        session = Session(id="toolcheck", system=system,
                          history=[{"role": "user", "content": said}])
        text, calls, err, malformed, _usage = asyncio.run(_one_round(model, session, tool_specs()))
        if err and not malformed:
            print(f"SKIPPED — the assistant model is unavailable ({err})")
            return
        got = calls[0].name if calls else ""
        args = dict(calls[0].input or {}) if calls else {}

        if malformed:
            verdict, detail = "FAIL", "the model produced a malformed tool call"
        elif got != want_tool:
            verdict = "FAIL"
            detail = f"called {got or '(nothing)'}, wanted {want_tool or '(nothing)'}"
            if not got:
                # What it said INSTEAD is the whole diagnosis. "I can't know that" is an honest
                # miss; inventing a time is a lie; saying nothing at all is a broken turn. Three
                # very different faults that all print as "called nothing" without this.
                detail += f" — it said {(text.strip() or '(nothing at all)')[:140]!r}"
        elif want_arg and want_arg[1] not in str(args.get(want_arg[0], "")).lower():
            verdict = "FAIL"
            detail = f"{want_tool}({args}) — {want_arg[0]} should contain {want_arg[1]!r}"
        else:
            verdict = "ok"
            detail = f"{got}({args})" if got else "answered without a tool"
        failures += verdict == "FAIL"
        rows.append((verdict, said, detail, why))
        print(f"{verdict:4} {head}\n       {detail}\n       ({why})", flush=True)

    ran = len(_TOOL_CASES) - skipped
    print(f"\ntool-call check: {ran - failures}/{ran} run, {skipped} skipped, "
          f"model {getattr(model, 'model', '?')}")
    if failures:
        raise SystemExit(f"{failures} case(s) FAILED")

def _selfcheck() -> None:
    # The live tool-call suite (`--check-tools`) needs a model, so what is checkable offline is
    # that its cases are ANSWERABLE: every tool it names exists, every parameter it expects is
    # one that tool actually takes, and every enum value it wants is in the enum. Without this a
    # renamed tool or parameter reads as nine model failures rather than a stale test.
    from shared.config import load_schemas as _schemas
    _reg = {t["name"]: t for t in _schemas()["tools"]["tools"]}
    for _said, _want, _arg, _why in _TOOL_CASES:
        assert _want == "" or _want in _reg, f"_TOOL_CASES names an unknown tool: {_want!r}"
        if _arg:
            _props = _reg[_want]["parameters"]["properties"]
            assert _arg[0] in _props, f"{_want} takes no parameter {_arg[0]!r}"
            _enum = _props[_arg[0]].get("enum")
            assert _enum is None or _arg[1] in _enum, \
                f"{_want}.{_arg[0]} has no value {_arg[1]!r} (it allows {_enum})"
    print("tool_check selfcheck OK: every case names a real tool/param/enum")


if __name__ == "__main__":
    import sys
    if "--selfcheck" in sys.argv:
        _selfcheck()
    else:
        _check_tools()
