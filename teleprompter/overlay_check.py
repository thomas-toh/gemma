"""Offline check for the island's motion logic — `python -m teleprompter.overlay_check`.

decode.py's selfcheck covers the Qt-free half (framing, the reducer). This covers the half
that has actually produced the bugs: the interplay between the island growing, the text
scrolling, and the typewriter revealing words into a box that is still moving.

Runs on Qt's `offscreen` platform, so it needs no display and opens no window.

The invariant is the one a person actually sees: REVEALED TEXT NEVER RENDERS OUTSIDE THE
BLACK. It is measured against the *animated* height and y, not their target values, because
the whole class of bug here is the background lagging its contents. Two failure shapes:

    short  — the island is not yet tall enough for the lines already revealed
    below  — the newest line has been pushed past the island's inner bottom edge

Both were live defects: the Canvas silhouette repainted asynchronously and left a freshly
wrapped line over the desktop, and later the reveal timer gated on the island's GROWTH but
not on its SCROLL, so past three lines words landed while the text was still sliding. Delete
the gate in Overlay.qml and this check fails loudly — that is the point of it.
"""
from __future__ import annotations

import os
import sys
import time
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import PySide6  # noqa: E402

# PySide6's DLLs are not on PATH when it is imported as a library (see __main__.py).
_d = os.path.dirname(PySide6.__file__)
os.environ["PATH"] = _d + os.pathsep + os.environ.get("PATH", "")
try:
    os.add_dll_directory(_d)
except (AttributeError, OSError):
    pass

from PySide6.QtCore import QObject, QUrl  # noqa: E402
from PySide6.QtGui import QFontDatabase, QGuiApplication  # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine  # noqa: E402

from teleprompter.model import OverlayModel  # noqa: E402

HERE = Path(__file__).resolve().parent
# Long enough to pass maxLines, so growth AND scroll are both exercised.
REPLY = ("The agent confirms the lease renews at the current rent for a further twelve "
         "months and they need your signature on the renewal by Friday afternoon at the "
         "latest, otherwise the holding deposit is forfeited.")


def _pump(app, ms: int) -> None:
    end = time.monotonic() + ms / 1000
    while time.monotonic() < end:
        app.processEvents()
        time.sleep(0.002)


