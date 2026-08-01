# STATE — the jump table

Purpose: make track-hopping free. Thomas works by mood; that is fine **because** the
contracts isolate the tracks. The rules that keep it safe: pick a track by mood, but
within a track always take the next queued action · max one item in flight per track ·
when abandoning mid-task, park it here with a one-line note · read this file at session
start, update it in the same commit as the work · when a step closes, collapse its
entry to one or two lines — durable knowledge moves out (behaviour → spec · run
instructions → README · findings → NOTES.md · decisions → a D-number in spec/00).

Last updated: 2026-07-31

## Handoff — start here (2026-07-28)

**M0 IS CLOSED.** Its criterion (ask-hotkey → the reply streams to the Teleprompter, perceptible
feedback < 1.5 s, ×10 consecutively, B1, zero tools) passed and was measured on 2026-07-22, 10/10.
The **"M0-close gate" is RETIRED** (Thomas, 2026-07-28): it was bolted on after the fact, was never
part of spec/00's M0 criterion, and "the settings window is up to par" is not a testable bar. The
quality it stood for is real and now has its own section — **Config & routing**, below.

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

**Dictation latency — a day of measurement, 2026-08-01. Four bugs found, all fixed, nothing yet
committed to spec.** The complaint was "local cleanup is slower than Groq". It was, by ~10×, for
reasons that had nothing to do with the model:

- **STT ran on the CPU, not the 5080** (~950 ms → **~35 ms**). `_add_cuda_dll_dirs()` called
  `os.add_dll_directory()`, which **ctypes honours and ctranslate2 does not** — so the directory was
  right, the DLL was loadable, and every transcribe still failed with `cublas64_12.dll is not found`
  and fell back to CPU, 16 times in the log before anyone noticed. Reordering the calls does not
  help (tested both ways). Fix: **preload each CUDA DLL by absolute path** — Windows keys loaded
  modules by base name, so ctranslate2's later `LoadLibrary` finds the copy already in the process.
  Now `_load_cuda_dlls()` in `listen.py`, guarded by an idempotency check that runs without a GPU.
- **`localhost` cost ~2 s per connection** (→ **0.2 ms**). It resolves to IPv6 `::1` first and every
  local runner binds IPv4, so the wasted attempt was paid on *every* call, not just failures.
  Rewritten to `127.0.0.1` in `base_url()` — deliberately in the URL builder, not only the
  catalogue default, so it repairs endpoints already stored in a profile and ones typed by hand.
  The three local cards now default to `127.0.0.1` too.
- **A dead local runner took 9.66 s to report itself** (→ ~2 s). The SDK retried a refused loopback
  socket twice. Local providers now get `max_retries=0` and a 2 s **connect** budget; the 600 s
  read timeout is untouched, because a local model may legitimately think for a long time once it
  HAS answered. Cloud providers keep their retries — their faults really are transient.
- **Thinking models reasoned during cleanup** (6.5 s → **0.44 s**, and one case looped to **71,391
  tokens** and never answered). `transform` now sets `Session.thinking = False` — an invariant of
  the verb, beside `temperature=0`, not a user setting: a constrained rewrite has nothing to
  deliberate about. Each adapter translates it; on the OpenAI wire "off" is a *value* of the effort
  scale (`reasoning_effort: "none"`), gated on the card listing `none`, because a rejected value
  costs the whole turn. Ollama's card now declares it — `think:false` and `chat_template_kwargs`
  are both ignored on `/v1` (tested, v0.32.5), so this is the only reachable route.
- **Owed:** none of this is in spec yet, and the `transform`-never-thinks invariant belongs in
  spec/20 beside the other Session overrides.

