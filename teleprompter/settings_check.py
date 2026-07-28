"""The settings window's offline check (D29) — the sibling of overlay_check.

    python -m teleprompter.settings_check

Runs on Qt's `offscreen` platform, so it needs no display and no credential store. What it
guards is the thing QML fails at quietly: a binding that throws leaves the window looking
almost right and only prints a warning, so this drives the window through every state it has
— empty, one provider, two, each pane, the Manage sheet — and fails on ANY warning.

It also guards the schema→UI contract: the window is generated from
`spec/schemas/settings.json`, so a knob added there with a missing label or an unknown pane
would render as a blank row rather than an error. Checked here instead.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

# Must precede the Qt import, exactly as overlay_check does.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import PySide6  # noqa: E402

# Store-Python quirk (NOTES.md): Qt's QML plugin loader does not search the PySide6 package
# dir where the Qt6*.dll live. Same fix __main__.py applies, needed again here.
_d = os.path.dirname(PySide6.__file__)
os.environ["PATH"] = _d + os.pathsep + os.environ.get("PATH", "")
try:
    os.add_dll_directory(_d)
except (AttributeError, OSError):
    pass

from PySide6.QtCore import QUrl                                          # noqa: E402
from PySide6.QtQml import QQmlApplicationEngine                          # noqa: E402
from PySide6.QtWidgets import QApplication                               # noqa: E402

from bridge import settings                                              # noqa: E402
from teleprompter.model import OverlayModel                              # noqa: E402
from teleprompter.settings_model import SettingsModel                    # noqa: E402
from teleprompter import gem                                             # noqa: E402

HERE = Path(__file__).resolve().parent


def check_icon_font() -> None:
    """The window draws its icons as Material Symbols glyphs (D29). A missing or renamed font file
    turns every icon to tofu with no QML warning — exactly the silent failure this check exists to
    catch — so load the bundled file and confirm the family the Glyph component asks for resolves.
    """
    from PySide6.QtGui import QFontDatabase
    ttf = HERE / "fonts" / "MaterialSymbolsOutlined.ttf"
    assert ttf.exists(), f"icon font missing: {ttf}"
    fid = QFontDatabase.addApplicationFont(str(ttf))
    fams = QFontDatabase.applicationFontFamilies(fid) if fid != -1 else []
    # The literal must match Theme.qml's `fontIcon`; both name the same bundled family.
    assert "Material Symbols Outlined" in fams, f"icon font family changed or failed to load: {fams}"

    # Since D29 a Glyph's `d` is a glyph char (an `ico.*`), never an SVG path. A leftover path
    # literal renders as literal text with no QML warning — the Add-a-model sheet shipped two like
    # that. Fail on any `d: "M…"`/`d: "m…"` (an SVG path starts with a move + coords); `ico.*`
    # bindings have no quote, and the Mark logo uses `PathSvg { path: … }`, so neither trips this.
    import re
    src = (HERE / "SettingsWindow.qml").read_text(encoding="utf-8")
    stray = re.findall(r'\bd:\s*"[Mm][\d\s.\-]', src)
    assert not stray, f"{len(stray)} Glyph(s) still fed an SVG path instead of an ico glyph char"
    print(f"  icon font: {ttf.name} -> {fams[0]}; no raw glyph paths")


def check_recorder(engine, app) -> None:
    """Instantiate a KeyRecorder in isolation, feed it Ctrl+Alt+1, release, and confirm it
    commits 'ctrl+alt+1' — then that a bare key is rejected. Standalone rather than found in the
    live window: the recorder is its own file precisely so its state machine is testable without
    spelunking a Flickable's delegate tree. `cfg` is in the engine's context, so validateBinding
    works exactly as in the window."""
    from PySide6.QtCore import Qt, QEvent, QUrl
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtQml import QQmlComponent

    comp = QQmlComponent(engine, QUrl.fromLocalFile(str(HERE / "KeyRecorder.qml")))
    rec = comp.create(engine.rootContext())
    assert rec is not None, "KeyRecorder.qml did not load:\n  " + "\n  ".join(
        e.toString() for e in comp.errors())

    committed: list[str] = []
    rec.committed.connect(lambda c: committed.append(c))

    def press(key, text=""):
        rec.event(QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier, text))
        app.processEvents()

    def release(key):
        rec.event(QKeyEvent(QEvent.Type.KeyRelease, key, Qt.KeyboardModifier.NoModifier))
        app.processEvents()

    rec.metaObject().invokeMethod(rec, "start")
    app.processEvents()
    press(Qt.Key.Key_Control)
    press(Qt.Key.Key_Alt)
    press(Qt.Key.Key_1, "1")
    assert rec.property("keyName") == "1", rec.property("keyName")
    release(Qt.Key.Key_1)
    assert committed == ["ctrl+alt+1"], committed
    assert rec.property("recording") is False, "commit must end the recording"

    # A bare key must not commit — the daemon would reject it, so the recorder must too.
    committed.clear()
    rec.metaObject().invokeMethod(rec, "start")
    app.processEvents()
    press(Qt.Key.Key_5, "5")
    release(Qt.Key.Key_5)
    assert committed == [], "a modifier-less binding must be rejected, not committed"
    assert rec.property("invalid") is True, "a rejected capture should flag itself"
    rec.metaObject().invokeMethod(rec, "stop")
    app.processEvents()
    print("  recorder: Ctrl+Alt+1 captured and committed; bare key rejected")


def check() -> None:
    # A throwaway settings file: the check must never read or write the real one.
    tmp = tempfile.mkdtemp(prefix="gemma-settings-check-")
    os.environ["GEMMA_SETTINGS"] = str(Path(tmp) / "settings.json")

    # --- the schema→UI contract, before any window exists -----------------------
    schema = settings.schema()
    pane_ids = {p["id"] for p in schema["panes"]}
    assert pane_ids, "the schema declares no panes — Config would have no bands"
    for key, s in schema["settings"].items():
        assert s.get("label"), f"{key}: a row with no label renders blank"
        assert s["pane"] is None or s["pane"] in pane_ids, f"{key}: unknown pane {s['pane']!r}"
        # A row that pairs a toggle with a value must name a toggle that exists, or the switch
        # binds to nothing and silently reads false.
        if s.get("toggledBy"):
            assert s["toggledBy"] in schema["settings"], f"{key}: no such toggle {s['toggledBy']!r}"
            assert schema["settings"][s["toggledBy"]]["type"] == "bool", key
    # Not "no unbuilt switch defaults on" — some should (the cleanup steps are on by default).
    # The rule that matters is narrower: nothing that removes a safety gate starts removed.
    assert schema["settings"]["skip_permissions"]["default"] is False, (
        "a permission bypass must never default on")
    for pid, p in schema["providers"].items():
        assert p.get("name"), f"{pid}: a provider with no name renders blank"
        assert isinstance(p.get("capabilities", {}), dict), pid
        assert p.get("auth") in ("key", "endpoint"), pid
        if p["auth"] == "key":
            assert p.get("credential"), f"{pid}: a keyed provider needs a credential name"

    app = QApplication.instance() or QApplication(sys.argv)
    from teleprompter.__main__ import apply_tracking      # match the app's global letter spacing
    apply_tracking(app)
    check_icon_font()
    engine = QQmlApplicationEngine()
    engine.addImportPath(str(HERE.parent))          # so `import teleprompter` finds Theme

    # Both held in locals for the check's lifetime: a context property does not own the
    # Python object, so an inline `setContextProperty("overlay", OverlayModel())` is collected
    # and every binding onto it reads null. (The lamp reads `overlay.state`, so it fails first.)
    cfg = SettingsModel()
    overlay = OverlayModel()
    engine.rootContext().setContextProperty("cfg", cfg)
    engine.rootContext().setContextProperty("overlay", overlay)
    engine.rootContext().setContextProperty("fontFamily", "Arial")
    engine.rootContext().setContextProperty("reducedMotion", False)
    # Gem in the top bar (Track P): the same provider + frame-count property the real host wires,
    # so the window's Gem row renders here instead of throwing an unknown-source / undefined warning.
    engine.addImageProvider("gem", gem.GemImageProvider())
    engine.rootContext().setContextProperty("gemFrames", gem.frame_counts())

    warnings: list[str] = []
    engine.warnings.connect(lambda ws: warnings.extend(w.toString() for w in ws))

    engine.load(QUrl.fromLocalFile(str(HERE / "SettingsWindow.qml")))
    roots = engine.rootObjects()
    assert roots, "SettingsWindow.qml did not load:\n  " + "\n  ".join(warnings)
    win = roots[0]

    def settle() -> None:
        for _ in range(3):
            app.processEvents()

    # --- every state the window has ---------------------------------------------
    # Empty: Model selection before any provider is added. This is the first-run screen and
    # the one most likely to break, because every card binding is evaluated against nothing.
    assert cfg.models == {}, "the check must start from an empty profile"
    # Both sections, so every binding in each view is evaluated — the content Loader only
    # builds the active one, so a throw in Config hides until Config is shown.
    for section in ("models", "config"):
        win.setProperty("section", section)
        settle()

    win.setProperty("section", "models")
    cfg.addProvider("anthropic")                   # one provider: no Primary pill yet
    settle()
    assert cfg.values["primary"] == "anthropic"

    cfg.addProvider("groq")                        # two: Primary appears on both cards
    settle()
    # Capability-driven rows: the pane must not offer a control the provider lacks.
    caps = cfg.catalog["anthropic"]["capabilities"]
    assert "effort" in caps and caps.get("thinking") is True, "Claude should offer both rows"
    assert not cfg.catalog["groq"]["capabilities"], "Groq offers neither — its card is one row"

    cfg.addProvider("ollama")                      # local: the second group appears
    settle()
    assert any(cfg.catalog[p]["where"] == "local" for p in cfg.models), "no local provider added"

    win.setProperty("manageOpen", True)
    settle()

    # The Add-a-model form, both sides. Step 2's rows are bound to the chosen provider's
    # capabilities, so walking the whole catalogue is what proves a provider with no effort
    # scale, or no models to list, does not throw.
    win.setProperty("addStep", 2)
    for where in ("cloud", "local"):
        win.setProperty("addKind", where)
        for pid in cfg.providersFor(where):
            win.setProperty("addProviderId", pid)
            for has_key in (False, True):
                win.setProperty("addHasKey", has_key)
                settle()
    win.setProperty("addStep", 1)
    settle()
    # Credential state is a property, not a slot call, so the chips refresh after a save.
    # (The expanded key editor's own bindings are still constructed with the delegate — QML
    # builds a collapsed item, it just does not paint it — so a throw in there is caught here.
    # What is NOT covered is the interaction itself; that needs a real mouse.)
    assert set(cfg.keys) == set(cfg.catalog), "every provider needs a credential state"
    assert all(v in ("stored", "none", "unavailable") for v in cfg.keys.values()), cfg.keys
    win.setProperty("manageOpen", False)
    settle()

    # Toggling through the model card's own controls, which is where most bindings live.
    cfg.setModel("anthropic", "on", False)
    settle()
    cfg.setModel("anthropic", "on", True)
    cfg.setModel("anthropic", "thinking", True)
    cfg.setModel("anthropic", "effort", "max")
    settle()

    # The one accent control in the app, and the lamp that follows it.
    cfg.set("listen_for_me", True)
    settle()
    cfg.set("listen_for_me", False)
    settle()

    # Back to empty — removing the last provider must restore the empty state cleanly.
    for pid in list(cfg.models):
        cfg.removeProvider(pid)
    settle()
    assert cfg.models == {} and cfg.values["primary"] == ""

    # The keybind recorder: drive it with synthetic key events and confirm it captures a combo
    # and commits the validated string. Done here because its logic (modifier accretion, the
    # commit-on-release) has no non-Qt half to unit-test.
    check_recorder(engine, app)

    assert not warnings, (
        f"{len(warnings)} QML warning(s) — a binding is throwing:\n  "
        + "\n  ".join(warnings))

    os.environ.pop("GEMMA_SETTINGS", None)
    print(f"settings_check OK: window built from {len(schema['settings'])} declared settings, "
          f"{len(pane_ids)} panes, {len(schema['providers'])} providers; "
          f"empty/one/two/local/manage states clean, no QML warnings")


if __name__ == "__main__":
    check()
