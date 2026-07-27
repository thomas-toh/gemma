# Review: Rust backend port — adversarial assessment against the actual codebase

*Prepared 2026-07-24. Trigger: Thomas finds daemon startup (~10–15 s felt; 22.1 s measured cold on 2026-07-22, STATE) too slow and asks whether a Rust port of the back-end would cause problems. Method: full codebase review (this session already held every file of `bridge/` and `teleprompter/` from the 2026-07-22 adversarial review), plus web verification of the current Rust ecosystem for each engine the daemon uses. Written in plain language throughout, per Thomas's standing instruction. This review allocates no D-number; if its outcome is adopted it should be recorded by a design session per CLAUDE.md's coordination rule.*

*Relationship to D21: D21 (2026-07-21) already evaluated a Rust port, deferred it, and bound every session with an anti-relitigation clause — no runtime re-debate until the app is feature-complete AND instrumentation has produced numbers. Thomas is invoking re-open trigger ① (boot-time pain). The honest reading of that trigger is that it requires *measured* numbers, and today only one aggregate number exists (one "warm-up done in 22.1 s" log line). This review therefore does two things: it tests the premise with the evidence that does exist, and it specifies the instrumentation that makes the decision data-driven. It does not overturn D21; on the evidence below, it re-affirms it.*

---

## Verdict, up front

**A Rust port would not fix the thing that is annoying you.** The 10–15 seconds is almost entirely *loading AI models into memory and waking up the GPU* — work done by compiled C++ engines that are the same speed from any language. Rust would remove roughly the 2–4 seconds that are genuinely Python's fault (starting the interpreter and importing libraries), and keep the other ~10–18 seconds essentially unchanged. Meanwhile the port would cost you: a forced swap of the wake-word engine (no usable Rust port of openWakeWord exists), either a forced swap or a hard Windows build for the speech-to-text engine, a hand-rolled replacement for the Anthropic SDK, the loss of your entire test suite (selfchecks + replay harness are Python, wired into Python internals), and a weeks-to-months feature freeze at the exact moment Track D (dictation) has just been unblocked.

**The startup pain has three fixes that live in Python, are small, and together make startup effectively disappear.** Two of them are things the spec already decided and the code simply hasn't caught up with: the default product (D23: speech off, wake word off) is currently paying startup cost for two engines it is configured never to use. The third — tray residency, so the daemon starts once at login and just stays running — is literally D21's recorded answer to this exact complaint: *"slow boot is model loading (any runtime) — answered by tray-residency, not a rewrite."*

Recommendation in one line: instrument the warm-up (5 log lines), apply fixes F-1..F-4 below, re-measure — and keep the port deferred per D21, unless the numbers afterwards say otherwise or you decide you want the Rust rewrite *as a project in itself*, which is a legitimate tinkerer's reason and is addressed at the end.

---

## Part A — Where the 10–15 seconds actually goes

Plain-language walk through what happens when you launch `python -m bridge.orchestrator` (`run()`, orchestrator.py:570-596). Think of it as opening a workshop in the morning:

| Stage | What it is, plainly | Est. share | Would Rust remove it? |
|---|---|---|---|
| 1. Interpreter + imports | Python wakes up and reads in every library (numpy, sounddevice, onnxruntime, the API client…). On Store Python with no venv this is slower than it should be — thousands of small file reads. | ~2–4 s | **Yes** — this is the part Rust deletes (a compiled binary starts in milliseconds). |
| 2. Wake-word model | `download_models()` checks/fetches, then `Model(...)` loads three small ONNX models. | ~0.5–1 s | No — same ONNX files loaded by the same ONNX Runtime. |
| 3. Silero VAD | One small ONNX model. | ~0.2 s | No — same. |
| 4. Whisper (STT) | `transcribe(zeros)` forces the big one: create a CUDA context (waking the GPU driver, 1–3 s by itself), copy the `small.en` weights into VRAM, run one warm-up pass. | ~3–6 s | No — CUDA context + weight loading cost the same from Rust. (The one-off ~26 s Blackwell JIT is already cached — NOTES.) |
| 5. Kokoro (TTS) | `synth("ready")`: fetch-check two files (~310 MB model + voices), load them, synthesize one throwaway word on CPU. | ~2–5 s | No — same model into the same runtime. |
| 6. Hotkey registration | Deliberately *after* all of the above (orchestrator.py:590-592), so a press during loading can't queue a ghost turn — which means the daemon is completely unusable for the whole warm-up. | ~0 s | n/a — but see F-4: this ordering is why the wait is *felt* so hard. |

Two caveats stated honestly: the shares are estimates — only the aggregate (22.1 s) was ever logged, because `run()` wraps the whole warm-up in a single timer. That is exactly the instrumentation gap D21's trigger ① requires closing before a port decision is legitimate. And your "10–15 s" vs the measured 22.1 s suggests conditions already improved (venv? warm OS file cache) — another reason to measure before deciding.

