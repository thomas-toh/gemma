"""System tray (Track P C3) — the only "Gemma is running" signal there is.

The island hides completely at idle (spec/40: "gone = asleep"), so without this you cannot
tell the overlay from a dead process. Since D29 it is also the door to the settings window:
the output toggles and the Groq key that used to live in this menu as a stopgap now have a
real home, so the menu is back to three items.
"""
from __future__ import annotations

import logging
import sys

from PySide6.QtCore import QRectF, Qt, QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QMenu, QSystemTrayIcon

from teleprompter import gem

log = logging.getLogger("gemma.teleprompter")

# Windows 11 Fluent flyout colours — the SHELL's, not the app's. A tray menu is part of the
# desktop, so it follows the Windows light/dark setting and ignores Gemma's own palette
# entirely. Nothing here is duplicated from Theme.qml, because none of it should match.
MENU_COLOURS = {
    #                 background  text       border     hover                   separator
    "light": ("#f9f9f9", "#1b1b1b", "#e5e5e5", "rgba(0, 0, 0, 0.05)", "#e5e5e5", "#9d9d9d"),
    "dark":  ("#2c2c2c", "#ffffff", "#3d3d3d", "rgba(255, 255, 255, 0.07)", "#3d3d3d", "#8a8a8a"),
}


def windows_uses_light_theme() -> bool:
    """The user's Windows app-theme setting. Defaults to light if it cannot be read, which is
    the Windows default."""
    if sys.platform != "win32":
        return True
    try:
        import winreg
        key = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as k:
            return bool(winreg.QueryValueEx(k, "AppsUseLightTheme")[0])
    except OSError:
        return True


def menu_qss(light: bool) -> str:
    bg, fg, border, hover, sep, dim = MENU_COLOURS["light" if light else "dark"]
    return f"""
QMenu {{
    background: {bg};
    color: {fg};
    border: 1px solid {border};
    border-radius: 8px;
    padding: 5px 4px;
    font-size: 14px;
}}
QMenu::item {{
    padding: 8px 32px 8px 36px;
    margin: 1px 4px;
    border-radius: 5px;
}}
QMenu::item:selected {{ background: {hover}; color: {fg}; }}
QMenu::item:disabled {{ color: {dim}; }}
QMenu::separator     {{ height: 1px; background: {sep}; margin: 5px 10px; }}
QMenu::icon          {{ left: 12px; }}
"""


# Stroked 24×24 paths, the same set the settings window draws from.
GEAR = ("M12 3v2M12 19v2M3 12h2M19 12h2M5.6 5.6l1.4 1.4M17 17l1.4 1.4M18.4 5.6L17 7"
        "M7 17l-1.4 1.4M12 8.6a3.4 3.4 0 1 0 0 6.8a3.4 3.4 0 1 0 0-6.8")
CHECK = "M4.5 12.6 9.5 17.5 19.5 6.5"
POWER = "M12 4v8M7.8 6.8a7 7 0 1 0 8.4 0"


def glyph_icon(path_d: str, colour: str, px: int = 16) -> QIcon:
    """A menu icon painted from a path, in whatever colour the shell's theme calls for.

    Generated rather than loaded from teleprompter/icons/: those are fixed-colour assets for
    the peek, and a tray icon has to flip with the Windows light/dark setting.
    """
    from PySide6.QtCore import QByteArray
    from PySide6.QtSvg import QSvgRenderer
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24">'
           f'<path d="{path_d}" fill="none" stroke="{colour}" stroke-width="2" '
           f'stroke-linecap="round" stroke-linejoin="round"/></svg>')
    pm = QPixmap(px * 2, px * 2)                  # 2× then downscaled: crisp on hiDPI
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    QSvgRenderer(QByteArray(svg.encode("utf-8"))).render(p)
    p.end()
    pm.setDevicePixelRatio(2.0)
    return QIcon(pm)


