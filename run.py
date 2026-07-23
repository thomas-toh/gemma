"""Dev launcher — start the daemon and the Teleprompter overlay from one command.

    python run.py

One window, both logs interleaved, one Ctrl-C stops both. They stay separate PROCESSES on
purpose (spec/00 D19): the overlay is a dumb subscriber that reconnects, so if one dies the
other keeps running and you restart just the changed one in its own tab. That restart-one
independence is the whole reason two procs beats a merge *for dev* — a true single-process
merge would force a full-app restart on every change.

ponytail: launcher, not a real merge. Owed for the SHIPPED app (STATE, parked) — fuse into
one process (Qt on the main thread, orchestrator.run on a background thread) so a user gets
one thing to launch and one crash restarts everything, which is what a user actually wants.
Also unowned here: a Windows Job-Object lifetime tie (launcher C2) — kill the launcher hard
and these children can orphan; Ctrl-C and normal exit are handled, a SIGKILL of run.py is not.
"""
from __future__ import annotations

import subprocess
import sys
import time

CHILDREN = {
    "daemon": [sys.executable, "-m", "bridge.orchestrator"],   # voice loop + Contract P feed
    "overlay": [sys.executable, "-m", "teleprompter"],         # subscribes to the feed
}


def main() -> int:
    procs = {name: subprocess.Popen(cmd) for name, cmd in CHILDREN.items()}
    reported: set[str] = set()
    try:
        while any(p.poll() is None for p in procs.values()):
            for name, p in procs.items():
                if p.poll() is not None and name not in reported:
                    reported.add(name)
                    print(f"[run] {name} stopped (exit {p.returncode}); the other keeps "
                          f"running — restart it alone with: {' '.join(CHILDREN[name])}")
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


if __name__ == "__main__":
    sys.exit(main())
