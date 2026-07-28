# ROADMAP — router / tools / dictation checklist + concurrent-build ledger

The queued build items (mirrors the task list #7–12) and who is building what right now.

**Coordination model.** One **coordinator** session (holds this file, writes handoff prompts,
arbitrates file access) + one or more **concurrent** sessions, each restricted to a **file scope**.
If a concurrent session finds it needs a file outside its scope, it **STOPS and reports to Thomas**
(it does not edit it) — Thomas relays to the coordinator, and the **coordinator decides when to
release** that file. Shared append-only files (`checks.yml`, `STATE.md`, `spec/00`) are sequenced by
the coordinator at commit time.

## Concurrent-build ledger (live)

| Owner | Item | May edit (file scope) | Status |
|-------|------|-----------------------|--------|
| **coordinator** | #12 dictation word-replacement | `bridge/replace.py` *(new)* · `spec/schemas/word_replacements.json` *(new)* · `bridge/orchestrator.py` (`_dictate` hook only) · `spec/60_dictation.md` · `checks.yml` · `STATE.md` | built + green — awaiting review to commit |
| **session A** | #11 `find_document` | `bridge/tools.py` · `spec/schemas/tools.json` · `.github/workflows/checks.yml` · `spec/30_contract_t.md` · `STATE.md` | in progress (backend has landed in the working tree) |

Off-limits to everyone but their owner: `bridge/orchestrator.py` (coordinator), `bridge/tools.py`
(session A), all `teleprompter/` (UI-session lane), `spec/schemas/settings.json` (router #7 later).

## Router / model
- [x] **Router v1** — role → model (D33)
- [ ] **#7 Named model instances (shape B)** — instance-keyed `models` + `roles`/`routes` + migration + UI. *The foundation.*
- [ ] **#8 Router 2 — request classifier** — intent → *skill* (bypass LLM) / task-type → *model*; first skill = world-time + live clock.
- [ ] **`local_only` / privacy routing** — force a local model for private requests (spec/50 rule 6).

## Tools
- [x] **Tier-1** + the tool loop + audit (D31)
- [ ] **#9 Tier-2** — open_app · focus_window · media_control · set_timer
- [ ] **#10 Tier-3 + propose-then-tap** (D26) — destructive actions; overlay confirmation + limited account
- [ ] **#11 find_document** (Windows Search) → **search_email** (Outlook)   ← *session A*
- *A **skill** (intent-invoked) and a **tool** (LLM-invoked) share the same deterministic backend — build it once.*

## Dictation
- [x] **D1** capture→STT→cleanup→paste · **D2** overlay states · cleanup prompt (self-corrections, spoken punctuation, spelled-out letters)
- [x] **#12 word-replacement table (D15)** — deterministic acronyms / names / jargon, before cleanup (2026-07-28)
- [ ] **spoken-structure formatting** — numbered lists / bullets from spoken cues
- [ ] **per-mode STT (D12)** — a higher-accuracy engine for dictation
- [ ] **context injection** (#3 lift) · **D3 rewrite** (select → speak instruction → transform)

## Through-line
**Deterministic-first.** Table/hardcode what is exact (acronyms, time, unit conversion, timers);
reserve the LLM for the open-ended tail. The word-replacement table (#12), the skills layer (#8),
and per-task routing (#8) are the same move.
