# Spec 40 — Interaction model

**Last reconciled: 2026-08-03** · Build progress: [STATE.md](../STATE.md) (Tracks G · P) · Earcon ids: [schemas/earcons.json](schemas/earcons.json)

## State machine (orchestrator: `bridge/orchestrator.py`)

```
IDLE ──wake──▶ LISTENING ──end-of-speech──▶ THINKING ──┬─▶ SPEAKING ─▶ IDLE
                   │                                    └─▶ ACTING(tools) ─▶ earcon ─┘
                   └── timeout 5 s / mute ──▶ IDLE
```

Dictation (spec/60, D2) is a **second branch off the same capture** — entered by the DICTATE
hotkey, not WAKE:

```
DICTATE-key ─▶ LISTENING ──end──▶ TRANSCRIBING ─▶ TRANSFORMING ─▶ PASTED ─▶ IDLE
```

It pastes at the caret and shows no reply, so `transcribing` / `transforming` / `pasted` drive a
**status-only** island (a status word, then a brief "Pasted ✓") rather than `THINKING` / `SPEAKING`
— see spec/60 §Overlay states.

- `LISTENING` opens on WAKE; end-of-speech = VAD silence (initial: 1 s, tune in M0);
  give-up if speech never starts: 5 s (decided 2026-07-13; was 10 s).
- **`IDLE` means the daemon is free — not that the island is blank (D24).** The answer stays on
  screen after the turn ends, and **how long is the overlay's decision, not the daemon's**: it
  hides itself a fixed interval after the text has finished *revealing*. The daemon owned this
  for two revisions and could only estimate the island's typing rate; both estimates blanked
  long answers mid-sentence. The dwell is only the walked-away backstop — dismissal (Esc, owned
  by the overlay) is the intended exit, and a new turn supersedes it.
- **Two dwells, because acting and answering are not the same event (D43).** A turn that ACTED —
  it opened an app, raised a window — leaves nothing to read: you watched it happen, and the
  island is then sitting on top of the thing it just opened. A turn that ANSWERED has to survive
  long enough to walk back to the desk. So the reply carries which kind of turn it was (`dwell`
  on the Contract P `response` message, `quick` or `slow`) and the overlay times it.
  **The daemon names the kind and never the duration** — the seconds are the user's setting
  (spec/70), and the split of responsibility is the same one D24 drew: the daemon knows what
  happened, only the overlay knows what is on screen.
  `quick` requires BOTH that the turn acted and that there is nothing to read, so a turn that
  acted *and* answered in one breath keeps the readable dwell. Anything unstamped is `slow`:
  the failure that matters is an answer vanishing mid-read, so the default fails that way round.
- **Binding: opening a capture window clears the previous turn** — whichever entrance opens it
  (wake · ask key · barge-in · a keypress mid-reply), the island must never show the mic bars
  over a stale answer. Since D24 the `listening` state **is** that clear
  (`spec/schemas/status.json` → `clearsTurn`), so no entrance can skip it; it previously lived
  in one caller, and the barge-in entrance duly skipped it.
- `listening` clearing a turn is sound **only because every capture window is user-initiated.**
  It was not, briefly: an 8 s FOLLOW-UP window accepted speech without re-wake, and because it
  held the mic open it had to publish `listening` (spec/50 rule 4 — no dark listening), which
  erased the answer it existed to let you respond to. That window is removed. Whether one
  returns — and how it would signal an open mic truthfully — is deferred to the "listen to me"
  design (STATE, Track P); **if it does, `clearsTurn` must change back before it lands.**
- **Barge-in (binding):** user speech during `SPEAKING` stops TTS ≤ 250 ms and routes
  the speech as new input.
- `THINKING` **is itself** the D11 feedback guarantee: the overlay's near-instant flip to the
  THINKING state is the perceptible signal for any turn that can't answer fast (D25). The
  `working` earcon that used to cover this is retired (D28) — the screen carries it.
- Conversation history threads through one wake-chain (`Session.history`) and dies at
  IDLE; whether it should persist across wakes is an open question (parked — STATE).

## Narration rules (agreed 2026-07-10; enforced by the orchestrator)

- **Register (decided 2026-07-13):** impassive system voice — declaratory or imperative,
  no interjections, exclamations, filler, or performed warmth. A system AI, not a
  companion. Lives in the brain's system prompt (M0: the B1 adapter's placeholder;
  M0.5: the versioned persona). Chosen partly because the M0 TTS cannot act emphasis —
  the script must not demand what the voice can't perform.
