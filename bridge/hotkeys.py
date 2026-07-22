"""Track G step ② (STATE): the two doors (D20) — global hotkeys for **ask** and **dictate**.

Each door is hybrid (spec/40): **tap** opens a capture and a second tap closes it;
**hold ≥ HOLD_S** is push-to-talk and the release closes it. The key is the endpoint —
the assistant's 1 s VAD silence cut does not end a keyed turn (see `capture_over` in
bridge/orchestrator.py, and `auto_end` for the config-adjustable alternative).

**Why the narrow Win32 API and not a keyboard hook (spec/50).** The obvious library
(`pynput`) installs a system-wide low-level keyboard hook — Gemma's process would then
see *every* keystroke on the machine. `RegisterHotKey` instead asks the OS to deliver
only the specific combos we registered: no keystream, nothing else observed, and the
combo is consumed so other apps never see it either. `GetAsyncKeyState` is a query, not
a hook, and we only ever query the key we registered.

**macOS is NOT covered.** The narrow equivalent is Carbon `RegisterEventHotKey` (needs
pyobjc) — unbuilt. On a Mac `start()` warns and the doors never fire; the wake word is
still the hands-free entrance to the ask door, so the assistant works (spec/00 D10 gap).

Run:
    python -m bridge.hotkeys              # live: press the keys, watch the events
    python -m bridge.hotkeys --selfcheck  # no keyboard: parsing + the tap/hold machine
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import threading
import time

from bridge.log import setup_logging

log = logging.getLogger("gemma.hotkeys")

HOLD_S = 0.5        # spec/40: held this long -> push-to-talk, release is the endpoint
POLL_S = 0.025      # key-release poll; 25 ms is well inside the 300 ms press->indication target

# Bindings live in config (spec/70); until that file exists, defaults + an env override.
DEFAULT_BINDINGS = {
    "ask":     os.environ.get("GEMMA_HOTKEY_ASK", "ctrl+alt+1"),
    "dictate": os.environ.get("GEMMA_HOTKEY_DICTATE", "ctrl+alt+2"),
}

# Win32 (winuser.h). MOD_NOREPEAT means one message per press — without it, holding the
# key floods the queue and every repeat would read as another tap.
_MOD_ALT, _MOD_CONTROL, _MOD_SHIFT, _MOD_WIN, _MOD_NOREPEAT = 1, 2, 4, 8, 0x4000
_WM_HOTKEY = 0x0312

_MODS = {"alt": _MOD_ALT, "ctrl": _MOD_CONTROL, "control": _MOD_CONTROL,
         "shift": _MOD_SHIFT, "win": _MOD_WIN, "cmd": _MOD_WIN}
_KEYS = {"space": 0x20, "esc": 0x1B, "escape": 0x1B, "tab": 0x09, "enter": 0x0D,
         **{f"f{i}": 0x6F + i for i in range(1, 13)}}


def parse_binding(combo: str) -> tuple[int, int]:
    """'ctrl+alt+1' -> (modifier mask, virtual-key code). Raises ValueError on anything
    we cannot register, so a bad config line fails loudly at startup rather than
    silently leaving a door unbound."""
    parts = [p.strip().lower() for p in combo.split("+") if p.strip()]
    mods, key = 0, None
    for p in parts:
        if p in _MODS:
            mods |= _MODS[p]
        elif key is None:
            key = p
        else:
            raise ValueError(f"more than one non-modifier key in binding {combo!r}")
    if key is None:
        raise ValueError(f"no key in binding {combo!r}")
    vk = _KEYS.get(key)
    if vk is None and len(key) == 1 and key.isalnum():
        vk = ord(key.upper())
    if vk is None:
        raise ValueError(f"unknown key {key!r} in binding {combo!r}")
    if not mods:
        # A bare key registers globally and would be swallowed everywhere you type.
        raise ValueError(f"binding {combo!r} needs a modifier (ctrl/alt/shift/win)")
    return mods, vk


class Door:
    """One hotkey and the two signals it produces. The orchestrator polls `start` and
    clears it when it takes the turn; `end` is cleared here on the next press, so a
    double-tap that lands before the orchestrator looks still reads as open-then-close."""

    def __init__(self, name: str, combo: str):
        self.name = name
        self.combo = combo
        self.mods, self.vk = parse_binding(combo)
        self.start = threading.Event()
        self.end = threading.Event()
        self.open = False          # module-owned: are we between the two taps?


class Hotkeys:
    def __init__(self, bindings: dict[str, str] | None = None):
        self.doors = {n: Door(n, c) for n, c in (bindings or DEFAULT_BINDINGS).items()}
        self.hold_s = HOLD_S
        self._down = self._key_down

    # --- the tap/hold state machine (pure enough to selfcheck; _down is injectable) ---

    def _fire(self, door: Door) -> None:
        """One WM_HOTKEY on `door`. ponytail: this blocks the message loop for the whole
        of a push-to-talk hold, so the other door is deaf while one is held — you cannot
        dictate and ask at the same moment anyway. Revisit if a third door lands."""
        if door.open:                                   # second tap: the endpoint
            door.open = False
            door.end.set()
            log.info("%s: closed (tap)", door.name)
            return
        door.open = True
        door.end.clear()
        door.start.set()
        t0 = time.perf_counter()
        while self._down(door.vk):
            time.sleep(POLL_S)
        if time.perf_counter() - t0 >= self.hold_s:     # push-to-talk: release ends it
            door.open = False
            door.end.set()
            log.info("%s: closed (hold released)", door.name)
        else:
            log.info("%s: open (tap) — tap again to close", door.name)

    @staticmethod
    def _key_down(vk: int) -> bool:
        import ctypes
        return bool(ctypes.windll.user32.GetAsyncKeyState(vk) & 0x8000)

    # --- the daemon ---

    def start(self) -> None:
        """Register the combos and pump their messages on a daemon thread. Never fatal:
        a combo another app already owns logs and leaves that door unbound."""
        if sys.platform != "win32":
            log.warning("hotkeys are Windows-only for now (%s) — the doors will not fire; "
                        "use the wake word for the ask door", sys.platform)
            return
        threading.Thread(target=self._pump, name="gemma-hotkeys", daemon=True).start()

    def _pump(self) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        by_id: dict[int, Door] = {}
        for i, door in enumerate(self.doors.values(), start=1):
            if user32.RegisterHotKey(None, i, door.mods | _MOD_NOREPEAT, door.vk):
                by_id[i] = door
                log.info("hotkey %s -> %s", door.combo, door.name)
            else:
                log.error("could not register %s for %s — another app likely owns it",
                          door.combo, door.name)
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == _WM_HOTKEY and msg.wParam in by_id:
                self._fire(by_id[msg.wParam])


def _selfcheck() -> None:
    """No keyboard, no Windows: binding parsing and the tap/hold machine."""
    assert parse_binding("ctrl+alt+1") == (_MOD_CONTROL | _MOD_ALT, 0x31)
    assert parse_binding("CTRL + Alt + d") == (_MOD_CONTROL | _MOD_ALT, 0x44)
    assert parse_binding("win+shift+f5") == (_MOD_WIN | _MOD_SHIFT, 0x74)
    for bad in ("1", "ctrl+", "ctrl+nope", "ctrl+a+b", ""):
        try:
            parse_binding(bad)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{bad!r} should not parse")

    hk = Hotkeys({"ask": "ctrl+alt+1"})
    door = hk.doors["ask"]

    hk._down = lambda vk: False                    # tap: released immediately
    hk._fire(door)
    assert door.start.is_set() and not door.end.is_set() and door.open
    hk._fire(door)                                 # second tap closes it
    assert door.end.is_set() and not door.open

    down = iter([True, False])                     # hold: still down after hold_s
    hk._down = lambda vk: next(down, False)
    hk.hold_s = 0.0
    door.start.clear(); door.end.clear()
    hk._fire(door)
    assert door.start.is_set() and door.end.is_set() and not door.open

    door.start.clear(); door.end.set()             # a press clears a stale endpoint
    hk._down = lambda vk: False
    hk.hold_s = HOLD_S
    hk._fire(door)
    assert door.start.is_set() and not door.end.is_set()

    print("selfcheck OK: binding parsing, tap-toggle, hold-PTT, stale-end clearing")


def main() -> None:
    setup_logging()
    ap = argparse.ArgumentParser(description="Gemma hotkeys — the two doors (D20)")
    ap.add_argument("--selfcheck", action="store_true",
                    help="verify parsing and the tap/hold machine without a keyboard, then exit")
    args = ap.parse_args()
    if args.selfcheck:
        _selfcheck()
        return
    hk = Hotkeys()
    hk.start()
    print("press " + " or ".join(d.combo for d in hk.doors.values()) + " (Ctrl-C to stop)")
    try:
        while True:                                 # watch the doors and report
            for door in hk.doors.values():
                if door.start.is_set():
                    door.start.clear()
                    print(f"[{door.name}] capture opened")
                if door.end.is_set():
                    door.end.clear()
                    print(f"[{door.name}] capture closed")
            time.sleep(POLL_S)
    except KeyboardInterrupt:
        print()


if __name__ == "__main__":
    main()
