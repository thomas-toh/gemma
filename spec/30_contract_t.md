# Spec 30 — Contract T: tools & safety tiers

**Last reconciled: 2026-07-31** · Build progress: [STATE.md](../STATE.md) · Registry (executable): [schemas/tools.json](schemas/tools.json)

*(The executor and its Tier-1 backends now exist — `bridge/tools.py` (D31); see STATE, Track T
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
4. Growth is **tracked, not gated**. Adding a tool waits on nothing, but no tool is silently
   assumed good: every one carries a record of when it was built and whether it has since been
   invoked repeatedly, in real use, without misfiring. That ledger is in STATE, Track T (build
   progress is STATE's alone — CLAUDE.md hard rule 1); `logs/audit.jsonl` is its evidence, since
   rule 2 already records the outcome of every call. The reason is unchanged from docs/01 §6.2:
   tool-call reliability compounds per step, so an unproven tool must be *visible* as unproven —
   and a tool that misfires in use is a candidate for removal, which is the real check on a
   sprawling tool list.
5. B3 (agent CLI) does not use this registry; its containment is `--allowedTools`
   (spec/20).

## The executor (`bridge/tools.py`)

One entry point, `execute(call) -> (content, outcome)`, dispatching by name to a backend. Design
constants:

- **The brain is offered only what it can actually call** (rule 3). `tool_specs()` filters the
  registry to tools that have a backend on this platform AND sit within the enabled tier
  (`MAX_TIER`, today 1) AND whose **connector the user has switched on** (D38), so a tool with no
  implementation — above the ceiling, or unwanted — never reaches the model. `execute()` re-checks
  the same allowlist: the filter is convenience, the allowlist is the defence (spec/50 rule 1). An
  unknown, out-of-tier or disconnected call is refused, not run.
- **The tier ceiling is one knob.** `MAX_TIER` holds at 1 until Tier 2's announce earcon and Tier
  3's propose-then-tap confirmation (D26) are built; raising it is how a tier turns on.
- **Tier and connector are orthogonal gates (D38).** A **tier** answers "may Gemma do this without
  asking?" — it is about danger, and it is the designer's judgement. A **connector** answers "does
  this user want Gemma reaching that at all?" — it is about consent, and it is the user's. A
  Tier-1 tool is safe to run unattended, which is not the same as wanted: someone may want
  dictation and answers and nothing that touches their files. Every tool therefore declares a
  `connector` in `schemas/tools.json` and passes BOTH gates or is not offered. Anything reading
  personal data (Files, Email, Clipboard) is **off by default**; the user turns it on knowing which
  tools that enables and what each reaches (spec/70 § Connectors). A disabled connector is also
  named to the brain in prose, so it answers "file search is off" rather than improvising — a
  capability failure must not narrate as a negative result (the D36 lesson).
- **Every call is audited before it returns** (rule 2), whatever the outcome, as one JSONL line
  `{ts, session, transcript_snippet, tool, args, outcome, duration_ms}` in `logs/audit.jsonl` —
  the same `logs/` folder that purges everything in one delete (spec/50 rule 3). A failed audit
  WRITE is logged loudly and the call proceeds (degrade, don't crash); hardening to
  refuse-if-unloggable is noted in code.
- **A tool fault is data, not a crash.** A backend that raises returns an `error` string the brain
  reads and narrates; the turn survives.
- **Retrieval tools compose the query, never read the corpus.** The model turns the utterance into
  query parameters, the STORE does the filtering, and at most eight headers come back — never the
  content itself, and nothing is opened. `find_document` queries the Windows Search index
  (`SystemIndex`) for `name · date · path`; `search_email` restricts the desktop Outlook inbox over
  MAPI to `sender · date · subject`. Deciding what to do with a hit is a later turn.

  Both backends drive a COM provider through PowerShell, a sanctioned Windows backend (rule 3) and
  **not** the raw shell rule 1 forbids: the model supplies search *terms*, never a command; the
  terms are stripped to bare words before they can enter a query string (a DASL restriction is an
  injection surface exactly as a SQL `WHERE` is); and the finished query reaches the subprocess in
  an environment variable, so nothing the model wrote is ever parsed as PowerShell.

  Both corpora are **local** — the Windows index and the desktop mail store, no Graph and no cloud
  API — so a query and its results stay on the machine (spec/50). What the model then *says* about
  a result travels wherever that turn is routed, which is the `local_only` question, not this one.
  A retrieval tool that cannot reach its store (no index, no mail profile) answers "not available"
  in prose rather than raising, so a missing corpus degrades the turn instead of ending it.

The multi-round loop that carries a tool result back to the brain is Contract B's, not Contract
T's — see spec/20 "The tool loop".

## Starter set (defined in schemas/tools.json)

`system_status` (Tier 1) · `read_clipboard` (Tier 1) · `find_document` (Tier 1, Windows-only) ·
`search_email` (Tier 1, Outlook on Windows) · `open_app` (Tier 2) · `focus_window` (Tier 2) ·
`media_control` (Tier 2) · `set_timer` (Tier 2)

Each carries a `connector` naming the consent card it sits under, and a `label` — the tool said
in a sentence a person would use (D38). The label serves both halves of consent: the card lists
it before the fact, the island shows it while the tool runs. It lives in the registry because
`description` is written for the model and a second wording kept in the window would drift from
it. The ids, labels and defaults are in `schemas/tools.json` and `schemas/settings.json`, never
restated here (hard rule 3).

## Connectors (D38)

The consent gate above, as a surface. One card per connector, each stating **what it reaches** and
**which tools it enables**, so switching one on is consent to something specific. `MAX_TIER` still
governs danger independently — turning a connector on cannot raise a tier.

**Consent is stated twice — before and during.** The card is the "before". The "during" is a
Contract P `tool` message (spec/40, `schemas/status.json`), published by the orchestrator as each
call starts and again as it returns, around **every** outcome including a refusal — so the island
can name what is being reached while it is being reached, and the indicator can never outlive the
work. Without it a turn that searched your mail looks identical to one that did not.

**MCP is deliberately not here yet.** An MCP server supplies tools at runtime with no declared
tier, so it cannot pass the gate rule 1 depends on (no raw shell below Tier 3 — and an MCP server
may expose precisely that). Admitting one needs its own decision: where a runtime tool's tier comes
from, and who vouches for it. Until then the pane holds a dimmed slot and nothing else.
