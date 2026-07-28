# Review: Gemma vs VoiceInk — transcription, app injection, and buy-vs-build

*Prepared 2026-07-18. Sources: full read of the Gemma repo (as connected), full read of the VoiceInk source (github.com/Beingpax/VoiceInk, GPL-3.0, cloned at HEAD), and a check of current product pages.*

---

## 1. Where Gemma stands (codebase review)

Short version: the bridge is in better shape than you might think, and the discipline in the repo is well above hobby-project average. But everything green so far is *offline logic* green — the project's central claims are still unproven on live audio.

**What's built and working (per code + STATE.md):** the full M0 voice loop is code-complete. Wake word (openWakeWord, `hey_jarvis` stand-in, ONNX) → Silero VAD with pre-roll ring buffer → faster-whisper `small.en` (CUDA fp16 with graceful CPU int8 fallback) → Claude brain via the Contract-B event interface → Kokoro TTS through the persistent `OutputPump` that doubles as the Bluetooth keep-alive. Barge-in, earcons, the 1.4 s "working" ping, and per-turn latency self-measurement are all implemented. Every module has an offline `--selfcheck`, and CI runs them on `windows-latest`.

**Genuine strengths worth naming:**

- The contract architecture is honored in practice, not just on paper — `orchestrator.py` is the only module that imports the others, and audio constants/earcons/tools all flow from the JSON schemas rather than being duplicated in code.
- The replay harness (`tests/replay.py`) is the best thing in the repo: real wake/VAD/STT driving the real orchestrator with fakes only at the edges. That's an eval-set instinct most professional teams don't apply to audio.
- The torch-free ONNX stack (forced by the Windows long-path issue) turned out to be a good constraint: fewer heavy dependencies, one runtime for wake/VAD.

**Open issues, in rough priority order:**

1. **The M0 acceptance run has never happened.** No ×10 live-turn run, no replay WAVs recorded, no real-speech STT latency figures. Until that happens, the <1.5 s / <4 s numbers are aspirations.
2. **Generate-then-play is the latency risk.** The whole reply is collected and fully synthesized before the first word plays. Kokoro on CPU is ~0.3–0.4× real-time, so a two-sentence answer plus STT plus LLM time makes the 4 s budget tight. `synth()` is already per-sentence, so sentence-streamed TTS is a small change if the live run confirms the problem.
3. Known-fragile heuristics, all flagged in-code: the sentence counter, the bare `\bread\b` readback match, and the misleading "first token" measurement (it was whole-response-in-one-chunk).
4. The daemon is a synchronous `while True` loop with `asyncio.run` per turn — fine for M0, but it diverges from the async-daemon design in docs/02, and will need resolving before tools/streaming land.
5. Tracks H and T are empty, as STATE.md honestly records.

## 2. What VoiceInk actually is (codebase review)

VoiceInk is ~53k lines of mature Swift/SwiftUI, macOS 14.4+. It is a *dictation* tool: hotkey → record → transcribe → optionally clean up with an LLM → paste into whatever app has focus. The end-to-end pipeline (`TranscriptionPipeline.swift`) is:

**transcribe → filter artifacts → format paragraphs → deterministic word-replace → AI enhance → deliver (paste) → save.**

The pieces that matter for your purposes:

- **Transcription.** Four backends behind one protocol: whisper.cpp (local, Metal/CoreML-accelerated, models from `ggml-tiny` to `large-v3-turbo`, built-in Silero VAD), Parakeet/Nemotron via the FluidAudio CoreML package (local, streaming-capable), Apple's native SpeechAnalyzer (feature-gated), and ~11 cloud APIs. Streaming mode shows live partials and reconciles overlapping hypotheses with a word-agreement engine.
- **"Plugging into apps" is less magic than it looks.** There is no accessibility-API text insertion. `CursorPaster.swift` writes the transcript to the clipboard (tagged as transient so clipboard managers ignore it), waits 100 ms, and posts a synthetic Cmd+V via CGEvent (AppleScript keystroke as fallback), optionally restores the old clipboard afterwards, optionally presses Enter for chat apps. That's the whole mechanism.
- **Power Modes (context awareness).** On record start it reads the frontmost app's bundle ID, and if it's a known browser, runs an AppleScript to grab the active tab URL. That selects a per-app/per-URL profile: which STT model, which prompt, whether AI enhancement runs, whether to auto-send.
- **AI enhancement.** A fixed system prompt (`AIPrompts.swift`) with a strict contract — the dictation is wrapped in `<USER_MESSAGE>` tags and the LLM is told to *transform, never answer* — plus rules for spoken self-corrections ("scratch that"), spoken punctuation ("new paragraph"), numbers/dates, and two few-shot examples. Context blocks (selected text, clipboard, screen OCR) and a custom-vocabulary section are appended. Providers include Ollama and a pipe-through-any-local-CLI option, so fully-local enhancement is first-class.
- **Hotkeys.** Toggle, push-to-talk, and a hybrid mode (tap = toggle, hold ≥0.5 s = PTT), with cooldowns and accidental-start handling — this state machine is pure logic and worth copying.
- **License reality.** GPL-3.0, sold as lifetime tiers (~$25–49) for a signed binary, auto-updates and support. The point that matters here is the copyleft, not the price: anything *derived from* this source carries GPL-3.0 obligations the moment it is distributed. Ideas and pipeline ordering are free to learn from; expression is not.

