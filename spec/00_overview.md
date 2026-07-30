# Spec 00 — System overview & status

**Last reconciled: 2026-07-30** · Build progress: [STATE.md](../STATE.md) · Decisions record: [docs/02](../docs/02_architecture/02_system_architecture.md)

## The system in one paragraph

Gemma is a **UI-first desk assistant on Windows** (D23): the **bridge** (**G**), a Python
daemon on the hub machine (Windows PC or Mac — D10), driving one visible surface — the
**Teleprompter** (**P**), a Dynamic-Island overlay in its own process on the status feed
(D13/D19). Two doors (D20): a **dictate** hotkey puts speech at the caret, and an **ask**
hotkey opens the assistant — speech → STT → **Contract B** to a swappable brain (B1 Claude
API → B2 local LLM → B3 agent CLI) → an answer that renders on the Teleprompter, rewrites a
selection, or calls tools. Requested PC actions run through the **Contract T** tool registry
with tiered safety gates (M1). **Display always, speech by choice (D23):** the Teleprompter
always carries the answer, while **TTS** and the **wake word** are supported capabilities
behind user switches (default off, spec/70) — turn them on and Gemma speaks and answers
hands-free; leave them off and it is a screen-and-keyboard tool.

```mermaid
flowchart LR
    U["wake word · ask-hotkey · dictation hotkey"] --> G[Bridge]
    G <-- "Contract B" --> B["Brain B1/B2/B3"]
    G <-- "Contract T" --> T["Tools / PC"]
    G -- "status feed (D13)" --> V["Overlay / teleprompter + audio out"]
```

## Legend — naming scheme

One letter per element. The **bridge (G)** is the hub; **B/T/P** are the things it
connects to, each over the matching Contract.

| Letter | Element | Contract | Component IDs |
|--------|---------|----------|---------------|
| **G** | Bridge — the Gemma daemon (audio, wake, STT, TTS, orchestrator) | — (it *is* the hub) | build steps 0–7 |
| **B** | Brain — swappable LLM | Contract B | **B1** Claude · **B2** local · **B3** CLI |
| **T** | Tools — registry + executor + PC actions | Contract T | safety **Tier 1–3** |
| **P** | Teleprompter — on-screen overlay (separate process) | Contract P | status feed ([schemas/status.json](schemas/status.json)) |

Orthogonal axes: **milestones M0–M4** (project-wide stages — see below) and the frozen
**decision records docs 01–04**. Milestone *definitions* live in this file; the live
per-track *sub-steps* live in `STATE.md`; the frozen M0 build order is in docs/04 §8.

> **Terminology note (old → current).** The frozen docs/01–04 use earlier names and are
> not retro-edited (hard rule 2). Current truth: STATE.md tracks relettered **A→G**
> (Bridge), **C→B** (Brain), with a new **T** (Tools) track — so "Track A's queue" in
> docs/04 §8 is now Track G's.

## Component inventory

| Component | Spec | Code location | Lands at |
|-----------|------|---------------|----------|
| Hotkey triggers (ask-Gemma · dictation) | [40_interaction](40_interaction.md) + 60_dictation (owed) | `bridge/hotkeys.py` | ask pre-M0-run (D16) · dictation at D1 |
| Audio pipeline (wake, VAD, STT, TTS, earcons) | [40_interaction](40_interaction.md) | `bridge/audio/` | M0 |
| **Teleprompter** (P) — overlay, separate process on the status feed | [40_interaction](40_interaction.md) § Visual output | `teleprompter/` | v0 pre-M0-run (D13/D19) · dictation states at D2 |
| Orchestrator (state machine) | [40_interaction](40_interaction.md) | `bridge/orchestrator.py` | M0 (build step 6) |
| Brain adapters | [20_contract_b](20_contract_b.md) | `bridge/brains/` | B1 + B2 built (D30) · B3 at M4 |
| Tool registry + executor | [30_contract_t](30_contract_t.md) + [schemas/tools.json](schemas/tools.json) | `bridge/tools/` | M1 |
| Security posture | [50_security](50_security.md) | cross-cutting | always (BINDING) |
| Dictation (hotkey → transform → paste) | [60_dictation](60_dictation.md) | `orchestrator._dictate` + `bridge/paste.py` | D1 built (2026-07-25); D2/D3 owed |

## Milestones

Definitions only — live progress per track is in [STATE.md](../STATE.md).

| Milestone | Definition (acceptance test) |
|-----------|------------------------------|
| **M0 — Loop closed (UI-first, D23)** | Ask-hotkey → question: the response **streams to the Teleprompter**; perceptible feedback < 1.5 s (D11/D16), ×10 consecutively · B1 brain, zero tools. **With speech enabled** (not pass/fail for M0, measured when on): first spoken word < 4 s; **with "listen for me" enabled**: the wake word opens the same door. Supersedes D16(2)'s speech-gated shape — display is what M0 proves. |
| **M0.5 — It speaks well** | A 10-prompt bank (factual · complex · list-shaped · tool-result) each renders voice-correctly *without* the sentence-count heuristic: short answers spoken whole, long → spoken TL;DR + held detail, no markdown/emoji/URL reaches TTS, numbers/units read naturally. A model-driven output contract replaces spec/40's ≤2-sentence stopgap; adapter-agnostic (B2-tolerant parse). |
| **M1 — It acts** | "Open Spotify and play something" → `listening` earcon; audit log shows the calls; 6 starter tools |
| **M2 — It's local** | M1 script passes with Wi-Fi unplugged (B2 brain) |
| **MD — It types** *(feature milestone, parallel to the M-ladder)* | Hotkey → dictated speech lands in the focused app: ×10 consecutive dictations across ≥3 apps paste correctly after cleanup, zero answer-instead-of-transcript failures; capture in RAM; assistant loop unaffected |
| **M4 — Experiments** | B3 adapter · per-request routing |

*(No M3: it was the custom-headset milestone, removed when Contract H was excised — D18.)*

## Fixed platform decisions

Python 3.12+ / asyncio for the bridge (rationale: docs/02 §6). Audio: 16 kHz 16-bit mono
PCM in, 24 kHz mono out (constants in [schemas/audio.json](schemas/audio.json)). Wake
word: user-specified phrase → trained keyword model (openWakeWord) — never an LLM, never
continuous transcription. STT: faster-whisper (`small.en`), GPU where
available (CUDA on the RTX-5080 host; CPU on Mac until a Metal engine is added).

**D10 (2026-07-10): cross-platform hub.** The bridge targets **Windows 11 and macOS as
full peers** (Thomas runs a Windows/RTX-5080 desktop and a Mac laptop; an M4/M5-class
Air can also run B2 locally via Ollama/Metal). Platform-specific code is confined to
exactly two seams: audio endpoint access and the Contract T tool-executor backends
(spec/30 rule 3). Everything else — orchestrator, brains, transports, schemas — is
platform-neutral by construction. Windows is the reference platform (built and tested
first); macOS parity is checked at each milestone, not retrofitted at the end.
Portability design: docs/04 §3.

**D11 (2026-07-12): feedback-first latency posture.** The system guarantees fast
*feedback*, not fast *answers*. Every turn class produces something audible within
**1.5 s** of end-of-speech (the first spoken word, or — since D25 — the overlay's THINKING state). A no-tool
conversational answer must then start speaking within **4 s** (B1) / **5 s** (B2) —
provisional numbers pending the owed measurements (STATE: step-3 live mic test, B1
first-token re-run). A tool-running turn is acknowledged within the same 1.5 s but has
**no completion bound** — it finishes when it finishes and signals with the
`success`/`failure` earcon. Consequences: TTS stays **generate-then-play** for
M0/M1 (sentence-streamed TTS parked; reopen only if measured use feels slow); spoken
tool-progress narration is config-gated, **default off** (silence by default —
the PC overlay carries continuous state). Clock definition in spec/40. No "complex task
mode": long-running work is a property of the turn the orchestrator observes (ToolCall
events), never a spoken mode the user must remember to enter or exit.
*(Amended by D16: "audible feedback" is now "perceptible feedback" at the desk —
earcon, first spoken word, or overlay state change; audible alone must still satisfy
the guarantee away from the screen.)*
*(Amended by D25: the 4 s / 5 s first-word numbers are **demoted from pass/fail gates to
measured diagnostics** — under generate-then-play they are a reply-length proxy, and D23 made
the streaming text, not the first spoken word, the first feedback. The fast-**feedback**
guarantee stands and is now met by the screen. All numbers live in `spec/schemas/targets.json`.)*

