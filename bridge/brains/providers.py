"""The provider catalogue — one lookup layer shared by every adapter and by the settings window.

The catalogue itself is `spec/schemas/settings.json` -> `providers` (hard rule 3): which
providers exist, where each runs, how it authenticates, which credential-store entry holds its
key, which env var stands in for that key, **which wire protocol serves it** (`wire`) and its
API base URL (`api`). Nothing here restates any of it — this module only reads it.

Two wires cover all eleven providers:

  `anthropic`  Anthropic's own Messages API, served by B1 (`claude.py`).
  `openai`     everything else, served by B2 (`compat.py`) — Groq, OpenAI, xAI, DeepSeek,
               Mistral, OpenRouter and Google's compat layer in the cloud; Ollama, LM Studio
               and llama.cpp locally, which all expose an OpenAI-compatible `/v1`.

Deliberately NOT here: choosing which provider to use. That is the router (spec/20 §Routing),
which is still unbuilt and out of scope — this module answers "how do I reach X", never
"should I use X".
"""
from __future__ import annotations

import logging
import os

from bridge.settings import schema

log = logging.getLogger("gemma.brains")

# How long the settings window is willing to wait on a provider's model list. Short on purpose:
# it runs off a background thread, but a user staring at a spinner is the real budget.
FETCH_TIMEOUT_S = 6.0

# Every outcome `probe()` can report. Closed set: the settings window turns each into a sentence
# for the user (SettingsWindow.qml `addProbeMessage`), so a new one added here without a sentence
# there shows the user nothing. The selfcheck pins this list for exactly that reason.
PROBE_STATUSES = ("ok", "nokey", "auth", "unreachable", "empty", "error")


def catalog() -> dict[str, dict]:
    """Every provider card, keyed by id."""
    return schema()["providers"]


def card(pid: str) -> dict:
    """One provider's card, or {} for an id that is not in the catalogue."""
    return catalog().get(pid, {})


def wire(pid: str) -> str:
    """Which wire protocol serves this provider: 'anthropic' or 'openai'."""
    return card(pid).get("wire", "")


def base_url(pid: str, endpoint: str | None = None) -> str:
    """The provider's OpenAI-compatible base URL.

    Cloud providers declare it outright (`api`), because the hosts genuinely differ. Local
    runners declare a user-editable `host:port` instead and the URL is built from it — `/v1`
    is the OpenAI-compat convention shared by Ollama, LM Studio and llama.cpp alike, not a
    per-provider value, so composing it here restates nothing. `endpoint` overrides the
    catalogue default, which is what the settings entry stores when the user moves a port.

    A blank `endpoint` falls back to the catalogue default deliberately: clearing the field in
    the settings window should restore the standard port, not produce a URL that cannot resolve.
    """
    c = card(pid)
    if c.get("auth") == "endpoint":
        # Strip BEFORE falling back, so a field holding only spaces counts as cleared.
        host = ((endpoint or "").strip() or (c.get("endpoint") or "").strip()).rstrip("/")
        if not host:
            return ""
        if "://" not in host:
            host = f"http://{host}"
        return host if host.endswith("/v1") else f"{host}/v1"
    return c.get("api", "")


def credential_for(pid: str) -> str | None:
    """A provider's API key: OS credential store first (spec/50 rule 10, service 'gemma'),
    then the env var the card names.

    Both names come from the catalogue — the account name from `credential` and the fallback
    variable from `env` — so adding a provider is still a JSON edit and nothing else. Local
    runners authenticate by endpoint and have no key; they return None and the compat adapter
    sends a placeholder, because OpenAI's own client requires the header to exist.
    """
    c = card(pid)
    if c.get("auth") != "key":
        return None
    try:
        import keyring

        key = keyring.get_password("gemma", c["credential"])
        if key:
            return key
    except Exception as e:                        # a locked/broken backend must not be fatal
        log.warning("credential store unreadable for %s: %s", pid, e)
    env = c.get("env")
    return os.environ.get(env) if env else None


def _chat_only(ids: list[str]) -> list[str]:
    """Drop the ids that cannot serve a turn, and sort what remains.

    `GET /models` returns everything an account can reach, which includes speech-to-text,
    text-to-speech, embeddings, image models and safety classifiers — 15 ids for Groq, 129 for
    OpenAI (measured 2026-07-24). The substrings come from the schema's `not_chat` (hard rule 3)
    and are matched conservatively: anything ambiguous stays in the list, because hiding a model
    the user wanted is worse than showing one they don't.
    """
    bad = schema().get("not_chat", [])
    # Case-insensitive: provider ids mix case (`meta-llama/…`, `Qwen/…`) and a plain sort would
    # file every capitalised vendor above every lowercase one.
    return sorted((m for m in ids if not any(b in m.lower() for b in bad)), key=str.lower)