def style_menu_native(menu: QMenu, light: bool) -> None:
    """Dress a Qt menu as a Windows 11 flyout: rounded, shadowed, and in the SHELL's theme.

    Rounding and the dark/light popup frame come from DWM, which applies both to any top-level
    window that asks — including a Qt popup — so these two attributes do what a stylesheet
    cannot (a QSS `border-radius` leaves square corners outside the painted area).

    Re-read on every open rather than cached, so switching Windows between light and dark takes
    effect on the next right-click with no restart and no settings-change hook.

    ponytail: a Qt menu dressed as a native one, not a native one. A genuine Windows 11 context
    menu is a WinUI 3 control, which PySide6 cannot host without an XAML island — a far bigger
    dependency than a three-item tray menu is worth. Revisit only if the app ships WinUI anyway.
    """
    if sys.platform != "win32":
        return
    import ctypes
    from ctypes import wintypes
    DWMWA_USE_IMMERSIVE_DARK_MODE, DWMWA_WINDOW_CORNER_PREFERENCE = 20, 33
    DWMWCP_ROUND = 2
    try:
        hwnd = wintypes.HWND(int(menu.winId()))
        for attr, val in ((DWMWA_USE_IMMERSIVE_DARK_MODE, 0 if light else 1),
                          (DWMWA_WINDOW_CORNER_PREFERENCE, DWMWCP_ROUND)):
            v = ctypes.c_int(val)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, ctypes.c_int(attr), ctypes.byref(v), ctypes.sizeof(v))
    except Exception as e:                        # pragma: no cover — cosmetic only
        log.debug("could not style the tray menu natively: %s", e)


def make_icon() -> QIcon:
    """The island silhouette, painted rather than shipped as a binary asset. White fill with a
    dark keyline so it survives both light and dark taskbars.

    ponytail: one state. D29's on-air lamp gives this three — ink / amber outline while the
    wake ring is open / filled amber while capturing — and lands with the `listen_for_me`
    gating that makes the middle state mean anything.
    """
    pm = QPixmap(32, 32)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(4, 9.5, 24, 13), 6, 6)
    p.fillPath(path, QColor("#f4f6f8"))
    p.setPen(QColor(0, 0, 0, 150))
    p.drawPath(path)
    p.end()
    return QIcon(pm)