**D12 (2026-07-18): dictation joins as an assistant-internal feature.**
The project re-centres on bridge + brain + tools: audio I/O runs on commodity gear
(IEMs + built-in/desk mic). **Dictation** becomes a first-class feature *within* the
assistant (the assistant remains primary): a global hotkey (hybrid — tap = toggle, hold
= push-to-talk) triggers capture → STT → LLM cleanup ("transform, never answer") →
clipboard-paste into the focused app. **Trigger-is-the-mode:** the wake word always
means assistant, the hotkey always means dictation — no spoken mode-switching, no intent
inference. The paste is
deterministic post-processing, never a Contract-T tool — the model cannot invoke it;
only the user's keypress does. Capture stays in RAM (spec/50 rule 3 unchanged). Full
behaviour spec: `spec/60_dictation.md` (owed — drafted after the M0 acceptance run,
sequencing decided 2026-07-18). Design study:
[Review — Gemma & VoiceInk codebases](../docs/01_scoping/Reviews/2026-07-18_1643_Review-gemma-voiceink-codebases.md).

**D13 (2026-07-18): overlay architecture — a separate process on a status feed.** The
PC overlay (spec/40 § Visual output) runs as its **own process**, never inside the
daemon: the orchestrator broadcasts JSON status events — state transitions,
partial/final transcript, mic level, per-turn latency — over a **localhost-only**
socket, and the overlay is a dumb subscriber rendering whatever arrives. Rationale:
crash isolation (overlay death never touches the voice loop) · no GIL contention
between repaints and audio/STT · renderer swappability. Its listening indicator inherits
spec/50's truthful-indicator rule. The feed's message schema lands in `spec/schemas/` at
build (hard rule 3).
Renderer: **PySide6/Qt** on Windows — frameless, translucent, and **non-activating
(BINDING, spec/40)**: the overlay must never take focus, because during dictation focus
determines where the paste lands. A later mac renderer consumes the same feed. Build
order: overlay v0 (state · live transcript · latency readout) lands **before the M0
acceptance run** as its instrument; dictation states at Track D's D2.

**D14 (2026-07-20): the assistant at the desk — teleprompter overlay, third trigger,
in-memory history.** With H parked (D12) the desk is the primary context, and the
overlay graduates from supplement to **first-class surface at the desk**: a
teleprompter rendering the transcribed prompt, the brain's response as it streams
(text deltas), and tool activity — expandable to the full current-session turns.
**Eyes-free is demoted, not deleted:** away from the screen, earcons and TTS alone
must still fully carry the experience (spec/40 amended). **Third trigger — the ask-Gemma hotkey** (push-to-ask): trigger-is-the-mode
survives because each trigger still means exactly one thing — wake word = assistant
hands-free · dictation hotkey = dictation · ask hotkey = assistant push-to-ask. At the
desk the ask hotkey will likely dominate the wake word (instant, zero false-accepts);
the wake word's constituency is away-from-desk — accepted
knowingly. **History: in-memory only** — the expandable view shows the current
session's turns from RAM; nothing is written to disk (spec/50 unchanged); revisit only
if real use demands recall across restarts. Rendering reality: the response side can
teleprompter-scroll from day one (brain deltas already stream); the prompt side
appears as a block at end-of-speech until streaming STT (deferred) exists.
*(Amended by D22: the **⌄ expandable-overlay mechanism is cut** — built, seen and rejected.
The island carries no controls; prior prompts move to the expanded view. In-memory-only and
response streaming stand.)*
*(Amended by D23: "eyes-free is demoted, not deleted" is demoted one step further — audio
away from the screen is a **capability behind a switch**, not an obligation. Speech and the
wake word ship off by default; the Teleprompter always carries the answer.)*