**The spec-drift finding buried in this table (the most useful thing in this review):** stages 2 and 5 — wake word and TTS — serve features that are **off by default** in the shipped product (D23: speech and "listen for me" are switches, default off). The code loads them unconditionally because the switches aren't built yet (they wait on the spec/70 config source — the same M0-close settings gate you already set). So roughly a third to a half of your startup is spent loading engines the D23 default product never uses. The settings gate you already planned is also the startup fix.

## Part B — What Rust would actually buy, tested against the ecosystem as it stands

Verified by current research (sources at the end), engine by engine, because "rewrite it in Rust" really means "find or rebuild each of these five engines from Rust":

- **ONNX Runtime (VAD, wake scoring):** fine. The `ort` crate (pykeio/ort) is active and mature enough — this piece ports cleanly. **But:**
- **openWakeWord: no viable Rust port exists.** The only attempt found (`oww_rs`) is a 7-star, inference-only partial extraction with the Alexa model as its example. openWakeWord isn't one model — it's a three-stage pipeline (mel-spectrogram → embedding → classifier) with its own buffering, which you would hand-port and re-validate. The realistic alternative is an **engine swap** (rustpotter, or the `livekit-wakeword` crate — LiveKit is already on your parked list as a possible swap) — but any swap means re-tuning false-accept behaviour and re-recording the regression story, and your custom-wake-phrase plan (spec/40) currently assumes openWakeWord's training pipeline.
- **faster-whisper (STT):** faster-whisper *is* Python glue over CTranslate2. From Rust you either take `ct2rs` (community CTranslate2 bindings — meaning you build CTranslate2 with CUDA/cuDNN on Windows yourself; you have lived the Windows-CUDA-DLL experience already, this is that but with a C++ build system in the loop) or swap engines to whisper.cpp via `whisper-rs` (real project, CUDA feature exists — but a *different engine* with different speed/accuracy, invalidating your measured STT numbers and your replay-case similarity thresholds until re-tuned).
- **Kokoro (TTS):** surprisingly decent news — `Kokoros` (lucasjinreal) is an active Rust Kokoro with espeak-ng phonemization and even voice-style *mixing* (your blended `bf_emma:45,af_heart:40,bm_george:15` voice has an equivalent). Caveats: no Windows documentation, and your en-gb-dominant-voice phoneme logic (`_voice_lang`) would need re-verifying, since accent flattening was the reason it exists.
- **Anthropic API:** **no official Rust SDK.** Several community SDKs exist (varying maturity); realistically you hand-roll reqwest + SSE streaming and re-implement Contract B's error taxonomy (auth/rate_limit/context/unavailable) and — at M1 — the tool-use loop, by hand, against a moving API.
- **Audio I/O:** sounddevice/PortAudio → `cpal` (WASAPI). Portable in principle; the OutputPump's Bluetooth keep-alive semantics (spec/40 BINDING) and device quirks would need re-proving on your actual gear.
- **Hotkeys, keyring:** genuinely *easier* in Rust (the `windows` crate makes RegisterHotKey cleaner than ctypes). One compatibility check owed: whether the Rust `keyring` crate reads the credentials Python's `keyring` already stored under service `gemma` (worst case: re-enter two keys — trivial).

So the port is *feasible* — D21's preserved plan (Rust daemon behind Contract P, same NDJSON feed, QML Teleprompter unchanged) remains sound architecture. The issue is not feasibility. It is that the *startup* payoff is ~2–4 s, and the price is Part C.

## Part C — Port risk register

- **R-01 (High) — The test suite dies with the port.** Every `--selfcheck`, the CI workflow, and above all the replay harness (`tests/replay.py`) are Python programs that reach *into* Python objects (FakeMic feeding the real orchestrator, real `Door` events, fake brain). The WAV fixtures survive; everything that runs them does not. D21 says the QML Teleprompter doubles as the port's behaviour oracle — true, but Contract P only shows *display* behaviour. The things your hardest-won bugs lived in — capture endpoints (D20), barge-in, door state — are proven today only by Python-coupled tests, all of which must be rewritten in Rust before the port is even *checkable*.
- **R-02 (High) — Forced engine swaps.** Wake word: no Rust openWakeWord → swap (rustpotter / LiveKit) → re-tune false accepts, redo the custom-phrase plan. STT: ct2rs-with-a-C++-build or whisper.cpp-with-different-behaviour. Either way, the measured numbers (STT 273–603 ms real-speech GPU; the replay transcript thresholds) stop being valid until re-earned.
- **R-03 (Medium) — Hand-rolled brain adapter.** No official Anthropic Rust SDK; streaming, error mapping, and the M1 tool loop become your code to maintain against API changes.
- **R-04 (Medium) — Feature freeze at the worst moment.** Track D (dictation — the feature you actually use daily once it exists) was unblocked two days ago; the 26-finding fix list is queued; M0-close waits on the settings gate. A port is weeks-to-months of a solo hobby schedule during which none of that moves. For this project the realistic failure mode of a rewrite is not "it's buggy," it is "the project stalls in the middle of it."
- **R-05 (Medium) — Two audio stacks' worth of physical-world debugging.** cpal/WASAPI will have its own versions of the quirks you already paid for once in PortAudio (BT keep-alive, duplex behaviour, buffer sizes). The physical world needs tuning twice.
- **R-06 (Low) — Dev-loop friction.** The project's working style — build, see it live, reject it same-day (the ⌄ handle; the window-animation rewrite) — runs on a seconds-long edit-run loop. Rust's compile-check-borrow loop is slower for you specifically (a vibecoder with AI assistance), and while AI writes Rust well, *you* reviewing Rust diffs is a different proposition from reviewing Python.
- **R-07 (Low) — Small compatibility checks.** Keyring target-name compatibility; schema loading (trivial via serde); `GEMMA_*` env parity; log-format parity for anything that greps `gemma.log`.