- [ ] **A deleted model is reported as `unknown`** (found 2026-08-01). Delete a model from Ollama and
  Gemma finds out only when it calls, then flattens Ollama's precise `404 · model 'x' not found`
  into the generic `unknown` bucket — so dictation silently pastes raw transcripts and the assistant
  says "something went wrong on my end". Same **can't-rendered-as-didn't** failure D36 fixed for
  tool calls. The settings window doesn't catch it either: the picker fetches the live list but
  nothing compares the *stored* selection against it. Fix is small but touches spec/20's closed set
  of error kinds, so it wants a decision: ① map `NotFoundError`/404 to its own kind in `compat.py`
  (by type and status, never message prose — B-02) · ② a user-facing line in the orchestrator's
  message map · ③ optionally, flag a stored model missing from the fetched list in the settings UI.

- [ ] **The absent settings — wants its own design session, probably its own tab.** Four settings
  are specced in spec/70 §3 but surfaced nowhere: **STT model · wake phrase · TTS voice ·
  word-replacement table**. Thomas: likely a **tab of their own** rather than more rows on an
  existing pane. **Also owed by this session (2026-08-01): the sidebar SEARCH** — it ships disabled
  under D40 and what it should search (labels only, or help text too, or connector/tool names) is
  a design question. Owed by that session: which tab (and whether Speech is the grouping) · types,
  defaults and validation for each · the word-replacement **table editor**, which is a repeating
  from→to grid, not a row control, and so has no precedent in the window yet · whether STT model is
  per-mode (D12 says dictation is the stricter test) or one process-wide value, since the code holds
  one constant today. Note the window's other named gaps live above (AddCard dashed border, roster
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
- [x] **DONE 2026-07-31 (D39) — one app: lifetimes tied, processes NOT merged.** The single-process
  merge was considered and **rejected** — the complaint was about what dies when, and that is a
  launcher concern. `run.py`: a **clean** exit of either child (code 0) stops the other, so tray Quit
  and Ctrl-C are each one door out; a **crash** (nonzero) spares the survivor, so D13/D19 isolation is
  untouched and a dead daemon still has a live overlay to be reported by. Expected to amend D13/D19
  and D10; **amends nothing** in the end, and **spec/50 rule 12 stays untouched** — a `quit` upstream
  verb was rejected because that channel may only stop work in flight and is unauthenticated, so the
  verb would let any local process kill Gemma. Cost accepted: two hand-started terminals stay untied.
  Guarded by `python run.py --selfcheck` (all four clean/crash × daemon/overlay cases), CI-wired.
  - [x] **Cold start, fixed in the same work.** Warm-up is no longer one serial block — it is split by
    **when a model is first needed**. Wake + VAD load before serving (`serve()` predicts every block,
    `_capture` needs the VAD); **whisper and Kokoro moved to a background thread**, so the **hotkeys
    now register without waiting** for them. (b) **Kokoro is no longer preloaded** — `tts` is off by
    default (D23), so most starts were loading a speech model to discard its audio; lazy is also the
    only correct answer when it's toggled on mid-session. (c) **`local_files_only` with a network
    fallback**, killing the per-start huggingface.co revision call for a model already on disk. The
    **lock** in `listen.py`/`speak.py` is what makes this safe: warm-up now runs concurrently with a
    live hotkey, so without it an early press and the warm thread each build a CUDA model.
    ⚠ **Not yet measured on the box** — the 3.8–45.9 s spread was the *before*; the after wants a
    real start with a stopwatch, and an early keypress during warm-up wants trying once.