**D15 (2026-07-20): prompt hygiene — shared word-replacement; LLM cleanup as a gated
experiment.** A **deterministic word-replacement layer** (user-curated find-and-replace
table for known STT mishearings — names, jargon; word-boundary matching, longest match
first) runs on every transcript in **both** paths: before `transform` in dictation,
before the brain in the assistant loop. Microsecond cost, no model, fixes only what
it's taught; the table lives in `spec/schemas/` (hard rule 3, schema owed at build).
Separately, **`--clean-prompts`** (config flag, **default off**): the assistant path
may pass the transcript through `transform()` ("fix transcription errors and restore
structure only; change nothing else") before the brain — motivation: long composed
prompts arrive as rambles. Runs **per-prompt**, never per-sentence (self-corrections
span sentences; batch STT yields no early sentences anyway; the incremental-clean
option opens only if streaming STT lands). Engine: a small local model once the Ollama
groundwork (Track B) exists — not the cloud brain. Judged empirically: cleanup gets
its own row in the per-turn latency table, and an A/B on ~20 real transcripts (raw vs
cleaned → compare brain answers) decides default-on or delete. D11's bounds apply to
the flag-off path; flag-on latency is precisely what the experiment measures. The
overlay shows raw → cleaned whenever the flag is on (D14 teleprompter).
*(Amended 2026-07-18/D19 and 2026-07-23/S-06: the cleanup **engine is per-role and
configurable**, not one global choice. **Dictation** cleanup uses **Groq** (cloud, fast/cheap;
key in the tray → `("gemma","groq")`), revising this decision's "not the cloud brain" for that
path. The **assistant-path `--clean-prompts`** engine **stays local for now** — this decision's
latency/privacy argument holds there. Each role selects its own engine in settings (spec/70),
default local. *(The config source landed at D28 and the per-role router at D33, so this plumbing
now exists; what the router does not yet cover is its Layer 2 — see spec/20 §Routing.)*

**D16 (2026-07-20): re-founding — the desk product.** Adversarial review of the
accumulated D12–D15 patches against the original eyes-free spec; every survivor below
survives by re-affirmation, not inertia. Rulings: **(1) Both, always.** At the desk
every answer streams to the overlay **and** is spoken (barge-in intact) — redundant by
design: glance or listen. Away from the screen, audio alone must still carry (D14).
Amends D11 as noted there.
*(Amended by D23: "both, always" becomes **display always, speech by choice**. The
Teleprompter always carries the answer; TTS and the wake word are capabilities behind
switches, default off, and neither gates the project. Ruling (2)'s M0 shape is restated
there too — the ×3 audio-alone variant is no longer a pass/fail criterion.)* **(2) Desk-shaped M0.** The acceptance test now matches the
product: ×10 ask-hotkey turns with overlay streaming + speech, plus a ×3 wake-word
variant proving the spoken path carries alone. Consequence: the ask-hotkey (and the
shared hotkey module) builds **before** the acceptance run — reversing D14's ordering;
Track D's D1 now reuses Track G's hotkey plumbing, not vice versa. **(3) Re-affirmed on
merit:** the capture stack (wake/VAD/whisper — both doors and dictation stand on it) ·
OutputPump's BT keep-alive (any Bluetooth audio) · spec/50 invariants · Contracts B/T ·
the wake word as the hands-free/away door, knowing the ask-hotkey will dominate at the
desk. Nothing else from the eyes-free era binds the desk product.

**D17 (2026-07-20): rewrite mode in principle; interaction-consolidation gate before
Track D.** Field use of VoiceInk (review: docs/01_scoping/Reviews, 2026-07-20)
surfaced a third interaction format Gemma lacked: **rewrite** — select text in any
app, invoke, speak an *instruction* ("make this firmer and halve it"), and the
selection is replaced by the transformed text. Adopted **in principle** as a Track D
slice (D3, after dictation works): selection capture via simulated Ctrl+C round-trip
(Windows) · spoken utterance = the instruction, selection = the content ·
`transform()` with a rewrite-ladder contract (selection → instruction+text →
bare text; see the review §3) · delivery = paste over the selection, user-initiated —
the D12 boundary holds, the model never chooses to paste. **Gate (binding on Track
D):** before any Track D build begins, a dedicated **interaction-consolidation
review** answers "how exactly does a user interact with Gemma?" The trigger inventory
has grown piecemeal — wake word · ask-hotkey · dictation hotkey · proposed rewrite
trigger; VoiceInk ships three unique shortcuts for its three functions, and
alternatives are open (one key + modifiers · press-patterns · selection-presence
switching a shared key · a radial/pill menu on the overlay). Terms of the review:
mode selection stays **deterministic** — no intent inference, the D12 invariant — but
the *mapping* of gestures to modes is open, including revisiting how many distinct
keys exist. Output: a consolidated trigger scheme recorded as its own D-number and
encoded in `spec/60_dictation.md` (which is drafted only after the review).

**D18 (2026-07-20): Contract H excised — the custom headset is cancelled, not parked.**
The "do I actually want to build this" test (D12's stock-hardware-first plan) came back
negative: AirPods and IEMs deliver excellent audio, so the custom bone-conduction
headset isn't worth building. **Contract H, the H0–H4 ladder, the transport adapters, the
M3 milestone, and all attendant language are removed from current truth** — the design is
preserved in git history + the frozen docs/01–04 if ever revived. Supersedes the headset
halves of D12 (parking → cancellation), D13 ("a second headset made of pixels"), and D16
((3) parked banner). Survivors the desk product inherited stay, reframed: the audio
format constants (16 k / 24 k) moved from the deleted `messages.schema.json` to
`spec/schemas/audio.json` (loaded by `wake.py` / `speak.py`); `earcons.json` (the bridge
plays them); spec/50's truthful-indicator rule (now the overlay's indicator, not an LED);
OutputPump's BT keep-alive (any Bluetooth audio); push-to-talk (now the hotkey).
`spec/10_contract_h.md` and `messages.schema.json` are deleted; audio stays commodity
(AirPods / IEMs / desk mic).

**D19 (2026-07-21): the Teleprompter formalised — component P, Contract P, front/back
split.** The on-screen overlay is named the **Teleprompter** and lettered **component P**
in the naming scheme (legend above); the localhost status feed it subscribes to is
**Contract P** (`spec/schemas/status.json`). Architecture (D13 restated as a contract):
the system splits front/back. The **back-end** is the headless `bridge/` daemon, which
owns a **crash-isolated broadcaster** (`bridge/broadcaster.py`) publishing Contract-P
messages as NDJSON over a localhost-only TCP socket (127.0.0.1, the docs/04 §5 reserved
port 8990). The **front-end** is a new top-level **`teleprompter/`** package (PySide6 +
QML) — a dumb subscriber that renders whatever arrives and never drives the voice loop.
*(Amended by D24, 2026-07-22: still a subscriber, and it still cannot drive the loop — but it
owns the display decisions the daemon could only guess at, and may send one upstream verb,
`dismiss`, which cancels and never commands. spec/50 rule 12.)*
**Crash-isolation is by construction:** the broadcaster's `publish()` never blocks and
never raises, and a busy port just disables the feed, so a slow, absent, or dead overlay
(or the broadcaster itself) can neither stall nor crash the orchestrator. The always-up
daemon is the server; the overlay is the reconnecting client. Contract P gains an
**`error`** message (`kind` + human-facing `message`) so the surface can explain a fault,
not merely flag it. Secrets stay provider-scoped in the OS credential store (spec/50 rule
10): the tray's cleanup-engine field writes the Groq key under `("gemma","groq")` —
per-role provider *routing* is a later concern (STATE Parked/someday), kept out of the key
name. Supersedes the `bridge/ui/` code-path (now `teleprompter/`) in the component
inventory and spec/40. Build sequence and progress: STATE Track P.

**D20 (2026-07-21): the two-door interaction model.** The D17 interaction-consolidation
review (held 2026-07-21) resolved to **two doors, not three modes**: **dictate** (dumb)
and **ask** (smart), one hotkey each (bindings live in config — spec/70), hybrid
tap-toggle / hold-PTT per key (D14). **Dictate:** capture → deterministic word-replace
(D15) → `transform` cleanup → paste at the caret — no intelligence beyond cleanup,
ever. Safety rule: invoking dictate while text is selected warns on the Teleprompter
before pasting over it. **Ask:** the full assistant — utterance + context (selection,
clipboard) go to the brain, which *is* the toolpicker: Contract B tool-calling over the
tools.json registry routes intent (answer · rewrite · fetch · act). Answers render on
the Teleprompter and speak (D16). *(Amended by D23/S-04: answers render **always**;
they are **spoken only with speech enabled** — default off. "and speak" reads as
unconditional above; D23 made it a switch.)* **Rewrite is not a mode — it is an ask outcome**
(supersedes D17's separate-slice framing; the selection is the content, the utterance
is the instruction). Write-actions from the ask door are **propose-then-tap** by
default: the proposal renders on the Teleprompter and a second tap of the ask key
applies it — only a user keypress ever pastes (D12). An **`auto_apply`** setting
(spec/70, present from the first config, **default off**) bypasses the tap knowingly.
The wake word remains the hands-free second entrance to the ask door — no new mode.
Resolves D17's gate: Track D is unblocked by this record (the M0 acceptance run
remains its other gate).

**D21 (2026-07-21): Rust port — evaluated and deferred.** An adversarial runtime
review (external critique + counter-analysis, 2026-07-20/21) examined moving the
engine to Rust. **Ruling: finish the app in Python first; port later, if ever —
triggered by observable facts, not rhetoric.** The port plan is preserved so a future
port inherits it ready-made: **back-end only, behind Contract P** — a Rust daemon
(Tokio · `cpal` capture · ONNX runtime for STT/VAD/wake · `reqwest` streaming brains ·
native hotkey/paste seams) publishing the same NDJSON feed on the same port, so the
QML Teleprompter keeps working unchanged and doubles as the port's live behaviour
oracle; same-repo Cargo workspace; the Python engine becomes the reference
implementation. **Re-open triggers (any one):** ① measured pain — boot-time/RSS
instrumentation (a planned Contract-P addition) shows real leak or latency problems in
daily use · ② Gemma becomes an always-on battery-powered laptop daemon · ③ shipping
to a second non-technical user (signed-installer era). **Anti-relitigation clause
(binding on every session, human or AI):** no runtime/architecture re-debate until the
Python app is feature-complete (Teleprompter C2/C3 · hotkeys · dictate door · ask
door) *and* the instrumentation has produced numbers. Recorded findings: the engine's
heavy work runs in native GIL-releasing libraries; leaks are logic bugs in any
language, bounded here by fixed buffers and discard-after-use; slow boot is model
loading (any runtime) — answered by tray-residency, not a rewrite.

**D22 (2026-07-21): the island carries no controls — the ⌄ handle is cut, everything it
promised moves to the expanded view.** D14 gave the overlay a **⌄ handle** that expanded to
the session's prior prompts. It was built, seen in place, and **rejected**: the tab hanging
below the pill spoiled the line of an otherwise sleek teleprompter. **The island is now a pure
display surface with no interactive elements at all.** Consequences: (1) prior prompts move
into an **expanded view**, which becomes the single home for everything the island deliberately
does not carry — prior prompts, the **full text of a long reply** (the island caps at 3 lines
and scrolls, so this is also how spec/40's "longer answers: full text on the overlay" is
honoured), and **copy / save / export**. Its design is explicitly NOT settled here and gets its
own pass; recorded now because the override itself is decided and the code already reflects it
(hard rule 1). Scope caution for that pass: copy is safe, save/export must reuse spec/50's
transcript-logging rather than invent a second path, and "send" is an integration belonging
behind Contract T (M1+), not a button the overlay owns. (2) Having no controls is what lets the
island be **wholly click-through** (`WS_EX_TRANSPARENT`) so it never intercepts a click meant
for the window beneath it — it sits over a maximised browser's tab strip. **Implementation
warning:** do NOT reach for `QWindow.setMask()` for this; Qt documents it as an input hint but
on Windows it is `SetWindowRgn`, which clips *painting* too (measured: island 70% painted
before, 10% after). Per-region click-through in a single window would need `WM_NCHITTEST` →
`HTTRANSPARENT`; unnecessary while the island has no controls, and the expanded view wants its
own window regardless. Supersedes D14's expandable-overlay mechanism; D14's other rulings
(in-memory only, response streaming, eyes-free demoted) stand.
*(Amended by D27, 2026-07-23: the expanded view is now built as a "peek". "No controls" holds **at
rest**, but the island takes hover+clicks over its silhouette while a reply is peekable — so
click-through is now **per-region** (`WM_NCHITTEST`), not the blanket `WS_EX_TRANSPARENT` this
decision relied on. In-memory-only stands.)*

**D23 (2026-07-21): identity — a UI-first desk assistant; display always, speech by choice.**
States plainly what the build has become, and settles the drift between a spec that made
speech mandatory and a working intent that treats it as a feature.

**Identity.** Gemma is a **UI-first desk assistant on Windows**: an STT + AI pipeline whose
surface is the **Teleprompter**, reached through two doors — **dictate** (speech to text at the
caret) and **ask** (the assistant, which also rewrites and calls tools). Closest kin are
VoiceInk and Siri, but the shape is its own: dictation and assistance over one capture stack,
one brain contract, one visible surface. This is a statement of what exists, not a change of
direction — **D12 stands unchanged**: dictation remains a first-class feature within the
assistant, and the assistant remains primary.

**The Teleprompter is the spine.** Every answer renders on it, always. It is not optional, not
configurable, and not a supplement: D20's propose-then-tap cannot function without it (an
ask-door rewrite has nowhere to show its proposal), and dictation's feedback depends on it.
Accordingly PySide6 stops being an optional `[ui]` extra and becomes a core dependency.

