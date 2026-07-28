"""Gem — the mascot sprite renderer (Track P).

Reads the sprite kit (`teleprompter/gem/gem-sprites.json`, palette-indexed 20×20 frames — the
kit's own source of truth; never hand-edit it, the next export overwrites it) and paints a frame
to a QImage / QIcon. ONE renderer, three consumers:

  - the Windows taskbar / app icon (`app_icon`, portrait.plain on a chip),
  - the tray, animated by the live status feed (`tray.py`),
  - the settings window, via `GemImageProvider` (`image://gem/<state>/<frame>`).

Recolouring is a MAP over the kit's indices (README: "ship the indices, not the colours"), never a
repaint. Gem's native accents (purple/orange/grey) are kept exactly as the kit ships them, per
Thomas; only the BODY flips to suit its ground, because the native body #1B1714 is invisible on a
dark surface (the island, the app shell) and the near-white eyes vanish on a light one.

    python -m teleprompter.gem            # offline selfcheck (renders on Qt's offscreen platform)
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QIcon, QImage, QPainter, QPainterPath, QPixmap
from PySide6.QtQuick import QQuickImageProvider

_JSON = Path(__file__).resolve().parent / "gem" / "gem-sprites.json"

# The accents are Gem's own and stay put on every ground. Only body ("1") and eye/mouth ("2") flip.
_ACCENTS = {"3": "#6c4be8", "4": "#d97a28", "5": "#9a94a6"}
ISLAND = {"1": "#f4f6f8", "2": "#000000", **_ACCENTS}   # light body, eyes as holes — DARK surfaces
NATIVE = {"1": "#1b1714", "2": "#fbf9f5", **_ACCENTS}   # the kit's own — LIGHT surfaces


@lru_cache(maxsize=1)
def _data() -> dict:
    return json.loads(_JSON.read_text(encoding="utf-8"))


def cell() -> int:
    return _data()["cell"]


def states() -> list[str]:
    return list(_data()["states"])


def fps(state: str) -> int:
    return (_data()["states"].get(state) or {}).get("fps", _data()["fps"])


def frame_count(state: str) -> int:
    return len(_data()["states"][state]["frames"])


def frame_counts() -> dict[str, int]:
    """Every state's frame count — handed to QML as a context property so the settings window can
    tell when the one-shot `arriving` entrance is done, without hard-coding it here or there."""
    return {s: frame_count(s) for s in states()}


# The daemon's status vocabulary (status.json) is a shade richer than the sprite kit's — dictation
# adds transcribing / transforming / pasted. Map each onto the nearest Gem animation so a consumer
# never KeyErrors on a state the kit does not draw; anything unmapped rests at idle.
_STATE_MAP = {
    "transcribing": "thinking",
    "transforming": "working",
    "pasted": "done",
    "no-transcript": "misheard",
}


def gem_state(feed_state: str) -> str:
    """The Gem animation for a Contract-P feed state. A kit state passes straight through; the few
    dictation states map to their nearest cousin; anything else rests at idle."""
    if feed_state in _data()["states"]:
        return feed_state
    return _STATE_MAP.get(feed_state, "idle")


def frame_image(state: str, index: int, palette: dict | None = None) -> QImage:
    """One 20×20 frame as a transparent QImage, painted from the palette-indexed grid. Needs no
    QApplication (QImage is not a platform paint device), so the pixel logic is CI-testable bare."""
    d = _data()
    c = d["cell"]
    frames = d["states"][state]["frames"]
    rows = frames[index % len(frames)]
    cols = {k: QColor(v) for k, v in (palette or ISLAND).items()}
    img = QImage(c, c, QImage.Format.Format_ARGB32)
    img.fill(Qt.GlobalColor.transparent)
    for y, row in enumerate(rows):
        for x, ch in enumerate(row):
            col = cols.get(ch)
            if col is not None:                       # '.' is transparent; unknown index skipped
                img.setPixelColor(x, y, col)
    return img


def frame_pixmap(state: str, index: int, px: int, palette: dict | None = None) -> QPixmap:
    """Scaled with FastTransformation (nearest-neighbour) — smooth scaling blurs the cells."""
    img = frame_image(state, index, palette)
    if px != img.width():
        img = img.scaled(px, px, Qt.AspectRatioMode.IgnoreAspectRatio,
                         Qt.TransformationMode.FastTransformation)
    return QPixmap.fromImage(img)


def icon(state: str, index: int = 0, px: int = 32, palette: dict | None = None) -> QIcon:
    return QIcon(frame_pixmap(state, index, px, palette))


def app_icon(px: int = 256) -> QIcon:
    """The app / Windows-taskbar icon: `portrait.plain` on a rounded near-black chip. The chip is
    the light-body Gem's ground, so it reads on a light OR dark taskbar (a bare light body would
    disappear on a light one)."""
    inset = round(px * 0.14)
    gem = frame_pixmap("portrait.plain", 0, px - 2 * inset, ISLAND)
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, px, px), px * 0.22, px * 0.22)
    p.fillPath(path, QColor("#000000"))
    p.drawPixmap(inset, inset, gem)
    p.end()
    return QIcon(pm)


def _parse_id(image_id: str) -> tuple[str, int]:
    """`"<state>/<frame>"` -> (state, frame). An unknown state falls back to idle so a QML typo
    shows the resting Gem rather than a broken-image glyph. Split on the FIRST slash only, since a
    state name may contain a dot but never a slash (`portrait.plain/0`)."""
    state, _, frame = image_id.partition("/")
    if state not in _data()["states"]:
        state = "idle"
    try:
        return state, int(frame or 0)
    except ValueError:
        return state, 0


class GemImageProvider(QQuickImageProvider):
    """Serves `image://gem/<state>/<frame>` to QML in the ISLAND palette (every app surface Gem
    shows on is dark). Registered once on the QML engine; a QML Timer animates by stepping the
    frame in the source URL. `sourceSize` on the Image drives the (nearest-neighbour) scale."""

    def __init__(self) -> None:
        super().__init__(QQuickImageProvider.ImageType.Image)

    def requestImage(self, image_id, size, requestedSize):
        state, frame = _parse_id(image_id)
        img = frame_image(state, frame, ISLAND)
        w = requestedSize.width() if requestedSize and requestedSize.width() > 0 else img.width()
        h = requestedSize.height() if requestedSize and requestedSize.height() > 0 else img.height()
        if (w, h) != (img.width(), img.height()):
            img = img.scaled(w, h, Qt.AspectRatioMode.IgnoreAspectRatio,
                             Qt.TransformationMode.FastTransformation)
        if size is not None:
            size.setWidth(img.width())
            size.setHeight(img.height())
        return img


def _selfcheck() -> None:
    # QImage/QColor need no app, but QPixmap/QIcon/the provider do — so render on the offscreen
    # platform (same as the QML checks). The logic worth guarding: the frames load, the palette is
    # a body-flip that KEEPS the accents, the app icon builds, and the provider tolerates a bad id.
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QSize
    from PySide6.QtGui import QGuiApplication
    QGuiApplication.instance() or QGuiApplication([])

    ss = states()
    for need in ("idle", "listening", "arriving", "portrait.plain"):
        assert need in ss, f"{need} missing from the kit"
    assert cell() == 20 and fps("idle") >= 1

    # The palette is a MAP, not a repaint: the body flips between grounds, the accents never move.
    assert ISLAND["1"] != NATIVE["1"], "the body must differ between dark and light grounds"
    assert ISLAND["3"] == NATIVE["3"] == "#6c4be8", "the purple accent is kept on both"
    assert ISLAND["4"] == "#d97a28", "the orange accent is kept"

    img = frame_image("idle", 0, ISLAND)
    assert img.width() == 20 and img.height() == 20
    opaque = [(x, y) for y in range(20) for x in range(20) if img.pixelColor(x, y).alpha() > 0]
    assert opaque, "the idle frame rendered entirely transparent"
    # A body pixel must be the ISLAND ink, not the native ink — proof the map is applied.
    assert any(img.pixelColor(x, y) == QColor(ISLAND["1"]) for x, y in opaque), \
        "no body pixel took the island palette"

    assert not app_icon(64).isNull(), "the app icon failed to build"

    prov = GemImageProvider()
    out = prov.requestImage("listening/2", QSize(), QSize(48, 48))
    assert not out.isNull() and out.width() == 48, (out.isNull(), out.size())
    assert not prov.requestImage("nope/0", QSize(), QSize()).isNull(), \
        "an unknown state must fall back to idle, never a null image"
    assert _parse_id("portrait.plain/0") == ("portrait.plain", 0), "a dotted state id must survive"

    # The feed->Gem mapping the tray leans on: kit states pass through, dictation maps to a cousin,
    # and an unknown state must rest (not KeyError and blank the tray).
    assert gem_state("listening") == "listening"
    assert gem_state("transcribing") == "thinking" and gem_state("pasted") == "done"
    assert gem_state("totally-unknown") == "idle", "an unmapped feed state must rest at idle"

    print(f"gem selfcheck OK: {len(ss)} states, body-flip palette keeps the accents, "
          f"app icon on a chip, image://gem provider (bad id -> idle)")


if __name__ == "__main__":
    _selfcheck()