**Parked, not in the sequence:**
- **Local B2 brain (Ollama)** — deferred. M2 "it's local" and the *local* cleanup-engine option
  (S-06) both wait on it. B2's adapter already exists (D30) and speaks to any OpenAI-compatible
  endpoint, and the router (D33) can already point a role at one — so this is now "stand a local
  server up and pick it", not new adapter work.
  **Stood up 2026-08-01.** Ollama v0.32.5 on the 5080, reached through B2 with no adapter work —
  `qwen3:8b` · `qwen3:14b` · `qwen3.5:9b` pulled and measured (scoreboard in Track D). VRAM at the
  4096 default: 5.58 / 9.65 / 5.64 GB — it scales with `num_ctx`, so a 128 k context costs ~11 GB
  for nothing. **Context cannot be set through `/v1`** (`num_ctx` ignored in both shapes; native
  `/api/chat` honours it but *reloads the model*, ~3.4 s), so it is a load-time property, not a
  per-call knob — and the `"context": true` capability on the three local cards is **read by
  nothing** and arguably unimplementable as declared. Ollama needs **GGUF**; an ONNX build is the
  wrong artefact (it targets ONNX Runtime GenAI, a *library*, while B2 needs an HTTP endpoint).
  Model eviction is `OLLAMA_KEEP_ALIVE`, default 5 min — an intermittent dictation habit pays a
  cold start (8–12 s) each time.
  - [ ] **Headless Ollama — designed, not built** (Thomas: no tray clutter). The tray comes from
    `ollama app.exe`; `ollama.exe serve` is the server and has no GUI. So: disable its autostart
    (Task Manager > Startup, a user action), and have Gemma spawn `ollama.exe serve` with
    `CREATE_NO_WINDOW` when a role resolves to a local runner and nothing is listening.
    **"Start if absent, never stop"** — deliberately one-way: no supervision, no restart logic, no
    orphan handling, and Gemma never owns a third-party process's lifetime (D39 declined that for
    its own two). Belongs in D39's warm-up thread so the server is up before the first dictation.
    Undecided: whether it is always-on or behind a setting. If `ollama.exe` is absent, do nothing —
    D1 already pastes the raw transcript when cleanup is unreachable.
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
    one class with an explicit left/right orientation.
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
  - **Owed:** the **Add a model** sheet and the **remove confirmation** have never been looked at
    — `settings_check` only proves they do not throw. And the **tool-activity indicator** still
    has no renderer: Contract P's `tool` message and `overlay.tool` exist and are guarded, but
    nothing on the island draws it (this is the surviving half of D38's item 9; the connector
    cards half was absorbed into D40's table).

- **Built — the settings window (D29):** a schema-driven QML window off `spec/schemas/settings.json`
  (defaults, `built` flags and the provider catalogue all live there, so a knob is a JSON edit).
  **Models** = the provider roster, an editor card per model (the model well/picker, the dials that
  provider actually offers, on/off, primary, a key-status footer, and a gear opening the Add/Edit
  sheet). **Config** = profile · preferences · triggers. Guarded by `settings_check` (CI-wired,
  fails on any QML warning).
- **Built — the router v1 (D33):** `bridge/brains/router.py` resolves a role to the configured
  provider+model from settings, read fresh each turn — `assistant` ← `primary`,
  `cleanup_dictation`/`cleanup_prompts` ← their keys, each via `models[<provider>]`. The
  orchestrator (`_assistant_brain`, `_cleanup_brain`) rebuilds the adapter only when
  `router.signature(role)` changes, so the client is kept (spec/20 adapter lifetime) yet a picker
  change lands next turn with no restart. An unconfigured role falls back to the daemon default
  (`DAEMON_MODEL` / Groq cleanup); an injected brain (replay) bypasses the router entirely. **The
  model picker now drives the daemon** — all of D30's adapter work is reachable by the assistant,
  not just by dictation cleanup.
- **Built — the config source:** `%APPDATA%\gemma\settings.json` via `bridge/settings.py`, written
  by the tray/window and re-read by the daemon each turn. Started at D28 with the `tts` and `Pings`
  toggles.
- **Owed — the window is below par** (Thomas, 2026-07-28). Named gaps: the AddCard dashed border
  (Qt), roster reorder, and the settings not surfaced at all yet — **STT model · wake phrase · TTS
  voice · word-replacement** (spec/70 §3).
- **Owed — router Layer 2** (explicitly out of v1): several instances per provider + the
  roles/routes redesign (spec/70) · per-task-type routing and its classifier (short → Groq, long →
  Haiku) · a `local_only` policy. B1's `effort`/`thinking` stay unwired until M0.5, so `effort`
  currently reaches only B2.
- **Built 2026-07-28 — the dictation Engine card is live.** Both its controls now do something:
  the **Engine dropdown** was already resolved by the router (D33), and the **"Tidy dictation"
  toggle** is now read by `_dictate` — off skips the transform entirely and pastes the raw
  transcript, reusing the delivery path that already existed for cleanup failure, and it skips
  the `transforming` state too, since showing "Tidying…" while nothing tidies would be a lie.
  `built: true` on both keys. Found during the reconciliation pass: flipping the flag alone would
  have shipped a toggle that appeared to control tidying and did nothing. Guarded in the
  orchestrator selfcheck (toggle-off pastes raw, and the state run is
  `["transcribing","pasted","idle"]`), verified to FAIL when the gate is reverted.

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

- **DONE 2026-07-30 — dropdowns standardised to two classes.** Every dropdown shows either WORDS
  (provider names, languages, enum choices) or a MACHINE VALUE (a model id); the class picks the
  face *and* the size together and applies to the button and its popup rows alike. `Theme.fontDropdown`
  (16) / `fontDropdownMono` (12) — no new numbers, both taken from the exemplars Thomas named
  (Config > Preferences > Language, and Ask > Model). The enforcement is that `Dropdown.fontPx` is now
  **readonly**, computed from `mono`: a call site picks the class and *cannot* invent a size, which is
  how the window had drifted to three sizes across six dropdowns. Two were wrong and are the only
  visual change: Dictate > Engine was sans at the mono size (12 → 16, Thomas's complaint) and
  Add-provider > Model was mono at the sans size (16 → 12). Spec: spec/70 §2.
- **DONE 2026-07-30 — the Test button did nothing while a probe was in flight.** A production bug,
  not a test flake: `settings_model._fetch` guarded on `pid in self._fetching` *before* honouring
  `force`, so `testProvider` was swallowed by any probe already running — exactly when the user has
  just changed a key or endpoint, which is the only reason to press Test. Surfaced as a selfcheck
  failure on Thomas's box only (`a dead runner must be nameable, got 'empty'`): a live local Ollama
  with no models pulled answers `empty`, and CI has none, so it had always passed there. Fix is two
  parts — `force` now overtakes an in-flight probe, and a per-provider **generation counter** makes a
  returning worker prove it is still the newest before it writes, so the overtaken (slow, stale)
  answer is discarded instead of landing last. The check fakes both probes and returns them out of
  order, so it is deterministic and needs no network or local runner; confirmed to fail without the
  guard before being restored.

- **DONE 2026-07-28 (D34) — model + token count in the peek footer.** The peek names the model that
  answered + the turn's total tokens (`claude-opus-4-8 • 1847 tokens`, mono, bottom-left — variant A).
  Contract P: `response` gains optional `model`+`tokens` (`status.json` → v0.5.0), stamped on the `done`
  message (model from the router-resolved brain's `.model`; tokens summed from each round's
  `Done(usage)`, input+output); `decode`/`OverlayModel`/`PeekPanel` carry and render it. Guarded in
  `broadcaster` + `decode` selfchecks; overlay/settings checks green. Owed: live on the box (peek a
  real answer and read the footer).
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
  was swapped back out on 2026-07-31, Thomas) · Martian Mono · Material Symbols, with Instrument
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
- **Built (D24) — the island owns the display.** The prompt hands over to the reply only once it has
  finished revealing (`promptShown` + `Theme.durationPromptHold`), and the island hides *itself*
  `Theme.durationAnswerDwell` after the text finishes appearing, replacing a daemon-side timer that
  was estimating the overlay's own typing speed. `DismissKey`, a `QAbstractNativeEventFilter`, holds
  bare Esc via `RegisterHotKey` for exactly as long as the window is visible. **Verified live
  2026-07-22** — the prompt gate, Esc on a displayed answer, Esc mid-thought, and Esc handed back to
  other apps when the island is hidden.
- **Built (D27) — the expanded view / "peek".** Hover a shown answer → hint; click → the island
  grows *in place* into the current turn read in full (prompt pinned and collapsible past 2 lines ·
  reply scroll under a top/bottom fade · **Copy** + **Save**-to-file). Content-clamped height, then
  scroll; Esc collapses before dismissing; the dwell pauses while open. The island takes input over
  its silhouette when peekable, via per-region `WM_NCHITTEST` — **amends D22**. Action icons are
  hand-drawn SVGs; exact Material Symbols can drop in. **Unproven live:** the hover → click → peek
  path and the per-region hit-test have only run offscreen, with no real mouse (the `WM_NCHITTEST`
  mechanism itself is proven in the spike). "Send" stays a Contract-T integration (M1+), never an
  overlay button.
- **Built (D32) — Gem the mascot, first surfaces.** The commissioned ghost sprite kit
  (`teleprompter/gem/`, its own source of truth — never hand-edit) renders in three places through
  one renderer, `teleprompter/gem.py`: the **Windows taskbar / app icon** (`portrait.plain` on a
  rounded chip), the **tray** (status-driven off the live feed), and the **settings top bar**
  (replacing the on-air lamp — `arriving` on open → `idle` → `listening` while capturing). QML draws
  it through a `QQuickImageProvider` (`image://gem/<state>/<frame>`). Native purple/orange accents
  are kept; the **body flips light** on dark surfaces — a palette MAP over the kit's indices, never
  a repaint or a second export. Truthful by construction (spec/50 rule 4): every surface is driven
  by real Contract-P state. The overlay island is deliberately left alone for now. Parked kit extra:
  the costume portraits (DJ/engineer/…) for settings sections.
  - **Refined 2026-07-28 (`d468005`):** the tray follows the **taskbar** theme
    (`SystemUsesLightTheme`), not the app theme (`AppsUseLightTheme`) — the two differ on a common
    Windows 11 combo (light apps + dark taskbar), which rendered Gem's dark body invisible; and the
    tray now **animates idle** too (every multi-frame state animates; only a genuinely single-frame
    state rests). The settings top bar was simplified in the same commit: the orange brand Mark and
    the "Gemma" wordmark removed, Models/Config centred, Gem moved to the **top-LEFT** as the page's
    only mark and its mic indicator.
  - **Superseded 2026-07-29 by D35 (below).** The tray is no longer a Gem surface, and the kit is
    v3. Read D35 for what is true; the paragraph above is kept as the record of what D32 shipped.
    *(This also closes the "spec/00 D32 not updated with `d468005`" debt — D35 restates the tray.)*
- **Built (D35, 2026-07-29) — sprite kit v3 + the tray's mic ring.** Design shipped v2 then v2.2/v3
  in a day; neither is drop-in over v1. States hold named **clips** with
  policies (loop / oneshot / hold), and the kit carries its own **timing script**. `idle/rest` is a
  single frame, so `gem.py` now runs that script — `GemPlayer` (a Qt-free port of the kit's own
  player) plus `QmlGem`, which hands QML one bindable URL, so the settings window sets a state and
  stops counting frames. Both palettes are read **from the JSON** (a light + a dark hex per role,
  plus a `shade`); only body and eye are overridden — this amends D32's "the accents don't
  flip", which predates the kit having ground-specific accents (Thomas). Gem's surfaces are now two:
  the **taskbar / app icon** (`idle/rest`, cropped to the frame's own ink) and the **settings top
  bar at 52px** (2× the cell — the whole cell fits the 58px bar, so nothing is cropped; 3×/78px was
  tried and is too tall, and there is no integer step between). `idle` with its own fidgets →
  `listening` while capturing. The **tray drops Gem**
  for a **mic-level ring** — hollow ink while the mic is closed, a coral core with a halo that grows
  and brightens with the real RMS while open; no timer (mic frames are the clock), repaint gated on
  a 12-step quantisation. Thomas is commissioning a separate tray set. Gone with v1: `portrait.plain`,
  `arriving`, `question`, `alert`, and `gem.gem_state()` (the tray was its only consumer).
  Guarded: `teleprompter.gem` + a new `teleprompter.tray` selfcheck, both CI-wired.
  - **We ship Design's 26px build**, not their 32 — same art, tighter cell, Gem 54% of the width
    instead of 44%. Checked on arrival: 462 frames / 24 clips, every frame 26 × 26 legal chars,
    both atlases compared to the JSON pixel-for-pixel (a 26-cell JSON beside a 32-cell atlas throws
    nothing and renders garbage). Our earlier self-recrop and its `recrop_26.py` are superseded by
    Design's own export and removed.
  - **The idle script is two-tier now** — `filler` (blink, look-around) on a fast beat, a **gag**
    (`jump` `skip-rope` `guitar` `phone` `basketball` `disguise`) every `gagEvery` fillers. The trap:
    a v2 loader *runs* a v3 kit and just plays gags where fillers belong, so Gem performs constantly
    — no crash, no warning. `GemPlayer` was ported to the two-tier shape and the selfcheck asserts
    the tiers stay separate over ~74 simulated minutes. Eyes are 2px wide as of this kit.
  - **Owed — the sprite lab:** `needs-permission/granted` f5 (the falling lock) loses 5px off the
    bottom to the 26px crop. Design says flag it and leave it — it wants a human pass, not invented
    pixels.
  - **Gem mimes the turn (settings bar):** `listening` → `working` while the brain composes →
    `speaking` for as long as the ISLAND's typewriter is still laying the answer down → `done` →
    `idle`. Driven by `overlay.revealing`, a new UI-side field on `OverlayModel` that `Overlay.qml`
    publishes — the daemon's `speaking` state never fires with TTS off, and its stream finishes
    seconds before the reveal does. It needed its own notify signal — published through the model's
    blanket `changed` it invalidated its own inputs and QML spun a binding loop.
  - **Gem is on the island too, behind `gem_in_island`** (preferences, default on — Thomas).
    52px inside the pill on the left, `gemLeft` 4 / `gemGap` 6 over a cell that carries ~12px of
    its own margin; the waveform used to be centred in the whole pill and ran 30px under her, so it
    now starts after her column and the Gem theme narrows to 14 bars / 10px fade (from 20 / 22).
    Compact pill 230 → 238px. Off restores the pre-Gem island **exactly**, which `overlay_check`
    proves by re-deriving the original formulas rather than trusting the branch. Her x/y are
    rounded to whole pixels (an odd pill width would land a nearest-neighbour sprite on a half
    pixel), CI-guarded. The phase ladder moved out of QML into `QmlGem` now two windows drive one
    player, and gained `error` (which outranks a pending reply) plus dictation's
    `transcribing`/`transforming` → `working` and `pasted` → `done`. **No Gem on the peek** — a
    `search` clip for it is commissioned.
  - **Owed — live on the box:** the tray ring against a real mic, the taskbar icon, and Gem
    miming a real turn on both surfaces. Headless cannot show them.
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

  *Update the right-hand column when a tool has been invoked by the brain, in a real turn, several
  times without misfiring — that is the column the rule exists for.*
- **Not built:** Tier 2 (`open_app` · `focus_window` · `media_control` · `set_timer` — need backends
  plus the announce earcon) and Tier 3 (propose-then-tap confirmation, D26, on the Teleprompter). No
  raw shell below Tier 3 (spec/30 rule 1).
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
  - **The two schemas.** Every tool declares a `connector` (`system` · `clipboard` · `files` ·
    `email` · `apps_media`) and a `label` — the tool said in a sentence a person would use, which
    both the card and the island's indicator read, so there is one wording and no copy of it in
    code. `settings.json` gained a `connectors` pane and one `connector_*` bool each; **System is
    the only one defaulting on**, asserted as a rule in `settings_check` rather than trusted per
    entry, so a new personal connector cannot quietly ship on. Web, Apps & media and a dimmed
    **MCP** slot are `built: false`. `tools.json` → v0.3.0, `settings.json` → v0.3.0.
  - **The gate is two lines and a backstop.** `tool_specs()` filters on the connector beside
    `MAX_TIER`; `execute()` re-checks, so a switched-off tool is dead even if a stale round or a
    caller that skips the filter reaches it. An unrecognised connector id fails **closed**. The
    connector map is derived from the schema, so adding one is a JSON edit.
  - **A disabled connector is SAID, not silently missing.** `tools.disabled_note()` appends one
    sentence to the persona naming what is off ("…never imply you looked and found nothing") —
    the D36 can't-rendered-as-didn't failure, prevented by construction. It names only connectors
    with a usable tool behind them: "Web is off" would imply switching it on would work.
  - **The pane is a third top-bar section** (Models | Connectors | Config), a card roster on the
    Models precedent — each card states what it reaches and lists the tools it enables, ticked
    where they can actually run. Rendered and eyeballed offscreen; **not yet seen on the box.**
  - **Contract P gained `tool`** (`status.json` → v0.6.0): `{name, label, done}`, published as a
    call starts and again as it returns — around every outcome, refusals included, so the
    indicator can never outlive the work. Reduced by `decode`, exposed as `overlay.tool`.
    **Nothing renders it yet**, deliberately: that is item 9.
  - Guarded: `bridge.tools --selfcheck` (fresh install offers System only · all-on offers the four
    Tier-1 and no Tier-2, proving the gates independent · a connector alone excludes · `execute()`
    refuses one anyway · the note names the right connectors), plus `settings_check` (every tool's
    connector has a setting, or it would be withheld forever with no warning) and `decode`
    (the label is cleared by its own `done`). The tools check now points `GEMMA_SETTINGS` at a
    temp file, so it no longer passes or fails with whatever is toggled on this box. Verified to
    FAIL with the gate reverted.
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
- **Next:** ① D38's design pass (item 9) — the connector cards and the tool-activity indicator;
  Thomas's, and the indicator is what makes the `tool` message visible at all. ② live-verify a tool
  turn end to end (Claude asks `system_status`, then answers) **with a connector switched off too**,
  so the "file search is off" answer is seen rather than assumed: `search_email` has been driven by
  a brain (D36) but the ledger's column is otherwise still empty. ③ `search_email` against a
  complete mailbox — see the retrieval note below. Tier 2 backends when a tool is genuinely wanted.
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
  (spoken formatting commands) · **D38** (connectors). Schemas current: `status.json` v0.6.0 ·
  `settings.json` v0.3.0 · `tools.json` v0.3.0 · `earcons.json` v0.4.0 · `targets.json` v1.0.0.
- **Reconciled 2026-07-28** (a sweep against what had actually shipped): **spec/00 D32** corrected
  on two points the tray had outgrown — the theme source is `SystemUsesLightTheme` (the taskbar),
  not the app setting, and idle no longer rests on a single frame; both carry an inline amendment
  note rather than a silent overwrite. **spec/00 D15** no longer says the cleanup plumbing waits on
  a config source — D28 and D33 built it. **spec/70 §1 + §3** no longer call the settings window
  "the M0-close gate" (retired; build status belongs in STATE anyway).
  **`spec/schemas/settings.json`** Engine card flipped to `built: true` — see Config & routing.
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