**Speech and the wake word are demoted, not retired** — this is the substantive amendment to
D16(1)'s "both, always". Both remain fully built and supported; both move behind user
switches, **default off**; and **neither gates the project's success**. Out of the box Gemma is
hotkey-driven and screen-only. Turn on **speech** and answers are spoken as well as shown; turn
on **"listen for me"** and the always-on-mic behaviours — wake word and barge-in — come alive
together (they are one privacy decision, not two: both open the mic without a keypress, so they
share one switch, and the truthful-indicator rule of spec/50 rule 4 governs both). Settings
live in spec/70.

**The away-from-screen guarantee is demoted from BINDING to a supported capability.** spec/40's
"earcons and TTS alone must still fully carry the experience" was the last load-bearing residue
of the cancelled eyes-free/headset era (D18). Walking away and talking to Gemma still works —
that is what speech-on and the wake word are *for* — but it is no longer an obligation the
whole system is held to, and no longer something the acceptance test proves. This retires the
residue without retiring the capability.

**Consequences.** (a) M0's acceptance test becomes display-first: ×10 ask-hotkey turns with the
answer streaming to the Teleprompter, feedback < 1.5 s; the spoken path is exercised only with
speech enabled, and the ×3 "spoken path carrying alone" variant is no longer pass/fail.
(b) spec/40's narration rules and § Visual output are reworded accordingly. (c) The parked
"listen for me" decision is **settled here** rather than left owed. (d) D11's feedback budget is
unaffected — "perceptible feedback" already counts an overlay state change, so a screen-only
Gemma still meets it.

**D24 (2026-07-22): the Teleprompter owns what is on screen — Contract P gains one upstream
verb.** Three display bugs in three days had one root: **the daemon was deciding things only
the overlay could see.** It timed how long an answer stayed up (a guess at the island's own
typing speed — first a flat 8 s, then 8 s + 0.45 s/word, and it blanked long answers mid-reveal
both times); it decided when the prompt gave way to the reply (which truncated any prompt past
~11 words, every warm turn); and it armed the bare Esc key against its own idea of what was
displayed (holding Esc hostage from every other application for up to 90 s per turn, while the
loop that was actually running never once looked at it). None of these are facts the daemon
possesses. All three are facts about a reveal happening in another process.

**Ruling.** The overlay owns the display: when the prompt hands over, when the island stops
showing, and the Esc key that dismisses it. The daemon owns the voice loop and says only what
it knows.

- **`idle` is demoted to "the daemon is free".** It no longer blanks the island and no longer
  clears the turn. The overlay hides itself a fixed interval after the text has **finished
  revealing** — the clock finally starts from the right event, so the knob is a legible
  "N seconds after it finishes appearing" instead of a per-word estimate of someone else's
  animation.
- **The turn-clear moves onto `listening`.** Opening a capture window *is* the clear, so the
  binding "never draw the mic bars over a stale answer" stops depending on a caller remembering
  to blank first — which is exactly how the barge-in entrance came to violate it. Sound only
  because every capture window is now user-initiated (the follow-up window is gone); if a
  non-turn capture ever returns, this must change back **before** it lands.
- **Contract P stops being strictly one-way.** The overlay may send exactly one message,
  `dismiss`, and the daemon accepts nothing else (allowlisted from `status.json`). This
  **amends D19's "never drives the voice loop" and spec/70 §2's "no control channel back"** —
  both written before dismissal existed as a gesture. The replacement guarantee is narrower and
  stated as **spec/50 rule 12: the upstream channel can cancel, never command.** It can only
  stop work already in flight; it can never start a turn, invoke a tool, or change a setting.
  The exposure it adds is minor next to what the same socket already grants a local process —
  which is to *read* every prompt and reply.
- **Esc moves to the overlay**, which registers it only while the island is on screen. That is
  exact rather than inferred: the overlay *is* the window. A press hides the island immediately
  and tells the daemon afterwards, so dismissal never waits on a busy or dead daemon.
  spec/50 rule 11 (narrow registration, no keyboard hook) governs it unchanged. Ask and dictate
  keep their modifiers and stay with the daemon.
- **Deletions this buys:** the daemon's dwell constants and `answer_dwell()`, its `self.shown`
  guess at the island's contents, and the whole transient-door arming protocol in
  `bridge/hotkeys.py` (with its cross-thread race on `_armed` and its duplicated hotkey-id
  derivation). `parse_binding` loses its modifier-less exemption entirely.
- **Cost, eyes open:** with the Teleprompter not running there is no dismiss gesture at all
  (the ask key still interrupts) — coherent with D23's "the Teleprompter is the spine". The
  overlay needs a Win32 native event filter; macOS is unbuilt there, the same seam
  `bridge/hotkeys.py` already has. `status.json` → **v0.3.0** (`dismiss` message; the clearing
  rule and the upstream allowlist promoted from prose to loaded data, hard rule 3).

Source: the adversarial review of 2026-07-22 (G-01, G-02, P-01's class, and STATE's own
refactor brief — *"a fact living on two sides of a seam, and one side not being told"*).

**D25 (2026-07-22): latency targets re-derived for the desk, and made a single source.** The
acceptance criteria are **D11 (2026-07-12) — written for the eyes-free headset era**, and never
re-derived after D18 cancelled the headset or D23 made the screen the spine. Audited 2026-07-22.
Two things were wrong and one was messy:

- **`first_word` (< 4 s B1 / < 5 s B2) was a latency gate that is really a reply-length cap.**
  Under generate-then-play (D11) the first spoken word waits for the *whole* reply to be
  generated and synthesised, so its latency scales with reply length — the acceptance run fits
  ≈ 2100 ms + ~45 ms/output token, i.e. the 4 s "gate" is a ceiling of ~42 tokens dressed as a
  stopwatch. And since D23 the streaming text on the island, not the first spoken word, is the
  first feedback. **Demoted to `measured`:** recorded per turn as a diagnostic, never pass/fail.
  M0's acceptance test already treated it this way ("measured when speech on, not pass/fail");
  this makes the spec and the overlay agree. A first-word *target* becomes meaningful again only
  with sentence-streamed TTS (parked, D11) — reopen that with the measured number, not on feel.
- **The `feedback` gate measured the headset, not the desk.** The instrument credited only
  *audible* events, so it reported our own 1.4 s `working`-earcon timer every turn and gave the
  screen zero credit — even though D16 says an overlay state change is perceptible feedback. The
  instrument now credits the near-instant flip to THINKING; the earcon is the speech-mode
  fallback. The fast-feedback guarantee stands and is now honestly met by the screen.
