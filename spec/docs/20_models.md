# Chapter 2 — The model layer

**Last reconciled: 2026-08-04 02:55** · Build progress: [STATE.md](../plans/STATE.md) (Tracks G · B) · Provider catalogue (executable): [shared/schemas/settings.json](../../shared/schemas/settings.json)

`backend/llm/` is the only part of Gemma that talks to a language model. One async interface;
every provider plugs in behind it. The internal message shape is the chat-completions convention —
system / user / assistant / tool messages, JSON-schema tools.

| File | Holds |
|------|-------|
| `backend/llm/base.py` | the interface, the event types, `Session`, the two persona strings, `profile_note()`, `transform` |
| `backend/llm/claude.py` | `ClaudeModel` — the Anthropic Messages wire |
| `backend/llm/compat.py` | `CompatModel` — the OpenAI-compatible wire, one class for ten providers |
| `backend/llm/providers.py` | the provider catalogue: reachability, credentials, model lists, adapter construction |
| `backend/router.py` | which provider and model serve a given role |

## The interface

```python
class ModelAdapter(Protocol):
    def converse(
        self,
        session: Session,        # id, history, system, local_only, per-call generation overrides
        utterance: str,          # the transcribed prompt; "" continues a tool round
        tools: list[ToolSpec],   # tools.json entries, filtered by tier and connector (spec/30)
    ) -> AsyncIterator[ModelEvent]: ...
```

`ModelEvent` is one of `TextDelta(text)` · `ToolCall(id, name, input)` · `ToolResult(id, content)` ·
`Done(usage)` · `Error(kind, detail)`. `ToolResult` is emitted only by an adapter that runs its own
tools; neither built adapter does.

Every adapter:

- streams — no buffer-then-return;
- surfaces tool calls to the orchestrator rather than executing anything itself;
- maps every provider failure to a shared `Error` kind;
- carries no default model. A turn with no model named yields `Error("no_model", …)`, never a guess.
  The model is chosen by the settings picker and the router; the daemon's fallback lives in the
  orchestrator;
- translates the tool registry into its provider's own wire format and strips `tier`, which is
  Gemma's safety business and never leaves the machine.

`Session` carries the per-conversation state:

| Field | What it is |
|-------|-----------|
| `id` | the session id, written into every audit record |
| `system` | the system prompt; `None` uses `DEFAULT_SYSTEM`, the impassive system voice (spec/40) |
| `history` | prior messages, in the adapter's own wire shape |
| `local_only` | the utterance must not leave the machine (spec/50 rule 6) |
| `max_tokens` | per-call output cap; `None` uses `MAX_TOKENS` (1024) |
| `temperature` | per-call sampling; `None` uses the adapter's own |
| `thinking` | `False` = this call must not reason; `None` = leave the provider's default alone |

