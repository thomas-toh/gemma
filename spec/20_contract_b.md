# Spec 20 — Contract B: brain adapters

**Last reconciled: 2026-08-02** · Build progress: [STATE.md](../STATE.md) · Rationale: docs/02 §3

*(Interface contract. Build status + the standalone B1 API smoke test
(`scripts/b1_smoke.py`) live in STATE, Tracks G & B.)*

One async interface; every brain is a plug-in behind it. Internal message shape is the
chat-completions convention (system/user/assistant/tool messages, JSON-schema tools).

```python
class BrainAdapter(Protocol):
    async def converse(
        self,
        session: Session,          # id, history, local_only, per-call max_tokens/temperature
        utterance: str,            # transcribed user speech
        tools: list[ToolSpec],     # Contract T registry, filtered by tier config
    ) -> AsyncIterator[BrainEvent]: ...

# BrainEvent = TextDelta | ToolCall | ToolResult | Done(usage) | Error(kind, detail)

# The second verb — a free function over any adapter's converse, not a per-adapter method:
async def transform(
    brain: BrainAdapter,
    text: str,
    instructions: str,            # the task: "clean this transcript" / a spoken rewrite instruction
) -> tuple[str, Error | None]:    # the rewritten text, or ("", Error)
    ...
```

**`transform` — "transform, never answer" (D12).** The dictation and rewrite verb: rewrite `text`
per `instructions` and return it whole, never respond to it. It is deliberately *not* a method
each adapter reimplements — a transform is a constrained conversation (one guardrail system
prompt, no tools, no history, the whole reply buffered), so it drives `converse` and inherits
every adapter's streaming, error mapping, one-loop and deterministic-close guarantees. One
implementation therefore serves Groq, Claude and a local model alike. The caller chooses the
brain, and thereby the privacy posture: dictation cleanup uses Groq (cloud, D15/S-06),
`--clean-prompts` a local model — `transform` privileges neither and does not force `local_only`.
Errors come back as the same shared `Error` taxonomy `converse` uses, so a caller narrates one set.
Three per-call generation overrides ride on `Session` (`max_tokens`, `temperature`, `thinking`)
because a transform of a long dictation must exceed the short spoken cap and cleanup wants
determinism; every adapter honours them identically.

**A transform NEVER reasons (added 2026-08-01).** `transform` sets `Session.thinking = False`, an
invariant of the verb in the same way `temperature = 0` is — not a user setting. "Rewrite this,
never answer it" leaves nothing to deliberate about, and reasoning is pure cost in a path that
sits between speaking and pasting: measured on qwen3:8b, one dictation-length cleanup took 6.5 s
thinking against 0.44 s without, and on harder inputs it ran to 71k tokens and never answered at
all. `thinking` is stated as a provider-agnostic **intent**, never as a wire parameter — each
provider spells "don't think" differently, so translating it is the adapter's job, exactly like
error mapping and tool translation. An adapter with no way to express it sends nothing and the
model may think: a degradation, not an error. On the OpenAI wire "off" is a *value* of the effort
scale (`reasoning_effort: "none"`), so it is gated on the provider card declaring that value —
sending an effort a provider does not accept is rejected server-side and costs the whole turn.

Rules: adapters MUST stream (no buffer-then-return); MUST surface tool calls to the
orchestrator rather than executing anything themselves (B3 excepted, see below); MUST
map provider errors to the shared `Error` kinds (auth · rate_limit · context ·
unavailable · malformed_tool_call · no_model · unknown).

**`no_model` (added 2026-08-02).** The model named for this turn cannot be used: either none was
chosen, or the one chosen is not there — commonly a model deleted from a local runner after being
configured. One kind for both, because the user's remedy is identical: open settings and pick a
model that works. It exists because the alternative was narrating a **precise, actionable cause as
a shrug** — Ollama answers `404 · model 'x' not found`, and flattening that to `unknown` produced
"Something went wrong on my end", or in dictation a silent fall back to pasting the raw
transcript. Same can't-rendered-as-didn't failure D36 fixed for tool calls. Mapped by exception
type and status only, never message prose (B-02); on the OpenAI wire the 404 branch MUST precede
the generic `APIStatusError` branch, since `NotFoundError` subclasses it. The spoken line points
at the model *setting* rather than asserting a deletion, because a 404 can also mean a mistyped
endpoint path.

**Tool translation is the adapter's job (added 2026-07-24, D30).** A `ToolSpec` is an entry of
`spec/schemas/tools.json` verbatim — it spells the JSON-schema key `parameters` and carries a
`tier`. No provider takes that shape: Anthropic requires `input_schema` and rejects unknown
fields; the OpenAI wire wants `{type: "function", function: {name, description, parameters}}`.
Each adapter therefore translates the registry into its own wire format and **strips `tier`**,
which is Gemma's safety business and never leaves the machine. This sits in the adapter for the
same reason error mapping does: it *is* the provider's format. Passing the registry entry
through untranslated is a live fault, not a style choice — B1 did exactly that until D30, and
it went unnoticed only because M0 passes an empty list.

