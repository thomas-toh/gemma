# Chapter 3 — Tools and safety tiers

**Last reconciled: 2026-08-03** · Build progress: [STATE.md](../plans/STATE.md), Track T · Registry (executable): [shared/schemas/tools.json](../../shared/schemas/tools.json)

`shared/schemas/tools.json` is the single source of truth for tool names, parameter schemas, tiers
and connectors. The daemon loads it at startup; the model receives it, filtered, as its tool list;
the executor (`backend/tools.py`) refuses any call not present in it. Code never hardcodes a tool
definition.

## Tiers

| Tier | Meaning | Gate | Log |
|------|---------|------|-----|
| 1 | Read-only | none | audit |
| 2 | Reversible action | **announce** — one `success` or `failure` earcon as the call returns, refusals included | audit |
| 3 | Destructive or consequential | **confirmation** — the action renders on the teleprompter and a keypress confirms it (propose-then-tap); the `failure` earcon sounds and, with speech on, saying "confirm" within 8 s is the equivalent gate. No confirmation cancels. Planned — the gate is not built | audit |

`MAX_TIER` in `backend/tools.py` is the ceiling `execute()` will run and `tool_specs()` will offer.
It stands at 2. Raising it is how a tier turns on, and only once that tier's gate exists: a tier whose
gate is unbuilt is never offered however ready its backends are.

The Tier-2 announce is an earcon, so it follows the `pings` setting like every other earcon. It fires
on refusals and faults as well as successes — from where the user is sitting, an action that did not
happen is one event however it failed to happen — but only a real success marks the turn as having
acted, which is what earns it the short dwell (spec/40).

## Rules (binding)

1. No raw shell or PowerShell tool at Tier 1–2. A Tier-3 `run_command` may exist later; it ships
   disabled.
2. Every invocation — including refused and errored ones — is appended to the audit log:
   `{ts, session, transcript_snippet, tool, args, outcome, duration_ms}`. Append-only JSONL, local,
   user-purgeable. `logs/audit.jsonl` sits beside `gemma.log`, so deleting `logs/` purges both in one
   action (spec/50 rule 3). A failed audit *write* is logged loudly and the call proceeds.
3. The executor dispatches to per-OS backends behind the same registry: Windows via UI Automation,
   `pywin32` and `subprocess`; macOS via `osascript`, `open -a` and media-key events. A tool may be
   unavailable on a platform, and the model's tool list only ever contains what the running platform
   implements. Every backend is Windows today; off Windows each returns a sentence saying so.
4. Growth is tracked, not gated. Adding a tool waits on nothing, but every tool carries a record of
   when it was built and whether it has since been invoked repeatedly, in real use, without
   misfiring. That ledger is STATE, Track T; `logs/audit.jsonl` is its evidence, since rule 2 already
   records the outcome of every call. Tool-call reliability compounds per step, so an unproven tool
   must be visible as unproven — and one that misfires in use is a candidate for removal, which is
   the real check on a sprawling tool list.
5. The agent-CLI adapter (spec/20) does not use this registry; its containment is `--allowedTools`.

## The two gates

A tool is offered to the model, and will run, only if it passes both.

**Tier** — may Gemma do this without asking? It is about danger, and it is the designer's judgement.
It lives in the registry and is capped by `MAX_TIER`.

**Connector** — does this user want Gemma reaching that at all? It is about consent, and it is the
user's. Every tool names a `connector` in the registry, matched to a `connector_*` entry in
`shared/schemas/settings.json` that holds the label, the default and what it reaches. A new tool joins
an existing card by naming it, with no UI work.

The gates are independent: a Tier-1 tool is safe to run unattended, which is not the same as wanted.
Either gate alone withholds a tool, and turning a connector on can never raise a tier. Both fail
closed — a tool naming a connector that has no setting is treated as off, and the consent check tests
`is True`, so a hand-edited non-boolean setting reads as off rather than on.

| Connector | Reaches | Default |
|-----------|---------|---------|
| System | the time and date, the battery, the title of the front window | on |
| Files | the names and contents of files Windows has already indexed | off |
| Email | sender, date and subject in the desktop Outlook inbox | off |
| Clipboard | whatever was last copied | off |
| Apps & media | opening an app, raising a window, the media and volume keys | off |
| Web | pages and search results — planned | off |
| MCP servers | tools from a connected MCP server — planned | off |

Anything reading personal data is off by default; the user turns it on knowing which tools that
enables and what each reaches. Settings are re-read every turn, so a toggle applies to the next
utterance with no restart. The settings window renders one card per connector (spec/70).

**Consent is stated twice, before and during.** The card is the before. The during is the `tool`
status message (spec/40, `shared/schemas/status.json`), published by the orchestrator as each call
starts and again as it returns, around every outcome including a refusal — so the island can name
what is being reached while it is being reached, and the indicator can never outlive the work.

**A switched-off connector is named to the model in prose.** `disabled_note()` appends one sentence
to the system prompt listing the labels of connectors that are off, and instructs the model to say
plainly that a capability is switched off rather than imply it looked and found nothing. Without it a
hidden tool is merely absent, which the model reads as "no such capability exists" and improvises
around. Only connectors that would otherwise be usable are named — one with no implemented, in-tier
tool behind it is left unmentioned, since naming it would imply that switching it on would work.