## Part D — What actually fixes startup, in Python, this week

- **F-1 — Tray residency (removes the wait from daily life entirely).** The daemon starts at login, loads once, and stays resident; "starting Gemma" stops being a thing you do. This is D21's own recorded answer, and STATE already parks the launcher/Job-Object design (needs D24). Cost: small; the tray already exists in the overlay process.
- **F-2 — Stop loading what D23 turned off (cuts ~⅓–½ of cold start).** With speech off, don't load Kokoro; with "listen for me" off, don't load openWakeWord (and skip its download check). Blocked only by the spec/70 config source — the M0-close settings gate you already committed to. Until then, even a crude env-var gate would bank the win.
- **F-3 — Load in parallel and lazily (cuts most of the rest).** The four models load sequentially today; wake+VAD (~1 s) could be ready almost immediately, with Whisper (and Kokoro if enabled) loading on background threads — all these libraries release the GIL while loading. Wall-clock falls to roughly the slowest single component. Optionally defer Whisper to first use with a "warming" cue on the island.
- **F-4 — Register hotkeys first, not last (makes the remaining wait *feel* short).** The after-warm-up ordering exists so a press can't queue a ghost turn — but the right fix for that is a "warming" state (press acknowledged on the island: "waking up…"), not deafness. Perceived startup becomes near-zero even when real startup is 4 s.
- **F-0 — Instrument first (the precondition for all of it, and for D21).** Split `run()`'s single warm-up timer into per-stage log lines (imports / wake / VAD / whisper / kokoro — ~5 lines). Then F-1..F-4 are applied against numbers, and any future port debate starts from data. This is the instrumentation D21's trigger ① names.

Also note: part of the *felt* slowness is per-turn, not startup — every turn currently opens a fresh API connection (finding B-01 of the 2026-07-22 review). Fixing that is already queued and is language-independent.

## Part E — Ruling against D21, and the honest tinkerer's caveat

**On the merits, D21 stands: no port now.** Trigger ① is not yet properly met (no per-stage numbers exist), the pain it names is real but is answered by F-0..F-4 at ~1% of a port's cost, and the port carries R-01..R-07 for a startup payoff of a few seconds. Re-measure after F-1..F-4; if startup pain *survives* residency + conditional loading — or one of D21's other triggers fires (battery-powered always-on use; shipping to a second user) — reopen with data.

**The caveat this project is entitled to:** Gemma is a tinkering project, and "I want to build the engine in Rust because building engines in Rust sounds fun" is a valid reason that needs no latency justification. If that's the real motive, say so and do it *well*: after M0-close and the dictate door land (so the Python app is the complete, working reference D21's plan assumes), behind Contract P exactly as the preserved plan describes, with the replay-harness rewrite budgeted as part of the port, and with the Python engine kept runnable as the oracle. What this review argues against is not Rust — it is doing the rewrite *now, for startup time*, because that trade is roughly two months of feature freeze to save two seconds that F-1 makes invisible anyway.

---

## Sources (ecosystem verification, 2026-07-24)

- ort (Rust ONNX Runtime): https://github.com/pykeio/ort · https://ort.pyke.io/
- whisper-rs (whisper.cpp bindings, CUDA): https://github.com/tazz4843/whisper-rs · https://github.com/tazz4843/whisper-rs/blob/master/BUILDING.md
- ct2rs (CTranslate2 bindings): https://github.com/jkawamoto/ctranslate2-rs · https://docs.rs/ct2rs
- openWakeWord in Rust (partial): https://github.com/skoky/oww_rs · rustpotter: https://github.com/GiviMAD/rustpotter-cli · livekit-wakeword: https://crates.io/crates/livekit-wakeword
- Kokoro in Rust: https://github.com/lucasjinreal/Kokoros
- Anthropic Rust SDKs (community, no official): https://github.com/tmikus/anthropic-sdk-rust · https://github.com/ThreatFlux/anthropic_rust_sdk
