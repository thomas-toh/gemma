# Project Gemma — CLAUDE.md

## Hard rules to comply with in this project without deviation ##

1. **Rule 1 - Gating and permissions:** When something is stated to be gated on his approval —
   or asks a question, raises an option, or flags a decision as his — STOP. Ask, then WAIT for
   his explicit go-ahead. Do not implement, edit, or "just start." A recommendation is not
   permission; answering your own question is not permission. Silence is not permission.
   Only an explicit "yes / go ahead / do it" from the user is. This overrides every other
   instinct in this file. 
   
   **Rule 1a - Review gate on git:** show user the diff and the proposed commit message and get my
   explicit OK before any `git commit`; never `git push` without explicit approval.

2. **Rule 2 - Coding smart, not hard:** When coding:
   - DO NOT preserve backward compatability. Choose the simplest, cleanest implementation
     that entirely meets the current requirements. Refactor as required, but gate all large-
     scale refactors > 250k tokens by seeking permissions from the user.
   - DO NOT code patches over errors. You are NOT supposed to use janky fixes or "just for now"
     fixes in order to meet the user's requirements.
   - DO NOT be lazy. When the user states an outcome, building half "for now" is not meeting it,
     especially if the half-built thing is not capable of supporting the final model and requires
     full revisiting. Build features fully and faithfully.
   - Minimalism governs the ROUTE, not the DESTINATION. Reaching for an existing tool, the
     standard library or a native feature before writing new code is right; arriving at less than
     what was asked for is not. YAGNI covers work nobody has requested yet — speculative
     abstractions, scaffolding "for later" — and never licenses trimming the stated requirement.
     Where a `ponytail` session mode says otherwise, this bullet wins.
   - DO curiously investigate faults, bugs, contradictions or issues.
   - Prefer established, well-maintained libraries over custom implementations.

3. **Rule 3 - Explanations and jargons:** Keep your front-facing language to the user easily
   explained as if he does not code. The *why* of non-obvious technical choices as you go,
   in chat, is important. You can use as complex language as you require when thinking, but
   when writing to specs, drafting UI elements or explaining to the user, keep it straightforward
   and basic. Straightforward and basic means do not reach for > jargon; where a term is
   genuinely unavoidable, define it strictly in the same breath. An undefined term is a
   failed explanation, however correct it is.***

4. **Rule 4 - Spec discipline:** `spec/` is the single current truth. Any change to behaviour,
   an interface, or a schema updates the relevant `spec/` file **in the same commit**.
   Every spec file carries a `Last reconciled:` date (update it when touching the file)
   and a build-progress pointer to `STATE.md` — **STATE is the sole record of build
   progress**; spec files never state how built something is. Sections describing
   unbuilt behaviour are tagged inline (`planned, M1`). spec/50's `BINDING` header
   stays — that is normativity, not build status. Files under `docs/` record decisions
   and reasoning at a point in time. Never edit them to track reality; if superseded,
   add a one-line `> Superseded by spec/<file> §<n>` note at the top and nothing else.

5. **Rule 5 - Schemas are executable:** `spec/schemas/*.json` are loaded by the code at runtime.
   Never duplicate their contents into code or prose — import/reference them. Adding a
   tool, earcon, or message type means editing the schema file, not scattering literals.

6. **Rule 6 - Safety invariants (from spec/50):** no raw shell tool below Tier 3; Tier 3 requires
   explicit confirmation — a keypress on the proposal rendered on the Teleprompter
   (propose-then-tap, D20/D26), or a spoken "confirm" when speech is on; every tool call
   is audit-logged; raw audio is never written to disk; the overlay's listening indicator
   truthfully reflects audio capture. These are safety constants, not preferences.

7. **Rule 7 - Keep agentically created file thin:** CLAUDE and STATE should be kept thin. Be careful
   where you put information. Decisions which just reflect certain choices but do not constitute
   project-important decisions belong in NOTES. If not, it belongs in `spec/`.

## Overview ##

Gemma is a personal prototyping project: a **UI-first desk voice assistant + dictation
tool** on a Windows PC (a Teleprompter overlay is the primary surface), backed by swappable
LLM brains (Claude API first, local LLM second). Reached through two hotkey doors — ask and
dictate; an always-on wake word and spoken replies are opt-in switches, **off by default**
(D23). 

*(The package `bridge/` is named for the cancelled headset it once bridged to the brains
(D18); it is now just the daemon. A rename to `daemon/` is parked — STATE, Specs.)*

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
  20_contract_b.md    brain adapter interface (B1 Claude API / B2 local / B3 agent CLI)
  30_contract_t.md    tool registry + safety tiers
  40_interaction.md   session state machine, earcons, narration, latency targets
  50_security.md      binding security & privacy posture
  schemas/            EXECUTABLE truth — JSON the code imports (never copy values into code)
docs/              ← frozen decision records (01 scoping, 02 architecture, …). Never retro-edited.
bridge/            ← Python daemon (audio · orchestrator · brains) — Doc 04 defines it; build status in STATE.md
teleprompter/      ← the overlay (component P) — PySide6/QML front-end on Contract P (D19); the spine (D23)
tests/             ← replay harness (recorded WAVs → real pipeline → real orchestrator); WAVs untracked
scripts/           ← one-off smoke tests (e.g. b1_smoke.py)
```

## Conventions

- `ponytail:` code comments are the ponytail plugin's markers (deliberate minimal-code
  shortcut + its revisit condition). Leave them intact when editing nearby; the debt
  ledger is greppable, or harvested with `/ponytail-debt` where the plugin is loaded.
- **Reviews** (point-in-time studies of this codebase or others') live in
  `docs/01_scoping/Reviews/`, named `[YYYY-MM-DD]_[HHMM]_Review-[2-5 keyword summary].md`
  (e.g. `2026-07-18_1643_Review-gemma-voiceink-codebases.md`). Frozen like the rest of
  `docs/` (hard rule 2).
- **Session coordination.** Before opening a design session or allocating a D-number,
  read spec/00's decision tail and `git log -5`. One design session holds the pen at a
  time — parallel sessions caused the D18/D19 numbering collision of 2026-07-21.

## Other guiding ways when working with the user

- Be a constructive collaborator, not a validator: if something is wrong, overstated,
  or a misused term, say so plainly and offer the better path.
- When the user instructs you not to do something, do not over-interpret as a guardrail
  and include in specs — leads to bloating. Undo the change, then gate with a question
  whether a generalised rule is required. When in doubt, preference having no generalised
  rule.
- Keep a running task list on multi-step work.
- While working through a task, maintain a log of "modified files" for that task. Then, 
  for presentation completion of multi-step work: state at the end a "Changed files" 
  section, list all files which were modified since the last commit by that session.

## Current state

`STATE.md` is the live answer (per-track); milestone definitions live in
`spec/00_overview.md`. This file makes no status claims — dated claims here rot.