- **The numbers lived in four places** (spec/40 prose · `Overlay.qml` · the orchestrator's
  latency table · scattered comments) and had already drifted once (frozen docs/02 still carry
  the pre-D11 values). Consolidated into **`spec/schemas/targets.json`** (executable truth, hard
  rule 3), each target carrying its value, its `kind` (`floor` / `gate` / `measured`), and its
  clock. The overlay's readout and the latency table load it; the reclassification is now *data*
  the renderer obeys, so first_word cannot be coloured over-budget by a stray literal.

Kept unchanged and still sound: the 300 ms acknowledgement floors (wake, key-press), the 250 ms
barge-in stop, and the 1.5 s feedback *principle*. Source: the gates audit of 2026-07-22
(follows the B-01 finding, which is what surfaced the reply-length relationship in the log).

**D26 (2026-07-23): Tier-3 confirmation is a keypress, spoken alt when speech on.** The Tier-3
gate — the binding confirmation before a destructive tool runs — was written 2026-07-12 as
"play the `ask` earcon, user says 'confirm' within 8 s." That predates D20 and D23: the default
product now opens the mic only on a keypress and ships with speech off, so **there is no channel
on which to say "confirm"** — the safety gate on the most dangerous actions was unexecutable in
the default configuration. D20 had already invented the desk-native equivalent (propose-then-tap:
a proposal renders on the Teleprompter, a keypress applies it), so Tier 3 adopts it:

- **The proposed action renders on the Teleprompter; a keypress confirms it.** This is the same
  gesture D20 defined for ask-door rewrites — one confirmation mechanism, not two.
- **Spoken "confirm" within 8 s remains the equivalent gate when speech is on**, with the `ask`
  earcon (which now sounds only in that mode).
- Nothing was decided wrongly in 2026-07-12; Tier 3 simply was never revisited when the
  interaction model changed underneath it. Updates spec/30 (tier table), CLAUDE.md hard rule 4,
  `earcons.json` (`ask`), spec/40 narration. **No code** — Tier-3 tools are M1, unbuilt; this
  records the executable gate so it is right when the executor lands. Source: review S-02.

**D27 (2026-07-23): the expanded view — the island grows in place to "peek" the current turn, and
now takes input over its own silhouette (amends D22).** D22 cut the ⌄ handle, made the island a
controlless wholly-click-through surface, and parked the expanded view for its own pass. This is
that pass. **Hover a shown answer** and the island hints (a few px of downward nudge + a pointer
cursor); **click** and it grows *in place* — same black surface, same top-edge flares — into a
larger panel that reads the **current turn** in full: the prompt pinned and **collapsible past two
lines** (a genuinely long composed prompt is a Claude job, not this surface), the reply scrolling
under an always-on top/bottom fade, and **Copy** (clipboard) + **Save** (a save dialog). Height is
content-clamped between a floor and a ceiling; past the ceiling the reply scrolls with the prompt
and actions pinned. Esc collapses the peek before it dismisses the island; the answer-dwell pauses
while peeking.

- **Amends D22's "no controls / wholly click-through".** For the island to take a hover and a
  click it can no longer be blanket `WS_EX_TRANSPARENT` — which also stops it receiving
  `WM_NCHITTEST` at all. Click-through becomes **per-region** (`WM_NCHITTEST → HTTRANSPARENT`, the
  filter proven in `sandbox/qml_spike`): the painted silhouette takes input **only while there is a
  settled answer to peek**; the surrounding frame — and the whole island whenever nothing is
  peekable — stays click-through, so a click over empty frame still reaches the app beneath. The
  cost D22 avoided is now bounded to *while an answer is showing*, never at rest (idle hides the
  window entirely).
- **In-memory, current-turn only (D22/D14 stand).** Peek reads the turn already on the feed;
  nothing is written and no new Contract P message exists (`status.json` unchanged). Cross-session
  scroll-back and the full session view remain a later, separate surface tied to the
  conversation/memory model.
- **Save is user-initiated export** (spec/50 rule 3): every transcript is already logged to
  `logs/gemma.log`, so saving an on-screen answer to a file the user picks is strictly less
  exposure than the existing log. The host (`__main__.py`), not QML, owns the clipboard and dialog.
- Widens D14's expandable-session-view scope. Renderer: `teleprompter/PeekPanel.qml` +
  `Overlay.qml`; native input + actions in `teleprompter/__main__.py`. Guarded in `overlay_check`.
  Blueprint: `sandbox/teleprompter-expanded-mockup.html`.

**D28 (2026-07-24): earcon vocabulary cut to three, and TTS/Pings gated by a config file (TTS
default off, Pings default on).** The earcon set was seven meaning-bearing tones written for an
eyes-free device (D18). Since D23 made the screen the spine and D25 made its THINKING state the
feedback, most of them duplicated something already visible. Cut to **three designed WAVs** that
read as the device's own pings rather than a vocabulary of distinct meanings:

- **`listening`** (was `awake`) — a capture opened. **`success`** (was `task-complete`; also folds
  in the held-long-answer `answer-ready` and a future `timer`) — a result landed well.
  **`failure`** (was `error`; also absorbs the Tier-3 `ask`) — something needs your view. Retired
  outright: **`working`** — the screen's THINKING state is the feedback (D25). A normal no-tool
  turn now plays one sound (`listening`) or none.
- Designed WAVs (`bridge/assets/earcons/<id>.wav`, 24 kHz mono) replace the generated tones; the
  runtime loads them with the stdlib `wave` module — no audio-codec dependency.
- **Resolves the long-open "are earcons gated by the speech switch?" question (STATE):** no —
  earcons are their own channel behind a **Pings** toggle (default **on**); spoken **TTS** is a
  separate toggle (default **off**, the D23 capability — previously always-on in code).
- **Both toggles are the first step of spec/70's settings surface**, not a throwaway: a small JSON
  file at `%APPDATA%\gemma\settings.json`, written by the tray and read by the daemon, via
  `bridge/settings.py`. The full settings **page** is still owed (spec/70).
- Updates: `earcons.json` (→ v0.4.0), `speak.py`, `orchestrator.py` (remap + the `working`/G-03
  deadline machinery removed), `tray.py`, spec/40, spec/70, STATE. The `task-complete`/`ask`/`timer`
  mappings are **schema/spec-only** — those code paths (Tier-2 tools, Tier-3 propose-then-tap,
  timers) are M1, unbuilt; this records the mapping so it is right when they land. Source: Thomas,
  the owed earcon-redo session.

**D29 (allocated 2026-07-24; built 2026-07-27): the settings window — a schema-driven QML surface,
two sections.** spec/70's config surface, realised (the number was in use by the code and D30
before this record existed). A frameless PySide6/QML window — `Controls.Basic` borrowed only for
text entry, scrolling and popup dismissal; every visible control is hand-drawn to match the
island's austerity — spawned on demand from the tray (D13, zero idle cost) and reading
`spec/schemas/settings.json`, the **executable truth** (hard rule 3): panes, groups, labels,
defaults, `built` flags and the provider catalogue all live there, so a knob is a JSON edit and
nothing else. This answers spec/70 §4's open "does the config shape need a schema file" — yes, and
that is the file.

- **Two sections behind a top-bar toggle.** **Models** is the provider roster — an editor card per
  model in a horizontal band (Ask = the answer brains, Dictate = the cleanup roles); each card is a
  small editor: the model **well** (opens the live picker, D30), the dials the provider actually
  offers, on/off, primary, a key-status footer, and a gear that opens the Add/Edit sheet for the
  deep bits (key, temperature). **Config** folds Profile · Preferences · Triggers into one list.
- **Adapter-aware, as spec/70 §2 requires:** a card shows only the knobs its provider has — Claude
  effort + extended thinking, a local model temperature, Groq neither (a Notes line fills the card).
- **The tray's truthful mic indicator (spec/50 rule 4) is carried in the window too**, in the top
  bar — mic-closed · mic-open (wake ring) · listening (live), the three states the privacy argument
  turns on.
