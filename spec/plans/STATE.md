# STATE — the jump table

Purpose: make track-hopping free. Thomas works by mood; that is fine **because** the
contracts isolate the tracks. The rules that keep it safe: pick a track by mood, but
within a track always take the next queued action · max one item in flight per track ·
when abandoning mid-task, park it here with a one-line note · read this file at session
start, update it in the same commit as the work · when a step closes, collapse its
entry to one or two lines — durable knowledge moves out (behaviour → spec · run
instructions → README · findings → NOTES.md · decisions → a D-number in spec/00).

Last updated: 2026-08-04 02:35

## Handoff — start here (2026-07-28)

**M0 IS CLOSED.** Its criterion (ask-hotkey → the reply streams to the Teleprompter, perceptible
feedback < 1.5 s, ×10 consecutively, B1, zero tools) passed and was measured on 2026-07-22, 10/10.
The **"M0-close gate" is RETIRED** (Thomas, 2026-07-28): it was bolted on after the fact, was never
part of spec/00's M0 criterion, and "the settings window is up to par" is not a testable bar. The
quality it stood for is real and now has its own section — **Config & routing**, below.

**Staged roadmap (2026-08-02):** the current build sequencing lives in [ROADMAP.md](ROADMAP.md) → *Stages* (1 "Gemma acts" · 1.5 absent knobs · 2 conversation model · 3 TTS); the per-track checklist and concurrent-build ledger are there too.
**Stage 1 started 2026-08-03** with Tools v2 (D42), the two dwells (D43) and the wire-name rule (D44).
**Next, agreed 2026-08-03 and starting 2026-08-04: the ROUTER**, per the five-phase plan in
[ROADMAP.md](ROADMAP.md) → *The plan for the router* — measure the premise · latency suite ·
task routing · skills (design session first) · the round-2 skip last. The router is an umbrella
over three subsystems; the breakdown is in spec/20 § Routing.
**Where it stands 2026-08-04:** phase 0 skipped, phase 1 (`eval/latency.py`) BUILT but **never
run** — so phase 2 is still gated on numbers that do not exist yet, and running the sweep is
Thomas's call because it costs time locally and metered tokens on a cloud key. The boot preload
(an independent Stage 1 item) was built instead; see Track G.

**Build sequence (Thomas) — do in this order:**
1. **Config & routing** — the router v1 landed (D33); what remains is the settings window being
   below par, plus the router's Layer 2. Its own section below.
2. **Conversation / memory model** — the parked "chats vs dump-everything, want something in
   between" design. Unblocks the proactive context-overflow guard (B-02).
3. **M0.5 "It speaks well"** — sentence-streamed TTS forces the speak/hold decision (a
   model-tagged split replaces the ≤ 2-sentence heuristic) and carries the persona prompt, speech
   normalization, and the read-all-when-TTS-on direction. *(The earcon half of this item shipped
   separately as D28.)*
4. **Tools + dictation** — **Track T** Tier 2/3, and **Track D**'s deepening + the D3 rewrite.
   Tier 1 (D31) and dictation D1/D2 are done, so both tracks are live, not blocked.
5. **Mac parity (D10)** — last: the full-loop Mac test + macOS hotkeys (Carbon
   `RegisterEventHotKey`).

**Queued next (2026-07-31, Thomas) — three checklists.** All three are *design-first*; none should
start as code.

**Dictation latency — fixed 2026-08-01/02, all recorded elsewhere.** "Local cleanup is slower than
Groq" was true by ~10×, for four reasons that had nothing to do with the model: STT silently on the
CPU (~950 ms → ~35 ms) · `localhost` costing ~2 s per connection (→ 0.2 ms) · a dead local runner
taking 9.66 s to report itself (→ ~2 s) · thinking models reasoning during cleanup (6.5 s → 0.44 s,
one case looping to 71k tokens and never answering). Findings in **NOTES § GPU speech-to-text** and
**§ Local model runners**; the `transform`-never-thinks invariant and the `no_model` kind in
**spec/20**. Local cleanup now runs ~0.45 s against Groq-70B's ~0.24 s.

- [x] **DONE 2026-08-02 — `no_model`**, so a missing model is nameable instead of "something went
  wrong on my end". Full account in spec/20. One thing to not undo: the 404 branch MUST precede the
  generic `APIStatusError` branch (`NotFoundError` subclasses it) — the selfcheck pins that order,
  because reversing it regresses silently with every other test still green.
  - [ ] **Owed — the settings window still doesn't catch it earlier.** The picker fetches the live
    model list but nothing compares the *stored* selection against it, so a deleted model still
    displays as configured.

- [ ] **The absent settings — wants its own design session, probably its own tab.** Four settings
  are specced in spec/70 §3 but surfaced nowhere: **STT model · wake phrase · TTS voice ·
  word-replacement table**. Thomas: likely a **tab of their own** rather than more rows on an
  existing pane. **Also owed by this session (2026-08-01): the sidebar SEARCH** — it ships disabled
  under D40 and what it should search (labels only, or help text too, or connector/tool names) is
  a design question. Owed by that session: which tab (and whether Speech is the grouping) · types,
  defaults and validation for each · the word-replacement **table editor**, which is a repeating
  from→to grid, not a row control, and so has no precedent in the window yet · whether STT model is
  per-mode (D12 says dictation is the stricter test) or one process-wide value, since the code holds
  one constant today · **and how a model GETS onto the machine** (Thomas, 2026-08-03): download on
  demand, ship it bundled, or point at a file already on disk. Gemma's posture says the user picks
  the model, as they already do for brains; VoiceInk makes the opposite call and hardwires a
  Parakeet download. The reason this is not just another picker: a brain is a **URL and a
  credential**, an STT model is **weights on disk** — so it owes a size, a download progress state,
  a cache location and a part-downloaded failure mode that no provider card has ever needed.
  Note the window's other named gaps live above (AddCard dashed border, roster
  reorder) and are *not* part of this.
- [ ] **Router v2 (Layer 2) + its dependent design.** Several **named instances per provider**: one
  API key, several models, so a user exposes Opus 5 and Sonnet 5 but never Fable. Roles then target
  an *instance*, which makes the per-role `modelKey` override (2026-07-30, spec/70 §3) redundant —
  it folds in and should be removed, not kept alongside. Dependent design owed in the same session:
  the **schema migration** for existing provider cards (this is the risky part — a botched migration
  eats a profile, and one was already lost on 2026-07-31) · per-task-type routing and its classifier
  (short → Groq, long → Haiku) · a **`local_only`** policy, which is also what decides whether a
  retrieval tool's hits may reach a cloud brain (spec/30 §Retrieval). Existing detail: the "Owed —
  router Layer 2" entry below, and spec/20:140.
- [x] **DONE 2026-07-31 (D39) — one app: lifetimes tied, processes NOT merged**, plus the cold start
  split by when each model is first needed. Full account in spec/00; the CUDA and `localhost`
  findings are in NOTES. The two things that outlive it: **spec/50 rule 12 stayed untouched** (a
  `quit` upstream verb was rejected — that channel may only stop work in flight and is
  unauthenticated, so the verb would let any local process kill Gemma), and the **lock** in
  `listen.py`/`speak.py` is load-bearing now that warm-up runs beside a live hotkey.
  ⚠ **Not yet measured on the box** — the 3.8–45.9 s spread was the *before*; the after wants a real
  start with a stopwatch, and an early keypress during warm-up wants trying once.

**Parked, not in the sequence:**
- **Local B2 brain (Ollama)** — deferred. M2 "it's local" and the *local* cleanup-engine option
  (S-06) both wait on it. B2's adapter already exists (D30) and speaks to any OpenAI-compatible
  endpoint, and the router (D33) can already point a role at one — so this is now "stand a local
  server up and pick it", not new adapter work.
  **Stood up 2026-08-01.** Ollama v0.32.5 on the 5080, reached through B2 with no adapter work —
  `qwen3:8b` · `qwen3:14b` · `qwen3.5:9b` pulled and measured (scoreboard in Track D). The runner's
  quirks — the three fields `/v1` ignores, `num_ctx` VRAM figures, GGUF-not-ONNX, the two binaries —
  are in NOTES § Local model runners. The dead **`context` capability was deleted 2026-08-02**
  (Thomas): Gemma cannot set it, so declaring it invited a knob that does nothing. The schema now
  carries a don't-re-add note.
  - [ ] **Owed — a README section on local models.** README has no local-models content at all, so a
    user standing up Ollama has nothing to read. It should say at least: install Ollama · pull a
    model (CLI — Gemma deliberately does not) · Gemma prefills the endpoint and starts the server
    headless if it declares one · **context length is set in Ollama, not in Gemma** (Thomas,
    2026-08-02) · the tray comes from `ollama app.exe`, not the server.
  - [x] **DONE 2026-08-02 — headless Ollama, started and stopped by Gemma.**
    `providers.ensure_local_server()` starts it with no window when a role resolves to a provider
    declaring a **`serve` argv in its card** and nothing is listening; keep-alive 30 min via
    `OLLAMA_KEEP_ALIVE` at spawn. Rationale is in the card's own `$comment_serve` and the
    `local_server_stop_on_quit` `$comment`. Three things worth not relearning:
    - **The safety rule is NOT configurable: only a server WE started may be stopped.** One already
      running when Gemma arrived never enters the registry — it may be doing someone else's work.
      The setting governs only our own. Verified live.
    - **Keep-alive governs a server Gemma starts and cannot reach one the user started**, because
      `/v1` ignores `keep_alive` — so it rides in the spawn environment, not on the request.
    - **run.py ASKS before it insists** (`CTRL_BREAK` → `terminate` → `kill`), because
      `TerminateProcess` runs no cleanup and a tray Quit would otherwise strand the server every
      time. **Still incomplete:** a hard kill skips it; launcher C2 (Job Object) is the full fix.
    - [ ] **Owed — the whole quit chain has never been observed.** Every link is unit-tested with
      fakes and the links have never met: `run.py` → `CTRL_BREAK` → the daemon's `finally` →
      `stop_local_servers()`. Start it, tray Quit, confirm both processes and Ollama are gone.
  - [ ] **Untested: `reasoning_effort: "none"` against a NON-thinking model on Ollama.** Documented
    at the endpoint rather than per model, so it should be a no-op, but a rejected value costs the
    whole turn. One pull of any non-thinking model settles it.
  - **Models NOT worth pulling for cleanup:** anything with a thinking mode (the off-switch is
    provider-specific and may be unreachable through `/v1` — Qwen cost a day), so **Gemma 4**,
    **GPT-OSS** (requires effort *levels*, ignores booleans) and **DeepSeek-R1** are all deferred.
    Untried and worth it: `llama3.1:8b` locally (the model that scores 6/6 on Groq, ~4.9 GB),
    `gemma3:12b` (no thinking at all), `phi4-mini:3.8b` (a cheap punt — if 3.8b suffices, VRAM stops
    mattering). **Qwen3.6 is out**: smallest is 27b ≈ 17 GB, over the card.
- **Launcher / packaging** — tray autostart, launcher option **C2** (Job Object lifetime tie, so a
  SIGKILL of `run.py` cannot orphan children), daemon-death made visible in the tray, and a
  **windowless daemon** at packaging, which is what finally removes the console as a thing to look
  at. *(The **single-process merge** is no longer on this list — D39 considered and rejected it; the
  lifetime complaint it existed to solve is fixed by the launcher tie, and two processes stay
  deliberate for dev: restart only the component you changed.)*