def probe(
    pid: str,
    endpoint: str | None = None,
    timeout: float = FETCH_TIMEOUT_S,
    key: str | None = None,
) -> tuple[list[str], str]:
    """Ask a provider what models it has. Returns `(ids, status)` and NEVER raises.

    `key` tests a CANDIDATE credential instead of the stored one, and is what the settings
    window's Test button passes: in the Add flow the typed key has not been saved yet (it goes
    to the credential store only on commit), so probing the store would test the wrong thing —
    or nothing at all. A candidate key is used for this call and never written anywhere.

    The status is the whole reason this returns a pair rather than just a list: fetching the
    model list is also the cheapest honest test of a stored key, and "no models" has several
    causes a user needs told apart —

      `ok`           the list came back
      `nokey`        nothing in the credential store for a provider that needs one
      `auth`         the provider rejected the key (401/403) — the key is wrong or revoked
      `unreachable`  no answer: offline, or a local runner that isn't running
      `empty`        the provider answered, but with nothing this account can talk to
      `error`        anything else (a 404 on a bad endpoint path, unparseable JSON)

    Swallowing all of these into `[]` — which this did at first — leaves a wrong key and a
    down network looking identical, and leaves the settings window unable to say either.

    Anthropic goes through its SDK (`models.list()`) so the `anthropic-version` protocol
    constant stays the SDK's business. Every other provider answers `GET {base}/models`,
    including the three local runners, so there is one HTTP shape here and not nine.
    """
    import httpx

    if not wire(pid):
        return [], "error"
    needs_key = card(pid).get("auth") == "key"
    key = (key or "").strip() or credential_for(pid)
    if needs_key and not key:
        return [], "nokey"

    try:
        if wire(pid) == "anthropic":
            import anthropic

            client = anthropic.Anthropic(api_key=key, timeout=timeout)
            found = _chat_only([m.id for m in client.models.list(limit=100).data])
        else:
            url = base_url(pid, endpoint)
            if not url:
                return [], "error"
            headers = {"Authorization": f"Bearer {key}"} if key else {}
            r = httpx.get(f"{url}/models", headers=headers, timeout=timeout)
            r.raise_for_status()
            data = r.json().get("data") or []
            found = _chat_only([m["id"] for m in data if isinstance(m, dict) and m.get("id")])
        return found, ("ok" if found else "empty")
    except Exception as e:
        status = _probe_status(e)
        log.info("model probe for %s: %s (%s)", pid, status, e)
        return [], status


def _probe_status(exc: Exception) -> str:
    """Classify a failed probe by exception TYPE and status code, never message prose — the same
    rule the adapters map errors by (B-02). Both SDKs sit on httpx, so one ladder covers them."""
    import httpx

    status = getattr(exc, "status_code", None)
    if status is None:
        response = getattr(exc, "response", None)
        status = getattr(response, "status_code", None)
    if status in (401, 403):
        return "auth"
    if status is not None and status >= 500:
        return "unreachable"
    if isinstance(exc, (httpx.ConnectError, httpx.ConnectTimeout, httpx.ReadTimeout)):
        return "unreachable"
    if isinstance(exc, httpx.HTTPError):
        return "error"
    return "error"


def list_models(pid: str, endpoint: str | None = None, timeout: float = FETCH_TIMEOUT_S) -> list[str]:
    """The provider's live model ids, or [] if they cannot be fetched. See `probe` for why."""
    return probe(pid, endpoint, timeout)[0]


def build_brain(provider: str, model: str | None = None, endpoint: str | None = None):
    """Construct the adapter that serves `provider`, chosen by its `wire`: B1 (ClaudeBrain) for
    the anthropic wire, B2 (CompatBrain) for the OpenAI wire that the other ten share.

    This is adapter CONSTRUCTION, not routing: it builds the brain you name. Deciding *which*
    provider to use — the primary, per-role selection — is spec/20's router, still out of scope.
    Imports are local to dodge the providers <-> adapters import cycle (both adapters import from
    this module at load time).
    """
    if wire(provider) == "anthropic":
        from .claude import ClaudeBrain

        return ClaudeBrain(model=model)
    from .compat import CompatBrain

    return CompatBrain(provider, model=model, endpoint=endpoint)


