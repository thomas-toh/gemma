# Spec 30 — Contract T: tools & safety tiers

**Last reconciled: 2026-07-12** · Build progress: [STATE.md](../STATE.md) · Registry (executable): [schemas/tools.json](schemas/tools.json)

*(planned — executor and per-OS backends land at M1; the registry file itself is live
already, loaded by `bridge/config.py`. See STATE, Track T.)*

The registry file is the single source of truth for tool names, parameter schemas and
tiers. The bridge loads it at startup; brains receive it (filtered) as their tool list;
the executor refuses any call not present in it. Code never hardcodes a tool definition.

## Tiers

| Tier | Meaning | Gate | Log |
|------|---------|------|-----|
| 1 | Read-only | none | audit |
| 2 | Reversible action | earcon announce (`task-complete`/`error`) | audit |
| 3 | Destructive / consequential | **spoken confirmation** — orchestrator plays the `ask` earcon, requires the user to say "confirm" within 8 s, else cancels | audit |

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

## Starter set (defined in schemas/tools.json)

`system_status` (Tier 1) · `read_clipboard` (Tier 1) · `open_app` (Tier 2) · `focus_window` (Tier 2) ·
`media_control` (Tier 2) · `set_timer` (Tier 2)