- **Rename `bridge/` → `daemon/`** (S-07). The package is named for the cancelled headset it
  bridged to the brains (D18); it is now just the daemon. Prose is already de-headseted; the
  rename itself is churn (imports · `pyproject` · `checks.yml` · README · spec/00's legend) and
  wants a naturally-churny moment. Frozen docs stay per hard rule 2. The letter **G** survives
  either way — it is "Gemma", not "bridge".

**Owed designs — pick up by mood:**
- **Commands vs auto-detection for spoken lists** (Thomas, 2026-07-31; **gates the D37 pre-pass**).
  VoiceInk uses no list commands — the model renders a list from ordinary speech. **The tell is in
  our own suite:** case ⑧ (`"I need to do three things one call the bank two send the email three go
  home"`) is scored a FAILURE only because the command contract says so; a speaker saying that
  almost certainly wants a list. And case ③'s ambiguity disappears, because nothing has to identify
  a separator. Against: it deliberately loosens the CLEANUP-NOT-REWRITING rule tightened 2026-07-28
  (*"keep the speaker's own structure"*), and detection quality becomes model quality. Wants a
  settings toggle either way, and a conscious reversal rather than a quiet reinterpretation.
  Failure shapes differ usefully: today's failures **delete words silently**; auto-detection's
  failure is **unwanted structure**, which is visible the moment you look at the paste.
- **The dictation cleanup test suite, in TWO TIERS** (Thomas, 2026-07-31). What exists covers list
  formatting and one fidelity sample; the contract in `DICTATION_CLEANUP` names the rest — fillers ·
  self-corrections · spoken punctuation **and its false-positive guard** ("a period of rest") ·
  spelled-out acronyms · layout cues incl. **sign-offs** ("best regards", untested by anything) ·
  word fidelity · never answering a dictated question. Machinery is not new: `_FORMAT_CASES` already
  has the shape `(said, want, unwanted, why)` and `_format_verdict()` now scores it.
  **Two non-obvious parts:** ① **word fidelity cannot be a substring assertion** — compare the
  output's word multiset against the input's, allow deletions, flag **insertions**; that is what
  caught `llama-3.1-8b` scoring 6/6 while deleting "wanted to say". ② **size fights cost** — each
  case is a live call carrying the full prompt (~2k tokens), so a 40-case suite is ~80k tokens per
  model, roughly Groq's entire free daily tier. Hence two tiers: a **short smoke set** behind a
  user-facing button, the **full suite** as a maintainer command. A local model makes the full tier
  free to run.
- **DONE 2026-08-02 — the two-model VRAM note**, as help text inside the Dictate row: two roles on
  different models of one LOCAL provider means the server swaps them, and the failure is invisible —
  no error, just a reload on every switch. Text in the schema (`local_two_model_note`), condition in
  `settings_model.localTwoModelNote`, both guarded. Deliberately **not computed** — judging whether
  both fit would need VRAM totals we cannot see. **A standalone section under Dictate was tried and
  rejected** — the Models pane reads Ask · Dictate and a third peer heading is not the same kind of
  thing (Thomas); don't re-try it.
- **Model presentation — publish MEASUREMENTS, never recommendations** (Thomas, 2026-07-31). A
  curated "recommended" badge is a treadmill: re-earned at every release, and a stale recommendation
  misleads worse than silence. A **measurement** does not rot — "8/9 on 2026-08-01" stays true, and
  anything untested reads **"untested"**, which every new release gets at zero maintenance cost.
  Pair with a **"Test for cleanup" button** beside the model picker, reusing the D30 reachability-Test
  pattern, so a user generates evidence for the model *they* care about — their key, their tokens.
  **Do NOT disallow models** — the evidence is far too thin to block someone's paid model, a
  blocklist rots, and it breaks D30's rule that reachability is schema truth. What needs curating is
  small: the per-role **default**, one per provider, which is also what keeps the picker optional.
- **"Listen to me" / the always-open mic.** Reviving any always-open-mic mode must answer spec/50
  rule 4 truthfully. Thomas' view: a config-time warning that the mic is always on may do the same
  job as a live indicator. Pushback on record: consent to a *capability* is not the same as
  signalling *current* capture — a checkbox cannot reveal a window that failed to close. spec/50
  already separates the always-on wake ring (rule 3, ≤ 3 s RAM, discarded) from triggered capture
  (rule 4), so the argument may hold for the former and not the latter. If rule 4 should change,
  that wants a D-number and a written rationale, not a quiet edit.
- **Partial replies on a brain error.** A failed or blocked stream discards everything received and
  shows a generic apology. Keeping the partial with a fault marker needs a rendering decision (what
  a half-answer plus a fault looks like) — which is why it is parked rather than patched.
- **The conversation / memory model** (surfaced by B-02). History dies at IDLE, one chain. The
  poles are Claude's named persistent **chats** and Siri's **dump-everything-on-close**; Gemma
  wants something between, and it is undecided. It gates the *proper* overflow guard — a proactive
  token count against the model's context window before the call (Anthropic gives no distinct 400
  code for overflow, so an error heuristic cannot do it) — which only earns its keep once
  conversations persist. It also gates the overlay's cross-turn scroll-back (D27).
- **Read-all-when-TTS-on + the wake-phrase config ("listen for me")** — both land at M0.5. The
  `tts` toggle exists (default off); the read-all behaviour behind it does not. D23's "listen for
  me" switch (off = hotkeys only, no wake word and no barge-in; on = both live) is recorded but
  still unbuilt — the config source now exists, so this is buildable whenever it is wanted.
- **The two dead-air gaps (7a/7b).** The island shows the morphing status word until the transcript
  lands, then sits motionless. **(7a) before the transcript appears**: STT latency, plus whether
  LLM cleanup gates the display. Thomas' asymmetry: cleanup latency is invisible in *dictation*
  (you wait for the paste anyway) but visible in the *assistant* path. Contract P already allows
  both ways — `transcript.final:false` is reserved for partials, so raw text can show instantly and
  be replaced by the cleaned version; a verbal slip flashes then resolves, and the brain ignores it
  either way. This is the real reason **Parakeet** matters to Track P: whether it streams partials,
  not its cleanup. Blocked on the Parakeet + `--clean-prompts` (D15) decisions. **(7b) while the
  brain composes**: the longer wait, independent of the above, solvable any time; needs a cue that
  coexists with displayed text, since the status word's slot is taken by then.
- **The `Door` interface split** (review G-06) — the last item on the "duplicated state across
  seams" brief. The Door does two jobs: reporting raw key up/down events AND deciding tap-vs-hold →
  open/close. Job two duplicates the capture lifecycle the *orchestrator* already owns, so
  `close()` has to reach across the thread seam and clear shared flags — the G-06 race and the D24
  "stuck door" bug both lived there. The fix is to **split mechanism from policy**: the Door emits
  only raw key events (a `queue.Queue` of presses/releases — each consumed exactly once, no shared
  flag to clear), and the orchestrator's state machine turns those into open/close. Then
  `Door.open`/`close()` cease to exist and neither race can recur.