## The executor

`backend/tools.py`. One entry point, `execute(call) -> (content, outcome)`, dispatching by name to a
backend.

- **`tool_specs()`** — the tools handed to the model this turn: those with a backend on this
  platform, within `MAX_TIER`, and whose connector is on. A tool the model cannot call is one it
  never sees.
- **`execute()` re-checks all three.** The filter is convenience; the allowlist is the defence
  (spec/50 rule 1). A tool the user switched off must be dead even if something else names it —
  history from before the toggle, a resampled round, a caller that skipped `tool_specs()`. An
  unknown, out-of-tier or disconnected call is refused, not run, and the refusal is audited like any
  other outcome.
- **A registry entry is not a tool on this machine.** The registry states the interface — this is the
  name, these are the parameters, this is the tier. Whether anything implements it here is a separate
  question, answered by `implemented()`. A registered tool with no backend is neither
  offered nor run. `set_timer` is exactly that today: registered and within the tier, with no
  backend, because a timer fires outside any turn and the status feed has no message that can
  announce it.
- **`label_of(name)` / `tier_of(name)`** — the registry's `label`, which the island shows while the
  tool runs and the connector card lists beforehand; and the tier, which tells the orchestrator
  whether the call needs announcing.
- **A tool fault is data, not a crash.** A backend that raises returns an `error` string the model
  reads and narrates; the turn survives.

The multi-round loop that carries a tool result back to the model belongs to the model layer — see
spec/20, "The tool loop".

## What a tool may be given

**Retrieval tools compose the query, never read the corpus.** The model turns the utterance into
query parameters, the store does the filtering, and at most eight headers come back — never the
content itself, and nothing is opened. `find_document` queries the Windows Search index for
`name · date · path`; `search_email` restricts the desktop Outlook inbox over MAPI to
`sender · date · subject`. Deciding what to do with a hit is a later turn.

Both backends drive a COM provider through PowerShell, a sanctioned Windows backend under rule 3 and
not the raw shell rule 1 forbids: the model supplies search *terms*, never a command; every term is
stripped to bare words and every date to a bare `YYYY-MM-DD` before it can enter a query string (a
DASL restriction is an injection surface exactly as a SQL `WHERE` is); and the finished query reaches
the subprocess in an environment variable, so nothing the model wrote is ever parsed as PowerShell.

Both corpora are local — the Windows index and the desktop mail store, no Graph and no cloud API — so
a query and its results stay on the machine (spec/50). What the model then *says* about a result
travels wherever that turn is routed, which is the `local_only` question, not this one.

A retrieval tool that cannot reach its store answers "not available" in prose rather than raising, so
a missing corpus degrades the turn instead of ending it. `search_email` checks the Windows registry
for a MAPI profile before any COM call, because asking Outlook for a mailbox when no profile exists
can raise a modal dialog on the desktop — a prompt behind a voice assistant is a hang with no way to
answer it.

**Acting tools take a word, and match it against what already exists here.** A Tier-2 tool changes
something, so the binding constraint is on what the model may name. It supplies a plain word — an app
as a person says it, a fragment of a window title, one of a fixed list of media actions — and never a
path, a command line, or an identifier it composed. Each word is resolved against a list this machine
produced: the apps Windows itself reports (`Get-StartApps`), the titles of the windows open right now,
the action names the registry declares. `explorer.exe` is handed an argument list, never a command
line. So the worst a wrong guess reaches is something the user already has, and there is no parameter
through which a new thing can be named. The only place a path is accepted is the user's own alias
table (`shared/schemas/app_aliases.json`), which the model cannot write to and never reads from.

A resolution that matches nothing answers with the closest real names rather than a bare refusal. An
action Windows silently declined is reported as declined: `focus_window` works around the foreground
lock by attaching to the foreground window's input thread, then *checks* whether the window actually
came forward, and `media_control` reports that the key was sent, not that music is playing.

## The starter set

| Tool | Tier | Connector | Notes |
|------|------|-----------|-------|
| `system_status` | 1 | System | time, date, battery, front window |
| `read_clipboard` | 1 | Clipboard | capped at 2000 characters |
| `find_document` | 1 | Files | Windows Search index; ≤ 8 results |
| `search_email` | 1 | Email | Outlook on Windows; ≤ 8 results |
| `open_app` | 2 | Apps & media | Start Menu apps, plus the user's alias table |
| `focus_window` | 2 | Apps & media | matches a fragment of a visible window's title |
| `media_control` | 2 | Apps & media | play/pause, next, previous, volume up/down, mute |
| `set_timer` | 2 | Apps & media | no backend — see the executor, above |

Each entry carries a `label`: the tool said in a sentence a person would use. It serves both halves of
consent — the card lists it before the fact, the island shows it while the tool runs. It lives in the
registry because `description` is written for the model, and a second wording kept in the settings
window would drift from it. Ids, parameters and defaults live in `shared/schemas/tools.json` and
`shared/schemas/settings.json`, never restated here.

## MCP

Not admitted yet. An MCP server supplies tools at runtime with no declared tier, so it cannot pass the
gate rule 1 depends on — and an MCP server may expose precisely a raw shell. Admitting one needs its
own decision: where a runtime tool's tier comes from, and who vouches for it. Until then the
connectors pane holds a dimmed slot and nothing else.
