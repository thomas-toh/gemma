## Chapter 4 — Interaction model

**Last reconciled: 2026-08-03** · Build progress: [STATE.md](../plans/STATE.md) (Tracks G · P) · Earcon ids: [shared/schemas/earcons.json](../../shared/schemas/earcons.json)

### Teleprompter

**Description:** Taking reference from teleprompters, Gemma's primary UI interface is a solid black island fused to the top edge of the screen. This relays the status feed from the orchestrator. The teleprompter island takes multiple views - a standard, compact view which displays the response as a running transcript of text, and the expanded "peeked" view which displays the entirety of the response. Results of tool calls are also handled through discrete views, based off the expanded "peeked" view. 

**Architecture:** The teleprompter island is generated via Qt/QML as a separate process broadcasting the status feed from the orchestrator. The orchestrator broadcasts JSON status events, via a localhost only socket contained at `backend/broadcaster.py`; the teleprompter then subscribes to this socket, and renders what arrives:

The feed is NDJSON (one JSON object per line) over a localhost-only socket (`127.0.0.1`, port `8990` by default, or `$GEMMA_STATUS_PORT` if set), one-way apart from a single upstream message. The orchestrator broadcasts:

- `state` — the coarse session state: `booting`, `idle`, `listening`, `thinking`, `speaking`, `error`, plus the dictation states `transcribing` / `transforming` / `pasted`.
- `transcript` — the user's prompt, after the deterministic word-replacement cleanup.
- `response` — one chunk of the model's reply as it streams (`delta`, `done`; on completion also the `model` id, `tokens`, and the `dwell` kind).
- `mic` — input level in [0, 1] while a capture window is open (drives the listening bars).
- `tool` — a tool starting or finishing (`name`, human `label`, `done`).
- `latency` — a per-turn timing reading against the targets.
- `error` — why a turn failed (`kind`, human `message`).

Upstream, the teleprompter can send only `dismiss` — a cancel, never a command (spec/50).

The teleprompter's feed schema is defined by `shared/schemas/status.json`, which restricts the status types.

The teleprompter, which is intended to sit *above* one's work, must *never* steal focus from an active window.

### Activation and deactivation 

**Description:** Activation and deactivation is, strictly speaking, a daemon-side task, since audio capture is controlled by the daemon: `backend/audio/wake.py` watches for the wake phrase and `backend/audio/listen.py` runs the listening window, both driven by the orchestrator's serve loop. It is crucial, however, that the interaction with the daemon is natural to the user. Accordingly, Gemma exposes 2 activation and 2 deactivation surfaces, with only 1 of each active by default.

1. **Activation by hotkey:** Two global hotkeys activate Ask and Dictate. Each is hybrid and supports (i) a *tap* to open a capture, and (ii) a *hold of ≥ 0.5 s* for push-to-talk.
    - Hotkeys: Shared on `backend/hotkeys.py`. Hotkey combos are registered via the OS (Win32 `RegisterHotKey`) (Mac TBC, likely Carbon `RegisterEventHotKey`). 
    - **Ask:** the Ask hotkey opens `LISTENING`; the captured speech is transcribed and the transcript is sent to the **router** (`backend/router.py`), which selects the **model** (`backend/llm/`) to answer, and the reply renders on the teleprompter. The wake word (surface 2) is the hands-free entrance to this same door.
    - **Dictate:** the Dictate hotkey opens `LISTENING`; the captured speech is transcribed, cleaned, and pasted at the caret. It never answers and never routes to the model. If text is selected when Dictate is invoked, the teleprompter warns before pasting over it.

2. **Activation by wake-word:** This is being prototyped currently uses `openWakeWord` (running on ONNX). At this stage, the wake phrase is `openWakeWord`'s `hey_jarvis` — this is a stand-in, and a custom-trained phrase is a later task. Capture blocksize and detection threshold are code-level tuning in `backend/audio/wake.py`.

3. **Deactivation by hotkey:** Where hotkey starts the turn, a hotkey press ends the turn. A second tap of the hotkeys or a release of a hold ends the capture. The assistant's 1 s VAD silence cut does *not* end a keyed turn (`capture_over`, `backend/orchestrator.py`).