if __name__ == "__main__":
    # ponytail: runnable check of the lookups — the logic worth guarding is URL composition and
    # the credential/env fallback. No network: list_models is exercised only for its [] contract.
    cat = catalog()
    assert cat, "the provider catalogue must load from spec/schemas/settings.json"

    # Every card must declare a wire this code can actually serve, and cloud cards must carry
    # both an API base and an env fallback — otherwise the adapter has no way to reach them.
    for pid, c in cat.items():
        assert c.get("wire") in ("anthropic", "openai"), f"{pid}: unknown wire {c.get('wire')!r}"
        if c.get("auth") == "key":
            assert c.get("api", "").startswith("https://"), f"{pid}: cloud card needs an https api"
            assert c.get("env"), f"{pid}: cloud card needs an env fallback name"
        else:
            assert c.get("endpoint"), f"{pid}: a local runner must declare host:port"

    assert wire("anthropic") == "anthropic", "B1 keeps its native wire"
    assert wire("groq") == "openai"
    assert base_url("groq") == cat["groq"]["api"], "a cloud base URL is taken verbatim"

    # Local URL composition: bare host:port, an explicit scheme, and an already-suffixed URL
    # must all land on exactly one /v1.
    assert base_url("ollama") == "http://localhost:11434/v1", base_url("ollama")
    assert base_url("ollama", "127.0.0.1:9999") == "http://127.0.0.1:9999/v1"
    assert base_url("ollama", "https://box.lan:443") == "https://box.lan:443/v1"
    assert base_url("ollama", "http://x:1/v1") == "http://x:1/v1", "must not double the suffix"
    assert base_url("ollama", "  localhost:1234/  ") == "http://localhost:1234/v1"
    # A cleared field restores the catalogue default rather than yielding an unresolvable URL.
    assert base_url("ollama", "") == base_url("ollama") == "http://localhost:11434/v1"
    assert base_url("ollama", "   ") == "http://localhost:11434/v1", "whitespace is still blank"
    assert base_url("nosuch") == "", "an unknown provider resolves to nothing, never raises"

    # A local runner has no key by design; asking for one must not invent a placeholder here.
    assert credential_for("ollama") is None, "endpoint auth carries no credential"
    # The env fallback is read through the card's `env` name, never a literal in this file.
    env_pid = "openrouter"
    os.environ[cat[env_pid]["env"]] = "sentinel"
    try:
        import keyring                            # noqa: F401  - present in this project

        stored = None
        try:
            stored = keyring.get_password("gemma", cat[env_pid]["credential"])
        except Exception:
            pass
        if not stored:
            assert credential_for(env_pid) == "sentinel", "env must stand in when nothing is stored"
    except ImportError:
        assert credential_for(env_pid) == "sentinel"
    os.environ.pop(cat[env_pid]["env"], None)

    assert list_models("nosuch") == [], "an unknown provider fetches nothing and never raises"
    assert list_models("ollama", "127.0.0.1:1") == [], "a dead local runner returns [], not a crash"

    # The probe's STATUS is what lets the settings window tell a wrong key from a dead network —
    # the distinction the first cut lost by returning [] for both.
    import httpx

    assert probe("nosuch")[1] == "error", "an unknown provider is a programming fault, not a 401"
    ids, why = probe("ollama", "127.0.0.1:1", timeout=2.0)
    assert (ids, why) == ([], "unreachable"), (ids, why)

    def _http(status):
        return httpx.HTTPStatusError(
            "x", request=httpx.Request("GET", "http://x"),
            response=httpx.Response(status, request=httpx.Request("GET", "http://x")))

    assert _probe_status(_http(401)) == "auth", "a rejected key must be nameable as such"
    assert _probe_status(_http(403)) == "auth"
    assert _probe_status(_http(404)) == "error", "a bad path is not a bad key"
    assert _probe_status(_http(503)) == "unreachable"
    assert _probe_status(httpx.ConnectError("refused")) == "unreachable"
    assert _probe_status(httpx.ReadTimeout("slow")) == "unreachable"
    assert _probe_status(RuntimeError("boom")) == "error"

    # The status vocabulary is CLOSED. Two readers phrase these for the user —
    # SettingsWindow.qml's `addProbeMessage` switch and settings_model.modelState's docstring —
    # and neither can be checked from here, so adding a status must break this line first.
    assert PROBE_STATUSES == ("ok", "nokey", "auth", "unreachable", "empty", "error")
    for exc in (_http(401), _http(404), _http(503), httpx.ConnectError("x"), RuntimeError("x")):
        assert _probe_status(exc) in PROBE_STATUSES, exc
    # A cloud provider with no stored key must say so rather than looking like an outage.
    absent = next((p for p, c in cat.items()
                   if c.get("auth") == "key" and not credential_for(p)), None)
    if absent:
        assert probe(absent)[1] == "nokey", absent

    # The non-chat filter, against ids really returned by Groq and OpenAI on 2026-07-24. A brain
    # picker offering an STT or embedding model hands the user a turn that can only fail.
    assert schema().get("not_chat"), "the non-chat substrings must come from the schema"
    kept = _chat_only([
        "llama-3.3-70b-versatile", "whisper-large-v3-turbo", "openai/gpt-oss-safeguard-20b",
        "canopylabs/orpheus-v1-english", "meta-llama/llama-prompt-guard-2-22m",
        "text-embedding-ada-002", "tts-1", "dall-e-3", "gpt-4o", "openai/gpt-oss-120b",
    ])
    assert kept == ["gpt-4o", "llama-3.3-70b-versatile", "openai/gpt-oss-120b"], kept
    assert _chat_only(["B-model", "a-model"]) == ["a-model", "B-model"], "sorted for a stable picker"
    assert _chat_only([]) == []

    served = [p for p, c in cat.items() if c.get("adapter")]
    print(f"providers selfcheck OK: {len(cat)} cards, {len(served)} with an adapter "
          f"({', '.join(sorted(served))})")
