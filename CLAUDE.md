# Project Gemma — CLAUDE.md

Gemma is a personal prototyping project: a bone-conduction headset that talks to an
always-listening voice assistant ("the bridge") on a Windows PC, backed by swappable
LLM brains (Claude API first, local LLM second). Built by Thomas — a lawyer learning
to code — with AI assistance. Not a commercial product.

## Repo map

```
CLAUDE.md          ← you are here; keep THIN (index + rules only, never the spec itself)
STATE.md           ← the jump table: per-track status + next actions. Read at session start;
                     update in the same commit as the work it describes.
spec/              ← CURRENT TRUTH of the system. Read the relevant file before working on an area.
  00_overview.md      system map + milestone status (start here)
  10_contract_h.md    headset ↔ bridge interface
  20_contract_b.md    brain adapter interface (B1 Claude API / B2 local / B3 agent CLI)
  30_contract_t.md    tool registry + safety tiers
  40_interaction.md   session state machine, earcons, narration, latency targets
  50_security.md      binding security & privacy posture
  schemas/            EXECUTABLE truth — JSON the code imports (never copy values into code)
docs/              ← frozen decision records (01 scoping, 02 architecture, …). Never retro-edited.
bridge/            ← (future) Python daemon — Doc 04 defines it
firmware/          ← (future) ESP32 headset firmware — Doc 03 defines it
```

## Hard rules (do not relax)

1. **Spec discipline.** `spec/` is the single current truth. Any change to behaviour,
   an interface, or a schema updates the relevant `spec/` file **in the same commit**.
   Every spec file carries a `Status:` header (`DESIGNED` | `PARTIAL` | `AS-BUILT`) and a
   `Last reconciled:` date — update both when touching it.
2. **Docs are frozen.** Files under `docs/` record decisions and reasoning at a point in
   time. Never edit them to track reality; if superseded, add a one-line
   `> Superseded by spec/<file> §<n>` note at the top and nothing else.
3. **Schemas are executable.** `spec/schemas/*.json` are loaded by the code at runtime.
   Never duplicate their contents into code or prose — import/reference them. Adding a
   tool, earcon, or message type means editing the schema file, not scattering literals.
4. **Safety invariants (from spec/50):** no raw shell tool below Tier 3; Tier 3 requires
   spoken confirmation; every tool call is audit-logged; raw audio is never written to
   disk; LED state must truthfully reflect audio streaming; the hardware mute switch
   physically cuts the mic. These are design constants, not preferences.
5. **Keep this file thin.** If a section here grows past a screen, it belongs in `spec/`.

## How to work with Thomas

- Ask when unsure; present options rather than guessing. Discuss before building
  anything non-trivial; no go-ahead, no proceeding.
- Be a constructive collaborator, not a validator: if something is wrong, overstated,
  or a misused term, say so plainly and offer the better path.
- Thomas is a vibecoder: explain the *why* of non-obvious technical choices in
  plain language as you go, in chat — not by bloating the specs.
- When Thomas instructs you not to do something, do not over-interpret as a guardrail
  and include in specs — leads to bloating. Undo the change, then gate with a question
  whether a generalised rule is required. When in doubt, preference having no generalised
  rule.
- Keep a running task list on multi-step work.
- Review gate on git: show me the diff and the proposed commit message and get my
  explicit OK before any `git commit`; never `git push` without explicit approval.

## Current state

`STATE.md` is the live answer (per-track). Milestone definitions live in
`spec/00_overview.md`. As of July 2026: everything is `DESIGNED`, no code exists yet.
First build target is **M0** (voice loop closed on stock headset + Claude API brain).
