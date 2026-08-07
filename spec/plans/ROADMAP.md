# ROADMAP

**Last reconciled: 2026-08-07 03:35** · Build minutiae: [STATE.md](STATE.md) · Published spec: [spec/docs](../docs) · Router design: [router_master_plan.md](router_master_plan.md)

The build order and the open questions. How far along a given piece is belongs in STATE; this file
carries what is queued, in what order, and what each item is waiting on.

Marks: `[ ]` not started · `[~]` part done · `[x]` done. Items are numbered by stage, and a number
is an address — cite `1.3`, not "the routing one".

## Summary of stages

| Stage | Delivers | State |
|-------|----------|-------|
| 1 | Gemma acts — acting on the world, routing, showing what it is doing, gated by consent | in progress |
| 1.5 | The absent knobs — settings the window was built to hold but does not surface | runs beside stage 1 |
| 2 | The conversation model — history that survives a turn | design session before any code |
| 3 | Voice out — sentence-streamed speech and the versioned persona | not started |
| D | Dictation — runs alongside every stage, gated by none | in progress |

Stage 1 makes it act, stage 3 gives it a voice, stage 2 gives it continuity. Mac parity is last and
off-stage.

## Stage 1 — Gemma acts

Ordering: fix what is broken, measure the premise, ship the safe half of routing, design the risky
half, then re-scope the last piece against what survives.

[ ] **1.1 — The empty round and the 1–9 s spread on the local ask path.** Blocking, and it
undermines the case for tools. The bar: 15 ms–1 s of fluctuation is acceptable; 1–9 s with
intermittent total failure is not. A retry was tried and reverted — the resample came back empty
too. The failing round is fast and returns nothing, which is not sampling noise, so the cause is
structural; start by capturing the raw stream. Constraint: qwen3.5:9b stays, being the best
dictation performer, and a 14b model is not wanted for a simple assistant.

[ ] **1.2 — Run the latency suite.** Built at `eval/latency.py` and never run, so it has produced
no numbers. Times speech-to-text and one model round over hundreds of runs, reports the tail
(p95/p99/max) rather than the mean, and records what the model did beside how long it took, so a
run that timed 200 rounds while the model invented the answer cannot read as a pass. Hundreds
rather than tens because the fault is a rare transient — one run in thirty hit 14.58 s with
reasoning already off, which a median hides. **Local models only** — a sweep spends GPU time and
nothing else, and the question it answers is whether a given local model is fast and steady enough
to deploy. Read beside the tool-selection score, which answers whether it picks the right tool.
Together they are the instrument for choosing the router's model: candidates are `qwen3.5:4b` and
`:2b` (same family as the 9b already scored 8/9, so one variable moves), `LFM2.5-8B-A1B` (built for
tool calling on consumer hardware) and `granite4.1:3b`. Gates 1.3, and settles the open
`tool_round_effort` question once the spreads are visible.

**LLM-driven router eval.** `eval/tool_check.py --sweep MODEL[,MODEL…] RUNS` repeats every case against each candidate and reports command accuracy and false-fire rate separately. Both numbers are needed: a model that never fires looks perfect on negatives and is useless, and one that always fires looks perfect on commands and is dangerous. Each model is evicted and proven wholly out of VRAM before the next loads, because partial CPU offload under memory pressure scores the same model two different ways. The case set gained six negatives for this — only one existed before, and firing on a negative is the failure the precision rule exists to prevent.

[ ] **1.3 — Task routing.** Utterance shape decides which model serves it. No disambiguation, so
none of the risk in 1.4, and it helps questions as well as commands. Slots into `router.resolve`;
only the data changes. Gated on 1.2 — do not pick the fast model before knowing which one is fast.
Ollama with reasoning off ran a 0.68 s median per round and may beat Groq once network is counted.

**Targeted "router" behaviour.** The router *intercepts the request and decides where it goes*: to a tool whose result speaks for itself (deterministic), to a tool whose result is then handed to a **composer** (semideterministic; semiagentic), or to the model (agentic). The router therefore "routes" between *a tool call and a genuine prompt*, based on the available context of the tools exposed to it via the tools harness. Hence note that Skills (1.4) are one outcome of this router, not the whole of it; 1.3, 1.4 and 1.5 are all pieces of it.

**Router invariants, settled before design.** The router decides and never executes: dispatched calls go through `execute()`, so they pass tier and connector like any other call and land in the audit log. Routing around those gates would let a switched-off connector still act. The whole ledger is offered — the router is generic over `tools.json` and adding a tool needs no router work — and each tool declares in the registry how far it can be reached without a model and whether its result needs a composer. Argument extraction is the limit: `open_app` takes a word, `find_document` takes a composed query, and a tool that cannot be reached honestly falls through. Ask path only; dictation never routes. Fall-through stays byte-identical to today.

