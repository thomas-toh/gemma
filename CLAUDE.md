# Project Gemma — CLAUDE.md

Gemma is a personal prototyping project: an always-listening voice assistant +
dictation bridge on a Windows PC, backed by swappable LLM brains (Claude API first,
local LLM second), with a bone-conduction headset as a parked hardware ambition (D12).
Built by Thomas — a lawyer learning to code — with AI assistance. Not a commercial
product.

## Repo map

```
CLAUDE.md          ← you are here; keep THIN (index + rules only, never the spec itself)
STATE.md           ← the jump table: per-track status + next actions. Read at session start;
                     update in the same commit as the work it describes.
NOTES.md           ← operational findings (topic-keyed, lean). NEVER required reading —
                     consult only when a task touches its topic; promote anything
                     load-bearing into spec/README/code.
spec/              ← CURRENT TRUTH of the system. Read the relevant file before working on an area.
  00_overview.md      system map + milestone status (start here)
  10_contract_h.md    headset ↔ bridge interface
  20_contract_b.md    brain adapter interface (B1 Claude API / B2 local / B3 agent CLI)
  30_contract_t.md    tool registry + safety tiers
  40_interaction.md   session state machine, earcons, narration, latency targets
  50_security.md      binding security & privacy posture
  schemas/            EXECUTABLE truth — JSON the code imports (never copy values into code)
docs/              ← frozen decision records (01 scoping, 02 architecture, …). Never retro-edited.
bridge/            ← Python daemon — Doc 04 defines it; build status in STATE.md
firmware/          ← (future) ESP32 headset firmware — Doc 03 defines it
```

## Hard rules (do not relax)

1. **Spec discipline.** `spec/` is the single current truth. Any change to behaviour,
   an interface, or a schema updates the relevant `spec/` file **in the same commit**.
   Every spec file carries a `Last reconciled:` date (update it when touching the file)
   and a build-progress pointer to `STATE.md` — **STATE is the sole record of build
   progress**; spec files never state how built something is. Sections describing
   unbuilt behaviour are tagged inline (`planned, M1`). spec/50's `BINDING` header
   stays — that is normativity, not build status.
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

## Conventions

- `ponytail:` code comments are the ponytail plugin's markers (deliberate minimal-code
  shortcut + its revisit condition). Leave them intact when editing nearby; the debt
  ledger is greppable, or harvested with `/ponytail-debt` where the plugin is loaded.
- **Reviews** (point-in-time studies of this codebase or others') live in
  `docs/01_scoping/Reviews/`, named `[YYYY-MM-DD]_[HHMM]_Review-[2-5 keyword summary].md`
  (e.g. `2026-07-18_1643_Review-gemma-voiceink-codebases.md`). Frozen like the rest of
  `docs/` (hard rule 2).

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

`STATE.md` is the live answer (per-track); milestone definitions live in
`spec/00_overview.md`. This file makes no status claims — dated claims here rot.
