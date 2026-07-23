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
# DISMISS IS NOT HERE (D24). Esc is a bare key, so a standing registration would consume it
# machine-wide; it used to be a "transient" door this module armed and disarmed in step with
# the daemon's idea of what was on screen. The Teleprompter now owns Esc outright, because it
# is the thing on screen and therefore the only party that knows — which deleted the arming
# protocol, its cross-thread race, and the modifier-less exemption below along with it.
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
    silently leaving a door unbound. A modifier-less binding is rejected unconditionally:
    every door here is registered for the life of the daemon, and a bare combo held that
    long is swallowed everywhere you type."""
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
        self.open = False          # are we between the two taps? see close()

    def close(self) -> None:
        """The capture this door opened has ended — HOWEVER it ended: second tap, hold
        release, VAD (`auto_end`), the no-speech give-up, the 30 s cap, or a dismiss.

        The orchestrator owns when a capture is really over; this door only counts
        presses, and the two must never be left disagreeing. They were: a capture that
        ended without a second press left `open` set, so the next press was read as the
        closing tap — it fired `end`, opened nothing, and the user had to press twice to
        get going again. Called from _capture()'s finally, so no exit path can skip it.

        ponytail: KNOWN RACE (G-06, accepted). This clears `start` unconditionally from the
        orchestrator thread. A press that lands in the sliver between the capture's real end
        and this `finally` running is recorded by `_fire` (`start.set()`) on the pump thread
        and then erased here — one silently lost press. The window is ~ms and self-heals (press
        again), so it is accepted. The real fix is not local to `close()`: it is the Door
        redesign parked in STATE (mechanism vs policy — see there), so noted, not patched."""
        self.open = False
        self.start.clear()
        self.end.clear()


class Hotkeys:
    def __init__(self, bindings: dict[str, str] | None = None):
        self.doors = {n: Door(n, c) for n, c in (bindings or DEFAULT_BINDINGS).items()}
        self.hold_s = HOLD_S
        self._down = self._key_down

    # --- the tap/hold state machine (pure enough to selfcheck; _down is injectable) ---

    def _fire(self, door: Door) -> None:
        """One WM_HOTKEY on `door`. The hold-vs-tap split is deliberate and is a FEATURE, not
        a quirk to design around: a tap toggles the capture, a hold ≥ HOLD_S is push-to-talk
        that ends on release — like hold-to-crouch vs tap-to-toggle-crouch in a game.

        ponytail: watching for the release busy-polls the message-pump thread, so while ONE
        door is held the OTHER door (dictate vs ask) is deaf until release. Accepted (G-05):
        you don't dictate and ask in the same instant, there is only ever one turn, and D24
        already moved the one key that mattered here (Esc) off this thread to the overlay. The
        real fix — watch the release off the pump thread (a GetAsyncKeyState poll, or fold it
        into the orchestrator's loop) — is worth it only if a third door lands or simultaneous
        doors ever matter."""
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

    def reset(self) -> None:
        """Forget every door's in-progress state — for a turn that was abandoned rather
        than finished (dismiss), where any door could be left mid-toggle."""
        for door in self.doors.values():
            door.close()

    def _pump(self) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.windll.user32
        by_id: dict[int, Door] = {}
        for i, door in enumerate(self.doors.values(), start=1):
            by_id[i] = door
            if user32.RegisterHotKey(None, i, door.mods | _MOD_NOREPEAT, door.vk):
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

    # D24: no door here may be modifier-less, with no exemption. Esc was the one exception —
    # a "transient" door armed and disarmed against the daemon's guess at what was on screen.
    # The Teleprompter owns Esc now (it is the thing on screen), so a bare binding in THIS
    # module can only mean a key consumed machine-wide for the life of the daemon.
    for bare in ("esc", "escape", "f5", "space"):
        try:
            parse_binding(bare)
        except ValueError:
            pass
        else:
            raise AssertionError(f"{bare!r} must not parse: a bare combo is swallowed globally")
    assert "dismiss" not in DEFAULT_BINDINGS, "dismissal belongs to the overlay (D24)"

    # A capture that ends WITHOUT a second press (dismiss · no-speech give-up · 30 s cap ·
    # auto_end) must not leave the door half-open, or the next press reads as the closing
    # tap: it fires `end`, opens nothing, and the user has to press twice to start again.
    d = Hotkeys({"ask": "ctrl+alt+1"}).doors["ask"]
    hk3 = Hotkeys({"ask": "ctrl+alt+1"})
    hk3._down = lambda vk: False
    hk3.doors["ask"] = d
    hk3._fire(d)                                   # tap: capture opens
    assert d.open and d.start.is_set()
    d.close()                                      # ...and ends some other way
    assert not d.open and not d.start.is_set() and not d.end.is_set()
    d.start.clear()
    hk3._fire(d)                                   # the NEXT press must OPEN, not close
    assert d.start.is_set(), "press after a non-tap capture end must open a new capture"
    assert not d.end.is_set(), "press after a non-tap capture end must not fire the endpoint"

    hk3.reset()                                    # abandon (dismiss) clears every door
    assert not d.open and not d.start.is_set() and not d.end.is_set()

    print("selfcheck OK: binding parsing (no bare combos), tap-toggle, hold-PTT, "
          "stale-end clearing")


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
