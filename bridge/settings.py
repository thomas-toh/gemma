r"""User settings — the config file the tray writes and the bridge reads.

The first step of spec/70's settings surface (the full settings page is still owed). One
small JSON file in the per-user config dir: the tray (teleprompter process) writes it, the
bridge reads it FRESH at each decision point, so a toggle takes effect on the next turn with
no restart and no file-watcher. Stdlib only — the bridge must read this headless, without Qt.

spec/70 §2: settings travel by FILE, not over the status socket — this is that file. When the
real settings page lands it grows from here: same location, same DEFAULTS, same load/set.
"""
from __future__ import annotations

import json
import logging
import os
from pathlib import Path

log = logging.getLogger("gemma.settings")

# Defaults in ONE place — the source of truth until a real settings schema lands (spec/70 §4).
# A missing file or missing key falls back to these.
DEFAULTS: dict[str, object] = {
    "tts": False,     # spoken replies — a capability behind a switch, default OFF (spec/40, D23)
    "pings": True,    # earcons (the three device pings) — default ON
}


def settings_path() -> Path:
    r"""%APPDATA%\gemma\settings.json on Windows; ~/.config/gemma/settings.json elsewhere.
    GEMMA_SETTINGS overrides the whole path (tests + power users), matching spec/70's env-override
    pattern. Location chosen here (spec/70 §4 open question) so the tray and bridge agree."""
    override = os.environ.get("GEMMA_SETTINGS")
    if override:
        return Path(override)
    base = os.environ.get("APPDATA")
    root = Path(base) if base else Path.home() / ".config"
    return root / "gemma" / "settings.json"


def _read_raw() -> dict:
    """Only the keys actually written to the file (no defaults merged in), so the file stays a
    minimal record of user overrides and DEFAULTS can evolve. Missing/broken file -> {}: settings
    must never be the reason the daemon won't start."""
    try:
        return json.loads(settings_path().read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    except (OSError, ValueError) as e:
        log.warning("settings unreadable (%s) — using defaults", e)
        return {}


def load() -> dict:
    """Every setting: defaults under whatever the file overrides."""
    return {**DEFAULTS, **_read_raw()}


def get(key: str):
    """One setting by name, falling back to its default (or None if unknown)."""
    return load().get(key, DEFAULTS.get(key))


def set(key: str, value) -> None:
    """Write one setting, preserving the others already in the file. Creates the dir/file on
    first write. The tray calls this; the bridge only reads."""
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    data = _read_raw()
    data[key] = value
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
    log.info("setting %s = %r", key, value)


if __name__ == "__main__":
    # ponytail: runnable self-check for the read/write/merge — points at a throwaway file so it
    # never touches the real settings.
    import tempfile

    with tempfile.TemporaryDirectory() as d:
        os.environ["GEMMA_SETTINGS"] = str(Path(d) / "settings.json")
        assert load() == DEFAULTS, "missing file must yield defaults"
        assert get("tts") is False and get("pings") is True
        assert get("nope") is None, "unknown key -> None"
        set("tts", True)
        assert get("tts") is True, "set() must persist"
        assert get("pings") is True, "set() must leave other keys at their default"
        set("pings", False)
        assert load() == {"tts": True, "pings": False}, "both overrides survive"
    print(f"settings selfcheck OK: defaults {DEFAULTS}, get/set/preserve, path -> {settings_path()}")
