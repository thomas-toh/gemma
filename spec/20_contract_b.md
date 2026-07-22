# Spec 20 — Contract B: brain adapters

**Last reconciled: 2026-07-22** · Build progress: [STATE.md](../STATE.md) · Rationale: docs/02 §3

*(Interface contract. Build status + the standalone B1 API smoke test
(`scripts/b1_smoke.py`) live in STATE, Tracks G & B.)*

One async interface; every brain is a plug-in behind it. Internal message shape is the
chat-completions convention (system/user/assistant/tool messages, JSON-schema tools).

```python
class BrainAdapter(Protocol):
    async def converse(
        self,
        session: Session,          # id, history policy, local_only flag, prefs
        utterance: str,            # transcribed user speech
        tools: list[ToolSpec],     # Contract T registry, filtered by tier config
    ) -> AsyncIterator[BrainEvent]: ...

# BrainEvent = TextDelta | ToolCall | ToolResult | Done(usage) | Error(kind, detail)
```

Rules: adapters MUST stream (no buffer-then-return); MUST surface tool calls to the
orchestrator rather than executing anything themselves (B3 excepted, see below); MUST
map provider errors to the shared `Error` kinds (auth · rate_limit · context ·
unavailable · malformed_tool_call · unknown).

**Adapter lifetime (added 2026-07-22).** Two guarantees the *orchestrator* owes every
adapter, provider-agnostic by design — they exist so that no adapter has to rebuild
per-turn what it could hold for a session:

- **One event loop per adapter.** Every `converse()` for the life of an adapter instance is
  awaited on the same event loop, so an adapter MAY create a client, connection pool or
  session once and reuse it. This was not true until 2026-07-22: each turn ran in its own
  `asyncio.run()`, and since an HTTP connection pool belongs to the loop that made it, *no*
  adapter could reuse a connection even by trying. Cost of that, measured on the PC: a fresh
  TCP+TLS handshake every turn, on top of ~190 ms of CPU re-parsing the CA bundle — both on
  the end-of-speech → first-word path. `bridge/brains/base.py::ssl_context()` memoises the
  trust store for any HTTP-based adapter; it is a helper, not an obligation (a local B2 over
  plain HTTP wants none of it).
- **Deterministic close.** The orchestrator calls `aclose()` on the generator when a turn is
  aborted, so `finally` / `async with` blocks release the provider stream at the abort rather
  than whenever the GC notices. An aborted turn must actually *drop* the request, not merely
  stop reading it.

Neither is a change to the `converse()` signature, so no adapter needs updating; B1 takes
advantage of both.

## Adapters

| Id | Backend | Notes | Maturity |
|----|---------|-------|----------|
| **B1** | Anthropic Messages API | First build (M0). Streaming + native tool use; bridge executes all tools through Contract T. Utterance text leaves the machine — blocked when `session.local_only`. | DESIGNED |
| **B2** | Local via Ollama / llama-server (OpenAI-compatible endpoint) on the RTX 5080 | Second build (M2). Needs a model-quirks layer: tolerant tool-call parsing + one retry on malformed. Default model = M2 bake-off winner (Gemma-family vs Qwen-family, see docs/02 §9 Q5). | DESIGNED |
| **B3** | Agent CLI: `claude -p --output-format stream-json --resume <id>` | Contained experiment (M4). Different trust model: the CLI acts directly with its own tools; gate via `--allowedTools`, not Contract T. Pricing-model risk flagged in docs/02 §3. | sketch only |

## Routing

Not built until B1 and B2 both pass M1's script. Then: config-file policy mapping
(`local_only` → B2 forced; default → configured primary). No automatic
content-sensitivity classification — routing is explicit, by session flag or utterance
prefix ("private mode"), never inferred.
