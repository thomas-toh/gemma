"""Dev launcher — start the daemon and the Teleprompter overlay from one command.

    python run.py

One window, both logs interleaved, and **one quit stops both** (spec/00 D39): whichever
child exits CLEANLY takes the other with it, so tray > Quit and Ctrl-C in the console are
each a single door out of the whole app.

A CRASH is the exception and stays isolated (spec/00 D13/D19): a child that dies with a
nonzero code leaves the other running, so you restart just the one that broke — and so a
dead daemon still has a live overlay to be reported by. That restart-one independence is
why two processes beat a merge, which D39 considered and rejected.

ponytail: still no Windows Job-Object lifetime tie (launcher C2) — SIGKILL run.py and these
children can orphan; Ctrl-C and normal exit are handled. Add it when orphans are seen.
"""
from __future__ import annotations

import subprocess
import sys
import time

CHILDREN = {
    "daemon": [sys.executable, "-m", "bridge.orchestrator"],   # voice loop + Contract P feed
    "overlay": [sys.executable, "-m", "teleprompter"],         # subscribes to the feed
}


def stop_others(exits: dict[str, int | None]) -> bool:
    """Should the survivors be stopped? True once some child has exited CLEANLY (code 0),
    which is what a deliberate quit looks like — tray > Quit, or Ctrl-C in the console.

    A crash (nonzero) is False: the survivor keeps running (D13/D19 crash isolation), and a
    child still running (None) decides nothing either way."""
    return any(code == 0 for code in exits.values())


def main() -> int:
    procs = {name: subprocess.Popen(cmd) for name, cmd in CHILDREN.items()}
    reported: set[str] = set()
    try:
        while any(p.poll() is None for p in procs.values()):
            exits = {name: p.poll() for name, p in procs.items()}
            for name, code in exits.items():
                if code is None or name in reported:
                    continue
                reported.add(name)
                if code == 0:
                    print(f"[run] {name} quit — stopping the other too.")
                else:
                    print(f"[run] {name} CRASHED (exit {code}); the other keeps running — "
                          f"restart it alone with: {' '.join(CHILDREN[name])}")
            if stop_others(exits):
                break
            time.sleep(0.3)
    except KeyboardInterrupt:
        pass
    finally:
        for p in procs.values():                     # ask both to stop...
            if p.poll() is None:
                p.terminate()
        for p in procs.values():                     # ...then insist if one won't
            try:
                p.wait(timeout=5)
            except subprocess.TimeoutExpired:
                p.kill()
    return 0


def _selfcheck() -> None:
    """The D39 tie, all four cases. The policy is the only non-trivial part of this file;
    spawning real processes to test it would test subprocess, not the rule."""
    # Nothing has exited yet -> nobody is stopped.
    assert not stop_others({"daemon": None, "overlay": None})
    # A clean exit of EITHER side stops the other. These are the two doors out.
    assert stop_others({"daemon": 0, "overlay": None}), "Ctrl-C in the console must stop the overlay"
    assert stop_others({"daemon": None, "overlay": 0}), "tray Quit must stop the daemon"
    # A crash of either side must NOT — the survivor keeps running (D13/D19).
    assert not stop_others({"daemon": 1, "overlay": None}), "a daemon crash must spare the overlay"
    assert not stop_others({"daemon": None, "overlay": 1}), "an overlay crash must spare the daemon"
    assert not stop_others({"daemon": 3221225477, "overlay": None}), "a hard crash is still a crash"
    # Mixed: one crashed earlier, then the other was quit cleanly -> stop.
    assert stop_others({"daemon": 1, "overlay": 0})
    print("run.py selfcheck OK — clean exit ties, crash isolates (D39)")


if __name__ == "__main__":
    if "--selfcheck" in sys.argv:
        _selfcheck()
    else:
        sys.exit(main())