## 3. The two facts that decide buy-vs-build

**Fact 1: VoiceInk does not run on Windows.** It's a native macOS app through and through — CoreAudio, CGEvent, NSPasteboard, AppleScript, CoreML. Your reference platform, your RTX 5080, and the machine Gemma's bridge runs on are Windows. Buying (or free-building) VoiceInk gets you nothing on the desktop where Gemma lives. (Wispr Flow does ship a Windows client, but it's cloud-transcription and closed — the opposite of the local-first premise.)

**Fact 2: Gemma already owns the hard front half.** VoiceInk's dictation flow is capture → VAD → local Whisper → LLM → output. Gemma has capture, VAD, faster-whisper on CUDA, and a working LLM adapter — tested, self-checked, latency-instrumented. What Gemma lacks is exactly the *back* half, and it's the easy half:

| VoiceInk capability | Gemma today | Gap size |
|---|---|---|
| Record + VAD + local Whisper | ✅ `listen.py` (faster-whisper, CUDA) | none |
| Global hotkey / push-to-talk | ❌ (wake-word only) | small — `keyboard`/`pynput` listener |
| Paste into focused app | ❌ (audio out only) | small — clipboard + `SendInput` Ctrl+V, same trick VoiceInk uses |
| LLM transcript cleanup | ❌ (LLM *answers*, never cleans) | small — a second prompt path through the existing brain |
| Per-app modes | ❌ | medium — `GetForegroundWindow` + process name; browser URLs are the hard part |
| Streaming partials, polished UI | ❌ | large — and skippable |

Note the deeper point in that table: Gemma and VoiceInk are *opposite poles of the same pipeline*. Gemma treats your speech as a question and answers it aloud; VoiceInk treats your speech as text and delivers it silently. The scoping study even makes this distinction explicitly ("dictation tools transcribe but do not act"). Adding dictation to Gemma isn't scope creep — it's a second output sink on a pipeline you've already built, and it gives Gemma a daily-use payoff long before the headset exists.

## 4. Recommendation

**Don't buy — but do both of the free things.**

1. **On the Mac laptop: build VoiceInk from source** (`git clone`, `make local` — no Apple developer account needed). Use it for a couple of weeks: it is the fastest way to learn what the UX gets right before designing anything in the same shape. If it earns a place in the daily routine, buy the ~$39 lifetime licence — the source build is sanctioned by the licence, but the purchase is what funds the developer. Either way it is not a build strategy: none of that Swift code will ever run on the Windows box or talk to the headset.

2. **On Windows: add a dictation mode to Gemma.** Concretely, as a post-M0 slice (don't let it jump the queue ahead of the acceptance run):
   - A global hotkey listener with VoiceInk's three-mode logic (toggle / PTT / hybrid) as the trigger — this is also a useful fallback input for headset development, since Contract H already anticipates a `BUTTON hold=push-to-talk` message.
   - A `dictate` path in the orchestrator: capture → existing `listen.py` transcribe → *optional* cleanup pass through the existing Contract-B brain → clipboard + `SendInput` Ctrl+V. The cleanup prompt is the piece worth thinking hardest about. `AIPrompts.swift` is the most instructive artifact in their repo — it encodes months of trial-and-error about self-corrections, spoken punctuation, and "transform, never answer" — but what it teaches is the *problem list*, not the wording. Take the problem list; write Gemma's own prompt against it. Copying the text would make Gemma's prompt a derivative of GPL-3.0 source, binding the moment anything is distributed, and the wording has to be ours regardless: British spelling, no `<USER_MESSAGE>` tag scaffolding, our own worked examples.
   - Later, if you want Power Modes: foreground-window detection via `pywin32` is an afternoon; per-app prompt profiles slot naturally into your existing JSON-schema config style. Skip browser-URL detection and screen-OCR context initially — on Windows they're the highest-effort, lowest-reliability pieces.
   - Skip streaming partials entirely for now; batch transcription of a 10-second utterance on the 5080 is fast enough that partials are cosmetic.

   Rough effort: a working hotkey→transcribe→paste loop is a weekend on top of what exists; the cleanup prompt and word-replacement dictionary another. VoiceInk's remaining ~50k lines are macOS plumbing, UI polish, and eleven cloud providers you don't need.

3. **What to lift from VoiceInk's source while you're at it:** the pipeline ordering (deterministic word-replace *before* LLM enhancement — cheaper and more predictable than making the LLM do spelling), the transient-clipboard + restore-after-paste pattern, the custom-vocabulary-as-spelling-authority idea, and the hybrid hotkey state machine. All of these are ideas, not code, and translate to Python directly.

One caution to keep the project honest with itself: the dictation sidecar is seductive precisely because it's easy and immediately useful. The thing that makes Gemma *Gemma* — the acceptance run, spoken-answer latency, and eventually the headset — still has its riskiest work (live audio validation) unstarted. Do the ×10 run first; it will also tell you whether `small.en` transcription quality is good enough for dictation, which is a stricter test than conversational use.

---

### Sources

- [VoiceInk source (GPL-3.0)](https://github.com/Beingpax/VoiceInk) — full clone reviewed
- [VoiceInk pricing — lifetime macOS plans](https://tryvoiceink.com/pricing)
- [VoiceInk product page (macOS)](https://tryvoiceink.com/)