On an ask turn the orchestrator sets `system` per turn rather than leaving it `None`:
`DEFAULT_SYSTEM`, then `profile_note()` (who it is speaking to — spec/70's Profile rows), then
`disabled_note()` (the connectors the user has switched off — spec/30). Both trailing clauses are
"" when unset, so an untouched profile with every connector on is the bare voice.

`thinking` is stated as a provider-agnostic intent, never as a wire parameter — each provider spells
"don't think" differently, so translating it is the adapter's job, like error mapping and tool
translation. An adapter with no way to express it sends nothing and the model may think: a
degradation, not an error.

## `transform` — the second verb

```python
async def transform(model, text, instructions, *, temperature=0.0, max_tokens=None)
    -> tuple[str, Error | None]
```

Rewrite `text` per `instructions` and return it whole; never respond to it. A free function over
`converse`, not a method each adapter reimplements: a transform is a constrained conversation — the
`TRANSFORM_SYSTEM` guardrail prompt, no tools, no history, the whole reply buffered — so one
implementation serves every adapter and inherits its streaming, error mapping, loop and close
guarantees.

Three things the verb fixes, not the caller:

- `temperature = 0`, so cleanup is deterministic;
- `thinking = False`, on every provider;
- `max_tokens = min(8192, max(1024, len(text) // 2))` unless the caller names one, so a long
  dictation exceeds the short spoken cap without inviting a runaway.

Errors come back as the same taxonomy `converse` uses, so a caller narrates one set. `transform`
does not force `local_only`: the caller chose the provider, and that choice is the privacy posture.
Its callers today are dictation cleanup (spec/60) and, once wired, prompt cleanup.

## Error taxonomy

Adapters map provider failures onto one closed set, by exception type and status code, never by
matching the message prose. `backend/orchestrator.py` turns each kind into one spoken sentence
(`SPOKEN_ERRORS`).

| Kind | Means |
|------|-------|
| `auth` | no API key, or the provider rejected it |
| `rate_limit` | the provider is throttling |
| `context` | the conversation is too long for the model. No adapter emits it — both wires collapse context overflow and every other bad request into one 400, and a heuristic over the message text mis-narrates. Detecting it properly means counting tokens against the model's window before the call |
| `unavailable` | the connection failed, the provider answered 5xx, or the session is `local_only` and this adapter is cloud |
| `no_model` | none was chosen, or the one chosen is not there — commonly a model deleted from a local runner after being configured. One kind for both: the remedy is the same, open settings and pick a model that works |
| `malformed_tool_call` | the model's tool arguments did not parse, or the provider rejected its own model's tool call |
| `unknown` | everything else, including a plain 400 |

Two constraints on the OpenAI-wire ladder. The 404 branch must precede the generic
`APIStatusError` branch, since `NotFoundError` subclasses it. And a tool call the provider rejects
mid-stream arrives as a bare `APIError` with no status code — the HTTP request logged 200 — so both
that and a 400 map to `malformed_tool_call` when the round offered tools.

The spoken line for `no_model` points at the model setting rather than asserting a deletion, because
a 404 can also mean a mistyped endpoint path.

## Wire shape and knob names

A request has two halves, and only one of them belongs to the adapter.

**The shape is the adapter's.** On Anthropic the system prompt is a separate parameter and tool
results thread back as content blocks inside a user message; on the OpenAI wire the system prompt is
the first message and tool results are `tool` messages. That is the wire, and it is why there are two
adapters and not one.

**The knob names are the catalogue's.** An adapter names each knob in Gemma's own vocabulary —
`max_output_tokens`, `effort`, `temperature` — and `shared/schemas/settings.json` → `wire_names` says
how that name is spelled on the way out. Defaults are keyed by wire; a provider card overrides only
what it spells differently (OpenAI: `max_completion_tokens`, and `temperature: null`).

Three outcomes when a knob goes out, and the last two stay distinct:

- **a name** — sent under it;
- **`null` in the card** — this provider has no such knob; dropped deliberately;
- **absent from the catalogue** — a gap in the schema. Dropped and logged, never guessed. An
  invented parameter is rejected server-side and costs the whole turn; omitting one degrades instead.

`capabilities` answers a different question and the two are not interchangeable: `capabilities` says
what the user may set (it drives which providers show a control), `wire_names` says what the provider
has. Gating the wire on `capabilities` would take deterministic cleanup away from Groq, which relies
on `temperature: 0` and declares no capability at all.

A card may also declare `tool_round_effort` — an effort value the provider demands on any round that
offers tools. OpenAI's reasoning models reject function tools combined with reasoning, and omitting
the parameter is not the same as setting it to `none`: absent, the model reasons at its own default
and the request fails identically. This is deliberately independent of `capabilities.effort`, which
is the user's menu.

`compat.py`'s selfcheck asserts offline that every knob it can emit is spelled for its wire, so an
omission fails a check rather than silently dropping a parameter at runtime.

## The tool loop

`converse` handles one model round: it streams text, surfaces any tool calls as `ToolCall` events,
and ends with `Done`. It never executes a tool. The multi-round loop is the orchestrator's
(`_collect`, `backend/orchestrator.py`).

```
utterance ─▶ converse ──┬── no tool call ──▶ answer streams to the island,
                        │                    history commits, turn ends
                        │
                        └── ToolCall(s) ───▶ executor (spec/30) ──▶ record_tool_round()
                                                                         │
                                          converse, utterance = "" ◀─────┘
```

Two pieces make that work across both wires:

**`record_tool_round(session, text, calls, results)`** — a per-adapter method that appends the
completed round to `session.history` in the adapter's own wire shape. Anthropic: one assistant
message interleaving text with `tool_use` blocks, then one user message of `tool_result` blocks.
OpenAI: one assistant message carrying `tool_calls`, then one `tool` message per result. It only
serialises; the orchestrator still owns execution (spec/50 rule 1).

**The empty-utterance continue signal** — after the first round the loop re-enters `converse` with an
empty `utterance`, meaning the new input is already in history. The adapter then adds no fresh user
turn; two user messages in a row would break Anthropic's strict alternation.

Four bounds on the loop:

- one retry per round on `malformed_tool_call`, then the turn gives up. Each fresh round gets its
  own retry budget;
- `MAX_TOOL_ROUNDS` (5) caps a model that never stops calling tools;
- history commits to `session.history` only when a round finally answers, so a failed or aborted turn
  leaves no dangling user message;
- only the final answering round reaches the island. The preamble rounds — the model narrating that
  it is about to call a tool — stay in history and the console.

## Adapter lifetime

Two guarantees the orchestrator owes every adapter, so that no adapter has to rebuild per turn what
it could hold for a session.

**One event loop per adapter.** Every `converse()` for the life of an adapter instance is awaited on
the same event loop, so an adapter may create a client, connection pool or session once and reuse it.
Both adapters do, in `_client_once()`. `base.ssl_context()` memoises this machine's TLS trust store
for any HTTP-based adapter; it is a helper, not an obligation — a local runner over plain HTTP wants
none of it.

**Deterministic close.** The orchestrator calls `aclose()` on the generator when a turn is aborted,
so `finally` and `async with` blocks release the provider stream at the abort. An aborted turn drops
the request rather than merely stopping reading it.

Both adapters build their client with the SDK's own `DefaultAsyncHttpxClient`, not a bare
`httpx.AsyncClient`: an SDK uses a supplied client verbatim, and a bare one swaps the SDK's 600 s read
timeout for httpx's 5 s default, which would cut off the slow-first-token turns. Against a local
runner `CompatModel` additionally sets `max_retries = 0` and a 2 s connect timeout — a refused
loopback socket is not a transient fault — while leaving the read timeout long, since a local model
may legitimately think for a while once it has answered.

## The adapters

| Id | Class | Wire | Serves |
|----|-------|------|--------|
| B1 | `ClaudeModel` (`backend/llm/claude.py`) | Anthropic Messages | Anthropic |
| B2 | `CompatModel` (`backend/llm/compat.py`) | OpenAI `/v1/chat/completions` | Groq · OpenAI · xAI · DeepSeek · Mistral · OpenRouter · Google's compat layer in the cloud; Ollama · LM Studio · llama.cpp locally |
| B3 | — | `claude -p --output-format stream-json --resume <id>` | planned. A different trust model: the CLI acts with its own tools, so containment is `--allowedTools`, not the tool registry (spec/30 rule 5) |

B1 · B2 · B3 are the ids STATE and the latency targets use. One class serves every OpenAI-wire
provider because what differs between them is a base URL and a credential, both read from the
catalogue.

`local_only` is enforced per adapter, not per provider row. `ClaudeModel` always refuses.
`CompatModel` refuses a `local_only` session when its card says `where: cloud` and serves it when the
card says local — the same class is both.

## The provider catalogue

`shared/schemas/settings.json` → `providers`, read by `backend/llm/providers.py`. Adding a provider is
a JSON edit; no adapter hardcodes a host, a key name or a model id.

| Card field | What it declares |
|------------|------------------|
| `wire` | `anthropic` or `openai` — which adapter serves it |
| `where` | `cloud` or `local`, which is what `local_only` is tested against |
| `auth` | `key` (credential store) or `endpoint` (a local host:port) |
| `api` / `endpoint` | the API base URL, or the user-editable host:port |
| `credential` · `env` | the credential-store account name and its env-var fallback |
| `capabilities` | which controls the settings window offers: the effort scale, temperature, keep-alive |
| `wire_names` · `tool_round_effort` | the knob overrides above |
| `serve` | the argv to start this provider's server headless. Only Ollama declares one |
| `adapter` | whether the settings window offers this provider at all |

What the module does with it:

- **`credential_for(pid)`** — the OS credential store (service `gemma`, spec/50 rule 10) first, then
  the card's env var. Local runners authenticate by endpoint and have no key; `CompatModel` sends a
  placeholder, because the OpenAI client requires the header to exist.
- **`base_url(pid, endpoint)`** — a cloud card's `api` verbatim; a local runner's `host:port` with
  `/v1` appended, which is the compat convention all three share. A cleared endpoint falls back to
  the catalogue default. `localhost` is rewritten to `127.0.0.1` wherever it arrives, including in a
  stored setting: it resolves to IPv6 `::1` first and every local runner binds IPv4, so the failed
  attempt costs about 2 s per connection. An explicit `::1` is left alone.
- **`probe(pid, …) -> (ids, status)`** — asks a provider what models it has, and never raises. The
  status is one of `ok · nokey · auth · unreachable · empty · error`, which is what lets the settings
  window tell a wrong key from a dead network. Ids that cannot serve a turn — speech, embeddings,
  image, safety classifiers — are dropped using the schema's `not_chat` substrings.
- **`ensure_local_server` / `stop_local_servers`** — start a local runner's server headless when a
  role resolves to it and nothing is listening. Only a server this process started is ever stopped;
  one that was already running belongs to someone else. `keep_alive`, how long a model stays in VRAM,
  rides in the environment at spawn because Ollama ignores it on the `/v1` wire, so it governs only a
  server Gemma started.
- **`build_model(provider, model, endpoint, effort, temperature)`** — constructs the adapter for a
  provider's wire. Construction, not routing: it builds the model you name.

## Routing

`backend/router.py`. A role resolves to a provider and model, read fresh from settings on every call,
so a change in the picker takes effect on the next turn with no restart.

| Role | Settings key | Serves |
|------|--------------|--------|
| `assistant` | `primary` | the answer model |
| `cleanup_dictation` | `cleanup_dictation` | the dictation transform (spec/60) |
| `cleanup_prompts` | `cleanup_prompts` | prompt cleanup — planned; the router resolves it, nothing reads it yet |

Each key names a provider whose per-card config lives in `models[<provider>]`
(`{on, model, effort, thinking, endpoint, temperature, keep_alive}`). A role may also name its own
model through the schema's `modelKey`, which beats the card's — so one provider and one key can serve
the assistant a large model and cleanup a small one. Which setting holds that override is declared in
the schema, so giving another role one is a schema edit.

- **`resolve(role)`** → the config, or `None` when the role is unconfigured: no provider named, the
  named provider never added, its card switched off, or no model chosen.
- **`signature(role)`** → `(provider, model, endpoint, effort, temperature)`. The orchestrator caches
  its adapter on this and rebuilds only when it changes, so the client is kept across turns yet a
  picker change lands next turn.
- **`build_for_role(role)`** → the adapter, via `providers.build_model`.

On `None` the orchestrator applies its own default, so an unconfigured profile still answers:
`DAEMON_MODEL` (env `GEMMA_MODEL`, a Claude model) for the assistant, and `GEMMA_CLEANUP_PROVIDER` /
`GEMMA_CLEANUP_MODEL` (Groq) for dictation cleanup. A model injected for replay or a selfcheck
bypasses the router entirely.

Two things the daemon does off the router at boot: start a headless server for every role that
resolves to a local runner declaring one, deduplicated by provider; and log any role pointed at a
local model the runner does not have.

Reaching only part way today: `effort` reaches the OpenAI wire alone — `ClaudeModel` ignores it, and
Anthropic declares no temperature capability. The per-card `thinking` value is resolved but is not
passed to an adapter; the only path that sets it is `transform`.

## What the router must achieve (binding)

`planned`. The section above describes the router as built: a lookup from role to model, which never
sees the utterance. This section states what the router is **for**, and it is binding on everything
built under that name.

**The router is the thing that intercepts the request and decides where it goes.** The model is one
destination among several, not the entry point. Today the model is the front door and every decision
runs through it — including the decision about whether a tool is needed at all, which costs a full
round before any work happens.

The judgement the router makes is between **a tool call and a genuine prompt**. A tool call is a
request to do something the harness already implements. A genuine prompt is everything else — a
question, a conversation, an open-ended instruction. This is intent identification, and it is
possible deterministically because **the tool registry is ours**: the router matches against a
closed set of capabilities this machine declares, not against an open world.

Four destinations:

| The request is | Goes to | Costs |
|----------------|---------|-------|
| a tool call the harness implements, whose result speaks for itself | the tool, and the answer ends there | no model |
| a tool call whose result needs prose to be useful | the tool, then the router sends the result to a **composer** | one model round, on the result rather than on the request |
| a genuine prompt | the model | a full turn, as today |
| anything the router is not certain about | the model | a full turn, as today |

```
utterance ─▶ ROUTER ──┬── tool ──────────────▶ answer
                      │
                      ├── tool ──▶ composer ─▶ answer
                      │
                      └── model ─────────────▶ answer   (also every uncertain case)
```

Three consequences, each deliberate:

- **A tool turn need not begin at a model.** "Open Spotify" is a five-token request that costs ~3,200
  input tokens across two rounds today, because the model is asked first whether a tool applies and
  then asked again to narrate the result.
- **Composition is a separate job from selection**, and the two may run on different models. Selecting
  a tool is cheap, bounded and testable; composing prose from a retrieval result is where a capable
  model earns its cost. A local model already picks the right tool 8 times in 9.
- **Role routing becomes a component, not the whole.** Resolving `assistant` to a provider still
  happens; it happens *after* the router has decided a model is wanted at all.

**The router's dials are Gemma's, not the user's.** The model it runs, its temperature and its
effort are fixed in code and appear in no settings pane. The user chooses the model that *answers*
them; the router is Gemma's own machinery, and a routing decision taken at the user's sampling
temperature would vary for no reason they asked for. `transform` already works this way, pinning
temperature 0 and never reasoning as invariants of the verb.

Two consequences. A fixed model that is absent from the machine cannot be an error — the router
falls through to the assistant, which is what it already does when uncertain, so a missing router
model costs speed and nothing else. And a router model is weights on disk, so it inherits the
delivery question the speech-to-text model has: a size, a download, a cache location, and a
part-downloaded failure mode.

**Binding constraint: precision over recall.** The router never fires on a tool unless it is certain.
A matcher that fires on "I was going to open Spotify but didn't" has acted against the speaker's
intent, which is a worse failure than being slow. Every uncertain case falls through to the model,
and the fall-through must be indistinguishable from today's behaviour. A skill and a tool share one
deterministic backend and are two doors to it, never two implementations (spec/30).

Skills, as scoped in the build plan, are one outcome of this router — the case where a deterministic
answer needs no model at all. The router is the larger thing: the dispatcher that makes skills, tool
turns and conversations three results of one decision.

Also planned, and separate from the above: several instances per provider with the roles-and-routes
redesign (spec/70), and mapping `local_only` to a policy that forces a local provider. The
orchestrator's seam (`build_for_role`) does not change when those land — only the data the router
reads.
