"""Qt-side model for the settings window — the only thing standing between QML and the two
places a setting can live: the config file (bridge/settings.py) and the OS credential store.

Deliberately thin, like model.py: no rule about what a pane contains lives here. Panes, rows,
labels, defaults and provider capabilities all come from `spec/schemas/settings.json`, so this
file exposes the schema rather than restating it (hard rule 3).

Secrets never touch the settings file. `keyState`/`setKey` talk to `keyring` under service
`gemma`, keyed by PROVIDER (spec/50 rule 10) — the same entries claude.py and the Groq cleanup
already read.
"""
from __future__ import annotations

import logging
import threading

from PySide6.QtCore import Property, QObject, Signal, Slot

from bridge import settings
from bridge.brains import providers

log = logging.getLogger("gemma.teleprompter")

KEY_SERVICE = "gemma"


class SettingsModel(QObject):
    """One `changed` signal for the lot — the window is small and rebuilt on open, so
    re-evaluating its bindings per write costs nothing worth plumbing around."""

    changed = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        # The live model lists, per provider, filled by refreshModels() off a worker thread.
        # Only ever holds a non-empty result: a failed fetch leaves the offline fallback in play
        # rather than blanking a picker the user was already reading.
        self._live: dict[str, list[str]] = {}
        self._fetching: set[str] = set()
        # The last probe outcome per provider: ok · nokey · auth · unreachable · empty · error
        # (bridge/brains/providers.probe). Absent until something has actually asked.
        self._status: dict[str, str] = {}
        # Per-provider probe generation. A forced probe can overtake one already in flight (that
        # is what Test means), so a returning worker must prove it is still the newest before it
        # writes — otherwise the stale answer lands last and the user reads the wrong status.
        self._gen: dict[str, int] = {}
        self._lock = threading.Lock()

    # --- the schema: what to draw ------------------------------------------------

    @Property("QVariant", constant=True)
    def panes(self) -> list:
        return settings.schema()["panes"]

    @Property("QVariant", constant=True)
    def meta(self) -> dict:
        """Every setting's declaration, keyed by id (type, default, pane, label, help, built)."""
        return settings.schema()["settings"]

    @Property("QVariant", constant=True)
    def catalog(self) -> dict:
        """The providers Manage can offer."""
        return settings.schema()["providers"]

    # --- the values: what is set --------------------------------------------------

    @Property("QVariant", notify=changed)
    def values(self) -> dict:
        return settings.load()

    @Slot(str, "QVariant")
    def set(self, key: str, value) -> None:
        settings.set(key, value)
        self.changed.emit()

    @Slot(str, result=bool)
    def validateBinding(self, combo: str) -> bool:
        """Is `combo` a shortcut the daemon can actually register? The keybind recorder asks
        before committing, so the window never stores something hotkeys.py will reject at
        startup. Reuses the real parser (hard rule 3) rather than re-listing the key vocabulary
        — a bare key, an unknown key, or two non-modifier keys all fail here exactly as they
        would there."""
        try:
            from bridge.hotkeys import parse_binding
            parse_binding(combo)
            return True
        except (ValueError, ImportError):
            return False

    @Slot(str, result="QVariant")
    def rowsFor(self, pane: str) -> list:
        """The setting ids that render as an ordinary row on `pane`, in schema order.
        `models` is excluded — Model selection draws it as provider cards, not a row."""
        return [k for k, s in self.meta.items()
                if s.get("pane") == pane and s["type"] not in ("object",) and k != "primary"]

    @Slot(str, str, result="QVariant")
    def rowsInGroup(self, pane: str, group: str) -> list:
        """The rows of one titled group within a pane (General's Profile / Preferences)."""
        return [k for k in self.rowsFor(pane) if self.meta[k].get("group") == group]

    @Slot(str, result="QVariant")
    def groupsFor(self, pane: str) -> list:
        """A pane's titled groups, or [] when its rows are drawn flat."""
        for p in self.panes:
            if p["id"] == pane:
                return p.get("groups", [])
        return []

    # --- providers ----------------------------------------------------------------

    @Property("QVariant", notify=changed)
    def models(self) -> dict:
        """Providers the user has added: id -> {on, model, effort, thinking, ...}."""
        got = settings.get("models")
        return got if isinstance(got, dict) else {}

    @Property("QVariant", notify=changed)
    def addedProviders(self) -> list:
        """The provider ids in play — what a role (dictation cleanup, prompt cleanup) can be
        pointed at. Empty until a model is added."""
        return list(self.models.keys())

    @Slot(str, result="QVariant")
    def providersFor(self, where: str) -> list:
        """Catalogue ids for one side of the Add flow: `cloud` or `local`."""
        return [pid for pid, p in self.catalog.items() if p.get("where") == where]

    @Slot(str, "QVariant")
    def addProvider(self, pid: str, config=None) -> None:
        """Add or update a provider. `config` carries whatever the Add form collected; anything
        it omits falls back to a sensible start, so the one-argument call still works."""
        cat = self.catalog.get(pid)
        if cat is None:
            return
        caps = cat.get("capabilities", {})
        efforts = caps.get("effort") or []
        entry = {
            "on": True,
            # Fallback list until the live fetch lands; may be empty (a local runner ships none).
            "model": (cat.get("models") or [""])[0],
            # `high` where offered — the provider default — else the top of a shorter scale.
            "effort": ("high" if "high" in efforts else efforts[-1]) if efforts else None,
            "thinking": False,
        }
        if cat.get("auth") == "endpoint":
            entry["endpoint"] = cat.get("endpoint", "")
        if isinstance(config, dict):
            entry.update({k: v for k, v in config.items() if v is not None})
        added = dict(self.models)
        added[pid] = entry
        settings.set("models", added)
        if not settings.get("primary"):
            settings.set("primary", pid)
        self.changed.emit()
        self.refreshModels(pid)     # so a freshly added card has a real picker, not an empty one

    @Slot(str)
    def removeProvider(self, pid: str) -> None:
        added = dict(self.models)
        added.pop(pid, None)
        settings.set("models", added)
        if settings.get("primary") == pid:
            live = [k for k, v in added.items() if v.get("on")]
            settings.set("primary", live[0] if live else "")
        self.changed.emit()

    @Slot(str, str, "QVariant")
    def setModel(self, pid: str, field: str, value) -> None:
        """Change one field of one added provider (on / model / effort / thinking / …)."""
        added = dict(self.models)
        if pid not in added:
            return
        entry = dict(added[pid])
        entry[field] = value
        added[pid] = entry
        settings.set("models", added)
        # Turning off the primary hands the crown to another enabled provider, so the daemon
        # is never pointed at a provider the user just disabled.
        if field == "on" and not value and settings.get("primary") == pid:
            live = [k for k, v in added.items() if v.get("on")]
            settings.set("primary", live[0] if live else "")
        elif field == "on" and value and not settings.get("primary"):
            settings.set("primary", pid)
        self.changed.emit()

    @Slot(str, int)
    def moveProvider(self, pid: str, delta: int) -> None:
        """Move a model up or down the Ask list.

        The order IS the key order of the `models` object: JSON objects preserve insertion
        order in both the writer (Python 3.7+) and the reader (QML/JS, for string keys), so
        reordering means rewriting the dict rather than carrying a parallel index that could
        fall out of step with it.
        """
        ids = list(self.models.keys())
        if pid not in ids:
            return
        i = ids.index(pid)
        j = i + delta
        if not 0 <= j < len(ids):
            return                                # already at an end — nothing to do
        ids[i], ids[j] = ids[j], ids[i]
        added = self.models
        settings.set("models", {k: added[k] for k in ids})
        self.changed.emit()

    @Slot(str)
    def setPrimary(self, pid: str) -> None:
        settings.set("primary", pid)
        self.changed.emit()

    @Property("QVariant", notify=changed)
    def modelOptions(self) -> dict:
        """Every provider's pickable model ids, keyed by provider id: the live list once fetched,
        else the card's offline fallback.

        A PROPERTY, not just the slot below, for the same reason `keys` is one: QML re-evaluates a
        binding when a property it read changes, but a plain function call is not tracked. A
        dropdown bound to `modelsFor(id)` would therefore keep showing the empty offline list
        forever, even after a fetch landed and `changed` fired — which is exactly what it did.
        """
        return {pid: self.modelsFor(pid) for pid in self.catalog}

    @Slot(str, result="QVariant")
    def modelsFor(self, pid: str) -> list:
        """The model ids to offer for a provider: the live list once fetched, else the card's
        offline fallback. Never blocks — call `refreshModels` to go and look.

        Note the fallback is EMPTY for every provider but Anthropic (the cards ship no `models`),
        so without a fetch a picker has nothing to show.
        """
        with self._lock:
            live = self._live.get(pid)
        return live or self.catalog.get(pid, {}).get("models", [])

    @Property("QVariant", notify=changed)
    def probeStates(self) -> dict:
        """Every provider's last probe outcome, keyed by id — a property so a binding that shows
        it re-evaluates when a fetch lands (same reason as `modelOptions`)."""
        return {pid: self.modelState(pid) for pid in self.catalog}

    @Slot(str, result=str)
    def modelState(self, pid: str) -> str:
        """What the window should say about this provider's models:

          `untested`     nobody has asked yet
          `fetching`     a probe is in flight
          `ok`           the provider answered with models
          `nokey`        no key stored
          `auth`         the provider REJECTED the key — the one a user must be told plainly
          `unreachable`  offline, or a local runner that isn't running
          `empty`        answered, but with nothing this account can use
          `error`        something else

        Anything but `ok` means the picker is showing the card's offline fallback, which is empty
        for every provider except Anthropic.
        """
        with self._lock:
            if pid in self._fetching:
                return "fetching"
            return self._status.get(pid, "untested")

    @Slot(str)
    @Slot(str, str)
    def testProvider(self, pid: str, key: str = "") -> None:
        """Re-probe a provider even if we already hold its list — what the Test button calls.

        Deliberately forceful: the user pressing Test has usually just changed the key, and the
        point of the button is to find out whether the provider accepts it.

        `key` is the key TYPED IN THE FORM, which matters because the Add flow does not store a
        key until you commit — so testing the credential store would test the old key, or none.
        It is used for the probe and never written anywhere.
        """
        self._fetch(pid, force=True, key=key)

    @Slot(str)
    def refreshModels(self, pid: str) -> None:
        """Fetch a provider's model list if we have not already got one. Safe to call from a
        binding or `Component.onCompleted` — repeats are free."""
        self._fetch(pid, force=False)

    def _fetch(self, pid: str, force: bool, key: str = "") -> None:
        """Fetch a provider's real model list in the background.

        On a worker thread because the window must never freeze on someone else's network: the
        fetch is a plain blocking GET with a short timeout (providers.FETCH_TIMEOUT_S), and Qt
        signal emission is thread-safe, so the worker can announce itself directly.

        Two forms of idempotence, because QML rebuilds bindings freely: a fetch already in flight
        is never started twice, and a provider whose list we already hold is not re-fetched unless
        `force` (which is what saving a key does — the key is precisely what changes the answer).
        """
        cat = self.catalog.get(pid)
        if cat is None:
            return
        with self._lock:
            # `force` overtakes a probe already in flight rather than being swallowed by it: Test
            # is pressed precisely when the key or endpoint just changed, so the in-flight answer
            # is about to be wrong. Unforced fetches keep both cheap idempotences.
            if not force and (pid in self._fetching or pid in self._live):
                return
            gen = self._gen[pid] = self._gen.get(pid, 0) + 1
            self._fetching.add(pid)
        # A local runner's port is user-editable, so ask the entry before the catalogue default.
        endpoint = (self.models.get(pid) or {}).get("endpoint")

        def work() -> None:
            try:
                found, status = providers.probe(pid, endpoint, key=key)
            except Exception as e:                # probe swallows its own, but never trust that
                log.warning("model probe failed for %s: %s", pid, e)
                found, status = [], "error"
            with self._lock:
                if self._gen.get(pid) != gen:   # a newer probe overtook this one — drop the answer
                    log.info("model probe %s: superseded, discarding %s", pid, status)
                    return                      # and leave `_fetching` set: the newer one owns it
                self._fetching.discard(pid)
                self._status[pid] = status
                if found:
                    self._live[pid] = found
            log.info("model probe %s: %s (%d models)", pid, status, len(found))
            self.changed.emit()

        threading.Thread(target=work, name=f"gemma-models-{pid}", daemon=True).start()

    # --- credentials (never the settings file) ------------------------------------

    @Property("QVariant", notify=changed)
    def keys(self) -> dict:
        """Every provider's credential state, keyed by provider id. A PROPERTY rather than
        only the slot below, because QML re-evaluates a binding when a property it reads
        changes — a plain function call is not tracked, so a chip bound to `keyState(id)`
        would never refresh after a key was saved."""
        return {pid: self.keyState(pid) for pid in self.catalog}

    @Slot(str, result=str)
    def keyState(self, pid: str) -> str:
        """'stored', 'none', or 'unavailable' if the credential store cannot be read."""
        cat = self.catalog.get(pid, {})
        if cat.get("auth") != "key":
            return "none"
        try:
            import keyring
            return "stored" if keyring.get_password(KEY_SERVICE, cat["credential"]) else "none"
        except Exception as e:                    # a broken/locked backend must not crash us
            log.warning("credential store unreadable: %s", e)
            return "unavailable"

    @Slot(str, str, result=bool)
    def setKey(self, pid: str, value: str) -> bool:
        """Store or clear a provider's key. The value is never logged and never written
        anywhere but the OS credential store (spec/50 rule 10)."""
        cat = self.catalog.get(pid, {})
        if cat.get("auth") != "key":
            return False
        name = cat["credential"]
        try:
            import keyring
            if value.strip():
                keyring.set_password(KEY_SERVICE, name, value.strip())
                log.info("key stored as (%s, %s)", KEY_SERVICE, name)
                # Saving a key is the moment the answer changes, so go and look straight away:
                # a picker that stays empty after a paste reads as "broken", not "unasked".
                # The Test button re-runs the same probe when the user wants to check by hand.
                self._fetch(pid, force=True)
            else:
                try:
                    keyring.delete_password(KEY_SERVICE, name)
                    log.info("key cleared for (%s, %s)", KEY_SERVICE, name)
                except Exception:
                    pass                          # nothing stored — clearing is a no-op
                # Drop what the old key told us, or the picker would keep offering models this
                # profile can no longer reach.
                with self._lock:
                    self._live.pop(pid, None)
                    self._status.pop(pid, None)
            self.changed.emit()
            return True
        except Exception as e:
            log.error("could not write the credential store: %s", e)
            return False