- Every answer renders in full on the Teleprompter as it streams — **always** (D23). The
  spoken channel is a capability behind the **TTS** switch (**default off**, spec/70); everything
  below about *speaking* applies only when TTS is enabled.
- **The three earcons (the "pings") are a separate channel, on by default** — gated by the
  **Pings** toggle (default on, spec/70), NOT by the TTS switch: they are device pings, not
  speech (D28, resolving the long-open "are earcons behind the speech switch?" question).
- Speech on, answers ≤ 2 sentences: spoken automatically.
- Longer answers (M0 heuristic): full text on the overlay; **held — SHOWN, not spoken.** The
  hold stops a long answer being read AT you (never lecture uninvited). **"read it" is retired**
  (S-03): there is no spoken-on-request escape hatch, and nothing parses utterances for one.
  Whether a held answer is ever spoken on request folds into the speech switch (spec/70) —
  **direction (Thomas, 2026-07-23): with TTS on, read all by default** rather than holding long
  answers silently; finalised at the TTS-switch / M0.5 stage, which also replaces this
  sentence-count heuristic with a model-tagged spoken TL;DR over displayed detail.
- Successful Tier 2 actions: the `success` earcon only. Failures: the `failure` earcon + a
  one-sentence explanation shown on the Teleprompter.
- Tier 3 (D26): the proposed action renders on the Teleprompter and a **keypress** confirms it
  (propose-then-tap, D20). Since D28 the proposal sounds the `failure` earcon — its meaning
  widened to "something needs your view" — rather than a dedicated `ask` tone; with speech on, a
  spoken one-line summary of what will happen follows, confirmed by saying "confirm". The keypress
  gate is what makes Tier 3 executable in the default (screen-only, mic-closed) product — a
  spoken-only gate could not run there.
- Tool progress (D11/D38): during `ACTING`, silence by default — the overlay's tool-activity
  indicator is the always-on visual, and the turn ends on `success`/`failure`. Spoken step
  narration ("Fetching X…") is a config flag, **default off**. The indicator's **feed** exists:
  Contract P's `tool` message carries the running tool's human label, sent as the call starts
  and again as it returns (spec/30 § Connectors). It **names** the tool rather than merely
  flagging one, because that is the "during" half of connector consent — you agreed to a
  capability in a settings page, and this is what says when it is being used. *Its rendering on
  the island is a design pass owed (STATE, Track T).*

> The ≤2-sentence speak/hold split above is an **M0 heuristic**. **M0.5 "It speaks well"
> (spec/00) replaces it** with a model-tagged output contract — the brain marks what to
> speak vs hold, plus TTS-safe formatting and speech normalization — so length isn't
> guessed post-hoc. *(planned, M0.5)*

## Latency targets (numbers in [`spec/schemas/targets.json`](schemas/targets.json), loaded — D11/D25)

The **values live in `targets.json`** (hard rule 3), loaded by the overlay's readout and the
orchestrator's latency table; they had drifted across four files, so this table describes what
each is and its **kind**, and never restates the number.

**Kinds (D25).** `floor` = a sub-second responsiveness acknowledgement — a real product
requirement independent of the screen. `gate` = a pass/fail feedback guarantee. `measured` =
recorded per turn as a diagnostic, shown neutrally, **never pass/fail** — the overlay must not
flag it over-budget.

| Turn class | Metric | Kind |
|------------|--------|------|
| any | Wake detect → `listening` earcon (`wake_ack`) | floor |
| any | Ask-hotkey press → listening indication (`press_ack`) | floor |
| any | End of speech → perceptible feedback (`feedback`) — the overlay's flip to THINKING or the first spoken word, whichever first (D16). Since D23 the screen is primary, so on a normal turn this is the near-instant THINKING state (the `working` earcon that used to be the audio fallback is retired, D28). | gate |
| no-tool answer | End of speech → first spoken word, B1 (`first_word`) / B2 (`first_word_b2`) | **measured** |
| tool turn | End of speech → starter-tool (Tier 2) action executed (`tool_ack`) | gate |
| tool turn | Completion of longer work | unbounded — ends with `success`/`failure` earcon |
| any | Barge-in → TTS stopped (`barge_stop`) | floor |

