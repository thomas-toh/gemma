# Spec 30 — Contract T: tools & safety tiers

**Last reconciled: 2026-07-27** · Build progress: [STATE.md](../STATE.md) · Registry (executable): [schemas/tools.json](schemas/tools.json)

*(The executor and the two Tier-1 backends now exist — `bridge/tools.py` (D31); see STATE, Track T
for status. Tier 2's earcon announce and Tier 3's propose-then-tap gate are `planned, M1`, and the
per-OS backends beyond Windows are a D10 seam. The registry file has been loaded by
`bridge/config.py` since M0.)*

The registry file is the single source of truth for tool names, parameter schemas and
tiers. The bridge loads it at startup; brains receive it (filtered) as their tool list;
the executor refuses any call not present in it. Code never hardcodes a tool definition.

## Tiers

| Tier | Meaning | Gate | Log |
|------|---------|------|-----|
| 1 | Read-only | none | audit |
| 2 | Reversible action | earcon announce (`success`/`failure`) | audit |
| 3 | Destructive / consequential | **confirmation (D26)** — the action is rendered on the Teleprompter and a **keypress** confirms it (propose-then-tap, D20); the `failure` earcon sounds ("needs your view", D28) and, with speech on, saying "confirm" within 8 s is the equivalent gate. No confirmation → cancels. | audit |

## Rules (binding)

1. No raw shell/PowerShell tool at Tier 1–2. A Tier 3 `run_command` MAY exist later;
   ships disabled.
2. Every invocation — including refused and cancelled ones — is appended to the audit
   log: `{ts, session, transcript_snippet, tool, args, outcome, duration_ms}`.
   Append-only JSONL, local, user-purgeable.
3. The executor dispatches to **per-OS backends behind the same registry** (D10):
   Windows via UI Automation / `pywin32` / `subprocess`; macOS via `osascript`
   (AppleScript), `open -a`, and media-key events. Doc 04 decides each tool's
   implementation. A tool MAY be unavailable on a platform; the brain's tool list
   only ever contains what the running platform actually implements. Fronting
   Windows-MCP on Windows is an allowed implementation detail.
4. Growth rule: start with the six starter tools in the registry; add tools only after
   ≥ 1 week of daily use without misfires (tool-call reliability compounds — docs/01 §6.2).
5. B3 (agent CLI) does not use this registry; its containment is `--allowedTools`
   (spec/20).

## The executor (`bridge/tools.py`)

One entry point, `execute(call) -> (content, outcome)`, dispatching by name to a backend. Design
constants:

- **The brain is offered only what it can actually call** (rule 3). `tool_specs()` filters the
  registry to tools that have a backend on this platform AND sit within the enabled tier
  (`MAX_TIER`, today 1), so a tool with no implementation — or above the ceiling — never reaches
  the model. `execute()` re-checks the same allowlist: the filter is convenience, the allowlist is
  the defence (spec/50 rule 1). An unknown or out-of-tier call is refused, not run.
- **The tier ceiling is one knob.** `MAX_TIER` holds at 1 until Tier 2's announce earcon and Tier
  3's propose-then-tap confirmation (D26) are built; raising it is how a tier turns on.
- **Every call is audited before it returns** (rule 2), whatever the outcome, as one JSONL line
  `{ts, session, transcript_snippet, tool, args, outcome, duration_ms}` in `logs/audit.jsonl` —
  the same `logs/` folder that purges everything in one delete (spec/50 rule 3). A failed audit
  WRITE is logged loudly and the call proceeds (degrade, don't crash); hardening to
  refuse-if-unloggable is noted in code.
- **A tool fault is data, not a crash.** A backend that raises returns an `error` string the brain
  reads and narrates; the turn survives.

The multi-round loop that carries a tool result back to the brain is Contract B's, not Contract
T's — see spec/20 "The tool loop".

## Starter set (defined in schemas/tools.json)

`system_status` (Tier 1) · `read_clipboard` (Tier 1) · `open_app` (Tier 2) · `focus_window` (Tier 2) ·
`media_control` (Tier 2) · `set_timer` (Tier 2)