**Router build order.** As the connectors and spoken-formatting work were built: registry fields and their offline guard first; then the matcher and its adversarial suite with nothing wired; then wiring behind a flag, default off, with fall-through proven identical; then the composer path; then dropping the model round for self-describing tools.

[~] **1.4 — Skills.** An utterance answered deterministically, with no model at all. Design session
and a decision record before any code. To settle: what counts as a skill (the 1.7 utilities set is
the same list — design them together); the matching strategy; the fall-through, which must be
indistinguishable from today; one backend behind two doors, so a skill and a tool reach the same
deterministic code and `system_status` is never reimplemented; and a test suite shaped like
`_FORMAT_CASES`, in which the adversarial non-commands are the point — "I was going to open
Spotify", "can you open Spotify?", and "what time is it in Tokyo", the last being a question
wearing a command's clothes, which must reach the model.

Binding constraint, settled before design: precision over recall. A matcher that fires on "I was
going to open Spotify but didn't" has acted against the speaker's intent, which is a worse failure
than being slow. It never fires unless certain and falls through to the model when unsure.

First skill is the clock, which failed both ways on 2026-08-03 — silent with reasoning on, and an
invented "16:05 UTC+8 (Hong Kong)" with it off — so it carries a correctness argument, not only a
speed one.

Scope it as a latency-and-cost fix rather than a correctness one: `qwen3.5:9b` already picks the
right tool 8 times in 9 with sensible arguments, the ninth being the clock. The counterweight is
that skills only help commands — a question still costs a full round however good the matcher is —
and the share of real utterances that are commands has not been measured. The user's estimate from
use is 40–50%, with opening apps, web search and finding files named as the wanted cases. The
transcripts in `gemma.log` will confirm or correct that for free as the work proceeds.

**In progress from 2026-08-07; the design is [router_master_plan.md](router_master_plan.md)** — what
is being built, the concepts, the training method, the evaluation protocol and a six-phase build
order. It changes two things above. The deterministic matcher is out, and what replaces it is a
small trained encoder carrying three heads, a few hundred megabytes, loaded directly rather than
through Ollama, so the router never occupies a model slot the user chose for Ask or Dictate. And
every figure measured on 2026-08-04 falls below that document's 100-run floor, so all three sweeps
are marked provisional and re-running them is phase 0.

**Owed after it lands: the cloud path.** The router removes latency only for what it catches. A
question falls through to the assistant model and pays a full cloud turn, and nothing in this plan
makes that faster. Prompt caching over the stable system-prompt-and-tool-list prefix is the obvious
lever; the minimum cacheable prefix differs by model, so it wants measuring rather than assuming.
Recorded as an open question in the master plan.

[ ] **1.5 — Skip the reply round for an action.** Last, deliberately, and it may prove unnecessary.
A tool turn is two model calls, and round two spends 1630 input tokens to produce 9 output tokens
saying "Spotify is open." Round two has three real jobs — compose prose from a machine result,
decide whether more tools are needed, and answer a question the tool only supplied an ingredient
for — and `open_app` needs none of them. After 1.4 the turns skills do not catch are
`find_document` and `search_email`, which is exactly where round two has its strongest claim, since
their output is raw rows. Conditions if still wanted: exactly one tool call in the round, that tool
flagged self-describing in the registry, and its sentence written into history. The full flow and
its costs are in spec/00 § Anatomy of a turn.

[ ] **1.6 — Named model instances.** Instance-keyed `models`, plus `roles` and `routes`, the
settings migration, and the UI. The migration is the risky part — a botched one has already eaten a
profile.

[ ] **1.7 — The utilities set (Tools 2.5).** The current tools are grouped unnaturally. Regroup
into utilities (timer, clock arithmetic, unit and weight conversions), apps and media, and a
Spotify integration. Design alongside 1.4, since a skill and a tool share one backend.

[ ] **1.8 — Tool activity indicator.** Render the `tool` status message on the island. The feed
carries it already; the collision to resolve is with the "Thinking…" slot. This closes the hole
left by tier 2: with pings off, a tier-2 action currently has no cue at all.

[ ] **1.9 — Tier 3 and propose-then-tap.** Destructive actions behind an overlay confirmation, plus
the limited account.

[ ] **1.10 — `set_timer`.** The open half of tier 2. It needs a status message for something that
fires outside a turn, which the feed has no shape for yet.

[ ] **1.11 — `local_only` privacy routing.** Force a local model for private requests (spec/50
rule 6).

[ ] **1.12 — First-run permissions round.** Ask for the connectors Gemma wants up front instead of
leaving the choice to be found in the Connectors pane. Owed at packaging.