if __name__ == "__main__":
    # ponytail: runnable check of the provider bookkeeping — the one place with real logic.
    # Points at a throwaway settings file; needs no Qt event loop and no credential store.
    import os
    import tempfile
    from pathlib import Path

    from PySide6.QtCore import QCoreApplication

    app = QCoreApplication([])                    # QObject needs an application object
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["GEMMA_SETTINGS"] = str(Path(tmp) / "s.json")
        m = SettingsModel()
        assert m.models == {}, "no providers before any are added"
        assert [g["id"] for g in m.groupsFor("general")] == ["profile", "preferences"]
        assert m.groupsFor("triggers") == [], "a flat pane declares no groups"
        assert m.rowsInGroup("general", "preferences") == \
            ["theme", "language", "pings", "listen_for_me", "tts", "gem_in_island"], \
            m.rowsInGroup("general", "preferences")
        # Every row of a grouped pane must land in a group, or it renders nowhere.
        grouped = sum(len(m.rowsInGroup("general", g["id"])) for g in m.groupsFor("general"))
        assert grouped == len(m.rowsFor("general")), "a General row is in no group"
        assert "models" not in m.rowsFor("models"), "cards are not rows"

        m.addProvider("anthropic")
        assert m.models["anthropic"]["on"] is True
        assert m.models["anthropic"]["effort"] == "high", "effort starts at the provider default"
        assert settings.get("primary") == "anthropic", "first added provider becomes primary"

        m.addProvider("groq")
        assert m.models["groq"]["effort"] is None, "no effort row for a provider without one"
        assert settings.get("primary") == "anthropic", "adding must not steal primary"

        m.setModel("anthropic", "on", False)
        assert settings.get("primary") == "groq", "disabling the primary must hand it on"
        m.setModel("groq", "on", False)
        assert settings.get("primary") == "", "nothing enabled -> no primary"

        m.setModel("groq", "on", True)
        assert settings.get("primary") == "groq", "re-enabling with no primary reclaims it"

        # Reorder: the key order of `models` is the display order.
        m.addProvider("openai")
        assert list(m.models) == ["anthropic", "groq", "openai"], list(m.models)
        m.moveProvider("openai", -1)
        assert list(m.models) == ["anthropic", "openai", "groq"], list(m.models)
        m.moveProvider("anthropic", -1)
        assert list(m.models) == ["anthropic", "openai", "groq"], "top cannot move up"
        m.moveProvider("groq", 1)
        assert list(m.models) == ["anthropic", "openai", "groq"], "bottom cannot move down"
        m.moveProvider("nosuch", 1)               # must not raise
        assert m.models["openai"]["on"] is True, "reordering must not disturb the entries"
        m.removeProvider("openai")

        m.removeProvider("groq")
        assert "groq" not in m.models and settings.get("primary") == ""

        # --- the live model fetch (no network) -------------------------------------------
        # Until a fetch lands, a picker shows the card's offline list and says so. That matters
        # because a fallback list goes stale silently: Anthropic's live list already carries
        # models this schema does not name.
        import time

        # `mistral` deliberately: the checks above added anthropic/groq/openai/ollama, and
        # addProvider now kicks its own probe, so those are no longer in a virgin state.
        assert m.modelsFor("mistral") == m.catalog["mistral"]["models"]
        assert m.modelState("mistral") == "untested", "nothing is claimed before anything asks"
        assert m.modelsFor("nosuch") == [], "an unknown provider offers nothing, never raises"
        m.refreshModels("nosuch")               # must not start a thread or raise

        # Every card must be answerable by the picker binding, or a dropdown renders undefined.
        assert set(m.modelOptions) == set(m.catalog)
        assert set(m.probeStates) == set(m.catalog)

        # A probe that finds nothing must LEAVE the fallback standing rather than blank the picker
        # the user is reading — and must say WHY, which is the whole point of the Test button.
        m.addProvider("ollama")                 # addProvider kicks its own (harmless) probe
        m.setModel("ollama", "endpoint", "127.0.0.1:1")
        m.testProvider("ollama")
        for _ in range(200):
            if m.modelState("ollama") != "fetching":
                break
            time.sleep(0.05)
        assert m.modelState("ollama") == "unreachable", \
            f"a dead runner must be nameable, got {m.modelState('ollama')!r}"
        assert m.modelsFor("ollama") == m.catalog["ollama"]["models"], "fallback must survive"

        # Test OVERTAKES a probe already in flight, and the overtaken answer is DISCARDED rather
        # than landing last. Both halves matter: without the first, pressing Test right after
        # adding a provider does nothing (the bug — `force` was swallowed by the in-flight guard);
        # without the second, the stale reply overwrites the fresh one and the user reads a status
        # for an endpoint they have already changed. Faked probes, so this needs no network and no
        # local runner: slow-and-wrong vs fast-and-right, deliberately returned out of order.
        real_probe = providers.probe
        try:
            first_started = threading.Event()

            def slow_then_fast(pid, endpoint=None, timeout=None, key=None):
                if endpoint == "127.0.0.1:2":
                    return [], "unreachable"          # the forced probe: immediate, correct
                first_started.set()
                time.sleep(0.5)                       # the overtaken probe: late, and wrong
                return [], "empty"

            providers.probe = slow_then_fast
            race = SettingsModel()
            race.addProvider("ollama")
            assert first_started.wait(3), "the first probe never started"
            race.setModel("ollama", "endpoint", "127.0.0.1:2")
            race.testProvider("ollama")               # must overtake, not be swallowed
            for _ in range(60):
                if race.modelState("ollama") == "unreachable":
                    break
                time.sleep(0.05)
            assert race.modelState("ollama") == "unreachable", \
                f"Test must overtake a probe in flight, got {race.modelState('ollama')!r}"
            time.sleep(0.8)                           # let the overtaken probe return late
            assert race.modelState("ollama") == "unreachable", \
                f"a superseded probe must not land last, got {race.modelState('ollama')!r}"
            race.removeProvider("ollama")
        finally:
            providers.probe = real_probe

        # ...and a probe that DID find something wins over the card, without another round trip.
        with m._lock:
            m._live["ollama"] = ["llama3.2:3b", "qwen3:8b"]
            m._status["ollama"] = "ok"
        assert m.modelState("ollama") == "ok"
        assert m.modelsFor("ollama") == ["llama3.2:3b", "qwen3:8b"], "the live list must win"
        assert m.modelOptions["ollama"] == ["llama3.2:3b", "qwen3:8b"], "the property must agree"
        # refreshModels must NOT re-fetch what we hold; testProvider must.
        m.refreshModels("ollama")
        assert m.modelState("ollama") == "ok", "a cached list is not re-fetched by refreshModels"
        m.removeProvider("ollama")
    os.environ.pop("GEMMA_SETTINGS", None)
    print("settings_model selfcheck OK: add/remove/enable/primary bookkeeping, "
          "live model fetch falls back without blanking the picker")
