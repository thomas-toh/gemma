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
| **coordinator** | Stage 1 · Tools v2 (#9) → **done 2026-08-03** (D42, uncommitted). Next: TBD | — | idle, awaiting next pick |

No concurrent session is running. #11 (`find_document` + `search_email`) closed 2026-07-28 and its
lane is released; nothing is off-limits at present. Re-cut this table when a second session opens —
a stale ledger is worse than none, because it reserves files nobody is holding.

## Stages (build sequencing)

The high-level order; the per-track checklists below are the granular items each stage pulls from.

**Stage 1 — "Gemma acts" (the assistant / Siri-like *doing*).** Act on the world, route
intelligently, show what it's doing — gated by consent.
- ~~**Tools v2** (#9 Tier-2)~~ — **done 2026-08-03 (D42)**: `open_app` · `focus_window` ·
  `media_control`, the announce earcon, `MAX_TIER` 2, `apps_media` live. `set_timer` deferred —
  it fires outside a turn and Contract P cannot announce that yet.
- **Tools v3** (#10 Tier-3 + propose-then-tap, D26) — destructive actions behind an overlay
  confirmation + limited account.
- **Router v2** (#7 named instances + migration · #8 classifier/skills · `local_only`) — what a tool
  turn routes its brain through; #7's schema migration is the risky part (a botched one ate a profile).
- **Tool activity indicator** — render `overlay.tool` on the island (wire built under D38; it
  collides with the "Thinking…" slot). **It now has something to show**, and it is what closes
  D42's hole: with pings off, a Tier-2 action currently has no cue at all.
- ~~**Two dwells**~~ — **done 2026-08-03 (D43)**: a confirmation clears in 2.5 s, an answer keeps
  its 20 s, both user-set in General > Preferences. Fell out of Tools v2 — an action that leaves
  nothing to read should not hold the screen like an answer.
- **Skip the reply round for an action** — *open, gated on #8 landing first*. Measured 2026-08-03:
  a tool turn is TWO model calls, and round 2 spends **1630 input tokens to produce 9 output
  tokens** saying "Spotify is open." Round 2 has three real jobs — compose prose from a machine
  result, decide whether more tools are needed, and answer a question the tool only supplied an
  ingredient for — and `open_app` needs none of them. Thomas' position: a fixed string covers more
  tools than first claimed; the LLM is needed only where the composition IS the value (web search).
  The counter-case to resolve: the same tool serves both a direct request and a question needing
  work ("what time in Tokyo?" is arithmetic over `system_status`, not its raw output). Full flow
  and costs now in spec/00 § Anatomy of a turn. **Latency suite queued after this** — see Router.
- **URGENT — the empty round + the 1–9 s spread on the local ASK path.** Thomas's bar: 15 ms–1 s
  of fluctuation is fine, 1–9 s with intermittent total failure is not, and it undermines the
  viability of tools. A retry was tried and reverted (it also came back empty). The live clue: a
  model returning *nothing* is not sampling noise, and the failing round is FAST, so the search is
  structural — start by capturing the raw stream. Constraint: **qwen3.5:9b stays** — it is the
  best dictation performer and a 14b model is not wanted for a simple assistant. *(STATE, Track T.)*
- **(2) Preload the local model at boot — STILL OWED, agreed but not built.** Measured 2026-08-03:
  the FIRST local turn waits ~9 s for Ollama to pull the weights into VRAM; every later turn is
  ~1 s a round. The server is already started at boot; the model is not. Fits D39's background
  warm-up walk (`_warn_missing_models` already resolves each role and filters to local), so it is
  a handful of lines in a walk that exists. **Must run AFTER the doors open**, or D41 drops every
  press for the extra ~10 s — that would trade a slow first answer for no first answer.
  **Open question for the build:** warm every role's local model, or only the assistant? Warming
  both surfaces the two-model VRAM collision at boot where it is visible, rather than mid-dictation
  where it is not. Independent of #8 — worth doing whenever the daemon path is next open.
- **`/v1/responses` as a third wire** — parked. It is the only route that restores reasoning to an
  OpenAI tool turn (D44); a different request/response shape, not a dialect difference.
- **Connectors folded in** — `apps_media` went live with D42; what remains is the first-run
  permissions round (owed at packaging).

**Stage 1.5 — the absent knobs (parallel).** What the settings window was built to hold but does not
surface yet: sidebar **search** · **STT model** · **wake phrase** · **TTS voice** ·
**word-replacement table editor** (the settings grid — the D15 backend is done, this is its UI).
Likely their own Speech/Dictation tab (spec/70 §3).

**Stage 2 — the conversation model.** History that survives a turn: the "between named chats and
dump-everything" design. Gates the proactive context-overflow guard and cross-turn scroll-back.
*The uncertain one — a design session before any code.*

**Stage 3 — TTS ("it speaks well," M0.5).** Sentence-streamed voice out: the model-tagged speak/hold
split (retires the ≤ 2-sentence heuristic), the versioned persona, speech normalization,
read-all-when-on.

*(Mac parity / D10 stays "last", off-stage.) The full "Siri-like" feel completes across the stages:
Stage 1 makes it ACT, Stage 3 gives it a VOICE, Stage 2 gives it CONTINUITY.*

## Router / model
- [x] **Router v1** — role → model (D33)
- [ ] **#7 Named model instances (shape B)** — instance-keyed `models` + `roles`/`routes` + migration + UI. *The foundation.*
- [ ] **#8 Router 2 — request classifier** — intent → *skill* (bypass LLM) / task-type → *model*;
  first skill = world-time + live clock. **NEXT after Tools v2** (Thomas, 2026-08-03). It is the
  "router within a router": a **deterministic** matcher that decides whether an utterance is a
  command, not a second model — a cheap LLM gate would add a round-trip and its own tokens, and the
  saving only exists if the model is removed entirely. Measured stake: "open Spotify" costs ~3,200
  input tokens across two rounds (~1.7¢ on Opus 4.8) for a five-token request; a matched phrase
  costs nothing and is instant. Design risk is D37's, exactly: telling a command from someone
  merely saying those words — that ambiguity cost a day on spoken lists.
  **Baseline measured 2026-08-03** (`--check-tools`, STATE Track T): `qwen3.5:9b` picks the right
  tool 8/9 with sensible arguments, so #8 is a LATENCY-AND-COST fix, not a correctness one — scope
  it accordingly. The 9th is the clock, which is already #8's first skill.

  **SPLIT THE NAME BEFORE THE DESIGN SESSION (2026-08-03).** "Router" already means one thing here
  — role → provider+model, D33, built. #8 as written bundles **two more**, and they have different
  risk, different cost and different schedules. Keeping them under one word will blur the spec and
  let the risky half drag the safe half:
  - **`router` (built, D33)** — role → provider + model.
  - **Task routing** — utterance *shape* → which model. No disambiguation, low risk. Addresses
    latency for questions as well as commands. Wants the latency suite first, and the answer is
    not obvious: Ollama with reasoning off ran a **0.68 s median per round**, which may beat Groq
    once network is counted.
  - **Skills** — utterance → deterministic answer, **no model at all**. The D37-shaped one, and
    where all the design risk lives.

  **Binding design principle — PRECISION OVER RECALL.** A bad matcher is worse than none: one that
  fires on *"I was going to open Spotify but didn't"* has acted against the speaker's intent, which
  is a worse failure than being slow. **Never fire unless certain; fall through to the model when
  unsure.** Settle this before writing the matcher, not after — D37 discovered the same ambiguity
  the expensive way.

  **The counterweight, so this is not read as pure upside:** a skills layer only helps *commands*.
  A question still costs a full round however good the matcher is — so #8's value is proportional
  to the share of real utterances that are commands, **and nobody has measured that share.** Worth
  a day of ordinary use with the transcripts counted before this becomes the centrepiece.

  **"The router" stays as the umbrella name (Thomas, 2026-08-03)** — one name over several
  subsystems is normal and the split above is what matters, not the label. The condition attached:
  **the breakdown gets written into spec/20 § Routing as it is built**, so the word never has to be
  explained twice. Noted there as `planned` already.

### The plan for the router (agreed 2026-08-03, to start 2026-08-04)

Ordering rationale: **measure the premise → build the instrument → ship the safe half → design the
risky half → re-scope the last piece against what survives.**

0. ~~**Measure the premise**~~ — **SKIPPED (Thomas, 2026-08-03).** The question was what share of
   ask-path utterances are commands, since everything below scales with it. Thomas' estimate from
   using it: **40–50%** — "opening apps on Windows is terribly annoying" — plus wanting **web
   searches** and **finding files**, both tool calls. At that share the skills layer clearly earns
   its place and the gate has done its job. *It stays an estimate, not a measurement; the
   transcripts in `gemma.log` will confirm or correct it for free as the work proceeds, so nothing
   needs to stop for it.*
   **Two things the answer surfaced:** file-finding is already `find_document` (so it wants a
   SKILL door onto an existing tool, not a new tool), and **web search does not exist at all** —
   `connector_web` is dimmed with no backend. Web search is also the clearest case where the
   round-2 reply genuinely earns its keep, since composing the results *is* the value — Thomas'
   own example, and it sharpens phase 4's scope.
1. **The latency suite** — *moved AHEAD of #8*, reversing the earlier "after" call, because every
   later phase is justified by latency numbers we cannot currently compare. Same utterance, N runs,
   per provider and model; report **spread and median, never mean**. Also settles the open
   `tool_round_effort` decision, which stops being a judgement call once the spreads are visible.
2. **Task routing** — utterance shape → which model. No disambiguation, so no D37 risk. Slots into
   `router.resolve`; only the data changes. **Helps questions as well as commands**, which skills
   never will. Gated on 1: do not pick "the fast model" before knowing which one is fast (Ollama
   with reasoning off ran 0.68 s median/round and may beat Groq once network is counted).
3. **Skills** — design session and a D-number BEFORE code. Settle: what counts as a skill (the
   Tools 2.5 "utilities" set is the same list — design them together) · matching strategy ·
   the fall-through, which must be indistinguishable from today · **one backend, two doors** (a
   skill and a tool share the deterministic backend — `system_status` is reached both ways, never
   reimplemented) · the test suite in `_FORMAT_CASES`' shape, where **the adversarial non-commands
   are the point**: "I was going to open Spotify", "can you open Spotify?", "what time is it in
   Tokyo" (a question wearing a command's clothes — that one must reach the model).
   **First skill: the clock** — it failed BOTH ways on 2026-08-03 (silent with reasoning on, an
   invented "16:05 UTC+8 (Hong Kong)" with it off), so it carries a correctness argument and not
   just a speed one.
4. **The round-2 skip** — last, deliberately. Only meaningful for tool turns skills do NOT catch,
   which after phase 3 is `find_document` and `search_email` — exactly where round two has its
   strongest claim, since their output is raw rows. **It may turn out to be unnecessary; that is a
   legitimate outcome.** Conditions if still wanted: exactly one tool call in the round, that tool
   flagged self-describing in the registry, and its sentence written into history.

**Two things to avoid:** building skills before phase 0 says they are the bottleneck, and letting
the risky half (3) drag the safe half (2) by scheduling them as one item.
- [ ] **Latency test suite (after #8 and the round-2 work — Thomas, 2026-08-03).** Not "is it
  fast" but **"why is it erratic"** — the same request measured repeatedly, per provider and per
  model, reporting the spread and not just the mean. The provoking measurements: identical input
  to `qwen3.5:9b` ranged **1.5 s – 4.6 s** over 12 runs, and **2 s – 9 s** for the same case across
  two `--check-tools` runs; the same 12-run sweep also found an **empty round 1 in 12**, which is
  a latency fault wearing a correctness costume (the user waits, then hears an apology).
  Deliberately AFTER #8, because #8 removes the model from the commands that hurt most — measure
  what survives, not what is about to be deleted. Sits beside `--check-tools` and `--check-format`
  as a third maintainer command, and feeds "publish measurements, never recommendations" below:
  a spread is exactly the kind of fact that does not rot.
  **Build it for HUNDREDS of calls, not tens (Thomas, 2026-08-03).** The fault it must catch is a
  rare transient — one run in thirty hit 14.58 s with reasoning already off — and a 30-run sweep
  cannot characterise a 1-in-30 event while the median hides it completely. Report the tail
  (p95/p99 and the worst case), never the mean.
  **Cover STT too**, which has never been measured this way at all: its numbers are single
  observations scattered through the log (44 ms · 61 ms · 182 ms · 687 ms cold), never a
  distribution. A slow tail in speech-to-text feels identical to a slow tail in the brain and is
  currently indistinguishable from one — so the suite has to time the whole path, not just the
  model call.
- [ ] **Tools v2.5** —  tools not built in a natural way (unnatural grouping of tools ) —
  next step is to have utilities, i.e., timer, clock calculations, conversions, weights, etc., apps and media
  and Spotify integration, all under **Tools 2.5**.
- [ ] **`local_only` / privacy routing** — force a local model for private requests (spec/50 rule 6).
- [ ] **Publish measurements, never recommendations** — the picker marks a model `tested 8/9 · date`
  or `untested`, never "recommended"; a curated badge is a treadmill and a stale one misleads worse
  than silence. Pairs with a "Test for cleanup" button and the suite below. *(STATE, Owed designs.)*

## Tools
- [x] **Tier-1** + the tool loop + audit (D31)
- [~] **#9 Tier-2 (D42)** — open_app · focus_window · media_control shipped 2026-08-03; the
  announce earcon is Tier 2's gate. **`set_timer` is the open half**: it needs a Contract P message
  for something that fires outside a turn (the D20-shaped gap). *(STATE, Track T.)*
- [ ] **#10 Tier-3 + propose-then-tap** (D26) — destructive actions; overlay confirmation + limited account
- [~] **#11** find_document ✓ (Windows Search, `d2188b0`) → **search_email** (Outlook) next   ← *session A*
- *A **skill** (intent-invoked) and a **tool** (LLM-invoked) share the same deterministic backend — build it once.*

## Dictation
- [x] **D1** capture→STT→cleanup→paste · **D2** overlay states · cleanup prompt (self-corrections, spoken punctuation, spelled-out letters)
- [x] **#12 word-replacement table (D15)** — deterministic acronyms / names / jargon, before cleanup (2026-07-28)
- [~] **spoken-structure formatting (D37)** — shipped, but **GATED ON A DECISION**: keep the spoken
  commands (`enumerate list`…) or drop them and let the model infer a list from ordinary speech, as
  VoiceInk does. Decides whether the deterministic pre-pass is ever built. *(STATE, Track D.)*
- [ ] **Cleanup test suite, two tiers** — a short smoke set behind a user-facing button, the full
  suite as a maintainer command. Word fidelity needs a multiset diff, not substring assertions: a
  model can pass every check while deleting a clause. *(STATE, Owed designs.)*
- [ ] **per-mode STT (D12)** — a higher-accuracy engine for dictation
- [ ] **Surface the absent settings** — STT model · wake phrase · TTS voice · the word-replacement
  table editor: specced in spec/70 §3, rendered nowhere. Probably its own tab. *(STATE, queued.)*
- [ ] **context injection** (#3 lift) · **D3 rewrite** (select → speak instruction → transform)

## Through-line
**Deterministic-first.** Table/hardcode what is exact (acronyms, time, unit conversion, timers);
reserve the LLM for the open-ended tail. The word-replacement table (#12), the skills layer (#8),
and per-task routing (#8) are the same move.