[ ] **1.13 — Publish measurements, never recommendations.** The model picker marks a model
`tested 8/9 · date` or `untested`, never "recommended". A curated badge is a treadmill and a stale
one misleads worse than silence. Pairs with a "Test for cleanup" button and with 1.2.

[ ] **1.14 — `/v1/responses` as a third wire.** Parked. It is the only route that restores
reasoning to an OpenAI tool turn, and it is a different request and response shape rather than a
dialect difference.

### Landed — stage 1

- [x] Tier 1, the tool loop and the audit log.
- [x] Router v1 — a role resolves to a provider and model.
- [x] `find_document` (Windows Search index) and `search_email` (Outlook).
- [x] Tier 2, 2026-08-03 — `open_app`, `focus_window`, `media_control`, the announce earcon,
  `MAX_TIER` raised to 2, the `apps_media` connector live.
- [x] Two dwells, 2026-08-03 — a confirmation clears in 2.5 s, an answer keeps its 20 s, both
  user-set in General > Preferences.
- [x] Boot preload of local models, 2026-08-04 — one throwaway one-token request per local model a
  role names, sent from the warm-up thread after `_ready` is set so the doors are never held for
  it. Every role's local model, so a two-model VRAM collision lands at boot where the log shows it
  rather than mid-dictation where it does not. Cloud roles are skipped. Not yet seen live: the
  roughly 9 s it removes is what a headless check cannot show.
- [x] The latency suite is built. Running it is 1.2.
- [x] Hotkeys read their bindings from settings, and recording a shortcut releases the doors,
  2026-08-04.
- [x] The user profile reaches the system prompt, 2026-08-04.

## Stage 1.5 — the absent knobs

What the settings window was built to hold and does not surface. Specced in spec/70, rendered
nowhere. Likely a Speech tab and a Dictation tab of their own.

Lettered, not numbered: `1.5` is already the address of a stage-1 item.

[ ] **1.5(a) — Sidebar search.**

[ ] **1.5(b) — Speech-to-text model.**

[ ] **1.5(c) — Wake phrase.**

[ ] **1.5(d) — Text-to-speech voice.**

[ ] **1.5(e) — Word-replacement table editor.** The backend is done; this is its UI.

## Stage 2 — the conversation model

[ ] **2.1 — History that survives a turn.** The design sits between named chats and
dump-everything, and neither end is right. A design session before any code — this is the
uncertain one. It gates the proactive context-overflow guard and cross-turn scroll-back.

## Stage 3 — voice out

[ ] **3.1 — Model-tagged speak/hold split.** The model tags its own output for what to speak and
what to show, retiring the two-sentence heuristic.

[ ] **3.2 — The versioned persona.** Replaces the placeholder system prompt.

[ ] **3.3 — Speech normalisation** for text-to-speech.

[ ] **3.4 — Read every answer when speech is on**, rather than holding long ones.

## Dictation

Runs alongside the stages and is gated by none of them.

[~] **D.1 — Spoken-structure formatting.** Shipped, and gated on a decision: keep the spoken
commands ("enumerate list" and the rest), or drop them and let the model infer a list from ordinary
speech as VoiceInk does. The answer decides whether the deterministic pre-pass is ever built.

[ ] **D.2 — Cleanup test suite, two tiers.** A short smoke set behind a user-facing button, the
full suite as a maintainer command. Word fidelity needs a multiset diff rather than substring
assertions: a model can pass every check while deleting a clause.

[ ] **D.3 — Per-mode speech-to-text.** A higher-accuracy engine for dictation than for the ask
path.

[ ] **D.4 — Context injection and the rewrite verb.** Selected text, clipboard or screen as
context; then select, speak an instruction, and transform.

### Landed — dictation

- [x] Capture, transcribe, clean up, paste; the overlay states; the cleanup prompt covering
  self-corrections, spoken punctuation and spelled-out letters.
- [x] The word-replacement table, 2026-07-28 — deterministic acronym, name and jargon fixes, run
  before cleanup.

## Through-line

Deterministic-first. Table or hardcode what is exact — acronyms, time, unit conversion, timers —
and reserve the model for the open-ended tail. The word-replacement table, the skills layer and
task routing are the same move.

## Working practice

One coordinator session holds this file, writes the handoff prompts, and arbitrates file access.
Any number of concurrent sessions may run, each restricted to a file scope.

A concurrent session that finds it needs a file outside its scope stops and reports rather than
editing it; the user relays, and the coordinator decides when to release the file. Files everything
appends to — `checks.yml`, `STATE.md`, `spec/docs/00_overview.md` — are sequenced by the
coordinator at commit time.

No concurrent session is running and nothing is off-limits. Re-cut a scope table when a second
session opens, and delete it when that session closes: a stale ledger reserves files nobody holds,
which is worse than no ledger.