- **Look (Thomas, 2026-07-26/27):** cool near-black, a single **white** UI accent, coral for the
  on-air indicator, pink for faults; bold normal-case **Archivo** for headings (an earlier
  wide-caps "Marathon" pass was rejected as looking like a sports app), **Martian Mono** strictly
  for machine values (model ids). **Instrument Serif is bundled and registered but deployed
  nowhere** — reserved for a serif accent on an explicit later say-so. Tokens live in `Theme.qml`;
  the island's pure black stays reserved for the island.
- Files: `teleprompter/SettingsWindow.qml` + `KeyRecorder.qml` (+ `qmldir`), `settings_model.py`
  (the Qt↔config/keyring bridge), `settings_check.py` (offline guard: fails on any QML warning,
  clips-checks every glyph; CI-wired), `Theme.qml`, bundled fonts. Keys never touch the settings
  file — OS credential store only (spec/50 rule 10). Source: Thomas, the M0-close settings sessions.

**D30 (2026-07-24): B2 widened to "any OpenAI-compatible endpoint" — ten providers, one adapter.
The router is explicitly NOT part of this.** The settings window offers eleven providers
(D29) but only Anthropic could be called, so the window could offer a brain the daemon had no way
to reach. Thomas's direction: build the adapters out fully, and Groq should serve as a brain and
not only as the dictation cleanup engine.

- **One adapter, not nine.** Every provider except Anthropic speaks OpenAI's
  `/v1/chat/completions` — Groq, OpenAI, xAI, DeepSeek, Mistral, OpenRouter and Google's compat
  layer in the cloud; Ollama, LM Studio and llama.cpp locally. What differs between them is a base
  URL and a credential, so `bridge/brains/compat.py` is parameterised by both and spec/20's **B2
  row was widened rather than a fourth row added**: "local OpenAI-compatible server" and "cloud
  OpenAI-compatible API" were never two pieces of code. B2 therefore arrives before M2, and M2
  "it's local" becomes a question of which endpoint it is pointed at.
- **Reachability is schema truth** (hard rule 3). Each provider card gains `wire`
  (`anthropic`|`openai`), `api` (cloud base URL), `env` (env-var fallback), and `adapter: true`;
  local runners keep their user-editable `endpoint` and B2 composes `http://<endpoint>/v1`, the
  compat convention all three share. `bridge/brains/providers.py` reads it; no adapter hardcodes a
  host, a key name or a model id. B1 stopped hardcoding its own keyring account name in the same
  pass. `settings.json` → v0.2.0.
- **Fixes a live fault in B1.** `spec/schemas/tools.json` spells `parameters` and carries `tier`;
  Anthropic requires `input_schema` and rejects unknown fields, and the registry was being passed
  through verbatim — so the first real tool call would have 400'd and surfaced as an unexplained
  apology (a 400 maps to the generic case by B-02). **Tool translation is now the adapter's job**,
  stated in spec/20, and `tier` never leaves the machine.
- **Live model lists, and a Test button** (the latter Thomas's call, same day). The picker's
  `models` array is the offline fallback — **empty for every provider but Anthropic** — so the real
  list comes from `GET {api}/models` (Anthropic via its SDK), fetched off a worker thread so the
  window never blocks. A `not_chat` substring list in the schema drops what cannot serve a turn:
  measured, not speculative — Groq returns 15 ids of which 7 are speech, TTS or safety
  classifiers; OpenAI returns 129 including embeddings and image models.
- **Fetching the model list IS the key test, so one button does both.** It follows that the fetch
  must report WHY it failed rather than returning an empty list: `probe()` returns
  `(ids, status)` over a closed set — `ok · nokey · auth · unreachable · empty · error` — because
  a rejected key and a dropped connection are the same empty picker otherwise, and the user can
  act on one but not the other. Classified by exception type and status code, never message prose
  (the B-02 rule). The button passes the **typed** key, not the stored one: the Add flow saves a
  key only on commit, so probing the credential store would test the previous key or none —
  which is precisely why a pasted key appeared to do nothing. Candidate keys are used for the
  call and never written.
- **Deliberately out of scope: the router** (Thomas, explicitly). spec/20 §Routing stays unbuilt,
  so `primary` remains written-but-unread and the orchestrator still constructs B1 directly.
  Recorded as a known gap rather than hidden. The `transform` verb (dictation cleanup, D12) is the
  next Contract B change and is not in this decision.
- Verified live: Anthropic and Groq (model fetch + a streamed turn). The other nine share the exact
  code path but no key has been held to them here. Guarded: `bridge.brains.providers`,
  `bridge.brains.compat --selfcheck`, `bridge.brains.claude --selfcheck` (tool translation against
  the real registry), `teleprompter.settings_model`.

**D31 (2026-07-27): the Tier-1 tool executor — Contract T runs, and the brain loops over it.**
Track T's first build (spec/30). The registry has existed since M0 but nothing executed it; now
`bridge/tools.py` does, and the assistant turn is a multi-round loop rather than a single reply.

- **The loop lives in the orchestrator; the adapter only serialises.** `converse` still handles one
  round and surfaces `ToolCall`s — it never executes (spec/50 rule 1), exactly as the contract
  always said. `Orchestrator._collect` executes each call through Contract T, has the adapter record
  the round into history in its own wire shape (`record_tool_round` — Anthropic content blocks vs
  OpenAI `tool` messages, the one place the two wires diverge here), and re-enters `converse` with
  an empty utterance until the brain answers. One retry on `malformed_tool_call` (spec/20), a
  5-round cap, and history committed only on success so an aborted turn leaves no dangling user
  message. spec/20 "The tool loop" is the interface record.
- **The brain sees only tools it can actually call** (spec/30 rule 3). `tool_specs()` offers only
  tools with a backend on this platform and within `MAX_TIER` (today 1), so the two Tier-1
  read-only tools — `system_status`, `read_clipboard` — are all that is exposed; `execute()`
  re-checks the allowlist as the real defence. Tier 2 (announce earcon) and Tier 3
  (propose-then-tap, D26, which renders on the Teleprompter — a separate surface, the UI session's
  lane) are deferred.
- **Every call is audited** (spec/30 rule 2, CLAUDE.md hard rule 4): one JSONL line per invocation
  — run, refused or errored — in `logs/audit.jsonl`, purged with the rest of `logs/` (spec/50
  rule 3). A tool fault becomes a string the brain narrates, never a crash.
- **The persona stopped lying.** `base.py::DEFAULT_SYSTEM` claimed "you have no tools yet"; the
  model now learns its tools from the wire tool list, so the false clause is gone (a per-turn
  capability clause remains the M0.5 persona work). `system_status`'s volume and media fields need
  COM/WinRT and are deferred — time · active window · battery ship now. Guarded + CI-wired:
  `bridge.tools`, the loop/retry/cap in `bridge.orchestrator`, and `record_tool_round` in both
  adapter selfchecks. Source: Thomas, the adapter → dictation → tools sequence.

**D32 (2026-07-28): Gem the mascot arrives — first surfaces.** Thomas commissioned a pixel ghost
("Gem") derived from the Gemma mark; it is introduced STAGED, and only where it earns its place.

- **One renderer, three surfaces.** `teleprompter/gem.py` reads the kit's palette-indexed frames
  (`teleprompter/gem/gem-sprites.json`, its own source of truth — never hand-edited) and paints a
  QImage/QIcon. It feeds the Windows **taskbar / app icon** (`portrait.plain` on a rounded chip), the
  **tray** (animated by the live status feed, `tray.py`), and the **settings top-bar** (via a
  `QQuickImageProvider`, `image://gem/<state>/<frame>`), which replaces the on-air lamp.
- **The body flips, the accents don't.** Gem's native body `#1B1714` is invisible on the black island
  / dark shell, so on dark surfaces the body renders light and the eyes become holes — the kit's own
  dark-surface rendering, a one-line palette MAP over the indices (README: "ship the indices, not the
  colours"), NOT a repaint or a second export from Design. Gem's purple/orange accents are kept
  exactly (Thomas); the tray flips the body by the Windows **taskbar** theme
  (`SystemUsesLightTheme`). *(Amended 2026-07-28: this read "the Windows light/dark setting", which
  is the APP theme `AppsUseLightTheme`. The two differ on a common Windows 11 combo — light apps,
  dark taskbar — and a tray icon lives on the taskbar, so the app setting rendered Gem's dark body
  invisible. The fallback is the light body, since the usual taskbar is dark.)*
- **Truthful, never decorative** (spec/50 rule 4): every surface is driven by the real Contract-P
  state, so `listening` / `asleep` mean the mic truly is / isn't capturing. `gem.gem_state()` maps the
  daemon's few extra states (dictation's transcribing / transforming / pasted) onto the nearest Gem
  and rests unknowns at idle, so a consumer never KeyErrors.
- **Staged, per Thomas.** Settings shows only `arriving` (on open) → `idle` → `listening` (mic on);
  the tray shows the full vocabulary and animates every state that has more than one frame, idle
  included — only a genuinely single-frame state rests. *(Amended 2026-07-28: idle and asleep used
  to rest on one frame, "no perpetual wiggle". Thomas wants the tray reading alive rather than
  frozen on frame 0, so the exemption is gone.)* The overlay island is deliberately left untouched
  for now. Guarded: `teleprompter.gem` (CI-wired) +
  the Gem row driven through `settings_check`. Live-on-the-box verification (tray, taskbar, entrance)
  is owed — headless cannot show them. Parked kit extra: the costume portraits for settings sections.

**D33 (2026-07-28): the per-role router v1 — the model picker finally bites.** Until now the
settings model-picker was decorative for the assistant: `primary` was written-but-unread and the
orchestrator constructed B1 (Claude) directly, so the D30 multi-provider adapters went unused by the
answer brain. `bridge/brains/router.py` closes that: a ROLE resolves to the configured provider +
model, read fresh from settings each turn.

- **Roles → settings, v1.** `assistant` ← `primary`; `cleanup_dictation` / `cleanup_prompts` ← their
  own keys; each names a provider whose card config lives in `models[<provider>]`. `resolve` returns
  the config or `None` (unconfigured); `build_for_role` builds the adapter via
  `providers.build_brain`. The orchestrator caches on `signature(role)` and rebuilds only when the
  pick changes — the client is kept across turns (spec/20 adapter lifetime), yet a change lands on the
  next turn with no restart. Unconfigured → the daemon default (`DAEMON_MODEL` / the Groq cleanup
  default), so a fresh profile still answers; an injected brain (replay) bypasses the router.
- **Deliberately v1 only.** NOT the several-instances-per-provider redesign (spec/70), NOT
  per-task-type routing ("short → cheap") + its classifier, NOT `local_only` policy mapping — those
  are Layer 2, and v1 is the foundation they sit on (the `build_for_role` seam does not change when
  they land, only the data the router reads). B1 effort/extended-thinking stay unwired (M0.5), so a
  card's `effort` reaches only the B2 wire for now.
- Guarded: `bridge.brains.router` selfcheck (resolution + signature, no network; CI-wired). spec/20
  §Routing rewritten from "not built" to v1-built. Source: Thomas — "respect the config the user
  inputs, so if the user says use X, it actually does so."

**D34 (2026-07-28): model + token count in the peek footer.** The expanded-answer view now names the
model that produced the reply and the turn's total token count — `claude-opus-4-8 • 1,847 tokens`, a
quiet Martian-Mono line bottom-left, opposite Copy/Save (variant A of the sandbox; Thomas). It rides
Contract P: the `response` message gains optional `model` + `tokens` fields (`status.json` → v0.5.0),
stamped by the orchestrator on the `done` message — the model from the router-resolved assistant
brain (`.model`), the tokens summed from each round's `Done(usage)` across the tool loop (input +
output). The overlay reducer reads them (`decode.OverlayState`), `OverlayModel` exposes them, and
`PeekPanel` renders the footer once the reply settles. Both fields are optional and absent on
streaming deltas, so an older sender just shows no footer. Guarded: the shape in
`bridge.broadcaster --selfcheck` (validates against the schema) + the read in
`teleprompter.decode --selfcheck`; overlay/settings checks green. Owed: live on the box — peek a real
answer and read the footer.