4. **Deactivation by lapse-of-time:** a wake-word turn has no key, so it ends on 1 s of VAD silence; `auto_end` (configurable, default: off) extends that silence cut to keyed turns for one-tap use. Independently, every turn carries time backstops: give up 5 s after entry if no speech starts, a 30 s runaway cap on an Ask turn, and a 300 s backstop on a Dictation (whose real endpoint is the key).

### Orchestrator

Lives at: `backend/orchestrator.py`

It is the daemon. It runs the serve loop that sits in `IDLE` watching for both the wake word and the two hotkey doors, drives the session state machine, and wires the pipeline end to end: capture → VAD → transcribe → router → model → speech for an ask turn, or capture → transcribe → clean → paste for a dictation. Every state change is broadcast over the status feed, and the orchestrator is the only part of Gemma that talks to the model.

### Interacting with Gemma

**Ask**

Entry is the ask hotkey or the wake word (see *Activation and deactivation*, above). The orchestrator captures and transcribes the utterance, routes it to the model, and streams the reply back. The teleprompter is a pure subscriber — it never transcribes or talks to the model — and renders the states and the streaming `response` off the feed: the `listening` bars, then `thinking`, then the reply typing in, then `speaking` if TTS is on.

```
IDLE ──wake──▶ LISTENING ──end-of-speech──▶ THINKING ──┬─▶ SPEAKING ─▶ IDLE
                   │                                    └─▶ ACTING(tools) ─▶ earcon ─┘
                   └── timeout 5 s / mute ──▶ IDLE
```

**Dictate**

Dictate is the second variant interaction method. By activating the hotkey (default: Ctrl+Alt+2), Gemma does: 

```
DICTATE-key ─▶ LISTENING ──end──▶ TRANSCRIBING ─▶ TRANSFORMING ─▶ PASTED ─▶ IDLE
```

Dictate pastes at the caret and shows no reply, so `transcribing` / `transforming` / `pasted` drive a *status-only* island (a status word, then a brief "Pasted ✓") rather than `THINKING` / `SPEAKING`.

**Cleaning up:** Both Ask and Dictate support two clean-up stages:
1. A deterministic pass against a table of known-misheard replacements, run on every turn.
2. A `--clean-prompts` pass (default: off for Ask, on for Dictate): a per-prompt `transform()` that fixes errors and structure only. The model backing `--clean-prompts` is per-role and configurable.

**Status messages.**

`LISTENING`: Opens on hotkey press activating `WAKE`. End-of-turn is denoted by hotkey press again.

`IDLE`: The daemon is free and not processing information (but *not* that the teleprompter island is blank). The answer displays on the teleprompter island after each turn until one of three events fires: (i) the user presses the Esc key (which closes the teleprompter island); (ii) the dwell timer (dwell-short or dwell-long) elapses; or (iii) a new turn is activated via a hotkey (or, later, by the user continuing to speak during the dwell period — to be built).

**Dwell duration:** When a turn ends, the answer's dwell on the teleprompter island takes one of two lengths, depending on what the turn did:

- **dwell-short:** the daemon "acted" (e.g. opened an app, raised a window) and produced no text. Nothing was written to the island to be read, so it clears quickly.
- **dwell-long:** the daemon "answered" (i.e. produced text). The answer stays up long enough for a user to read the response, but clears automatically after an extended period.

The `response` status message informs the teleprompter island which applies (and, in turn, how long the island stays up). Where the daemon both acts and answers, dwell-long is used. For safety, the default is dwell-long, so a response with no tag defaults to dwell-long. Both durations are set by the user.

**Clearing a stale turn (binding).** Opening a capture window clears the previous turn, regardless which entrance opens it — wake, ask key, barge-in, or a keypress mid-reply. The clearing function is carried via `listening` (*see* `shared/schemas/status.json` → `clearsTurn`).

## Narration rules

**Register:** An impassive system voice: declaratory or imperative, with no interjections, exclamations, filler, or performed warmth. This is injected into the model's system prompt (currently a placeholder today; a versioned persona to be iterated and TBC).