def mark_icon(px: int = 256, colour: str | None = None) -> QIcon:
    """The Gemma mark, for the tray and the Windows taskbar — loaded from the shipped SVG so the
    shape lives in one place (`teleprompter/icons/gemma-mark.svg`). `colour` recolours the mark
    (the tray passes white); the default keeps the asset's coral. Falls back to the island
    silhouette if the asset is ever missing.

    ponytail: the tray is a flat white mark. Its on-air role (spec/50 rule 4, D29) could later
    tint it by mic state; the settings window's top-bar lamp carries that meaning for now.
    """
    from pathlib import Path
    from PySide6.QtCore import QByteArray
    from PySide6.QtSvg import QSvgRenderer
    src = Path(__file__).resolve().parent / "icons" / "gemma-mark.svg"
    try:
        svg = src.read_text(encoding="utf-8")
    except OSError:
        return make_icon()
    if colour:
        svg = svg.replace("#cf6142", colour)
    r = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    if not r.isValid():
        return make_icon()
    pm = QPixmap(px, px)
    pm.fill(Qt.GlobalColor.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    r.render(p)
    p.end()
    return QIcon(pm)


class Tray(QSystemTrayIcon):
    # States that rest on a single frame in the tray: an icon that wiggles forever is a nuisance,
    # and idle/asleep are the long-lived ones. Every other state animates while it is briefly true,
    # then the model returns to idle and the tray falls still again.
    _STILL = {"idle", "asleep"}

    def __init__(self, app, model=None, on_settings=None) -> None:
        super().__init__()
        self._app = app
        self._model = model
        self.setToolTip("Gemma — Teleprompter")

        # Gem, driven by the live status feed (spec/50 rule 4 — the tray shows only what the daemon
        # is really doing, never inferred). The palette is read per state-change, not per frame:
        # winreg on every tick would be waste.
        self._state = gem.gem_state(model.state) if model is not None else "idle"
        self._frame = 0
        self._pal = self._palette()
        self._anim = QTimer(self)
        self._anim.timeout.connect(self._tick)
        if model is not None:
            model.changed.connect(self._on_model)
        self._sync()                              # initial icon + start/stop the loop for `idle`

        menu = QMenu()
        self._act_settings = None
        self._act_lat = None

        if on_settings is not None:
            self._act_settings = QAction("Settings", menu)
            self._act_settings.triggered.connect(on_settings)
            menu.addAction(self._act_settings)
            # Double-clicking a tray icon opening its window is the Windows convention, and it
            # is the gesture people try first.
            self.activated.connect(
                lambda reason: on_settings()
                if reason == QSystemTrayIcon.ActivationReason.DoubleClick else None)
        if model is not None:
            # A dev tool (D13's acceptance-run instrument), deliberately not a setting.
            # NOT a checkable action: Qt draws that as a box in its own indicator column, which
            # is not how Windows shows a toggled menu item — it puts a tick in the icon column
            # beside everything else's icon. So the state is ours to hold and to draw.
            self._act_lat = QAction("Show latency", menu)
            self._act_lat.triggered.connect(self._toggle_latency)
            menu.addAction(self._act_lat)
        menu.addSeparator()
        act_quit = QAction("Quit", menu)
        act_quit.triggered.connect(app.quit)
        menu.addAction(act_quit)
        self._act_quit = act_quit
        # Restyled on every open, not once at construction: the DWM attributes need a real
        # window (a menu has none until it is about to show, and a re-shown popup can get a
        # fresh HWND), and re-reading the registry here is what makes both the colours and the
        # icons follow Windows switching between light and dark.
        menu.aboutToShow.connect(self._restyle)
        # Held deliberately: setContextMenu does not take ownership, and a menu that is
        # garbage collected takes the tray's right-click with it. Assigned before the first
        # _restyle(), which reads it.
        self._menu = menu
        self._restyle()                          # so the first right-click is already styled
        self.setContextMenu(menu)
        self.show()

    def _toggle_latency(self) -> None:
        self._model.toggle_latency(not self._model.showLatency)
        self._restyle()                          # the tick follows immediately

    def _restyle(self) -> None:
        """Colours and icons, both taken from the Windows theme rather than Gemma's."""
        light = windows_uses_light_theme()
        ink = MENU_COLOURS["light" if light else "dark"][1]
        self._menu.setStyleSheet(menu_qss(light))
        if self._act_settings is not None:
            self._act_settings.setIcon(glyph_icon(GEAR, ink))
        if self._act_lat is not None:
            # An empty icon still reserves the column, so the labels stay aligned whether or
            # not the tick is showing.
            self._act_lat.setIcon(glyph_icon(CHECK, ink) if self._model.showLatency else QIcon())
        self._act_quit.setIcon(glyph_icon(POWER, ink))
        style_menu_native(self._menu, light)

    # --- Gem animation (spec/50 rule 4: the tray reflects real status, never inferred) --------

    def _palette(self) -> dict:
        # Dark taskbar -> the light body; light taskbar -> the kit's native dark body. Accents kept.
        return gem.NATIVE if windows_uses_light_theme() else gem.ISLAND

    def _on_model(self) -> None:
        # `changed` fires on every feed message (mic levels included); only a real STATE change
        # restarts the animation.
        s = gem.gem_state(self._model.state)
        if s != self._state:
            self._state = s
            self._frame = 0
            self._pal = self._palette()
            self._sync()

    def _sync(self) -> None:
        if self._state in self._STILL or gem.frame_count(self._state) <= 1:
            self._anim.stop()
        else:
            self._anim.start(max(1, round(1000 / gem.fps(self._state))))
        self._paint()

    def _tick(self) -> None:
        self._frame += 1
        self._paint()

    def _paint(self) -> None:
        self.setIcon(gem.icon(self._state, self._frame, 32, self._pal))