**Why first_word is `measured`, not a gate (D25).** Under generate-then-play (D11) the first
spoken word cannot arrive until the *whole* reply is generated and synthesised, so first-word
latency scales with reply length (~45 ms/output token, measured 2026-07-22) — it is a
reply-length proxy, not a latency the system can tighten, and a fixed ceiling on it is a
length cap wearing a stopwatch's clothes. It also stopped being the *first* feedback the moment
D23 put the streaming reply text on the island. It is kept as a diagnostic, not a gate.
Sentence-streamed TTS (parked, D11 "feedback beats speed") is what would make a first-word
*target* meaningful again — reopen it with this number, not on feel.

*The `floor`/`gate` numbers are still provisional against the owed live measurements (STATE:
step-3 live mic test); confirm or amend the values in `targets.json` with data.

**Clock (binding).** "End of speech" = the moment VAD *declares* the turn over. The
silence timer (1 s) runs before this clock starts — it is a turn-taking cost, tuned
separately (`--silence-ms` now; semantic endpointing at M1), not part of the response
budget.

## Wake detection (M0)

Engine **openWakeWord** on ONNX (spec/00), cross-platform (spec/00 D10). M0 uses the
bundled model **`hey_jarvis`** as the wake phrase — a stand-in; a custom-trained phrase
is a later task. **LiveKit Wakeword** is a noted future alternative (lower false-accept
rate) — a contained swap behind the same audio pipeline, would update spec/00. Capture
blocksize and detection threshold are code-level tuning (`bridge/audio/wake.py`), not
spec constants.

**Triggers — the two doors (D20; planned).** Two hotkeys, bindings in config (spec/70):
- **Dictate** — dumb by contract: capture → word-replace (D15) → `transform` cleanup →
  paste at the caret. Never answers, never routes. Safety rule: invoking dictate while
  text is selected warns on the Teleprompter before pasting over it.
- **Ask** — the assistant: utterance + context (selection · clipboard) to the brain,
  which is the toolpicker (Contract B tool-calling over tools.json). Answers render on
  the Teleprompter **always** and are **spoken only with speech enabled** (D16 as amended
  by D23/S-04 — default off). Write-actions (rewrite of the selection, etc.) are
  **propose-then-tap**: proposal on the Teleprompter, second tap of the ask key
  applies — only a user keypress ever pastes (D12). `auto_apply` (spec/70, default
  off) bypasses the tap knowingly.

Each key is hybrid: tap = toggle, hold ≥ 0.5 s = push-to-talk; **the key is the
endpoint** — a second tap or the release ends capture, and the 1 s silence cut does not.
Two exits survive it: nothing-said (5 s) and the 30 s runaway cap. `auto_end` (spec/70,
default off) restores the silence cut on a keyed turn for one-tap use (D20, refined
2026-07-22 — the flat "the key is the endpoint" now carries this knob).

The ask key opens `LISTENING` directly (wake phrase skipped); the wake word stays the
hands-free entrance to the same door. Shared module `bridge/hotkeys.py`, which the
dictate door reuses. Combos are registered **narrowly with the OS** (Win32
`RegisterHotKey`) rather than through a keyboard hook — see spec/50 rule 11; the
consequence is a per-OS seam, and **macOS is unbuilt** (Carbon `RegisterEventHotKey`),
where the wake word remains the only entrance. Bindings live in config (spec/70).
Rewrite is an ask *outcome*, not a mode (D20, superseding D17's separate slice).

## Speech capture & transcription (M0)

After wake, the bridge opens a listening window (`bridge/audio/listen.py`): **Silero
VAD** marks end-of-speech at **1 s** of silence (`--silence-ms` to tune), then **faster-whisper**
(`small.en`, English-only) transcribes to the console. Engine **choice A** (spec/40
review): faster-whisper on GPU (CUDA) where present, else CPU — one code path on Windows
and macOS. `transcribe()` is the swap-point for a Mac-GPU engine (whisper.cpp / MLX) if
Mac CPU speed disappoints — added only if measured (it would introduce a per-OS STT
seam, extending spec/00 D10). Normal turns end on VAD silence at any length; the **30 s**
cap is a runaway backstop only (on hit: transcribe what we have, warn). Audio is
RAM-only, discarded after transcription (spec/50 rule 3).

**Transcript hygiene (planned, D15).** Every transcript passes the deterministic
word-replacement table (known mishearings; schema-defined) before use — both paths.
The assistant path additionally supports `--clean-prompts` (**default off**): a
per-prompt `transform()` pass ("fix errors and structure only"), added as its own row in
the latency table and judged by A/B before ever becoming default. The overlay shows raw →
cleaned when the flag is on. **Cleanup engine is per-role and configurable (S-06):** dictation
cleanup uses Groq; the assistant-path `--clean-prompts` stays a small local model for now; each
is set in settings (spec/70, default local).

## Voice out — earcons & TTS (M0)

Two output paths (`bridge/audio/speak.py`), played via sounddevice at the 24 kHz schema
rate:
- **Earcons** — three designed WAVs (`listening` / `success` / `failure`), one per
  `schemas/earcons.json` id (ids read from the schema, never hard-coded). They live in
  `bridge/assets/earcons/<id>.wav`, pre-rendered to the 24 kHz outbound rate and loaded via the
  stdlib `wave` module (no audio-codec dependency; the mp3→wav conversion is a one-time build
  step). **Cut from seven to three at D28:** since the screen carries listening/thinking/answer/
  tool state (D23/D25), most earcons were redundant with something already visible, so a normal
  no-tool turn now plays **one** sound (`listening`) or none. Gated by the **Pings** toggle
  (default on, spec/70). What's latency-bounded is the earcon **onset** (wake → `listening`
  < 300 ms), not its length — the ring-out overlaps the next phase.