**D35 (2026-07-29): the Gem sprite kit goes to v3 — Gem gains behaviour; the tray gets a mic ring
instead.** Design shipped two kits in a day (v2, then v2.2/v3), and neither is drop-in over v1: the
cell grew from 20px (props can now leave the body — a guitar, a phone, a laptop), a state is no
longer a flat frame list but a set of named **clips** with policies (`loop` / `oneshot` / `hold`),
and the kit carries its own **timing script**. `idle/rest` is a single frame, so the character is
now the script's, not the app's. Landed as one decision because none of it shipped separately.

- **The kit's script runs in `gem.py`.** `GemPlayer` is a Qt-free port of the kit's own
  `gem_sprites.py::GemPlayer` (minus its Pillow dependency): base loop, scripted idle clips,
  enter/exit clips on a state change, holds that freeze until released.
  `QmlGem` puts it on a QTimer and gives QML one bindable URL, so the settings window sets a state
  and binds a source — it no longer counts frames or hard-codes a one-shot's length. Kit-side
  reference loaders (`gem_sprites.py`, `gem_sprites.rs`) are deliberately NOT vendored: `gem.py` is
  the renderer, and a second loader would be a second, divergent source of behaviour.
- **Both palettes now come from the JSON.** The kit ships a light AND a dark hex per role (plus a
  `shade` role for depth on the body), so each ground takes the set drawn for it — amending D32's
  "the accents don't flip", which predates the kit having ground-specific accents (Thomas). Only the
  body and eye are overridden, to the app's own off-white and true black. Still a MAP over the
  indices, never a repaint.
- **The tray is no longer a Gem surface.** Thomas is commissioning a separate set for it; until then
  the tray draws its own **mic-level ring** — a hollow ink circle while the mic is closed, a coral
  (`Theme.flare`) core with a halo that grows and brightens with the real RMS while it is open. Same
  honesty rule (spec/50 rule 4), fewer moving parts: no timer, mic frames are the clock, and the
  repaint is gated on a 12-step quantisation so a steady voice is a handful of `setIcon` calls a
  second. This retires `tray.make_icon` / `tray.mark_icon` (dead since D32) and their `ponytail:`
  note asking for exactly this on-air behaviour.
- **What v1 named and the new kit does not.** `portrait.plain` is gone — the app icon uses
  `idle/rest`, a genuine one-frame still. `arriving` is gone, so the settings window has no
  entrance; idle running its own fidgets is livelier than the fixed one it replaces.
  `question` / `alert` are gone;
  `permission` → `needs-permission`, `asleep` → `resting`, and `misheard` is now a hold clip inside
  `listening`. `gem.gem_state()` (D32's feed→Gem map) went with the tray, its only consumer — the
  next Gem surface will map whatever vocabulary it needs.
- **The kit is Design's 26px build (v2.2, 2026-07-29).** The 32px cell carried dead margin in every
  frame, so Design ships a tighter crop as a first-class variant — same artwork, same clip and state
  names, same script, but Gem is 54% of the cell's width instead of 44%, i.e. 1.23× at a given box.
  We take it (Thomas). Verified on arrival: 462 frames across 24 clips, every frame 26 rows of 26
  legal characters, and both atlases compared to the JSON **pixel-for-pixel** — a 26-cell JSON
  beside a 32-cell atlas is the one failure that throws nothing and renders garbage. *(An earlier
  pass recropped v2 ourselves with Design's `recrop_26.py`; that script is superseded by their own
  `26/` export and has been removed.)* **Owed to the sprite lab:** `needs-permission/granted` f5
  (the falling lock) loses 5px off the bottom to the crop — flag it, do not invent pixels.
- **The idle script went two-tier, and a v2 loader gets it wrong silently.** v2 had one weight
  table, which cannot say "blink often, play guitar rarely" — the two draw from the same pool, so
  every blink is a missed gag. v3 splits them: `filler` (blink, look-around) fires every
  `restHold` passes, and every `gagEvery` fillers a **gag** fires instead, from six new/expanded
  clips (`jump` `skip-rope` `guitar` `phone` `basketball` `disguise`, all weight 1). The
  compatibility hinge is the dangerous part — a state with no `filler` key falls back to v2
  behaviour, so a v2 loader *runs* a v3 kit and merely plays gags where fillers belong, i.e. Gem
  performs constantly instead of blinking. `GemPlayer` was ported to the two-tier shape from the
  kit's own loader, and `teleprompter.gem` now asserts the **tiers stay separate** (measured over
  ~74 simulated minutes: both tiers fire, and the filler:gag ratio sits inside `gagEvery`), because
  the failure is a behaviour drift no smoke test would catch. Also in this pass: the **eyes are 2px
  wide** (v2's 1px was 1:14 of the body against Clawd's 1:8; it was also the first thing a
  fractional downscale destroyed, and a 1px hole closes up in the tray template).
