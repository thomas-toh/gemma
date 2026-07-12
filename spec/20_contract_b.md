# Spec 20 — Contract B: brain adapters

**Last reconciled: 2026-07-12** · Build progress: [STATE.md](../STATE.md) · Rationale: docs/02 §3

*(planned — no adapter code yet; B1 is build step 5. The B1 API path itself is
smoke-tested: `scripts/b1_smoke.py`. See STATE, Tracks G & B.)*

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