- **TTS** — **Kokoro** via `kokoro-onnx` (ONNX runtime, **no torch**; `espeakng-loader`
  bundles the espeak-ng phonemiser, so no manual install). Native 24 kHz. Generate-then-
  play — the accepted M0/M1 design (spec/00 D11); sentence-streamed TTS is parked
  (STATE), reopened only if measured use feels slow. CPU is faster-than-real-time,
  so no GPU needed. Model files fetch once to `~/.cache/gemma/`. **Behind the TTS toggle
  (default off, spec/70; D28):** with it off, replies still render on the Teleprompter — they
  are simply not spoken.

*When* each earcon fires and *whether* to speak vs. stay quiet is the orchestrator's job
per the narration rules above — `speak.py` is only the mechanism.

**Bluetooth output keep-alive (binding for BT devices).** Bluetooth output (AirPods, BT
earbuds) idles during silence and glitches on the first audio after silence — a brief
buzz at each earcon/reply onset. Wired output is unaffected. The daemon MUST hold a
**persistent output stream** open, feeding silence between sounds, so the link never idles
(the orchestrator's `OutputPump`). The standalone `speak.py` CLI opens/closes the device
per sound, so it exhibits the glitch by design — it disappears under the warm stream.

## Visual output — the Teleprompter (component P; D13/D19/D22)

**Locked design (D22; build status in STATE Track P).** A solid-black **Dynamic Island fused to
the top screen edge**: bottom corners round inward, top corners flare **outward** into the edge
(concave fillets). White on black. It has **two sizes and nothing else** — a compact pill showing
a **bars** indicator driven by the *real mic level* (audio-reactive, the spec/50 truthful
indicator, not decorative) while LISTENING, and a standard-width panel for every other visible
state. Text is a **typewriter**: the transcribed prompt, then Gemma's reply *replaces* it — never
stacked. While THINKING with no text yet, a **morphing status word** occupies the prompt's slot.
**No state labels, no dot, no spinner, no status icons, and no controls at rest** — the ⌄ handle
was built and cut (D22); interaction arrives only in the **expanded view** (D27, below).
Idle hides the window outright. **Gem** (the mascot) may sit at the pill's left edge, behind
`gem_in_island` — on by default, and off restores the pre-Gem geometry exactly (D35); she is a
mascot, never an indicator, so the bars keep the spec/50 truthful-indicator role either way.
Component row in spec/00; the top-level `teleprompter/` package
(component P, D19). Blueprint: `sandbox/teleprompter-mockup.html` (gitignored).

**Expanded view — "peek" (D27).** The island is controlless *at rest*, but **hovering a shown
answer** hints (a small downward nudge + a pointer cursor) and a **click** grows it *in place* —
same silhouette — into a larger panel reading the **current turn** in full: the prompt pinned and
**collapsible past two lines**, the reply scrolling under an always-on top/bottom fade, and
**Copy** + **Save** (Save is user-initiated export, spec/50 rule 3). Height is content-clamped
(floor↔ceiling; past the ceiling the reply scrolls with prompt and actions pinned). **Esc**
collapses the peek before dismissing the island; the answer-dwell pauses while it is open.
In-memory, **current-turn only** — cross-session scroll-back is a later surface (the
conversation/memory model). For the island to take input it is no longer blanket click-through:
hit-testing is **per-region** (`WM_NCHITTEST`), interactive over the silhouette **only while a
reply is peekable** and click-through everywhere else, so it never intercepts a click meant for
the app beneath. Blueprint: `sandbox/teleprompter-expanded-mockup.html` (gitignored).

Role and hard boundaries:
- **The spine, not a supplement (D23).** The Teleprompter is *the* surface: a teleprompter of
  the transcribed prompt, the streamed response, and tool activity. It always carries the
  answer — it is not optional or configurable, and D20's propose-then-tap cannot function
  without it (an ask-door rewrite has nowhere to show its proposal). Prior prompts and the full
  text of a long reply live in the **expanded view** (D22), **in-memory only** — nothing
  written to disk (spec/50 unchanged). For dictation (Track D) it is likewise the primary
  feedback surface *(planned, D2)*.
- **Audio away from the screen: supported, not guaranteed (D23).** Earcons and TTS once had to
  "fully carry the experience" away from the screen — the last load-bearing residue of the
  cancelled eyes-free era (D18). That is now **demoted from BINDING to a capability**: turn on
  speech and the wake word ("listen for me", spec/70) and walking away still works, but the
  system is no longer held to it and the acceptance test no longer proves it.
- **Carries continuous state**, which one-shot earcons can't — so it, not a sound,
  covers the awake→asleep (end-of-session) transition. This is *why* there is no
  `asleep` earcon: falling asleep is passive and a lasting state, better shown than beeped.

Architecture (D13, spec/00):
- **Separate process on a status feed.** The overlay never runs inside the daemon. The
  orchestrator broadcasts JSON status events — state transitions, partial/final
  transcript, mic level, per-turn latency, faults — over a **localhost-only** socket
  (`bridge/broadcaster.py`); the overlay subscribes and renders what arrives. Feed
  message schema: `spec/schemas/status.json` (Contract P, hard rule 3). Renderer:
  **PySide6/Qt (QML)** frameless translucent pill on Windows; a later mac renderer
  consumes the same feed.
- **Never takes focus (BINDING).** The window is non-activating (`WS_EX_NOACTIVATE` /
  Qt `WindowDoesNotAcceptFocus` + `ShowWithoutActivating`). Vital for dictation: focus
  determines where the paste lands — an overlay that steals focus misroutes the transcript.
- **Truthful state (BINDING).** The listening indicator inherits spec/50's truthful-indicator
  rule: it must truthfully reflect whether audio is streaming.
- **Owns the display, and only the display (D24).** The overlay decides when the prompt gives
  way to the reply, when the island stops showing, and holds the bare **Esc** key while it is on
  screen — all three are facts about a reveal that only this process can see. It may send the
  daemon exactly one message, `dismiss`, which **cancels and can never command** (spec/50
  rule 12). Esc is registered only while the island shows and released the instant it hides;
  spec/50 rule 11 governs it as it does the daemon's doors. A press hides the island
  immediately and tells the daemon afterwards — the surface never waits for permission to go
  away.
- **Build order:** overlay v0 (state · live transcript · latency readout) lands
  **before the M0 acceptance run** and doubles as its instrument; dictation states
  (recording + mic level · transcribing · transforming · pasted) land at Track D's D2.

## Open tuning items (M0)

Custom wake phrase (replace the `hey_jarvis` stand-in) + false-accept testing (D8) ·
end-of-speech silence threshold (1 s start, `--silence-ms` to tune live) · pre-roll
length · the prompt's handover hold (`Theme.durationPromptHold`, overlay-side since D24).
*(Answer-dwell length stopped being a tuning item at D43 — it is two user settings now, and the
Theme constants are only the fallbacks.)*

**End-of-speech: semantic endpointing (planned, M1).** A fixed silence timer can't be
both pause-tolerant and snappy — a long tolerance delays *every* reply. The proper fix,
like Siri/Alexa, is **semantic endpointing**: judge from the running transcript whether
the utterance is a complete thought, combined with the timer — so long composed prompts
can pause mid-thought without being cut off, while simple prompts stay fast. Related
levers: higher max-utterance cap, explicit dictation mode. Build when tools/LLM prompting
land (M1).
