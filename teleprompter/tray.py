"""System tray (Track P C3) — the only "Gemma is running" signal there is.

The island hides completely at idle (spec/40: "gone = asleep"), so without this you cannot
tell the overlay from a dead process. It also carries the one setting that cannot wait for
spec/70's real settings surface: the Groq cleanup key.
"""
from __future__ import annotations

import logging

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPainterPath, QPixmap
from PySide6.QtWidgets import QInputDialog, QLineEdit, QMenu, QSystemTrayIcon

log = logging.getLogger("gemma.teleprompter")

# spec/50 rule 10: secrets live in the OS credential store under service `gemma`, keyed by
# PROVIDER (not by role) — so a future router can point any role at this one key. This is the
# cleanup engine's key (D15/D20); the brain's is ("gemma", "anthropic") and is untouched here.
KEY_SERVICE = "gemma"
KEY_USER = "groq"


def make_icon() -> QIcon:
    """The island silhouette, painted rather than shipped as a binary asset. White fill with a
    dark keyline so it survives both light and dark taskbars."""
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


class Tray(QSystemTrayIcon):
    def __init__(self, app, model=None) -> None:
        super().__init__(make_icon())
        self._app = app
        self._model = model
        self.setToolTip("Gemma — Teleprompter")

        menu = QMenu()
        act_key = QAction("Set Groq API key…", menu)
        act_key.triggered.connect(self._set_key)
        menu.addAction(act_key)
        if model is not None:
            act_lat = QAction("Show latency", menu)      # D13's acceptance-run instrument
            act_lat.setCheckable(True)
            act_lat.setChecked(bool(model.showLatency))
            act_lat.toggled.connect(model.toggle_latency)
            menu.addAction(act_lat)
        menu.addSeparator()
        act_quit = QAction("Quit", menu)
        act_quit.triggered.connect(app.quit)
        menu.addAction(act_quit)
        # Held deliberately: setContextMenu does not take ownership, and a menu that is
        # garbage collected takes the tray's right-click with it.
        self._menu = menu
        self.setContextMenu(menu)
        self.show()

    def _set_key(self) -> None:
        """Read/replace/clear the Groq key. The value is never logged and never written
        anywhere but the OS credential store (spec/50 rule 10)."""
        import keyring

        try:
            existing = keyring.get_password(KEY_SERVICE, KEY_USER)
        except Exception as e:                      # a broken/locked backend must not crash us
            existing = None
            log.warning("credential store unreadable: %s", e)

        prompt = ("Groq API key — used for dictation cleanup only.\n"
                  f"Stored in the OS credential store as ({KEY_SERVICE}, {KEY_USER}).\n"
                  "Leave blank and press OK to clear it.")
        if existing:
            prompt += "\n\nA key is already stored; a new one replaces it."

        text, ok = QInputDialog.getText(None, "Gemma — Groq API key", prompt,
                                        QLineEdit.EchoMode.Password)
        if not ok:
            return
        text = text.strip()
        try:
            if text:
                keyring.set_password(KEY_SERVICE, KEY_USER, text)
                log.info("Groq key stored as (%s, %s)", KEY_SERVICE, KEY_USER)
                self.showMessage("Gemma", "Groq API key saved.", make_icon(), 3000)
            elif existing:
                keyring.delete_password(KEY_SERVICE, KEY_USER)
                log.info("Groq key cleared")
                self.showMessage("Gemma", "Groq API key cleared.", make_icon(), 3000)
        except Exception as e:
            log.error("could not write the credential store: %s", e)
            self.showMessage("Gemma", f"Could not save the key: {e}", make_icon(), 5000)