- **Latency readout styling** — a confirmed complaint, deferred to a static-screens design pass.
- **Amber limit-warning** (Track D; held on the Design session's sprites) — as a capture nears its
  cap (dictation's 300 s) the overlay should warn. Proposed: the daemon sends seconds-remaining on
  the `mic` message in the last ~30 s; listening bars go amber with a countdown. Choices pending —
  form (countdown / amber-only / word-cue) and threshold.

**Closed sagas, for the record.** Full accounts live in spec/00's D-numbers and in
`docs/01_scoping/Reviews/2026-07-22_2129_Review-adversarial-code-and-spec.md`: the **26-finding
adversarial review** (closed 2026-07-23; produced D24 · D25 · D26 · CLAUDE.md's Rule 0) · the
four-day **answer-display saga** (closed by **D24** — one root cause: the daemon deciding things
only the overlay can see) · the **three same-shape bugs** of 2026-07-22, each "a fact living on
both sides of a seam with one side not told" (closed; the surviving item is the `Door` split
above) · the **M0 acceptance run** (passed; its durable finding — first word ≈ 2100 ms + 45 ms per
output token under generate-then-play, making the old 4 s "gate" a ~42-token reply-length cap — is
recorded in spec/00 §D25 and `spec/schemas/targets.json`).

---

## Config & routing — the settings window + the router

- **BUILT (D40, 2026-08-01) — the settings window re-cut as a system-native surface.** Decision
  and what it amends: spec/00 D40. Designed against `sandbox/settings-claude-style-mockup.html`
  (gitignored; `?copy` edits its prose in place, `?sheet=add|add2|edit|confirm` and
  `?mic=0.7|live` reach the states a screenshot cannot). Built through ~10 rounds of Thomas's
  design review; every offline check green throughout.
  - **`Theme.qml`:** the warm field (reversing the cool-neutral set of 2026-07-26), the four-size
    scale **18/16/16/14**, `controlHeight`, and `danger` split from `pulse` so a destructive
    button is a real red while faults stay berry. The island is untouched — these tokens were
    already the window's alone.
  - **`SettingsWindow.qml` rewritten.** Sidebar generated from `panes` (+ Speech and Dictation as
    unclickable `soon` items); header row carrying the page title, its one action and Windows'
    own caption buttons; Models and Connectors as TABLES, retiring D29's card rosters; the three
    sheets (Add a model, per-model settings, confirm-before-remove). Mono is gone; dropdowns are
    one class with an explicit left/right orientation — left in a table column, where it lines up
    under its heading; right in a row's control slot, against the edge every toggle uses. The
    pane is **Models**, not "Model selection" (renamed in the schema, so the sidebar, the header
    and the row label all followed from one edit).
  - **The icon font is bundled WHOLE** (Thomas supplied it) — the 14-glyph subset was the binding
    constraint. Codepoints re-mapped across the board: the full Symbols font maps the same names
    differently from the old Material Icons subset, so a straight swap would have silently
    changed known-good icons.
  - **A palette rule came out of it, recorded in Theme.qml.** Three separate "flash on hover"
    reports had one cause: a `ColorAnimation` interpolates ALPHA too, so animating a translucent
    token against an opaque one makes the control briefly see-through on the way. `uiEdgeHover`
    and `uiTrackOff` are now the composited OPAQUE values (identical at rest), and the button's
    hover is an opaque step off `surfaceLift`. The rgba tokens that remain are safe because they
    animate against `transparent`, where fading up from nothing is the point.
  - **Guarded:** `settings_check` walks every pane from the schema and still fails on any QML
    warning; the D38 cross-schema guards are intact; `bridge.orchestrator --selfcheck` now
    asserts the persona actually NAMES a switched-off connector (the wiring, not just the
    sentence — verified to fail when detached).
  - **The credential trial (2026-08-01).** `probeStates`/`modelOptions` are caches keyed by
    PROVIDER, but the Add sheet asks a question about an unsaved CREDENTIAL — so a stored key's
    result was read as a verdict on a typed one, and a junk key could present 11 models. Split:
    `settings_model` gained a single `trial` slot (`trialProvider` / `clearTrial`) that never
    touches the provider cache; the sheet reads only that. Consequences, each deliberate:
    **Add** offers nothing until a trial succeeds (a model list only exists after a real fetch,
    so requiring one IS requiring a working key) and **Add model** stays greyed until there is
    also a model chosen · **Test is disabled on Add with an empty box**, because `key=""` falls
    back to the credential store — the stored key answering for the one being added · **on Edit a
    FAILED trial changes nothing**, since the stored key is the working state and a failure is a
    fact about the typed key only (D30's don't-blank-a-picker rule, applied where there is
    something worth protecting); a key is written only when the trial came back `ok`, so a wrong
    key cannot replace a right one, and success says so before you save. Guarded in
    `settings_check` against a warm cache — verified to FAIL when the leak is reintroduced.
  - **UI faults whose lesson lives in the code that carries it:** the `ColorAnimation` alpha /
    transparent-black flash (rule in `Theme.qml`), the row that centred its control on the LABEL
    rather than the row, and the singleton `open_settings` asking Qt via `app.topLevelWindows()`
    instead of trusting our own bookkeeping (which fails **open** every way it goes stale). The
    fourth — never bind `font.weight` to a state — is cross-cutting and now in NOTES § PySide6.
  - **Removing a model deletes its key by default (Thomas, 2026-08-01).** The confirmation carries
    a checkbox, **on** by default: the credential store is where GEMMA keeps its own key, not a
    shared vault another app reads — you would paste the key into that app and it would keep its
    own copy — so a key left behind after a removal is litter, not convenience. The checkbox shows
    only for providers that HAVE a key, and the credential is cleared BEFORE the provider is
    dropped, because `setKey` looks the credential's name up in the catalogue. Re-adding cannot
    corrupt anything either way: `keyring.set_password` overwrites the entry for
    `("gemma", <provider>)` rather than appending. **Verified live** — OpenAI removed, gone from
    `settings.json`, `primary` fell back to Anthropic, and the credential really was deleted.
  - **Two Add-flow bugs, one of them serious.** (i) The sheet is built ONCE and reused, so the key
    `Field` owned its own `text` — `addKey = ""` reset only the window's copy and the box came back
    pre-filled. Cleared explicitly on every entry point now. (ii) **`addProvider` discarded the
    entire form.** A QML object literal crosses into Python as a **QJSValue, not a dict**, so its
    `isinstance(config, dict)` check was always false and `entry.update(config)` never ran — every
    value the form collected was thrown away and the SCHEMA FALLBACKS stored instead. It surfaced
    as "the model I picked is not selected" only because OpenAI ships no offline list so its
    fallback is `""`; on Anthropic the fallback is a real id, so the wrong model would have been
    stored silently. **Anything added before this fix holds fallbacks, not choices** — worth
    opening the row menu on each existing provider once. Guarded: `settings_check` drives
    `commitAdd` through the real window and asserts the chosen model survives (fails on revert).
  - **One status line in the key form, not two:** "Add a key…" -> "Press Test…" once something is
    typed -> "N models available" or "The provider rejected that key."
  - **Adversarial fix pass, 2026-08-02** — 33 findings over the D40 window + the D38/model
    interfaces, confirmed set cleared in one batch, all 24 checks green. **Full account:**
    `docs/01_scoping/Reviews/2026-08-02_0212_Review-adversarial-settings-window-tool-interfaces.md`.
    Two consequences that do not live in that file: **anything added before the `addProvider` fix
    holds schema fallbacks, not the choices made** — worth opening each existing provider's row menu
    once; and the "caption buttons stay live behind a sheet" fix was **reverted** — it needed a hole
    in the scrim, which broke click-to-dismiss and left the page interactive, so a modal that
    briefly owns the whole window is the lesser evil.
  - **Temperature is now a real control** (Thomas): plumbed for the three local providers that
    declare the capability (Ollama / LM Studio / llama.cpp), written as a **number**, carried by
    `router.resolve` → `build_for_role` → `CompatBrain(temperature=…)`. No longer stamped as the
    string `"0.7"` onto every provider. `context` stays unsurfaced (unsettable through `/v1`).
  - **Owed:** nothing on this pane — the Add flow (cloud AND local), Edit, the remove confirmation
    and the sheets are all driven by `settings_check` end to end now.
  - **PARKED — the tool-activity indicator** (the surviving half of D38 item 9; the connector-cards
    half was absorbed into D40's table). Contract P's `tool` message, decode's reducer and
    `overlay.tool` are built and guarded; **nothing on `Overlay.qml` draws it.** Deferred by
    Thomas (2026-08-01) until there are more tools: it needs a design pass on the ISLAND, and
    with four Tier-1 tools there is not enough of a tool round to design against. The knot when
    it resumes: during a tool round the status-word slot already reads "Thinking…", which is the
    7b dead-air problem in another costume.

- **Built — D29** (the schema-driven settings window: every knob is a `settings.json` edit, guarded
  by `settings_check`) · **D33** (the router v1: role → configured provider+model, read fresh each
  turn, adapter rebuilt only when `router.signature(role)` changes — so the picker drives the
  daemon with no restart). Full accounts in spec/00; the config surface itself is spec/70.
- **Built — the config source:** `%APPDATA%\gemma\settings.json` via `bridge/settings.py`, written
  by the window and re-read by the daemon each turn (D28).
- **Built 2026-07-28 — the dictation Engine card is live.** Engine dropdown resolved by the router;
  "Tidy dictation" off skips the transform and pastes raw, and skips the `transforming` state too
  (showing "Tidying…" while nothing tidies would be a lie). Guarded in the orchestrator selfcheck.
- **Owed — the window is below par** (Thomas, 2026-07-28). Named gaps: the AddCard dashed border
  (Qt), roster reorder, and the settings not surfaced at all yet — **STT model · wake phrase · TTS
  voice · word-replacement** (spec/70 §3).
- **Owed — router Layer 2** (explicitly out of v1): several instances per provider + the
  roles/routes redesign (spec/70) · per-task-type routing and its classifier (short → Groq, long →
  Haiku) · a `local_only` policy. B1's `effort`/`thinking` stay unwired until M0.5, so `effort`
  currently reaches only B2.

## Track G — Bridge (Doc 04 → **M0 ✅**, M1, M2)

- **Works now:** steps 0–7 built and `--selfcheck`-green. `bridge/`: `config.py` (loads
  `spec/schemas/*`, hard rule 3) + `log.py`; `audio/wake.py` (mic → ≤ 3 s RAM ring →
  openWakeWord); `audio/listen.py` (wake → Silero VAD → faster-whisper `small.en`, GPU when
  loadable else CPU); `audio/speak.py` (earcons + Kokoro TTS, 24 kHz; `OutputPump` = the
  persistent warm output stream, spec/40's BT keep-alive); `brains/` (Contract B — see Track B);
  `tools.py` (Contract T — see Track T); `orchestrator.py` (the spec/40 state machine —
  listen → think → speak, barge-in, the ≤ 2-sentence speak/hold heuristic (`sentences()`, retired
  at M0.5), the dictation branch, the Tier-1 tool loop, per-turn latency logs). The daemon keeps
  **one event loop for the process** (`_run_async`), not one per turn — recorded in spec/20 as an
  adapter-lifetime guarantee the orchestrator owes. `serve()` stays synchronous on purpose: mic,
  wake model, VAD, whisper and Kokoro are all blocking C calls, so an async `serve()` would starve
  the loop unless every one moved to an executor. Cross-platform per D10. Run instructions:
  `README.md` · GPU setup, benchmarks, quirks: `NOTES.md`.
- **DONE 2026-08-04 — the boot preload: local weights are pulled at start-up, not on the first
  turn.** `_preload_local_models()` sends one throwaway one-token `transform` to every LOCAL model a
  role names, deduped by (provider, model). Amends D39 in spec/00 (a third warm-up tier). Four
  things worth not relearning:
  - **It runs AFTER `_ready` is set, outside `_warm`'s try/finally.** Inside it, the ~9 s per model
    would be added to the window in which D41 DROPS every door press — a slow first answer traded
    for no first answer. Running late costs nothing: a press in those seconds waits for the same
    load it would have waited for anyway.
  - **Through `transform`, not `converse`** — the verb already pins temperature 0, no tools, no
    history and, the part that matters, **never reasons**, so a thinking model cannot spend a
    minute deliberating over a warm-up ping.
  - **Cloud is skipped**, same rule as `_warn_missing_models`: no weights to pull, and the request
    would be billed. The selfcheck asserts this — it is the one that costs money when it breaks.
  - **The role's CACHED builder is used where one exists** (`_assistant_model` / `_cleanup_model`),
    so the adapter warmed is the adapter the turn uses, connection pool included. A role without
    one (`cleanup_prompts`) gets a throwaway, which still warms the runner — where the 9 s lives.
  - [ ] **Owed — unseen live.** Headless cannot show the thing it removes. Wants one start, then a
    local "what time is it" straight away, with the log's `preload:` line read beside it.
- **Works now — startup (D39, 2026-07-31).** `run()` warms in two tiers: wake + VAD before serving,
  whisper + Kokoro on a background thread, so the **hotkeys register early**. The lazy inits in
  `listen.py`/`speak.py` are lock-guarded — that is what makes an early keypress safe now that
  warm-up is concurrent. Kokoro is not preloaded (`tts` off by default) and whisper loads
  `local_files_only` first. Lifetime: `run.py` ties a clean exit of either process to the other, and
  spares the survivor on a crash. **Owed: measure the new start on the box** (before was 3.8–45.9 s).
- **Works now — the two doors (D20).** `bridge/hotkeys.py`: a combo-string parser (`ctrl+alt+1`
  ask · `ctrl+alt+2` dictate; env `GEMMA_HOTKEY_ASK`/`_DICTATE` until the settings window surfaces
  them — a modifier-less binding is rejected, it would be swallowed everywhere you type) → Win32
  `RegisterHotKey` + a `GetMessageW` pump on a daemon thread → per-door `start`/`end` events.
  Hybrid per key: tap-toggle, or hold ≥ 0.5 s for push-to-talk with the release as the endpoint.
  **Narrow registration, no keyboard hook** (spec/50 rule 11); the cost is a per-OS seam, and
  **macOS is unbuilt** (Carbon `RegisterEventHotKey`), where the wake word stays the only entrance.
  `capture_over()` implements the endpoint rule — **the key ends a keyed turn, not the 1 s silence
  cut**; nothing-said and the runaway cap still do. `--auto-end` (default off) puts the silence cut
  back for one-tap use. Proven live: `ctrl+alt+1` driven through `SendInput`, confirming the OS
  actually delivers.
- **Works now — the replay harness** (`tests/replay.py`): recorded WAVs through the real wake/VAD/
  STT pipeline driving the real orchestrator with fake mic/pump/brain/TTS, plus a per-turn latency
  table. Four keyed cases — `key_short` · `key_long_pause` · `key_hold` · `key_silence` — **4/4
  green on the PC, all four transcripts verbatim**. `key_long_pause` (a deliberate 2–3 s pause,
  12.75 s captured in one turn) is the only real-speech test of `capture_over`, which the wake
  word's 1 s silence cut would have truncated; `key_hold` exercises push-to-talk. A keyed case's WAV
  is recorded between two real presses (`_record_keyed`, which dogfoods `bridge/hotkeys.py`), so the
  clip *is* the capture window and its end *is* the endpoint. The three wake-word cases were removed
  when D23 made the wake word default-off (an opt-in config, and a false-accept test is meaningless
  when nothing is listening); barge-in returns as a **wake** case if that switch is ever built. Old
  definitions are in git and the WAVs are still on disk, so a revisit costs no re-recording.
  **Deviation from docs/04 §7:** replay does NOT run in CI — the WAVs are Thomas's voice and
  deliberately untracked (`tests/replay/wav/`, gitignored; copy the folder to the Mac clone by hand).
  Replay latency figures are harness figures (cold STT load, fake brain, fake TTS), never acceptance
  numbers.
- **Owed — replay coverage gap.** Removing the wake cases took `wake_barge` with them, so
  **barge-in has no replay case at all**, and the **key-interrupt** path (pressing the ask key
  mid-reply) has none either. Both want one; the key-interrupt case *can* be keyed, if the harness
  can script a second press mid-reply.
- **Owed — a press while the brain is streaming** is still queued rather than acted on:
  `_collect()` owns that window inside asyncio and the ask key is not polled there (Esc is, via
  D24's cancellation seam). Noted in code. *Re-check against D31's tool loop, which reshaped
  `_collect`.*
- **Owed — Mac parity (D10):** the full-loop live test and a 4/4 replay run, plus real-speech STT
  figures for the provisional D11 numbers. Watch items for that run: earcon ring-out bleeding into
  VAD on open speakers · BT A2DP↔HFP duplex behaviour (a BT earbud's mic use may degrade its
  output) · barge-in false-trigger rate on speakers (knob: `BARGE_CHUNKS` in `orchestrator.py`).
- **Post-M0 (D14/D15):** the word-replacement layer wired into the assistant path · the
  `--clean-prompts` experiment (after the Ollama groundwork; A/B ~20 real transcripts + a latency
  row). *(The overlay session view shipped as D27 for the current turn; cross-turn scroll-back waits
  on the conversation/memory model.)*
- **In flight:** —

## Track P — Teleprompter (Contract P) — built and live; in polish

- **DONE 2026-08-03 (D43) — two dwells: a confirmation goes in 2.5 s, an answer stays 20 s.**
  Full account in spec/00 D43; the behaviour is spec/40 § state machine, the settings spec/70 §3.
  `status.json` v0.8.0 (`response.dwell`). Guarded in `overlay_check` (**verified to FAIL** when
  the selection is reverted to one interval) · `decode` · `orchestrator`. Three things worth not
  relearning:
  - **The daemon sends a WORD, never a duration.** `quick`/`slow`, and the overlay turns it into
    seconds using the user's setting. Putting milliseconds on the wire would have quietly moved
    the user's preference into the daemon, which cannot see the screen — the D24 mistake again.
  - **Every default lands on the LONG dwell.** Absent field, junk setting, value outside the enum:
    all `slow`. An answer blinking away mid-read is the failure that matters; a confirmation
    overstaying is merely annoying, and Esc already dismisses it.
  - **A REFUSED Tier-2 call does not count as acting.** It announces (a `failure` ping) but its
    reply explains why nothing happened, and that is something to read.
  - [ ] **Owed — unseen live.** Both dwells have only run headless, where the timer's interval is
    read rather than watched. Wants one "open Spotify" and one ordinary question, side by side.
- **DONE 2026-08-02 (D41) — the boot island**: a `booting` state (status.json v0.7.0) drawn as a
  narrow pill with the shared `Spinner.qml`, and door presses **dropped** until warm-up finishes.
  Full account in spec/00. Guarded in `overlay_check` · `decode` · `orchestrator` (the gate defaults
  open, so replay is never gated). **Unproven live** — the two-process boot timing it exists to fill
  is exactly what headless cannot show.
- **DONE 2026-07-30 — dropdowns standardised to two classes** (WORDS vs a MACHINE VALUE; the class
  picks face and size together, and `Dropdown.fontPx` is readonly so a call site cannot invent a
  size). Rule: spec/70 §2.
- **DONE 2026-07-30 — the Test button was swallowed by an in-flight probe.** `force` now overtakes
  one, and a per-provider generation counter makes a returning worker prove it is still the newest
  before it writes. Guarded deterministically in `settings_model` (both probes faked, returned out
  of order).
- **DONE 2026-07-28 (D34) — model + token count in the peek footer** (`response` gains optional
  `model`+`tokens`, status.json v0.5.0). Full account in spec/00. **Owed:** live on the box — peek a
  real answer and read the footer.
- **Works now:** the island renders real turns end to end (key → STT → brain → Teleprompter → TTS).
  `teleprompter/`: `decode.py` (Qt-free NDJSON framing + reducer, loading `clearsTurn`/`upstream`
  from `status.json` rather than restating them) · `model.py` · `feed.py` (QTcpSocket + reconnect +
  a mic watchdog + `send()`, the one upstream verb) · `Overlay.qml` · `PeekPanel.qml` · `Theme.qml`
  (design tokens, a `pragma Singleton`) · `SettingsWindow.qml` + `KeyRecorder.qml` · `tray.py` ·
  `gem.py` · `settings_model.py` · `__main__.py`. Back end: `bridge/broadcaster.py`, a
  crash-isolated localhost NDJSON publisher (`publish()` never blocks or raises; a busy port
  disables it; the daemon is an always-up server, the overlay a reconnecting client) with a
  `--fake` driver that drives the whole overlay with **no audio, mic or models**. It retains the
  current turn and replays it to a client that reconnects mid-turn (P-02). PySide6 is a **core**
  dependency (D23). Fonts are bundled and registered at run time — **Inter** (the UI face; Archivo
  was swapped back out on 2026-07-31, Thomas) · Martian Mono · Lucide (icons), with Instrument
  Serif bundled but deployed nowhere — so there is no system install and the Mac
  gets the same faces (D10). Guarded by `teleprompter.overlay_check` (headless, software RHI),
  `decode --selfcheck`, `settings_check` and `teleprompter.gem`, all CI-wired.
- **The locked design** lives in spec/40 §Visual output: the island fused to the top screen edge,
  mic-driven bars, typewriter text, no controls (D22 — the ⌄ handle was built, seen in place, and
  **cut**). Windows gotchas are in NOTES.md. Three hard-won facts worth not relearning: a
  non-activating window *can* take clicks without taking focus · **`QWindow.setMask()` must NOT be
  used** for click-through — Qt documents it as an input hint, but on Windows it is `SetWindowRgn`,
  which clips *painting* too · and the **window itself never animates** (a native resize lands a
  frame apart from the scene graph, so newly exposed area paints late) — it is a fixed transparent
  frame and the island animates inside it, which is why `WS_EX_TRANSPARENT` is load-bearing.
- **Built — D24** (the island owns the display: prompt hand-over, self-hiding dwell, bare-Esc
  `DismissKey`; verified live 2026-07-22) · **D27** (the peek — hover→click expansion, Copy/Save,
  per-region `WM_NCHITTEST`, amends D22) · **D32 → superseded by D35** (Gem's first surfaces) ·
  **D35** (sprite kit v3, the tray's mic ring, Gem on the island behind `gem_in_island`). Full
  accounts in spec/00. Design constraints that outlive them are in spec/40 §Visual output and the
  Windows gotchas above.
  - **Owed — unproven live:** D27's hover→click→peek path and per-region hit-test have only run
    offscreen with no real mouse · D35's tray ring against a real mic, the taskbar icon, and Gem
    miming a real turn. Headless cannot show any of them.
  - **Owed — the sprite lab:** `needs-permission/granted` f5 (the falling lock) loses 5px off the
    bottom to the 26px crop. Design says flag it and leave it — it wants a human pass.
  - **Open (Thomas):** whether Gem stays on the island at all — "more professional" without her.
    The switch already carries either answer; only its **default** would change.
- **Settled (2026-07-21) — mic cues.** Barge-in detection is the **same species as the wake-word
  watch** — "always-on mic", not a capture window. `status.json`'s `mic` message means a capture
  window is open; wake-watch and barge-in deliberately emit none. No mic cue while Gemma speaks.
- **Owed — the Contract P gap (from D20).** Two surfaces D20 introduces still have no message type:
  the dictate-door **overwrite warning** (dictate invoked while text is selected) and the ask-door
  **propose-then-tap proposal** (a write action pending a confirming keypress). Neither fits
  `response` (a streamed reply, not something pending), `error` (a fault), or the `state` enum. Add
  each when its producer lands — deliberately not built speculatively.
- **In flight:** —

## Track B — Brain (Contract B)

- **Works now — B1** (`brains/claude.py`): the Anthropic adapter — async streaming, tool
  translation, and error mapping **by exception type + status code, never message prose** (B-02;
  a 400 → generic apology, because Anthropic gives no distinct code for context overflow — both are
  `invalid_request_error`). Smoke test green on Windows (auth, streaming, tool-call, tool-loop).
- **Works now — B2** (`brains/compat.py`, D30): **one adapter for any OpenAI-compatible endpoint,
  cloud or local** — which is every provider the settings window offers except Anthropic, since the
  only differences are a base URL and a credential. spec/20's B2 row was widened rather than a
  fourth row added, so **M2 "it's local" is now a question of which endpoint it points at**.
  Reachability is schema truth (`settings.json` `wire`/`api`/`env`/`adapter`, read by
  `brains/providers.py`): no adapter hardcodes a host, key name or model id. Live model lists come
  from `GET {api}/models` off a worker thread, with a schema `not_chat` list dropping ids that
  cannot serve a turn (Groq returns 15, of which 7 are speech/TTS/safety; OpenAI 129, including
  embeddings and images). Fetching the list *is* the key test, so `probe()` returns `(ids, status)`
  over a closed set (`ok · nokey · auth · unreachable · empty · error`) — otherwise a wrong key and
  a dead network are the same empty picker — and it tests the **typed** key, not the stored one.
  **Verified live: Anthropic (11) · OpenAI (108) · Groq (8)**, plus a wrong key reading `auth` and
  an absent key `nokey`; the remaining providers share the exact code path, untested for want of
  keys. Keys are spend-capped and live in the OS credential store (spec/50 rule 10).
- **Works now — `transform`** (dictation cleanup, D12's "transform, never answer"): a **free
  function over any adapter's `converse`** (`brains/base.py`), not a per-adapter method. A transform
  is a constrained conversation (guardrail system prompt, no tools, no history, buffered), so it
  reuses every adapter's streaming, error taxonomy and lifetime, and works on Groq, Claude or local
  identically. Returns `(text, Error|None)`. Two per-call overrides ride on `Session`:
  `max_tokens`, so a long dictation isn't truncated at the 1024 spoken cap, and `temperature`, so
  cleanup runs deterministic.
- **Model-agnostic by rule** (2026-07-25): neither adapter carries a default model, and a modelless
  turn yields a clean `Error("unknown", "no model chosen…")`. The daemon's fallback lives in
  `orchestrator.DAEMON_MODEL` (env-overridable), not in an adapter. spec/20 records the rule. Model
  choice is now the router's job (D33 — see Config & routing).
- **DONE 2026-08-03 (D44) — the catalogue spells every wire knob; no adapter does.** Full account
  in spec/00 D44, rule in spec/20. Three faults of one family in one night, all on OpenAI:
  `max_tokens` → `max_completion_tokens` · a stale stored `temperature: 0.7` going out to models
  that take none · tools+reasoning rejected. **The third is the one to remember**: dropping
  `reasoning_effort` did NOT fix it — the model reasons at its own default when the parameter is
  absent, and the request is rejected identically. The card must *set* `tool_round_effort: "none"`.
  The provider's error message said so from the first log; two guesses were spent not reading it
  literally.
  - **The diagnostic that ended it: log what we SENT on a rejection.** Parameter names and scalars,
    never `messages` or the tool bodies. It found fault three on its first run by showing a
    parameter we were *not* sending inside an error that named it. Worth keeping forever.
  - [ ] **Owed — live-verify OpenAI once more.** Fixed in source and green offline; the box has
    never seen a successful OpenAI tool turn. Anthropic, Groq and Ollama all pass end to end.
  - **Accepted consequence:** an OpenAI tool turn does not reason. `/v1/responses` is the route
    that would restore it — a third wire beside `anthropic` and `openai`, parked.
- **Owed — the first-token re-measure.** The recorded **1817 ms** ran with `chunks=1` (the whole
  short reply in one chunk, so first ≈ total) — really "time to full short response", cold, and well
  above the ~300–900 ms ballpark in `b1_smoke.py`. Re-run with a longer streamed output; it feeds
  the provisional D11 numbers.
- **In flight:** —
- **Next:** ① install Ollama on the 5080, pull one small model, sanity-check tokens/sec — B2
  groundwork, with no commitment to a final model (that is the M2 bake-off, and the engine for the
  D15 `--clean-prompts` experiment) · ② **M0.5 "It speaks well"**: the voice output contract —
  a model-tagged spoken/held split (retiring spec/40's sentence-count heuristic), a versioned
  persona prompt (persona = template + a capability clause derived per turn from the filtered tool
  list, never a static claim, which would go stale at M1), speech normalization, and a B2-tolerant
  parse. Consumed by the orchestrator.

## Track D — Dictation (spec/00 D12 → MD)

- **Works now (D1, 2026-07-25) — the dictate door, end to end.** Dictate key → `_capture` (shared
  with the assistant, key endpoint) → `transcribe` → `transform` cleanup → **paste at the caret**
  (`bridge/paste.py`: clipboard + synthetic Ctrl+V via stdlib ctypes, daemon-issued because the
  overlay never holds focus; the prior clipboard text is restored). Dispatch is by **`door.name`**
  in `_pressed()`, which has two callers (`serve` and `_speak`), so a dictate press mid-reply cuts
  TTS and dictates rather than being fed to the brain. Cleanup is an **enhancement, not a gate**: on
  failure the RAW transcript is pasted, so dictation works with no key and nothing leaves the
  machine. Verified end to end on the recorded WAVs. Behaviour spec: `spec/60_dictation.md`.
- **Works now (D2, 2026-07-27) — the overlay states, both sides.** Contract P gained
  `transcribing` · `transforming` · `pasted` (`status.json` → v0.4.0) and the overlay renders them:
  a steady status word, then a latched **"Pasted ✓"** beat that dwells `Theme.durationPasteDwell`
  and hides itself. `bodyText` is forced empty during dictation so a stray transcript cannot leak
  into the prompt slot, and the transcript is broadcast `mirror=False` (trace only), so dictation
  text never shows on the island nor joins the assistant's prompt history.
- **Cleanup quality (2026-07-28, committed in `13d60f5`).** `DICTATION_CLEANUP` was rebuilt from a
  one-liner to VoiceInk's structured editing rules (self-corrections like "scratch that"; spoken
  punctuation and layout cues, open-ended with a false-positive guard), then **tightened to
  CLEANUP-NOT-REWRITING** (Thomas: it was adding words and could shift emphasis — "that's the idea"
  → "the main idea"). It is now a DO / DO NOT split: never insert words the speaker didn't say, no
  new qualifiers or intensifiers, don't change meaning, emphasis or strength, keep the speaker's
  structure — plus an **acronym-join** rule (spelled "S I L E" → SILE). Groq
  `llama-3.1-8b-instant`, temperature 0. Study: VoiceInk's cleanup — **ONE call, the whole
  transcript, no chunking**. Dictation's runaway cap is 300 s (`DICTATION_MAX_CHUNKS`), not the
  assistant's 30 s (fixed in `c091a65`).
  **⚠ Committed but UNTESTED against live speech** — restart the daemon, dictate, and confirm it
  stopped adding words.
- **Works now (D15 word-replacement, 2026-07-28).** The deterministic find-and-replace seam is
  filled: `spec/schemas/word_replacements.json` (whole-word, case-insensitive, literal `to`),
  applied by `bridge/replace.py`, hooked in `_dictate()` right after STT — so it runs BEFORE
  cleanup and applies even when cleanup is off (deterministic fixes are never skipped). Empty table
  = no-op; ships one entry (`gemma`→`Gemma`). Selfchecked + CI-wired (`python -m bridge.replace`).
  A curating UI is a later lift (spec/70 §3); the fuzzy `<CUSTOM_VOCABULARY>` prompt half of #2 is
  still parked.
- **Works now (D37, 2026-07-30) — spoken formatting commands.** `enumerate list` (numbered) /
  `itemize list` (bulleted) / `end list`, with items separated by spoken counting ("one", "two") —
  the ordinals are separators, deleted, never the printed marker. Lives in `DICTATION_CLEANUP`, so
  detection is prompt-side and there is no new module: a formatting command restructures a *span*,
  which D15's word→word swap table cannot express, so `replace.py` is deliberately not its home
  (confirmed before building). **Dictation only.** Behaviour spec: spec/60 §Spoken formatting
  commands. `python -m bridge.orchestrator --check-format` runs the 9 cases live; the offline
  selfcheck asserts only that the prompt still *states* the contract, because a prompt is where the
  detection is. Deferred: a literal escape for a command phrase, parked until spoken quoting.
  - **A 30-case adversarial sweep (2026-07-30) broke the first cut**, 4 hard failures — and the
    5 shipped cases all passed while they broke, because none contained the trigger word for word.
    (a) the phrase VERBATIM inside prose fired ("the statute requires us to enumerate list items"
    → a list); (b) reported speech fired ("he told me to itemize list everything"); (c) **spoken
    counting with no command at all formatted** ("I need to do three things one call the bank two
    send the email" → a list) — the most damaging, since that is ordinary speech; (d) bare ordinals
    both formatted and LOST words ("list one is the priority" → `1. is the priority`). Fixed with
    three prompt rules: ordinals are inert unless a list is open · a phrase is a command only where
    the speaker is issuing it, not inside a sentence doing something else · never emit an empty
    marker and never drop words to make a list fit. All four are now committed cases, so they
    cannot regress silently.
  - **THE OLD SCOREBOARD WAS MEASURED WITH A BENT YARDSTICK — VOID.** Every figure recorded before
    2026-08-01 (70B 5/5 · `gpt-4o-mini` 8/9 · 8B 6/9) came from a `_check_format` that compared
    `want` **case-sensitively** against the raw output while comparing `unwanted` case-INsensitively
    against a lowercased one. The `want` entries are lowercase in the data, so a model that
    CAPITALISED a wanted phrase was marked failed — and the prompt *requires* capitalisation. The
    suite was penalising correct behaviour, and worse, **rewarding models that left everything
    lowercase**, which is one of qwen3:8b's actual defects. Fixed 2026-08-01: the comparison is now
    the pure `_format_verdict()`, case-insensitive on both sides, guarded in the offline selfcheck
    (extracted precisely so it could be — inline, it needed a live model and so was never tested).
    Do not quote the old numbers against the new.
  - **Scoreboard, re-measured 2026-08-01 with the corrected scoring.** Local runs repeated ×3 and
    identical every time (temperature 0 is genuinely deterministic). Format = the 9 `_FORMAT_CASES`;
    fidelity = 6 checks on one realistic dictation, plus a word-level diff.

    | model | format | fidelity | words dropped | warm |
    |-------|--------|----------|---------------|------|
    | `groq/llama-3.3-70b-versatile` | **9/9** | **6/6** | none | ~0.24 s |
    | `ollama/qwen3:8b` | **9/9** | 5/6 (`you know`) | none | ~0.44 s |
    | `ollama/qwen3.5:9b` | 8/9 (case 3) | 5/6 (`you know`) | none | ~0.45 s |
    | `ollama/qwen3:14b` | 7/9 (cases 3, 6) | **6/6** | none | ~0.61 s |
    | `groq/llama-3.1-8b-instant` | 6/9 (3, 8, 9) | 6/6 | **`wanted to say`, `and think`** | ~0.15 s |

    **`llama-3.3-70b` is the only model clean on both halves.** `llama-3.1-8b` scores 6/6 on every
    surface check *while deleting a clause* — caught only by the word diff, which is the whole
    argument for that check. No model INSERTED a word; the shared `{clause, not, one}` deletion is
    the licensed residue of the self-correction.
  - **Case 3 fails on every model but 70B and is probably unfixable.**
    `"enumerate list one buy two apples two get milk end list"` — two identical `"two"` tokens, one
    a separator and one content. No rule resolves it; a Python pre-pass faces the same ambiguity
    (first-match and last-match are each wrong about half the time). It is a *protocol* problem:
    the fix is separators distinct from content ("number one", "next"), which is a spec/60 change.
  - **Benchmark one model at a time, fully resident.** A combined run cycling five models over 16 GB
    produced a different score for qwen3.5:9b (7/9, failing case 2) than three isolated runs did
    (8/9 every time). Partial CPU offload under memory pressure changes the numerics.
  - [ ] **FIX — owed, wants its own session.** Options, in the order recommended:
    - [ ] **FIRST, AND IT GATES THE REST — drop the commands entirely?** See the parked design
      question (auto-detection vs commands). With no commands there are no phrases to detect and
      no separators to strip, and case 3's ambiguity disappears with them.
    - [ ] **Deterministic pre-pass** — *only if the commands stay*. Detect `enumerate list` /
      `itemize list` / `end list` and the ordinal separators **in Python**, mark the spans, hand
      cleanup text it cannot misread. **Fixes 2 of the 3 failure kinds, not 3** — the false
      positives vanish by construction, case 3 survives (above). Note `bridge/replace.py` still
      does **not** belong here — a swap table cannot express a span (confirmed 2026-07-30).
    - [ ] Re-run the suite on whatever model is chosen; promote any new failure into
      `_FORMAT_CASES` as the earlier four were.
  - Also seen on BOTH small models and NOT covered by the assertions: a verbatim-mention case keeps
    its prose but drops a word — 8B returned `"the statute requires us to list items"`, losing
    "enumerate". Cleanup word-fidelity, not D37's formatting contract — same family as the
    untested-against-live-speech note above.
  - **Still owed: a real keypress + voice**, same gap as the rest of Track D.
- **Owed — the live keypress test.** The whole dictate path (D1 + D2) has been verified against
  recorded WAVs and selfchecks, but never once by Thomas pressing the key and speaking. Every
  hotkey path is like this; `RegisterHotKey` is proven live separately.
- **Parked deepening (VoiceInk-derived), in rough value order:**
  - **#2 custom vocabulary** — the deterministic word-replace seam (D15) is **done** (see the
    Works-now note above). What remains is the fuzzy `<CUSTOM_VOCABULARY>` block — a prompt-side
    spelling authority for names/acronyms Whisper mis-hears in ways the exact table can't predict.
    Still the highest-value prompt-side lift.
  - **#3 live context** — inject clipboard / selected text as context blocks (VoiceInk's Power
    Modes). Both are cheap on Windows; screen-OCR is the high-effort, low-reliability piece,
    deferred per the design-time "skip screen-OCR" call.
  - **Formatting settings** — a deterministic typography layer AFTER cleanup (double space after a
    full stop [Thomas's], em/en dashes, curly quotes — regexes, not prompt lines), plus a
    user-editable cleanup prompt.
  - **Chunking long dictation — RESOLVED: don't.** A single call is correct at our lengths (~1k
    tokens, Groq ~1–2 s) and higher quality (no boundary artefacts); VoiceInk agrees. Revisit ONLY
    if dictations reach thousands of words → split at PARAGRAPH boundaries, never mid-thought. Live
    per-sentence cleanup is parked with the same trigger.
- **Design settled 2026-07-18 (D12; study:
  `docs/01_scoping/Reviews/2026-07-18_1643_Review-gemma-voiceink-codebases.md`).**
  **Trigger-is-the-mode** — hotkey = dictation, wake word = assistant · cleanup via the Contract-B
  `transform` verb · cleanup engine = **Groq** (cloud, fast and cheap; revises D15's local-model
  note) · STT and TTS stay local · delivery = clipboard + synthetic Ctrl+V, deterministic and
  user-initiated, never a Contract-T tool · capture stays in RAM (spec/50 rule 3) · the STT model is
  per-mode config, dictation being the stricter quality test · the shared deterministic
  word-replacement layer (D15) runs before `transform` here and before the brain in the assistant
  path · **rewrite (D20)** is an *ask-door outcome*, not a mode — propose-then-tap on the
  Teleprompter, `auto_apply` default off, slice D3.
- **In flight:** —
- **Next:** ① **test the tightened cleanup prompt live** (committed, above) · ② the parked deepening
  (#2 vocabulary first) · ③ measure `large-v3-turbo` vs `small.en` vs **Parakeet** (sherpa-onnx =
  a torch-free ONNX path; **gated** — adopt only if a real win, discuss first) on the 5080 for the
  per-mode STT default; a parallel session is on Parakeet · ④ **D3**: the ask-door rewrite (D20,
  propose-then-tap). *(D15 word-replacement — done 2026-07-28, above.)*
- **Deferred at design time:** voice-switch into dictation ("take dictation") · per-app modes
  (foreground-window detection) · streaming partials · browser-URL and screen-OCR context blocks.

## Track T — Tools (Contract T → M1)

- **Works now (D31, 2026-07-27) — the Tier-1 executor, and the brain loops over it.**
  `bridge/tools.py` executes Contract T, and the assistant turn (`orchestrator._collect`) is a
  multi-round tool loop. Two read-only tools have backends: `system_status` (time · active window ·
  battery; volume and media playback need COM/WinRT, deferred) and `read_clipboard` (reusing
  `bridge/paste.py`). The brain is handed only implemented, in-tier tools (`tool_specs()`,
  `MAX_TIER=1`), so it cannot name a tool that isn't wired; `execute()` re-checks the allowlist as
  the defence (spec/50 rule 1). Every call — run, refused or errored — is one JSONL line in
  `logs/audit.jsonl` (spec/30 rule 2), purged with `logs/`. The loop: `converse` surfaces
  `ToolCall`s and never executes them, the orchestrator runs them, and each adapter's
  `record_tool_round` serialises the round into history in its own wire shape (Anthropic blocks /
  OpenAI `tool` messages), re-entered with an empty utterance until the brain answers; one retry on
  `malformed_tool_call`, a 5-round cap, history committed only on success.
- **Works now (2026-07-28) — `find_document`, the third Tier-1 tool** (ROADMAP #11, first slice).
  "Find the document about X [from this day]" → one query against the **Windows Search index**
  (`SystemIndex`), back as up to eight ranked hits, `name · date · path`. The model composes
  `query` (+ optional `kind`, `since`) from the utterance; the tool retrieves and opens nothing.
  Ranked rather than date-sorted — a date sort floats anything that merely *contains* the words
  (a word-list file matches everything) above the document actually about them; `since` covers
  "from this day". Verified live on the box against real documents.
  Implementation: the index's provider (`Search.CollatorDSO`) is OLE-DB, so ADO is the only route
  and the stdlib has no COM — reached via **PowerShell COM in a subprocess** rather than adding
  pywin32, which is *not* a project dependency (the handoff assumed it was; `pywin32-ctypes` is
  present but is a keyring shim with no COM). Not the raw shell spec/30 rule 1 forbids: the model
  gives words, never a command; terms are stripped to bare `\w` before they reach the query and
  each is quoted and AND-ed (which also demotes a stray `OR`/`NEAR` to a literal word); the SQL is
  handed to the subprocess in an env var, so nothing the model wrote is parsed as PowerShell. Off
  Windows, or with the Search service off, it answers "not available" instead of raising — so CI
  needs no live index. Selfcheck covers the sanitiser directly plus both dispatch paths.
- **Works now (2026-07-28) — `search_email`, the fourth Tier-1 tool** (ROADMAP #11, second slice;
  closes #11). "The email from Sarah about the lease" → one restriction against the **desktop
  Outlook inbox** over MAPI, back as up to eight headers, `sender · date · subject`. All five
  params (`sender`, `subject`, `query`, `since`, `before`) are optional and AND-ed; the store does
  the filtering (`Items.Restrict` with a DASL query, sorted newest-first before restricting, and
  the loop breaks at eight) so a mailbox is never enumerated. Bodies are *searched* — that is what
  `query` is for — but only headers are returned; free text goes word-by-word over subject OR body
  so "lease renewal" still finds "renewal of the lease". Local desktop store only: no Graph, no
  cloud, no credentials (spec/50).
  **Not verified live — Outlook is installed on this box but has NO mail profile**, so every call
  here degrades to "no mail profile". The DASL property names and date literals are therefore
  written-not-proven; first run against a real mailbox is the test. Before any COM call the backend
  checks the profile registry keys, because asking Outlook for a mailbox with no profile can raise
  a modal *create-a-profile* dialog — a hang with no way to answer it behind a voice assistant. A
  false "no profile" is the failure mode to watch if an older Outlook (pre-16.0) ever turns up.
- **BASELINE 2026-08-03 — `--check-tools`, the live tool-selection suite.** Nine plain requests
  put to the real assistant brain with the real tool list; it reads the tool call the model
  produces and **executes nothing**, so it is safe to re-run. Connectors are read, never written —
  a case whose connector is off skips and says so. Guarded offline (the case table must name real
  tools, parameters and enum values, or a rename reads as nine model failures).
  **`ollama/qwen3.5:9b`: 8/9, no skips, repeated identically.** Every action and read case picked
  the right tool with sensible arguments — `focus_window` (not `open_app`) for "bring File Explorer
  to the front", all three media keys mapped correctly — and "how are you today" correctly called
  nothing with six tools available.
  - ⚠️ **The one failure is an EMPTY ROUND — intermittent, measured at 1 in 12.** Asked "what time
    is it", the model occasionally returns no tool call and no text at all. `_collect` returns
    `("", None)`, `_turn` reads `not reply`, and the user hears **"Something went wrong on my
    end."** — the generic apology, for a model that simply did not answer.
    **Correction, and the lesson is the lesson:** this was first written up as *deterministic*
    because the suite hit it twice in a row and I inferred a fixed property from two samples.
    Thomas contradicted it from real use, `logs/audit.jsonl` settled it in seconds (three real
    `'What time is it?'` turns, all `system_status ok`), and a 12-run sweep put the true rate at
    **1/12**. Punctuation and casing were also ruled out — all four phrasings call the tool.
    The cause is sampling: the router hands Ollama no temperature, so it runs at the runner's own
    default and the output varies run to run.
  - [ ] **OPEN — the empty round is NOT understood, and a retry was tried and REVERTED.**
    A one-shot resample (D36's cure) was written and pulled the same night: the retry came back
    empty too (`04:45:04→06` empty, retry `04:45:07→08` empty). It cured nothing and would have
    hidden an unexplained fault behind a longer wait — a patch over an error, which hard rule 2
    forbids. The bug stays visible until the cause is known (Thomas).
    **Thomas's argument, and it reframes the whole search:** a model returning *literally nothing*
    is not sampling noise — inference would return SOMETHING. So temperature and effort are the
    wrong tree. Two observations that fit "structural, not statistical": the immediate resample
    failed too (~0.6% likely if it were an 8% independent coin flip), and the failing round is
    FAST (1–2 s) rather than a long think.
    **This is the ASK path, not dictation** — the dictation-path determinism finding does not
    transfer, and citing it was a mistake.
    - **ROOT CAUSE FOUND 2026-08-03 by capturing the raw wire — it is REASONING.** Ollama's `/v1`
      streams a **`reasoning`** field beside `content` and `tool_calls`; `compat.py` reads only
      the latter two, which is correct. On the failing round the wire carried **360 characters of
      reasoning, zero content, no tool call, `finish_reason: stop`**. The model reasoned its way
      to the right answer and then said nothing:
      *"The user is asking for the current time. I have access to system_status which can report
      local date/time with UTC offset. This directly answers their question without needing
      additional tools or narration about how I'm…"* — note it deliberating about **not
      narrating**, which the persona explicitly instructs. It talked itself into silence.
      **Not** a connection fault, not a field we fail to read, not sampling noise in the usual
      sense: the wire genuinely carries nothing actionable.
    - **Reasoning also IS the latency spread.** `reasoning` was populated on **30/30** rounds, and
      time tracks its length (110 chars → 1.2 s, 978 chars → 5.5 s). Measured over 30 runs of the
      same utterance on one reused connection:

      | config | range | spread | median | empty |
      |--------|-------|--------|--------|-------|
      | as shipped | 1.18–5.00 s | 3.81 s | 1.99 s | **2/30** |
      | `effort=none` | 0.59–3.08 s | 2.49 s | **0.68 s** | **0/30** |

      Reasoning off removes the empty round entirely and cuts the median **2.9×**. Tool selection
      is **unchanged at 8/9** — no accuracy is bought by the reasoning.
    - ⚠️ **But the failure MOVES rather than vanishing, and it moves to a worse place.** With
      reasoning off, the clock case failed by **inventing an answer** — *"It is 16:05 UTC+8 (Hong
      Kong)"*, roughly twelve hours out and a city from nowhere — instead of going silent. A
      confident lie is worse than a shrug. **One sample; not a conclusion** (that inference error
      was already made once tonight and corrected). It wants repeating before it is trusted.
    - **RESOLVED for the empty round, 2026-08-03 — reasoning off, set from the settings window.**
      Thomas set Ollama's Effort to **None**; the router resolves `effort: "none"` and the wire
      carries it. Two further 30-run sweeps: **EMPTY 0/30 and 0/30, `reasoned` 0/30 both times** —
      with the earlier sweep that is **0/90 at effort=none against 2/30 and 1/12 with reasoning
      on**. Median fell to **0.60 s / 0.81 s** from 1.99 s, i.e. inside the bar. No code change
      was needed: `effort` was already wired end to end and only the CONTROL was illegible.
    - ⚠️ **OPEN — rare transient latency spikes, and the tail is now the whole problem.** One run
      of 30 hit **14.58 s** with reasoning OFF, so it cannot be deliberation (`reasoned` was 0/30
      in that very run). Two sweeps of the IDENTICAL config gave spreads of 14.07 s and 3.21 s, so
      the tail is **rare and random, not systematic**. Candidates, none tested: model eviction and
      reload (the cold load measured ~9 s, uncomfortably close), GPU contention from another
      process, Ollama queueing. **One sample proves nothing** — that inference error was made and
      corrected earlier the same night.
      **This needs HUNDREDS of calls, not tens** (Thomas): a 1-in-30 event cannot be characterised
      by a 30-run sweep, and the median hides it entirely. Sample size is the whole point — the
      queued latency suite (ROADMAP) should be built for volume and report the tail, not the mean.
      **The same argument applies to STT**, which has never been measured this way at all: its
      figures are single observations scattered through the log (44 ms · 61 ms · 182 ms · 687 ms
      cold), never a distribution. A slow tail there would feel identical to a slow tail in the
      brain and is currently indistinguishable from one.
    - **Noticed in passing:** the router now resolves `temperature: 0.7` for Ollama where it
      resolved `None` earlier the same night — populated by the card edit. Harmless-looking, but a
      stale stored temperature on the OpenAI card was one of D44's three bugs, so it is written
      down rather than assumed.
    - [ ] **Owed decision (Thomas): `tool_round_effort: "none"` on the Ollama card?** The mechanism
      exists (D44, built for OpenAI). The catch: on the assistant path `tool_specs()` is never
      empty, so *every* round is a tool round — this would mean **the local assistant never
      reasons at all**. That mirrors the `transform`-never-thinks invariant dictation already has,
      and the evidence says reasoning buys nothing here and costs a total failure now and then.
      It is still a policy change, not a bug fix, so it is not made unilaterally.
  - **Latency on identical input ranged 1.5 s – 4.6 s across those 12 runs**, and 2 s – 9 s across
    two suite runs. The local assistant path is not merely slow, it is ERRATIC, which is worse for
    a voice product: you can design around a predictable delay, not around an unpredictable one.
    A latency suite is queued (ROADMAP, after #8).
  - **It is also the case ROADMAP #8 already names as its first skill** ("world-time + live
    clock"). The evidence and the plan agree without being made to: the one thing this model will
    not fetch is the one thing a deterministic answer gets right instantly and for free.
  - [ ] **Owed — run it on Groq and on Anthropic.** Free and fast on Groq; ~20k input tokens on a
    cloud model. Tells us whether a small cheap model holds 9/9, which is also the per-task-type
    routing question (#8's other half).
- **The tool ledger (spec/30 rule 4).** Growth is tracked, not gated: nothing waits on a clock, but
  no tool is assumed good until it has misfired-free invocations in real use behind it. Evidence is
  `logs/audit.jsonl` (rule 2 already logs every call's outcome); this table is the human read of it,
  and a tool that keeps misfiring is a candidate for removal.

  | Tool | Tier | Built | Proven in real use |
  |------|------|-------|--------------------|
  | `system_status` | 1 | 2026-07-27 (D31) | **not yet** — no live tool turn on the box |
  | `read_clipboard` | 1 | 2026-07-27 (D31) | **not yet** — same |
  | `find_document` | 1 | 2026-07-28 | **not yet** — backend verified live against real documents, but never through a brain turn |
  | `search_email` | 1 | 2026-07-28 | **once, 2026-07-30** — driven by a brain end to end (D36), but it answered "no mail profile"; the retrieval itself has still never run |
  | `open_app` | 2 | 2026-08-03 (D42) | **yes, 2026-08-03** — "Open Spotify" driven end to end by FOUR brains (Anthropic · OpenAI · Groq · Ollama); each picked `open_app` with the right argument and the app opened. No misfires seen |
  | `focus_window` | 2 | 2026-08-03 (D42) | **not through a brain** — backend driven by hand 2026-08-03: a real window raised and confirmed in front |
  | `media_control` | 2 | 2026-08-03 (D42) | **not through a brain** — backend driven by hand 2026-08-03: a net-zero volume down/up pair sent |

  *Update the right-hand column when a tool has been invoked by the brain, in a real turn, several
  times without misfiring — that is the column the rule exists for.*
- **DONE 2026-08-03 (D42) — Tier 2 is on: `open_app` · `focus_window` · `media_control`.** Full
  account in spec/00 D42; the trust boundary for acting tools is spec/30 § The executor. `MAX_TIER`
  is 2, the announce earcon fires from `_run_tool_seen`, and `apps_media` is a live connector card
  (off by default, like every connector but System). Four things worth not relearning:
  - **The Start Menu FOLDERS are not the app list.** The first cut walked `%ProgramData%` and
    `%APPDATA%` for `.lnk` files and could not find Notepad, Calculator, Terminal or any Store app
    — 110 shortcuts on disk against the **139** Windows itself reports. `Get-StartApps` gives the
    real list (~0.7 s, uncached) and `shell:AppsFolder\<AppID>` launches classic and Store apps
    alike; the AppsFolder launch is **verified live** (Calculator opened and closed again).
  - **A fuzzy suggestion list needs a strict cutoff.** At difflib's 0.5, asking for an app this PC
    does not have answered *"the closest are: ReadMe, Camera"* (measured, for "chrome") — three
    confident wrong answers read worse than an honest bare no. 0.6 drops them and still gets
    `spotifi` → Spotify.
  - **`SetForegroundWindow` silently does nothing** from a process that does not already own the
    foreground, which the daemon never does. `_to_foreground` attaches our input thread to the
    foreground window's thread and detaches immediately, then **verifies** with
    `GetForegroundWindow` — the alternative workaround (a synthetic ALT keypress) lands in whatever
    app is in front and can pop its menu bar. **Proven live 2026-08-03**: a real Calculator window
    raised and confirmed in front.
  - **The announce obeys `pings`.** Deliberate, and it leaves a hole: pings off + the tool indicator
    unbuilt = a Tier-2 action with no cue at all. Recorded rather than patched, because the fix is
    the indicator (parked, Config & routing), not a sound that ignores a user's quiet mode.
  - [ ] **Owed — none of the three has run through a BRAIN.** All three backends were driven by
    hand on the box on 2026-08-03 and all three worked (Calculator opened, then raised; a
    volume down/up pair sent; a miss and a bad action both answering in prose). The selfcheck
    stubs them, because a check that really opens an app and moves a window is not one you want in
    CI. What has never happened is a *model* deciding to call one — that is the ledger's column
    below, and it is the only thing still missing.
  - [ ] **Owed — `set_timer` needs a Contract P surface.** Deferred at design time (Thomas): a timer
    FIRES outside any turn and no `status.json` message can carry that — the same gap as D20's two
    owed surfaces. It stays in the registry with no backend, so it is never offered and is refused
    if called. Sound-only was rejected: with pings off it would be silent AND invisible.
- **Not built:** Tier 3 (propose-then-tap confirmation, D26, on the Teleprompter). No raw shell
  below Tier 3 (spec/30 rule 1).
- **Fixed (D36, 2026-07-30) — a rejected tool call now retries.** `search_email`'s first live outing
  narrated "Something went wrong on my end"; the tool never ran. groq/llama-3.3-70b glued the
  arguments onto `function.name` and Groq rejected it server-side. **Measured: ~1 round in 3 fails
  this way** (5 of 14), the rest compose a correct call — so a resample is the cure, and the tool
  loop has had one since D31. It was gated on the `malformed_tool_call` kind and this arrived as
  `unknown`. Now mapped by a third typed input (did the round offer tools?), which keeps B-02's
  no-prose rule. The rejection arrives MID-STREAM — HTTP 200, bare `APIError`, no status code — so
  a first pass keyed on a 400 changed nothing; both shapes are mapped now. First real
  `search_email` invocation is in `logs/audit.jsonl`.
  - **Owed — Thomas's calls.** (1) A **capability failure narrated as a negative result**: the
    backend said "no mail profile", the brain said "I did not find the email". Nothing was
    searched, and the answer implies otherwise — a spec/40 narration question. (2) Whether
    tool-offering turns should route to a stronger tool-caller: one retry still leaves ~13% of
    turns failing, and that is a cost decision.
  - **Note:** the Groq free tier's daily token budget (100k) was exhausted measuring this, by the
    measurement runs themselves. Tool specs are ~2k tokens a round, so a tool turn is not cheap on
    a small daily cap.
- **Built (D38, 2026-07-31) — connectors: the user decides which tools exist.** Consent is now a
  second gate beside the tier — tier says whether Gemma MAY, the connector says whether the user
  WANTS it to, and a tool passes both or is neither offered nor run. Decision and rationale in
  spec/00 D38; the gate in spec/30 § Connectors; the pane in spec/70. **Items 1–8 of the checklist
  are done; item 9 (the design pass) is Thomas's and is the only one open.**
  - **The invariants worth not relearning:** an unrecognised connector id fails **closed**;
    `execute()` re-checks so a switched-off tool is dead even if a caller skips the filter; the
    disabled-connector sentence names only connectors with a usable tool behind them ("Web is off"
    would imply switching it on would work). Schemas: `tools.json` v0.3.0, `settings.json` v0.3.0,
    `status.json` v0.6.0 (the `tool` message). **System is the only connector defaulting on**,
    asserted as a rule in `settings_check` so a new personal connector cannot quietly ship on.
  - **Not yet seen on the box** — the pane has only been rendered and eyeballed offscreen.
  - **Owed (item 9) — the design pass on BOTH surfaces, Thomas.** The cards as built are
    functional, not designed: fixed 322px height (the Models card's) leaves visible dead space on
    the short ones, and the tool list is a tick plus a line of text. The running indicator has no
    treatment at all — and the island's status-word slot is already taken by "Thinking…" during a
    tool round, which is the 7b dead-air problem in another costume.

  *Owed, not in this build*
  - [ ] **First-run permissions round at packaging** — ask for what it wants up front rather than
    leaving it to be discovered in a pane (the VoiceInk/Parakeet pattern). Thomas.
  - [ ] **MCP** — deliberately out of scope: a runtime tool carries no tier, which drives through
    spec/30 rule 1. Its own decision and D-number; the pane holds a dimmed slot meanwhile.
  - [ ] **The `disabled_note()` wiring is unguarded.** `tools.py` proves the sentence is right;
    nothing proves `_turn` still attaches it, because `_turn` has no offline harness (it wants a
    fake brain, broadcaster and router). Same shape as D37's prompt-side check.
- **In flight:** —
- **Next:** ① **live-verify the Tier-2 three** — say "open Notepad", hear the announce, see it
  open; then a window raise, which is the one with a real chance of failing (the foreground lock).
  Switch `apps_media` on first: it is off by default. ② D38's design pass (item 9) — the connector
  cards and the tool-activity indicator; Thomas's, and the indicator is what makes the `tool`
  message visible at all, and what closes D42's pings-off hole. ③ live-verify a Tier-1 tool turn end
  to end (Claude asks `system_status`, then answers) **with a connector switched off too**, so the
  "file search is off" answer is seen rather than assumed. ④ `search_email` against a complete
  mailbox — see the retrieval note below. Tier 3 (D26) is the next tier, and needs the overlay
  confirmation before any backend.
- **Blocked, not broken — `search_email` retrieval (2026-07-31).** Repeated live searches return
  nothing, and the cause is **not** the tool: it queries `\\<account>\Inbox` correctly and returns
  hits for terms that are present (verified against "Amazon"). Classic Outlook has downloaded only
  **286 messages, covering 2026-07 and 2011–2012**, with a 14-year hole in between and
  `Terminated in error` five times in its sync log — so the months being searched are not on the
  machine. Two independent engines agree (MAPI `AdvancedSearch` and the Windows Search index both
  find no "camden" mail, though the index does find the Camden .docx files in Downloads).
  **Also found:** Windows Search DOES index Outlook mail (`System.Kind='email'`), so a ranked local
  backend is available through `find_document`'s existing ADO machinery — better than DASL `LIKE`,
  which ANDs every word of a free-text query and is brittle. Options on the table (Thomas):
  finish the sync · switch the backend to the Windows index and widen past the Inbox · or the
  OAuth route (Graph `Mail.ReadBasic` reads headers only and cannot send — scoped in chat, not yet
  a decision). Whichever wins, the AND-across-words and Inbox-only limits are real and outlive it.

## Specs — spec & decision docs

- **Works now:** the spec/ scaffold; Contract H excised (D18, the custom headset cancelled); docs
  01, 02 and 04 frozen. Decisions D10–D33 are recorded in spec/00 — most recently **D27** (the
  expanded view / peek) · **D28** (earcon vocabulary cut to three WAVs; `tts` and `Pings` as
  separate toggles) · **D29** (the settings window) · **D30** (B2 = any OpenAI-compatible endpoint;
  reachability as schema truth) · **D31** (the Tier-1 tool executor and the brain's tool loop) ·
  **D32** (Gem the mascot, first surfaces) · **D33** (the per-role router v1) · **D34** (the model
  + token footer) · **D35** (sprite kit v3) · **D36** (a rejected tool call retries) · **D37**
  (spoken formatting commands) · **D38** (connectors) · **D39** (one app, lifetimes tied) · **D40**
  (the settings window re-cut) · **D41** (the boot island) · **D42** (Tier 2 turns on) · **D43**
  (two dwells). Schemas
  current: `status.json` v0.8.0 · `settings.json` v0.3.0 · `tools.json` v0.4.0 ·
  `app_aliases.json` v0.1.0 · `earcons.json` v0.4.0 · `targets.json` v1.0.0.
  *(D42 bumped `tools.json` because two tools' model-facing descriptions changed; `settings.json`
  did NOT — a connector's `built` flag flipping is a value edit inside an existing entry, the same
  as the Engine card on 2026-07-28.)*
- **Reconciled 2026-07-28** (a sweep against what had actually shipped): **spec/00 D32** corrected
  on two points the tray had outgrown — the theme source is `SystemUsesLightTheme` (the taskbar),
  not the app setting, and idle no longer rests on a single frame; both carry an inline amendment
  note rather than a silent overwrite. **spec/00 D15** no longer says the cleanup plumbing waits on
  a config source — D28 and D33 built it. **spec/70 §1 + §3** no longer call the settings window
  "the M0-close gate" (retired; build status belongs in STATE anyway).
  **`spec/schemas/settings.json`** Engine card flipped to `built: true` — see Config & routing.
- **MEASURED 2026-08-04 — no small local model is fit to be the router unassisted.** Five models,
  17 cases, 25 runs each, 425 calls per model, evicted and proven out of VRAM between models.
  Commands and negatives scored apart.

  | model | commands | negatives (must NOT fire) |
  |-------|----------|---------------------------|
  | `qwen3.5:9b` | 232/250 (92.8%) | 152/175 (**86.9%**) |
  | `qwen3.5:4b` | 240/250 (96.0%) | 64/175 (**36.6%**) |
  | `qwen3.5:2b` | 221/250 (88.4%) | 130/175 (74.3%) |
  | `granite4.1:3b` | 240/250 (96.0%) | 50/175 (**28.6%**) |
  | `lfm2.5:8b` | 218/250 (87.2%) | 130/175 (74.3%) |

  - **The best two at commands are the worst two at negatives.** `granite4.1:3b` and `qwen3.5:4b`
    both score 96% picking tools and fire on ordinary speech two-thirds of the time. Scoring
    commands alone would have chosen exactly the wrong model, which is why the two numbers are
    reported apart and must stay that way.
  - **Both fired `open_app` 25/25 on "my sister works at Spotify" and "I hate it when Notepad
    crashes".** They match an app NAME, not a request. The best negative score in the set is 86.9%,
    so roughly one ordinary sentence in eight would act.
  - **The clock failure is now a rate, not an anecdote: 13/25 on `qwen3.5:9b`.** It invents a time
    rather than calling `system_status` — "It is 14:23 UTC+09:00", "It is 16:28 UTC-5". Earlier
    logged as one unconfirmed sample.
  - ⚠ **The prompt was the assistant persona, not a routing prompt.** These numbers describe these
    models in the assistant seat with a tool list. A prompt written to ask "is this a command"
    is untested and is the fair test of the LLM-router idea.
  - ⚠ **`lfm2.5:8b` numbers are a floor, not a measurement** — most of its failures are the
    `UnicodeEncodeError` below rather than model faults. `qwen3.5:9b` and `:4b` runs are clean.

- **MEASURED 2026-08-04 — a routing prompt fixes it, and temperature does not.** Same cases, 5 runs
  at temperature 0, assistant persona against `ROUTER_SYSTEM` (`eval/tool_check.py --router`).
  Negatives are the column that moves.

  | model | persona @ 0.7 | persona @ 0 | **router @ 0** |
  |-------|---------------|-------------|----------------|
  | `qwen3.5:9b` | 86.9% | 85.7% | **100%** (commands 100%) |
  | `lfm2.5:8b` | 74.3%※ | 100% | **100%** (commands 100%) |
  | `qwen3.5:4b` | 36.6% | 28.6% | 85.7% |
  | `qwen3.5:2b` | 74.3% | 57.1% | 100% (commands **90%**) |
  | `granite4.1:3b` | 28.6% | 42.9% | **28.6%** |

  - **Two models are clean on both halves: `qwen3.5:9b` and `lfm2.5:8b`** — 50/50 commands and
    35/35 negatives. An LLM router is viable; the first sweep measured the persona, not the ceiling.
  - **Temperature was not the lever.** At temperature 0 with the persona, negatives got *worse* for
    both small qwens (36.6→28.6, 74.3→57.1). At 0.7 the model sometimes failed to fire by luck and
    scored a pass; temperature 0 makes the wrong behaviour consistent. The prompt did the work.
  - **`granite4.1:3b` is immune to the prompt** — 28.6% under both. It calls `open_app` on an app
    name whatever it is told. Rules it out for this seat.
  - **`qwen3.5:9b` is already the assistant model**, so using it as the router costs no extra VRAM
    and cannot swap. `lfm2.5:8b` is built for edge tool calling and would be a second resident model.
  - ※ the 0.7 figure for `lfm2.5:8b` was depressed by the encode bug; its true persona score is
    higher.
- [ ] **BUG — a model's own words can kill a turn.** `orchestrator.py:346` prints every `TextDelta`
  to stdout as a dev trace. A character outside the console codepage raises `UnicodeEncodeError`,
  which leaves `_one_round` and ends the turn as a generic fault. Found by the sweep, where it also
  inflated failure counts. Unfixed; the trace must never be able to end a turn.
- **MEASURED 2026-08-04 — embedding classifiers do not do this job, and bigger ones do it worse.**
  Five embedders, same 17 cases, nearest-exemplar over 39 exemplars written to be disjoint from the
  suite (`--embed`). Best negatives 57.1%, against 100% for a prompted LLM.

  | model | VRAM | commands | negatives |
  |-------|------|----------|-----------|
  | `nomic-embed-text` | 0.3G | 90.0% | 57.1% |
  | `all-minilm:22m` | 0.0G | 80.0% | 57.1% |
  | `qwen3-embedding:0.6b` | 2.4G | 70.0% | 42.9% |
  | `embeddinggemma:300m` | 0.7G | 80.0% | 28.6% |
  | `mxbai-embed-large:335m` | 0.6G | 80.0% | **14.3%** |

  - **The inversion is the finding: 22M scores 57.1% and 335M scores 14.3%.** Embeddings measure
    topical similarity; routing needs pragmatic intent. "My sister works at Spotify" and "start
    Spotify" are topically near-identical and pragmatically opposite, so a stronger retrieval model
    places them closer and is more confidently wrong. This is structural, so more exemplars will not
    fix it — a fine-tuned classifier head might.
  - **No threshold separates right from wrong.** Margin to the next class was logged per miss:
    +0.003 to +0.15, the same band as the correct answers (one correct at +0.006, one wrong at
    +0.101). Confidence gating cannot be the precision knob here.
  - The `s/call` column in that run includes cold load and is not throughput — a 45 MB model cannot
    truly be slower than a 669 MB one.
- **The router intercepts the request and decides where it goes** — to a tool that answers outright,
  to a tool whose result goes to a composer, or to the model. The model is one destination and no
  longer the entry point. The judgement is tool call vs genuine prompt, made against the tools the
  harness exposes. Skills are one outcome of the router, not the whole of it.
- **DRAFTED 2026-08-04 — `spec/docs/60_evals.md`, "Chapter 6 - Evaluation of LLMs".** Its first
  section, *Router pre-flight latency evaluation*, is the design for ROADMAP 2.2 and is written in
  full: what is measured, the prompt set, the controls, the results format, and what the measurement
  cannot settle. The other four sections (tool selection · dictation cleanup · replay · provider
  smoke) are `[TBC]` placeholders. **Nothing under it is built** — the prompt set, the sweep driver,
  the offload guard and the report writer are all tagged `planned` in the chapter.
  - **Verified while drafting, so the guard is not written on faith:** Ollama's native API evicts a
    model (`keep_alive: 0`), the resident list then reads empty, and the reload cost **9.06 s** to
    first token — the same cold load the boot preload removes. The resident list also reports
    `size_vram` against total `size`, so the guard can detect a **partial CPU offload** rather than
    merely presence, which is the condition that scored one model 7/9 against its isolated 8/9.
- **In flight:** —
- **Parked — rename `bridge/` → `daemon/`** (S-07): see the handoff's parked list.

## Parked / someday

B3 agent-CLI adapter · earcon sound design session · wake-phrase false-accept test protocol ·
**LiveKit Wakeword** trialled as an openWakeWord replacement (lower false-accept rate; a contained
swap behind `wake.py`) · **semantic endpointing** (M1) — complete-thought detection so long
composed prompts aren't cut off, the real fix beyond the silence timer (spec/40) · **long-task
interaction pattern** (dispatch-and-notify, heartbeat cadence during long silence, mid-task status
queries, "work on this in the background" phrasing) — design it when B3 or a heavyweight tool
lands · **usage/cost ledger** (2026-07-28) — record per-turn API usage and cost for **Ask and
Dictate** to a small store (JSONL/SQLite in `%APPDATA%\gemma`):
`{ts, role, provider, model, in/out tokens, cost}`. The data already exists (adapters normalise
`usage`); it is simply not persisted. RECORDING can start now — cheap, backend, router-independent —
so the parked **data page** inherits history instead of starting empty. Cost needs a `$/token`
table, whose home is the `settings.json` catalogue; splits by role, and dovetails with the router's
per-instance view.