def main() -> int:
    app = QGuiApplication([])
    # The offscreen platform ships no fonts, so the bundled family is what makes the metrics
    # real. Without it every line count below would be measured against a fallback.
    assert QFontDatabase.addApplicationFont(str(HERE / "fonts" / "Inter-Variable.ttf")) != -1, \
        "bundled Inter did not load — line metrics would be meaningless"

    model = OverlayModel()
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(HERE.parent))
    engine.rootContext().setContextProperty("overlay", model)
    engine.rootContext().setContextProperty("fontFamily", "Inter")
    engine.rootContext().setContextProperty("reducedMotion", False)
    engine.load(QUrl.fromLocalFile(str(HERE / "Overlay.qml")))
    assert engine.rootObjects(), "Overlay.qml failed to load"
    win = engine.rootObjects()[0]
    body = win.findChild(QObject, "body")
    sweep = win.findChild(QObject, "sweep")
    assert body is not None and sweep is not None, "Overlay.qml lost its objectNames"

    # --- entrance is a binding on `st`, not an imperative handler ---
    model.apply({"type": "state", "state": "idle"})
    _pump(app, 400)
    assert float(win.property("entrance")) < 0.01, "idle should leave the island faded out"
    model.apply({"type": "state", "state": "thinking"})
    _pump(app, 90)
    midway = float(win.property("entrance"))
    _pump(app, 400)
    assert float(win.property("entrance")) > 0.99, "a live state should fade the island in"
    # Reaching 1.0 alone would also pass if the Behavior were dead and it simply snapped, so
    # the fade is only proven by catching it part-way.
    assert 0.01 < midway < 0.99, f"the island snapped in rather than fading (entrance={midway})"


    # --- the status word wipes between words rather than cutting ---
    seen, partial = set(), 0
    for _ in range(60):
        _pump(app, 60)
        word = sweep.property("shown")
        if word:
            seen.add(word)
            partial += 1 if word != sweep.property("wordTo") else 0
    assert partial, "the status word never showed a mid-wipe frame — it is not animating"
    assert len({w for w in seen if len(w) > 3}) > 3, f"the status word never rotated: {seen}"

    # --- the reveal gate ---
    model.apply({"type": "state", "state": "speaking"})
    model.apply({"type": "response", "delta": REPLY})

    line_box = int(win.property("lineBox"))
    pad_bottom, base_h = int(win.property("padBottom")), int(win.property("baseH"))
    fade_top, max_lines = float(win.property("fadeTop")), int(win.property("maxLines"))
    short: list[str] = []
    below: list[str] = []
    revealed, peak_lines = 0, 0
    prev_len = len(body.property("text"))
    start = time.monotonic()
    while time.monotonic() - start < 6.0:
        _pump(app, 6)
        # animH, not the window height — the window is a fixed frame now and the island
        # animates inside it.
        height, y = float(win.property("animH")), float(body.property("y"))
        lines = int(body.property("lineCount"))
        peak_lines = max(peak_lines, lines)
        at = round((time.monotonic() - start) * 1000)
        if lines:
            needed = base_h + (min(lines, max_lines) - 1) * line_box
            if height < needed - 0.5:
                short.append(f"t={at}ms {lines} lines revealed, island {height:.0f}px, "
                             f"needs {needed}px")
            ink_bottom, inner = y + lines * line_box, height - fade_top - pad_bottom
            if ink_bottom > inner + 0.5:
                below.append(f"t={at}ms {lines} lines, ink to {ink_bottom:.0f}px, "
                             f"inner edge {inner:.0f}px")
        now_len = len(body.property("text"))
        revealed += 1 if now_len > prev_len else 0
        prev_len = now_len

    # Guards against the check quietly measuring nothing — the failure mode that let the
    # ungated scroll ship in the first place.
    assert int(win.property("scrolled")) > 0, "the reply never scrolled; scroll path untested"
    assert peak_lines >= max_lines, f"only reached {peak_lines} lines; growth path untested"
    assert revealed > 5, "no words were revealed; the check measured nothing"
    for line in short[:5] + below[:5]:
        print(f"  {line}", file=sys.stderr)
    assert not short, f"island too short for its own text in {len(short)} frames"
    assert not below, f"text rendered below the island edge in {len(below)} frames"

    # The hidden measurer drives the gate, so it must lay out IDENTICALLY to the visible text.
    # Once everything is revealed the two hold the same string, so any difference in line count
    # is a difference in layout — the exact failure that silently un-gates the reveal.
    measure = win.findChild(QObject, "measure")
    assert measure is not None, "Overlay.qml lost the measure objectName"
    assert measure.property("text") == body.property("text"), "reveal did not finish in time"
    assert int(measure.property("lineCount")) == int(body.property("lineCount")), (
        f"measurer wraps to {measure.property('lineCount')} lines but the visible text wraps "
        f"to {body.property('lineCount')} — they have drifted apart")
    assert float(body.property("contentWidth")) <= float(win.property("textW")) + 0.5, (
        f"text is {body.property('contentWidth'):.0f}px wide in a "
        f"{win.property('textW'):.0f}px column — a long token is overhanging the island")

    # --- the latency instrument must never sit on top of the reply it is timing ---
    # Both readings show at once during the acceptance run, which is the case a flat 96px
    # gutter did not cover. Checked at absurd readings so the guarantee is not luck.
    latency = win.findChild(QObject, "latency")
    assert latency is not None, "Overlay.qml lost the latency objectName"
    model.toggle_latency(True)
    model.apply({"type": "latency", "metric": "feedback", "ms": 88888})
    model.apply({"type": "latency", "metric": "first_word", "ms": 88888})
    _pump(app, 250)
    assert float(win.property("latencyGutter")) > 0, "the gutter did not open for the readout"
    text_right = float(win.property("flare")) + int(win.property("padSide")) \
        + float(win.property("textW"))
    assert float(latency.property("x")) >= text_right - 0.5, (
        f"latency readout starts at x={latency.property('x'):.0f} but the reply runs to "
        f"{text_right:.0f} — the instrument overlaps the text")

    # --- both edges must move at the same rate, and the island must stay inside its frame ---
    # The island is centred in a FIXED window, so its centre is a constant no matter how wide
    # it is. Any drift means one edge is moving before the other — which is what a native
    # window move racing a native resize looked like (the pill contracted faster on the left).
    # The containment assert covers the other half: the silhouette is drawn at animH, so if
    # that ever exceeded the frame its bottom corners would be clipped away mid-growth.
    # `idle` is what contracts the island now — the widest change it makes. It used to be
    # `listening`, but an open mic no longer ends a turn (spec/50 rule 4; see decode.py's
    # CLEARS_TURN), so listening leaves the answer up and the island open.
    model.apply({"type": "state", "state": "idle"})
    frame_w, frame_h = float(win.property("width")), float(win.property("height"))
    frame_x = float(win.property("x"))
    centre, drift, widths = frame_w / 2, 0.0, []
    start = time.monotonic()
    while time.monotonic() - start < 0.7:
        _pump(app, 6)
        x, w, h = (float(win.property("islandX")), float(win.property("animW")),
                   float(win.property("animH")))
        drift = max(drift, abs((x + w / 2) - centre))
        widths.append(w)
        # The load-bearing one. A centred island samples as perfectly centred even while the
        # real window tears, because the tear happens below Qt in the compositor — so this
        # cannot be caught by watching the island. What CAN be checked is that the tear has
        # nothing left to happen to: the window's own geometry must never change at all.
        assert (float(win.property("width")), float(win.property("height")),
                float(win.property("x"))) == (frame_w, frame_h, frame_x), \
            "the window itself resized or moved — a native move can race a native resize again"
        assert x >= -0.5 and x + w <= frame_w + 0.5, f"island escaped the frame sideways (x={x})"
        assert h <= frame_h + 0.5, f"island {h}px tall in a {frame_h}px frame — corners clipped"
    assert max(widths) - min(widths) > 50, "the island never actually contracted; nothing measured"
    print(f"contraction: {len(widths)} frames, {max(widths) - min(widths):.0f}px of travel, "
          f"worst centre drift {drift:.3f}px")
    assert drift < 0.5, f"the island's two edges moved at different rates (drift {drift:.2f}px)"

    print(f"selfcheck OK: entrance binds to state, status word wipes and rotates, and across "
          f"{revealed} revealed words at up to {peak_lines} lines (scrolled "
          f"{win.property('scrolled')}) no text ever rendered outside the island")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