- **Sizes in the app.** The settings Gem renders at **2× (52px)** — the whole cell fits the 58px top
  bar, so nothing is cropped and the props get their full run of the margin. 3× (78px) was tried and
  rejected as too tall: it needed the cell clipped to the played clips' ink box to fit at all, and
  there is no integer step between the two (a fractional scale makes some pixel-cells wider than
  their neighbours, which the kit forbids). `app_icon` crops to the **frame's own ink** rather than
  the kit's `anchor` box, which is the whole cell in the 26px build — cropping to it would have
  *shrunk* the icon by a fifth. No other call site assumed a cell size.

- **Gem mimes the turn, off the island's typewriter.** The settings Gem was mic-on/mic-off; she now
  runs `listening` → `working` (composing — the laptop, Thomas's pick over `thinking`/orbit) →
  `speaking` (the answer landing) → `done` → `idle`. Two things make this less obvious than it
  looks. First, **`speaking` cannot come from the feed**: the orchestrator only publishes that state
  when TTS actually plays, and TTS is off by default (D23), so the reply streams in while the state
  word still says `thinking`. Second, **the daemon's stream and the island's reveal finish at
  different times, in either order** — on a long answer the typewriter runs seconds past
  `response.done`. Gem follows the SCREEN, so `Overlay.qml` publishes its reveal state onto
  `OverlayModel.revealing` (UI state, not feed state — the precedent is `showLatency`); it is the
  only place a second window can read it, and it is what puts Gem on the island below.
  That field needed its **own** notify signal: published through the model's blanket `changed` it
  invalidated the very properties it was computed from, and QML spun a binding loop.
  `done` enters on `sparkle`, which is a HOLD, so `QmlGem` releases an enter-hold once it has
  played — that is what settles `done` onto `settled` and `error` onto `held`, per the kit's rule
  that a hold is the app's to release. A non-enter hold (`misheard`) still waits to be released by
  hand. Two ordering bugs were found by walking it rather than reading it: `gemState` reported the
  player's *current* state, so a QML Binding re-requesting during an exit clip restarted that clip
  forever (it now reports the REQUEST); and a ladder built from several derived booleans could see
  them disagree for one evaluation and drop through a lower rung, flashing the laptop between the
  answer and the sparkle — it is one expression now.

- **Gem joins the island, behind a switch.** The island is the app's professional face, so a mascot
  on it is a taste call that has to stay reversible: **`gem_in_island`** (preferences, default ON)
  turns her off, and off means the island is *exactly* what it was before her. Every Gem-aware
  value is written `gemOn ? … : <the original formula>`, and `overlay_check` re-derives those
  originals from scratch rather than trusting the branch — 230px classic against 238px with Gem on
  the compact pill. A drop-in nobody re-checks is a geometry claim that rots silently.
  She sits **inside** the pill on the left at 52px, the same 2× as the settings bar. The 26px cell
  carries ~12px of its own margin, so a 4px inset reads as ~16 and a prop can still leave the body;
  at worst the cell overhangs the 46px pill by 3px, which is the safety area doing its job
  (Thomas). She is a **sibling** of the clipping viewport rather than a child, and her x/y are
  rounded to whole pixels — `islandX` is a real number, an odd pill width lands a nearest-neighbour
  sprite on a half pixel, and a half-pixel pixel-art sprite is the one thing that visibly ruins it.
  CI guards the rounding. Fitting her cost the waveform its old anchor: it was centred in the
  *whole* pill, so it ran 30px underneath her. It now starts after her column, and the Gem theme
  narrows to 14 bars with a 10px fade (from 20 / 22) so the two never touch. The peek (D27) is its
  own surface and draws no Gem for now — a `search` clip for it is commissioned.
  With two windows driving one player, the phase ladder moved **out of QML** into `QmlGem`: two
  sets of bindings racing over one player is a bug waiting for a slow frame. It also gained the
  rungs the settings bar never exercised — an `error` outranks a pending reply (a fault used to
  fall through to `idle`), and dictation maps `transcribing` / `transforming` → `working` and
  `pasted` → `done` (Thomas). `listening` outranks everything, so a fresh mic is never masked by a
  stale fault.

Guarded: `teleprompter.gem` (the kit loads, palettes come from the JSON, both script tiers fire and
stay separate, enters resolve, enter-holds settle, a re-requested state cannot restart an exit, and
the resting pose fills the app-icon chip whatever the cell becomes next), `settings_check` (the turn
walked end to end, both reveal/stream orderings), `overlay_check` (whole-pixel placement, and the
switch off restoring the pre-Gem formulas) and a new `teleprompter.tray` selfcheck (the ring's
pixels + the repaint gate), all CI-wired. Owed: live on the box — the tray ring against a real
mic, the taskbar icon, and Gem miming a real turn on both surfaces.

**D36 (2026-07-30): a rejected tool call is a `malformed_tool_call`, so the retry can catch it.**
`search_email`'s first live outing failed with "Something went wrong on my end". The tool was
innocent — it never ran. The turn was routed to groq/llama-3.3-70b, which emitted a call whose
`function.name` carried the arguments glued onto it (`search_email {"sender": …}`), and Groq's own
validator rejected it. **Measured before fixing anything: ~1 round in 3 fails this way** (5 of 14
on the same utterance with four tools offered), and the other two thirds compose a perfectly
correct call. So the model is not incapable, it is unreliable — and the recovery for unreliable is
a resample, which the tool loop has already had since D31.

- **Why the retry never fired.** It is gated on the `malformed_tool_call` kind, and this failure
  arrived as `unknown`. The obvious fix — read the provider's message — is barred by **B-02**,
  which maps errors by exception TYPE and status code precisely so a prose heuristic cannot
  mis-narrate. The way through is a third typed input: **whether the round offered tools**. A
  rejection on a tools round is a bad tool call by construction, no prose required.
- **The shape was the trap.** The rejection arrives **mid-stream**: the HTTP request logs `200 OK`
  and the exception is a bare `openai.APIError` with **no status code at all**. A first pass keyed
  on a 400 and could never match — the live run proved it by not changing. Both forms are mapped
  now, since a provider rejecting before it streams would give the 400 instead.
- **Cost of being wrong:** one retried round. A mid-stream hiccup narrates as a bad tool call, and
  a retry was the right response to that anyway. `malformed_tool_call` also gained a spoken line —
  it had been falling through to the generic apology, which is why the failure was unreadable.
- **A capability failure must not narrate as a negative result.** End to end, the loop now works:
  the brain called `search_email`, the backend answered "Outlook has no mail profile set up on this
  machine", and the brain said *"I did not find the email"* — turning **can't** into **didn't**.
  Nothing was searched, and the answer implies the mailbox was. This is not model-specific and it
  is a spec/40 narration question, not a tool one. **Open — Thomas.**
- **Open — Thomas:** whether tool-offering turns should route to a stronger tool-caller at all. One
  retry leaves ~13% of turns failing, and this is a cost decision, not an engineering one.

Guarded: `bridge.brains.compat` — the tools-offered refinement in both shapes, and the kinds it must
NOT swallow (a 5xx, an auth failure, a dropped connection, a bad model id). Verified live against
groq: the kind now maps, and `logs/audit.jsonl` carries the first real `search_email` invocation.