**The tool loop (added 2026-07-27, D31).** `converse` handles ONE model round — it streams text,
surfaces any tool calls as `ToolCall` events, and ends with `Done`; it never executes a tool (B3
excepted). The multi-round loop is the **orchestrator's** (`_collect`): it executes each `ToolCall`
through Contract T, has the adapter serialise the round into `session.history`, and drives the next
round, repeating until the brain answers with no further call. Two pieces make that work across
both wires:

- **`record_tool_round(session, text, calls, results)`** — a per-adapter method that appends the
  completed round to `session.history` in the adapter's OWN wire shape (Anthropic: one assistant
  message interleaving text with `tool_use` blocks, then one user message of `tool_result` blocks;
  OpenAI: one assistant message carrying `tool_calls`, then one `tool` message per result). It sits
  in the adapter for the same reason tool translation does — it *is* the wire format — and it only
  serialises; the orchestrator still owns execution (spec/50 rule 1).
- **The empty-utterance continue signal.** After the first round the loop re-enters `converse` with
  an empty `utterance`, meaning "the new input is already in history"; the adapter then adds no
  fresh user turn (a second user message in a row would break Anthropic's strict alternation).

The single retry that `malformed_tool_call` earns (B2, when a small or local model emits
unparseable arguments) belongs to this loop — one re-run of the round, then the turn gives up. A
round cap bounds a model that never stops calling tools, and history is committed to
`session.history` only once a round finally answers, so an aborted or failed turn leaves no
dangling user message. What the executor does with a call (the allowlist, tiers, the audit log) is
Contract T, spec/30.

**Where a provider's reachability is declared.** Base URL, credential-store account name, env-var
fallback and which wire serves a provider all live in `spec/schemas/settings.json` → `providers`
(hard rule 3), read by `bridge/brains/providers.py`. Adding a provider is a JSON edit; no adapter
hardcodes a host, a key name or a model id.

**No adapter carries a default model (added 2026-07-25).** An adapter that silently defaulted to
one model would carry a preference, and — since only B1 did — an asymmetric one. Both adapters now
require the caller to name a model; a turn with none yields `Error("unknown", "no model chosen…")`
rather than a guess. The model is chosen by the settings picker and, in time, the router; the
daemon's pre-router operational default (necessarily a Claude model while it constructs B1
directly) lives in the orchestrator, not in an adapter.

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
| **B2** | **Any OpenAI-compatible endpoint, cloud or local** — Groq · OpenAI · xAI · DeepSeek · Mistral · OpenRouter · Google (compat layer) in the cloud; Ollama · LM Studio · llama.cpp on the RTX 5080. One adapter, parameterised by base URL + credential from the catalogue. Needs a model-quirks layer: tolerant tool-call parsing (emits `malformed_tool_call`) + one retry on malformed, the retry belonging to the tool loop. Local default model = M2 bake-off winner (Gemma-family vs Qwen-family, docs/02 §9 Q5). | BUILT (D30) |
| **B3** | Agent CLI: `claude -p --output-format stream-json --resume <id>` | Contained experiment (M4). Different trust model: the CLI acts directly with its own tools; gate via `--allowedTools`, not Contract T. Pricing-model risk flagged in docs/02 §3. | sketch only |

## Routing

**v1 BUILT (D33)** — `bridge/brains/router.py`. A **role** resolves to the configured provider +
model, read fresh from settings each turn:

  `assistant` → `primary` · `cleanup_dictation` → `cleanup_dictation` · `cleanup_prompts` → `cleanup_prompts`

each naming a provider whose card config lives in `models[<provider>]`. `resolve(role)` returns the
config or `None` (unconfigured — no provider named, never added, card off, or no model); `signature(role)`
is the cache key the orchestrator rebuilds its adapter on (so the client is kept across turns, spec/20
adapter lifetime, but a picker change lands next turn); `build_for_role(role)` builds the adapter via
`providers.build_brain`. This is what makes the model picker **bite** — until D33 `primary` was
written-but-unread and the orchestrator hardcoded Claude. The orchestrator applies the daemon default
(`DAEMON_MODEL` on B1) / the Groq cleanup default when a role resolves to `None`, so an unconfigured
profile still answers. An **injected** brain (replay/selfcheck) bypasses the router entirely.

**Not in v1 (Layer 2, later):** several instances per provider + the roles/routes redesign
(spec/70); per-task-type routing ("short → cheap") and its classifier; `local_only` policy mapping
(a `local_only` session forcing a local B2). v1 is role → instance; the orchestrator seam
(`build_for_role`) does not change when Layer 2 lands — only the data the router reads. B1's
effort/extended-thinking are still unwired (M0.5), so `effort` reaches only the B2 wire for now;
`temperature` likewise reaches only B2 (coerced to a float in `resolve`, since only the local
providers declare the capability, and carried on to `CompatBrain` at construction).

Note `local_only` is enforced per adapter, not per row: B2 refuses a `local_only` session when
pointed at a cloud provider and serves it when pointed at a local runner, since the same class is
both. B1 always refuses.
