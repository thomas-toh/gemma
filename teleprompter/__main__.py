"""The Teleprompter (component P) — a PySide6 + QML overlay on the Contract P status feed.

A dumb subscriber (spec/00 D19): it renders whatever arrives on the localhost feed and never
drives the voice loop. Start it before or after the daemon — it reconnects either way.

Run:
    python -m teleprompter                      # render the live daemon's feed
    python -m bridge.broadcaster --fake         # ...or drive it with NO audio/mic/models
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

import PySide6

# Store-Python quirk (NOTES.md; same class as listen.py's CUDA-DLL fix): Qt's QML plugin
# loader does not search the PySide6 package dir where the Qt6*.dll live, so qtquick2plugin
# fails with "module could not be found". Put it on the search path BEFORE importing Qt.
_pyside_dir = os.path.dirname(PySide6.__file__)
os.environ["PATH"] = _pyside_dir + os.pathsep + os.environ.get("PATH", "")
try:
    os.add_dll_directory(_pyside_dir)
except (AttributeError, OSError):
    pass

from PySide6.QtCore import QUrl                                          # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine                          # noqa: E402
from PySide6.QtWidgets import QApplication, QSystemTrayIcon              # noqa: E402

from teleprompter.decode import HOST, PORT                               # noqa: E402
from teleprompter.feed import Feed                                       # noqa: E402
from teleprompter.model import OverlayModel                              # noqa: E402
from teleprompter.tray import Tray                                       # noqa: E402

log = logging.getLogger("gemma.teleprompter")

FONTS_DIR = Path(__file__).resolve().parent / "fonts"

# The design's face is **Inter**, bundled beside this package and registered at startup — so
# it needs no system install and travels to the Mac unchanged (D10). Supersedes the mockup's
# Instrument Sans. The rest of the chain only matters if the bundled file goes missing: QML's
# font.family takes a single name and Qt substitutes silently (on a stock Windows box an
# absent family lands on Tahoma), so we walk the chain here and say out loud which one won.
FONT_STACK = ["Inter", "Segoe UI Variable Text", "Segoe UI", "Helvetica Neue", "Arial"]


def load_bundled_fonts() -> None:
    """Register every font shipped in teleprompter/fonts/ — no system install required.
    Needs a QApplication to exist first."""
    from PySide6.QtGui import QFontDatabase
    for path in sorted(FONTS_DIR.glob("*.ttf")):
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id == -1:
            log.warning("could not load bundled font %s", path.name)
        else:
            log.info("bundled font %s -> %s", path.name,
                     ", ".join(QFontDatabase.applicationFontFamilies(font_id)))


def pick_font() -> str:
    """First family in FONT_STACK that is actually available (bundled or installed)."""
    from PySide6.QtGui import QFontDatabase
    available = set(QFontDatabase.families())
    for family in FONT_STACK:
        if family in available:
            if family != FONT_STACK[0]:
                log.warning("%r unavailable — falling back to %r", FONT_STACK[0], family)
            return family
    log.warning("none of %s available; letting Qt choose", FONT_STACK)
    return ""


def reduced_motion() -> bool:
    """Windows' "Show animations" accessibility setting — the desktop equivalent of CSS
    `prefers-reduced-motion`, which the mockup honoured. Off => the island's transitions go
    instant. Fails open (motion allowed) if the query fails."""
    if sys.platform != "win32":
        return False
    import ctypes
    SPI_GETCLIENTAREAANIMATION = 0x1042
    enabled = ctypes.c_int(1)
    ok = ctypes.windll.user32.SystemParametersInfoW(
        SPI_GETCLIENTAREAANIMATION, 0, ctypes.byref(enabled), 0)
    return bool(ok) and not enabled.value


def stamp_overlay_styles(win) -> None:
    """Two native guarantees the Qt flags alone don't reliably give on Windows:

    NOACTIVATE — BINDING (spec/40): the overlay must never take keyboard focus, because during
    dictation focus decides where the paste lands. (Recipe proven in sandbox/qml_spike.)

    TRANSPARENT — the island is display-only: it has no controls, so it should never intercept
    a click meant for the window beneath it (it sits top-centre, over a maximised browser's tab
    strip). Unlike setMask, this affects hit-testing ONLY and does not clip painting.
    """
    if sys.platform != "win32":
        return
    import ctypes
    GWL_EXSTYLE = -20
    WS_EX_TRANSPARENT, WS_EX_TOPMOST, WS_EX_NOACTIVATE = 0x00000020, 0x00000008, 0x08000000
    user32 = ctypes.windll.user32
    hwnd = int(win.winId())
    cur = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
    user32.SetWindowLongW(hwnd, GWL_EXSTYLE,
                          cur | WS_EX_NOACTIVATE | WS_EX_TOPMOST | WS_EX_TRANSPARENT)


def main() -> int:
    logging.basicConfig(level=logging.INFO, datefmt="%H:%M:%S",
                        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s")
    ap = argparse.ArgumentParser(description="Gemma Teleprompter — Contract P overlay (Track P)")
    ap.add_argument("--host", default=HOST)
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--latency", action="store_true",
                    help="show the per-turn latency readout (D13's M0 acceptance-run "
                         "instrument); also togglable from the tray")
    args = ap.parse_args()

    # QApplication (not QGuiApplication as in the spike): C3's tray lives in QtWidgets, and
    # the BINDING non-activation is cheaper to prove against the final app class now.
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)   # the island hides at idle — that is not a quit
    load_bundled_fonts()                   # must follow QApplication, precede pick_font()

    model = OverlayModel(show_latency=args.latency)
    engine = QQmlApplicationEngine()
    # The repo root, so `import teleprompter` resolves this package's qmldir and its Theme
    # singleton (the design tokens).
    engine.addImportPath(str(Path(__file__).resolve().parent.parent))
    engine.rootContext().setContextProperty("overlay", model)   # not "model": Repeater shadows it
    engine.rootContext().setContextProperty("fontFamily", pick_font())
    reduce = reduced_motion()
    engine.rootContext().setContextProperty("reducedMotion", reduce)
    if reduce:
        log.info("system 'show animations' is off — island transitions run instant")
    engine.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parent / "Overlay.qml")))
    roots = engine.rootObjects()
    if not roots:
        log.error("QML failed to load — see the Qt errors above")
        return 1
    win = roots[0]

    def restamp() -> None:
        # The island hides at idle; a re-shown window can come back with a fresh HWND, so
        # re-apply the non-activating style every time it appears.
        if win.isVisible():
            stamp_overlay_styles(win)

    win.visibleChanged.connect(restamp)
    restamp()

    # NO setMask here. It looked like the way to stop the island swallowing clicks meant for
    # the window beneath, and it does confine input correctly — but on Windows it is
    # implemented with SetWindowRgn, which clips PAINTING as well: measured 70% of the island
    # painted before the mask, 10% after (clipped to the ⌄ tab). Per-region click-through
    # without clipping needs WM_NCHITTEST -> HTTRANSPARENT via a native event filter, or a
    # separate tiny window for the tab. Recorded in STATE, Track P.

    # Kept in locals for the app's lifetime — both are garbage collected otherwise.
    feed = Feed(model, args.host, args.port)                             # noqa: F841
    tray = None
    if QSystemTrayIcon.isSystemTrayAvailable():
        tray = Tray(app, model)                                          # noqa: F841
    else:
        log.warning("no system tray available — no way to quit but Ctrl-C")

    log.info("teleprompter up — subscribing to %s:%d", args.host, args.port)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