**Format:** Every answer renders in full on the teleprompter as it streams, always. Speech is a capability behind the TTS switch (configurable, default: off); everything below about *speaking* applies only when TTS is on.

**Audio:**
- **Pings:** The three earcons ("pings") are a separate channel (configurable, default).
- **TTS:** With speech on, short answers (≤ 2 sentences) are spoken automatically; longer ones are shown in full on the island but held — shown, not spoken — so a long answer is never read at you unprompted, and there is no spoken-on-request escape hatch. (TBC: with speech on, read every answer by default rather than holding long ones. The model tags its own output for what to speak versus show and normalises it for TTS, so the split is no longer guessed from sentence count.)
- Tier 2 actions: on success, the `success` earcon only; on failure, the `failure` earcon and a one-sentence explanation on the teleprompter.
- Tier 3: the proposed action renders on the teleprompter and a keypress confirms it (propose-then-tap); the proposal sounds the `failure` earcon. With speech on, a spoken one-line summary follows and can be confirmed by saying "confirm".
- Tool progress: during `ACTING`, silent by default — the island's tool-activity indicator is the signal, and the turn ends on `success`/`failure`. Spoken step narration ("Fetching X…") is configurable (default: off). The `tool` status message carries the tool's human-readable label, so the indicator names the running tool. Its island rendering is still to be designed.

## Latency targets

The values live in [`shared/schemas/targets.json`](../../shared/schemas/targets.json) (hard rule 3), loaded by the island's readout and the orchestrator's latency table. This table describes what each metric is and its **kind**; it never restates the number.

**Kinds.** `floor` — a sub-second responsiveness acknowledgement, required independently of the screen. `gate` — a pass/fail feedback guarantee. `measured` — recorded per turn as a diagnostic, shown neutrally and **never** pass/fail; the island must not flag it over-budget.

| Turn class | Metric | Kind |
|------------|--------|------|
| any | Wake detect → `listening` earcon (`wake_ack`) | floor |
| any | Ask-hotkey press → listening indication (`press_ack`) | floor |
| any | End of speech → perceptible feedback (`feedback`): the flip to `THINKING` or the first spoken word, whichever comes first. On a normal turn this is the near-instant `THINKING` state. | gate |
| no-tool answer | End of speech → first spoken word, B1 (`first_word`) / B2 (`first_word_b2`) | **measured** |
| tool turn | End of speech → starter-tool (Tier 2) action executed (`tool_ack`) | gate |
| tool turn | Completion of longer work | unbounded — ends with `success`/`failure` earcon |
| any | Barge-in → TTS stopped (`barge_stop`) | floor |

## Speech capture & transcription (M0)

After wake, the daemon opens a listening window (`backend/audio/listen.py`): **Silero VAD** marks end-of-speech at **1 s** of silence (`--silence-ms` to tune), then **faster-whisper** (`small.en`, English-only) transcribes it. The engine runs on GPU (CUDA) where present, else CPU — one code path on Windows and macOS. `transcribe()` is the swap-point for a Mac-GPU engine (whisper.cpp / MLX) if Mac CPU speed disappoints, added only if measured. Normal turns end on VAD silence at any length; the **30 s** cap is a runaway backstop only (on hit, transcribe what we have and warn). Audio is RAM-only, discarded after transcription (spec/50 rule 3).

### Next steps

**Wake phrases:** Currently, a start-of-turn is marked by a hotkey. A true assistant would use a wake-word (a la "Hey Alexa" or "Hey Siri"). Prototyped with faster-whisper's `hey_jarvis`, but (i) the name is incorrect for production, and (ii) configurability is best to match user's voice and prosidy.

**End-of-speech semantic endpointing:** Currently, an end-of-turn is marked by a hotkey press. A configurable setting permits automatic turn ending, which is deterministic based on the elapsing of a certain period of silence. *Semantic endpointing* would better judge, from the running transcript, whether an utterance is a complete thought. A proper semantic endpointing mechanism would disambiguate between a mid-thought pause and a genuine complete sentence. Related levers: higher max-utterance cap, explicit dictation mode. TBC.
