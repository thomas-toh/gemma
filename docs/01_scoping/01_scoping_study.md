# Project Gemma — Scoping Study

**A bone-conduction headset interface to a local LLM** — feasibility, teardown assessment, on-headset compute analysis, and a phased build roadmap.

*Personal prototyping project, not a commercial venture · July 2026 · Doc 01 of the project series*

---

## Executive summary

You asked three questions. Here are the three answers, defended in detail in the rest of this study.

**1. Can you build this?** Yes, and with less original invention than you might fear. Every sub-component — bone-conduction audio output, always-listening wake-word detection, streaming microphone audio to a PC, a local LLM that controls Windows, low-latency spoken and "ping" responses — exists today as a proven open-source project or a £5–15 part. What does not exist is the combination: nobody has cleanly merged an open AI-wearable pipeline (like Omi/OpenGlass) with bone-conduction output and local PC control. That integration is the genuinely novel part of your project, and it is well within tinkerer reach.

**2. Should you tear down a commercial bone-conduction headphone?** You can — but go in knowing that every waterproof bone-conduction headset opens destructively (silicone-glued seams, no screws that matter), and that the glued-in lithium pouch cell demands respect. The teardown is worth doing once, on a £25–40 generic unit, for the transducers, the band mechanics and the education. But the surprising finding is that you may not need a donor at all: bone-conduction transducers are sold as bare components for £7–12, and the DIY community has repeatedly shown they work well glued to a headband or eyeglass temples. The recommended strategy is two-track: buy one cheap donor to dissect, and breadboard the real audio chain from bare parts in parallel.

**3. Can an analog chip run the LLM on the headset itself?** No — not in 2026, and not by a small margin. This study examined every purchasable analog and edge-AI chip: the ones a hobbyist can buy (Aspinity AML100, Syntiant NDP-series) run micro-watt keyword-spotting networks a million times too small for a language model, and the ones that do run transformers (EnCharge EN100, Hailo-10H, Jetson Orin) are 2.5–25 W laptop- or belt-class parts that cannot be hung on a head thermally, gravitationally or battery-wise. Physics, not product maturity, is the barrier: a head-worn frame dissipates ~1–3 W safely, and LLM inference is memory-bandwidth-bound in ways tiny chips cannot address. Every commercial AI wearable — including Meta's, with effectively unlimited budget — offloads the model. Your headset should carry the wake word and the audio; the LLM lives on your PC. Revisit the on-headset question around 2028.

> **The recommended shape of the project:** a headset that is deliberately "dumb but alert" — microphone, bone-conduction transducer, wake-word chip, radio — talking to your RTX 5080 PC, which runs the entire intelligence stack (speech recognition, LLM with tool-calling control of Windows, text-to-speech and earcon pings). This is the same architectural split used by every shipping AI wearable, and it maps directly onto your later interest in office deployment: swap the gaming PC for a modest office machine or a shared firm server, and the headset does not change at all.

Budget fit: the full roadmap in Section 9 lands at roughly **£450–£700** of the £200–£800 envelope, spread across four phases, each of which produces a working artefact on its own.

## 1. The concept and its requirements

The device you described: a head-worn unit built around bone-conduction audio, which (a) actively listens for a wake word and spoken commands, (b) routes those commands to a local LLM that can control your PC and answer questions, and (c) responds through the headset with either short non-verbal pings (acknowledgement, success, failure, "answer ready") or fully narrated spoken answers when prompted. The LLM must be local — no cloud dependency for the core loop.

Decomposed into functions, with an honest note on difficulty:

| **Function**               | **How it will be done**                                              | **Difficulty**                                            |
|----------------------------|----------------------------------------------------------------------|-----------------------------------------------------------|
| Bone-conduction output     | Salvaged or bare transducer + small Class-D amplifier                | Easy — solved, £10–20 of parts                            |
| Always-listening wake word | On-headset (ESP32-S3 / Syntiant) or on-PC (openWakeWord / Porcupine) | Easy — mature open tooling                                |
| Speech capture → PC        | Bluetooth (v0), wire (v1), Wi-Fi/BLE streaming (v1.5), LE Audio (v2) | Easy to moderate; Section 5                               |
| Local speech-to-text       | faster-whisper / Parakeet on the 5080; or audio-native Gemma         | Easy — minutes to set up                                  |
| Local LLM + PC control     | Gemma 4 / Qwen3-class model + Windows-MCP tool server                | Moderate — the real engineering is reliability and safety |
| Pings and narration        | Pre-rendered earcon WAVs + streaming local TTS (Kokoro / Piper)      | Easy                                                      |
| LLM on the headset itself  | Not possible in 2026 at head-worn power/weight — see Section 2       | Not feasible yet                                          |

Design tenets adopted throughout this study, reflecting the project brief: local-first (audio and text never leave machines you own); prototype-not-product (no certification, no enclosure perfectionism, destructive teardowns are fine); and phased so that every stage yields something that works, rather than one long march to a distant integration.

## 2. Can the LLM live on the headset? The analog-chip question

This is the most interesting question you asked, and it deserves a full answer rather than a reflexive no. "Analog" AI chips are real: they perform matrix multiplication inside memory arrays using physical charge or current instead of shuttling numbers through a digital pipeline, and they achieve startling efficiency numbers. The question is what you can actually buy, and what those parts can actually run.

### 2.1 The analog in-memory compute landscape, honestly surveyed

| **Chip / company**     | **What it is**                                                                                           | **Can you buy it, and does it run LLMs?**                                                                                                                                                                                               |
|------------------------|----------------------------------------------------------------------------------------------------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Mythic M1076           | Flash-cell analog matrix processor, ~25 TOPS at \<4 W                                                    | B2B/defence sales only after a 2023 near-death rescue; runs CNNs (vision), **not transformers**. Next-gen M2000 'forthcoming' with no ship date.                                                                                        |
| EnCharge EN100         | Charge-domain analog SRAM; 200+ TOPS at 8.25 W on an M.2 card, up to 32 GB LPDDR                         | **The one analog part that genuinely runs transformers** (5–15B models pitched). But: OEM early-access programme only, no retail price, no hobbyist channel — and 8.25 W is a laptop part, 3–8× over a head-worn thermal budget anyway. |
| IBM NorthPole / Hermes | Research silicon; 16-chip NorthPole server ran a 3B model at \<1 ms/token, ~73× more efficient than GPUs | Pure research prototypes. Not products, not purchasable.                                                                                                                                                                                |
| Blumind AMPL           | All-analog ~60 µW always-on audio AI                                                                     | Sampling with partners; roadmap talk of analog small-language-models, but today it is keyword-scale only.                                                                                                                               |
| Aspinity AML100        | Analog event-detection core, \<100 µA always-on                                                          | **Yes — buyable** (Renesas eval board, Arduino shield). But it runs ~10³–10⁴-parameter event detectors. An LLM is ~10⁹. Six orders of magnitude short.                                                                                  |

The pattern: in 2026 an individual can buy exactly one class of analog AI silicon — micro-watt event detectors. The single analog chip that runs transformer models is locked inside an OEM early-access programme and is the wrong power class for a headset regardless. The analog revolution is real but it is arriving first in laptops, not wearables.

### 2.2 What could go on the headset: wake-word silicon

Where ultra-low-power chips do shine is the always-listening front door. These are the parts that belong in your headset:

| **Part**                              | **Power**     | **What it runs**                                                          | **Availability**            |
|---------------------------------------|---------------|---------------------------------------------------------------------------|-----------------------------|
| ESP32-S3 + ESP-SR                     | ~0.1–0.5 W    | WakeNet wake word + ~200 offline command words; free, superbly documented | Boards £8–12 everywhere     |
| Syntiant NDP120 (Arduino Nicla Voice) | µW–1 mW class | Wake word + small audio nets; multi-day coin-cell budgets                 | £37 board, 2 g              |
| Ambiq Apollo510                       | mW class      | Speech/health tinyML on Cortex-M55                                        | Eval boards at Mouser       |
| GreenWaves GAP9                       | ~50 mW        | Neural ANC and hearing enhancement in production earbuds                  | B2B-leaning; eval via sales |

None of these can run even a 0.5B-parameter language model — they have kilobytes-to-megabytes of RAM, and a 1B model quantised to 4 bits needs ~700 MB plus bandwidth to stream it every token. The gulf between "wake word chip" and "LLM chip" is not compute so much as **memory**: LLM decoding is bound by how fast you can read the weights, and no head-worn part has the DRAM or the bandwidth.

### 2.3 The smallest hardware that runs a usable LLM in 2026

| **Platform**              | **Price** | **LLM performance**                          | **Head-worn?**                                            |
|---------------------------|-----------|----------------------------------------------|-----------------------------------------------------------|
| Raspberry Pi 5 (8–16 GB)  | £60–95    | 1B models ~13 tok/s; 3B ~5 tok/s (CPU)       | No — 5–12 W, and 3B is painfully slow                     |
| Jetson Orin Nano Super    | ~£185     | 3B ~43 tok/s; 7B ~22 tok/s (INT4)            | No — 25 W, 175 g, fan-cooled. Fine as a **belt/desk hub** |
| Hailo-10H (M.2)           | enquiry   | 2B-class ~10 tok/s at ~2.5 W (chip alone)    | No — needs a host board + DRAM; belt-pack territory       |
| RK3588 SBCs (Orange Pi 5) | £75–140   | 1.1B ~10–15 tok/s on NPU, ~5–6 W board       | No, but a plausible pocket hub                            |
| Flagship Android phone    | owned     | 3B ~10 tok/s on NPU; Gemma 3n runs in 2–3 GB | **The realistic 'no PC' hub** — pocket, not head          |

A conversational assistant needs roughly 8–10+ tokens/second (reading speed) plus a fast first token. The Pi 5 is marginal, the Jetson is comfortable but is a small fan-cooled brick, and a modern phone is quietly the most interesting non-PC option: Google's Gemma 3n was designed precisely to run multimodally in 2–3 GB of phone memory. If you ever want this system to work away from your desk, the answer is a phone in your pocket, not silicon on your skull.

### 2.4 The physics, briefly

- **Thermal:** a head-worn frame can shed ~1–3 W before skin-contact surfaces approach the 43°C safety line; a modelled 5 W glasses design reached ~51°C at the temple. Every LLM-capable part above needs 2.5–25 W.

- **Battery:** glasses-class devices carry ~0.5–1 Wh to stay wearable. A 3 W LLM load on a 1 Wh cell is ~20 minutes of runtime. Even a 5 W hub board needs a ~20 Wh (~80 g) pack for a working day — fine on a belt, absurd on a face.

- **The market agrees:** Meta Ray-Ban glasses run only capture and wake word on-frame and offload the AI; the Humane Pin (cloud-only) died in February 2025; the Rabbit r1 teardown verdict was "there simply isn't enough processing power here"; every recorder pendant (Omi, Bee, Limitless) streams to a phone. Zero shipping wearables run an LLM on-device.

**Trajectory:** three developments to watch — phone-class models like Gemma 3n maturing (now), sub-5 W generative accelerators like Hailo-10H reaching hobbyist hosts (1–2 years), and EnCharge-class analog efficiency compounding another generation (~2028). Around 2028, a ~1B always-on model at 1–2 W on a glasses frame becomes an engineering problem rather than a physics violation. Design your headset now so the "brain" is swappable later.

## 3. Recommended system architecture

The architecture that follows from Section 2 — and that every phase of the roadmap builds toward — is a three-layer split:

| **Layer**      | **Components**                                                                                                                                  | **Rationale**                                                                                                           |
|----------------|-------------------------------------------------------------------------------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------------------------------|
| Headset (head) | MEMS microphone · bone-conduction transducer + Class-D amp · wake-word detection (ESP32-S3 class) · radio · physical mute switch · activity LED | Milliwatts, grams, all-day battery. Nothing here needs to be clever.                                                    |
| Link           | v0 Bluetooth HFP → v1 wire → v1.5 Wi-Fi/BLE PCM streaming → v2 LE Audio (LC3)                                                                   | Progressively better audio and latency; Section 5.                                                                      |
| Hub (PC)       | VAD + speech-to-text · LLM with tool-calling · Windows control layer (MCP) · earcon player + streaming TTS                                      | Your RTX 5080 runs all of it with headroom; later swappable for an office NPU laptop, a shared firm server, or a phone. |

The interaction loop: the headset hears the wake word locally and only then streams audio (a privacy and battery win); the PC transcribes, the LLM decides — answer, or act via tools — and the response comes back as an earcon the instant a tool succeeds (this is what makes the system *feel* instant) with narrated speech only where you asked for it. An important design gift from your own spec: **pings are latency-free**. A pre-rendered WAV fired on tool success arrives faster than any TTS pipeline, so "open my case file" can feel sub-second even when full spoken answers take a second or more.

## 4. Hardware: the bone-conduction question

### 4.1 Tearing down a commercial headset — what you would actually find

iFixit's teardowns of the Shokz (formerly AfterShokz) range are the best public evidence, and they are unambiguous: the seams are bonded with black silicone adhesive, opening requires scoring and levering with a knife, and iFixit explicitly frames its OpenRun teardown as "not a repair guide." The Trekz Titanium teardown found one screw, heavy adhesive everywhere, and a 200 mAh lithium-polymer pouch cell glued into a rigid pocket. Nothing inside is designed to come out. FCC filing photos confirm the same construction across the range. Waterproofing (IP55–IP68) is precisely what makes these products un-openable: you will not restore it after entry.

**What is worth salvaging:** the transducer pods and the sprung titanium band — the parts embodying Shokz's real engineering, which is clamping force and skin coupling. The pods, however, have essentially zero spare internal volume; the electronics fill them completely. So the realistic teardown outcomes are: (a) keep the headset intact and treat it purely as Bluetooth audio I/O; (b) salvage band + transducers and re-house your own electronics in a 3D-printed pod at the nape; or (c) skip the donor entirely and use bare exciters.

**Battery safety, seriously:** the LiPo pouch is glued tight against the case wall, and prying near it risks puncture — which can mean venting, fire, or both. Standard precautions: discharge the unit fully before opening, use plastic tools only near the cell, work on a non-flammable surface, and have a LiPo-safe bag or a tub of sand within reach. Replacement cells for Shokz models cost ~£8 on AliExpress if you nick one. Treat this as the one genuinely hazardous step in the whole project.

### 4.2 Donor selection

| **Candidate**                        | **Price** | **Assessment**                                                                                                                                                                                                                    |
|--------------------------------------|-----------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Generic AliExpress/Amazon BC headset | £20–40    | **The recommended sacrifice.** Cheap enough to destroy guilt-free; practice teardown, harvest transducers and band. Beware: many sub-£25 'bone conduction' units are actually tiny open-ear speakers — check reviews for true BC. |
| Shokz OpenMove                       | £79.95    | Cheapest true Shokz; the donor if you want known-good, properly tuned transducers. Still glued.                                                                                                                                   |
| Shokz OpenRun / Pro 2                | £130–180  | **Do not sacrifice.** Their value is the tuned transducer+DSP system, which you destroy by replacing the electronics. Keep one intact as your quality benchmark instead.                                                          |
| JLab JBuds Frames                    | ~£40      | Clip-on audio pods for glasses; self-contained BT+battery+amp bricks, screwed rather than bathtub-sealed — an underrated gut-donor if you want a glasses form factor.                                                             |

### 4.3 The bare-component route (probably your main path)

Bone-conduction transducers are just voice-coil exciters optimised for skin contact, and they are cheap:

| **Part**                       | **Price** | **Notes**                                                                                                                           |
|--------------------------------|-----------|-------------------------------------------------------------------------------------------------------------------------------------|
| Adafruit \#1674 bone conductor | ~£7       | 8 Ω, 1 W RMS, 14×21.5 mm; the community standard. Cover contacts (Sugru/heatshrink) against sweat.                                  |
| Dayton Audio BCE-1             | ~£11      | 4 Ω, 1 W, 22×14×8 mm; slightly beefier, well documented.                                                                            |
| AliExpress GD-02-class modules | £3–6      | Tiny (12.6×6×4 mm) — the only ones small enough for eyeglass temples.                                                               |
| MAX98357A I2S amplifier        | ~£4.50    | 3 W Class-D with digital I2S input — pairs perfectly with an ESP32; fully digital audio path.                                       |
| PAM8302 analog amplifier       | ~£3       | 2.5 W mono for analog sources (USB sound card, 3.5 mm). An unamplified transducer is nearly inaudible — amplification is mandatory. |

Intelligible bone-conducted speech needs only ~100–500 mW pressed against the mastoid or cheekbone; expect thin bass, a need for firm and correctly-placed pressure, and surprisingly low sound leakage. Prior art worth reading before you build: the Hackaday DIY bone-conduction glasses (which found the Adafruit part too big for temple arms — hence the GD-02 modules), Wes Honeycutt's 3D-printed clips that hook transducers onto eyeglass temples, and a £16 build that gutted a Bluetooth speaker and swapped its driver for a bone transducer.

> **The gap you would be filling:** the open-source AI-wearable projects (Omi pendant, OpenGlass — both under £20 of parts, both proven) stream audio *in* but have no audio *out* in their base designs. A bone-conduction output stage bolted onto an Omi-style firmware is a combination nobody has published. Every part of it is individually de-risked.

## 5. Getting audio to and from the PC

### 5.1 The Bluetooth trap, and why it matters less than it looks

Classic Bluetooth has two audio modes and a headset can only be in one: A2DP (good stereo out, no microphone) or HFP (bidirectional, mono, 8 or 16 kHz). The moment any app opens the mic, Windows drops the whole link to HFP — a limitation of the Bluetooth standard, not a bug. This is why headset audio "goes terrible" on calls.

For this project, though, the trap is shallow: **Whisper-class speech recognition natively operates at 16 kHz mono anyway**, so a 16 kHz mSBC hands-free link loses almost nothing for transcription accuracy. The genuine risks are silent fallback to 8 kHz (check Windows Sound settings: the "Hands-Free" endpoint should show 16,000 Hz, not 8,000) and over-aggressive noise-suppression DSP inside the headset. And since your output during assistant use is spoken replies and pings, mono voice-grade output is fine. Music quality suffers only while the mic is open.

Windows 11 24H2 has meanwhile shipped the real fix: **Bluetooth LE Audio (LC3)**, including "super wideband stereo" — simultaneous stereo playback plus a ~32 kHz microphone stream, ending the A2DP/HFP collapse, at ~10 ms codec frames. The catches: you need an LE-Audio-capable radio with proper drivers (common on 2024+ laptops, rare on desktop dongles — Creative's BT-W6, ~£37, is a clean workaround), and, notably, **no bone-conduction LE Audio headset exists yet** as of July 2026. Shokz's line is still Classic Bluetooth.

### 5.2 The recommended progression

| **Stage** | **What**                                                                                                                                              | **Cost**      | **Purpose**                                                                                                                                                                                                                       |
|-----------|-------------------------------------------------------------------------------------------------------------------------------------------------------|---------------|-----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| v0        | Stock Shokz OpenComm2 UC (boom mic + USB dongle), unmodified                                                                                          | ~£160         | Running this week, zero soldering. 16 kHz HFP is 'good enough for Zoom', which is good enough for Whisper. Learn the UX; build the whole PC pipeline against it.                                                                  |
| v1        | Wired custom headset: USB sound card (~£10) + lavalier electret + PAM8302 + bare transducer on a headband                                             | £35–60        | Full 48 kHz duplex, sub-10 ms, infinite battery. Isolates your software work from all radio variables; a 2–3 m USB-C extension gives desk-radius mobility.                                                                        |
| v1.5      | Wireless DIY: Seeed XIAO ESP32-S3 Sense (~£12) + INMP441/ICS-43434 mic + MAX98357A + transducer, streaming 16 kHz PCM over Wi-Fi; wake word on-device | £30–50 + LiPo | The 'real' prototype. 3–5 h continuous on a 500 mAh cell; 8–12 h with 1200 mAh or wake-word gating (radio only opens after the wake word). If battery life dominates, copy the Omi pendant's nRF52840 BLE firmware (24 h+ class). |
| v2        | LE Audio: Nordic nRF5340 Audio DK (~£150–180) built into a custom LC3 headset; or wait for a BC LE Audio product + BT-W6 dongle                       | £40–180       | The endgame: 32 kHz mic + stereo out simultaneously, 10 ms frames, native Windows 11 support. Fair warning: Zephyr dual-core firmware is a serious project, not a weekend one.                                                    |

### 5.3 Microphones

For a mic 5–20 cm from your mouth, a single £2–5 I2S MEMS microphone (INMP441, or its successor ICS-43434 since the 441 is end-of-life) plus PC-side noise reduction is sufficient and is what the entire voice-satellite community uses. Two exotic options worth knowing about: true bone-conduction *microphones* (Knowles V2S200D, PUI VMM-1627L-R) are buyable from DigiKey and reject ambient noise almost completely — but they are bare surface-mount parts needing a carrier PCB and skin contact, an advanced later experiment. Throat mics (£15–35) work in noise but produce muffled, formant-poor audio that measurably hurts recognition — a fallback, not a plan.

## 6. The PC software stack (built around your RTX 5080)

### 6.1 The components

| **Stage**      | **Recommended**                                                                                                                                     | **Notes**                                                                                                                                                  |
|----------------|-----------------------------------------------------------------------------------------------------------------------------------------------------|------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Wake word      | openWakeWord (PC) or Porcupine free tier; microWakeWord on the ESP32 from v1.5                                                                      | Custom wake phrases trainable from synthetic audio via free notebooks. Porcupine has the lowest false-accepts for an always-on mic.                        |
| Speech-to-text | faster-whisper large-v3-turbo; NVIDIA Parakeet TDT 0.6b for raw speed; Moonshine for true streaming                                                 | A short command transcribes in well under half a second on your GPU. All fit in VRAM alongside the LLM.                                                    |
| LLM            | Gemma 4 (Apache 2.0, April 2026) or Qwen3.5/3.6; via Ollama, llama-server or LM Studio                                                              | See 6.2 — tool-calling reliability is the number that matters.                                                                                             |
| PC control     | Windows-MCP (MIT, 6k+ stars): Click/Type/Snapshot via Windows UI Automation — no vision model needed — plus app-launch, clipboard, file tools       | 0.2–0.5 s per action. Open Interpreter has pivoted away from this role; MCP servers replaced it. Microsoft's UFO² docs are excellent architecture reading. |
| Voice out      | Earcon WAVs for pings (~0 ms) + Kokoro-82M for narration (Apache 2.0, ~100–300 ms to first audio)                                                   | Piper is the lighter fallback; XTTS/F5 only if you want voice cloning.                                                                                     |
| Glue           | RealtimeSTT / RealtimeTTS / RealtimeVoiceChat (KoljaB) as reference code; Home Assistant's Wyoming protocol if you want satellite plumbing for free | RealtimeVoiceChat demonstrated ~500 ms voice-to-voice on a 4090-class GPU.                                                                                 |

### 6.2 Model choice and the tool-calling reliability problem

For a voice assistant that *acts*, the metric that matters is not benchmark IQ but the rate of well-formed tool calls, because errors compound: a model that is 95% reliable per step is only ~66% reliable across an 8-step task. Current (mid-2026) measurements put Gemma 4 26B-A4B and Qwen3-class ~27–32B models at ~93–96% well-formed-call rates, while sub-7B models drop to 70–80% — visibly flaky in daily use. Practical guidance: **do not go below ~8B for the control loop**, and gate anything destructive behind confirmation regardless of model size.

Your GPU situation is comfortable. The 5080's 16 GB fits a Q4-quantised ~12B model plus STT plus TTS with room to spare, or a 26–27B-class model tightly. Better: you have a spare 5070 Ti — a genuinely nice option is a **two-GPU split**, with the 5080 dedicated to the LLM and the 5070 Ti running Whisper + TTS (and later, a vision model for screen-reading), eliminating all contention.

> **The Gemma angle (your project folder is aptly named):** Gemma 4 (April 2026, Apache 2.0) ships audio-native variants — E2B, E4B and 12B accept raw audio input directly through llama-server. That means one model can replace the entire separate speech-recognition stage: headset audio goes straight into the LLM as an input_audio block, and it transcribes, reasons and calls tools in a single pass. Real-world caveats from early integrations: a 30-second clip limit, multi-second cold starts, and recognition that collapses on noisy audio (~41% word-error vs ~16% for Whisper on meeting recordings) — fine for a close-mic headset, so run this as the elegant 'Gemma-purist' variant, with faster-whisper kept as the noisy-input fallback.

### 6.3 What response speed to expect

| **Stage**                             | **On your 5080** | **Comment**                                    |
|---------------------------------------|------------------|------------------------------------------------|
| Wake word detection                   | \<100 ms         | Continuous, negligible                         |
| End-of-speech detection (VAD silence) | 200–400 ms       | The biggest fixed cost; tune Silero VAD        |
| Transcription of a short command      | 50–200 ms        | Streaming STT hides most of this during speech |
| LLM first token (12–27B Q4, resident) | 80–250 ms        | Keep the model loaded; cache the system prompt |
| Each Windows tool action              | +200–500 ms      | UI Automation speed, not model speed           |
| First TTS audio (streamed)            | \<150 ms         | Earcon instead: effectively 0 ms               |

Net effect: roughly **1–1.5 seconds** from finishing your sentence to hearing the start of a spoken answer, and command-plus-ping interactions that feel near-instant. The published reference points bracket this nicely: a production build on a 3060-class GPU reports 2–3 s; an aggressively pipelined 4090 build reached ~500 ms. Your hardware sits at the fast end.

## 7. Security, privacy and the law of an always-listening device

An always-listening microphone wired to a model that can execute actions on your PC is, by construction, the maximum attack surface a personal system can have. Three problems deserve design-level answers from day one rather than retrofits:

**Prompt injection remains unsolved.** Anything the assistant reads — a web page, a document, an email — can contain instructions that steer its tool calls, and the industry consensus (OWASP ranks it the \#1 agentic failure; OpenAI has said it may never be fully solved) is to design around it, not past it. For a personal build: strict tool allowlist (no raw PowerShell by default), a spoken or on-screen confirmation gate for anything destructive or financial, run the agent under a limited Windows account, and log every tool call.

**Acoustic injection is trivial.** Anyone audible — a colleague, a TV advert, a YouTube video — can speak your wake word and issue commands. Most local stacks do no speaker verification (Picovoice's Eagle is a local option if you want it). The cheap mitigations are physical: a **hardware mute switch that breaks the microphone line** (not a software mute), an LED that is hard-wired to streaming state, and wake-word gating so raw audio is never continuously shipped to the PC.

**UK law, briefly.** Recording a conversation you are party to, for personal use, is lawful without consent; sharing recordings with third parties requires consent; and intercepting conversations you are *not* party to is a criminal offence under the Investigatory Powers Act 2016. Any systematic processing of other people's voices brings UK GDPR duties. A wake-word-gated design that discards untriggered audio and stores no third-party recordings keeps a personal prototype comfortably on the right side of all of this. (The office context is stricter — Section 8.)

## 8. The path from your desk to a law firm

You flagged that hardware and software choices should anticipate a work environment where nobody buys a supercomputer per lawyer. The good news is that the architecture in Section 3 was chosen with exactly this in mind: the headset never changes; only the hub does. Two deployment shapes exist, with very different economics.

### 8.1 Per-desk: the NPU laptop reality check

Copilot+ laptops (Snapdragon X, Intel Lunar Lake, AMD Ryzen AI; 45–50 NPU TOPS) can genuinely run this workload — with caveats that matter. First, the popular tools (Ollama, LM Studio, llama.cpp) **ignore the NPU entirely** and run on CPU/iGPU; NPU inference requires Microsoft's Foundry Local, ONNX Runtime with vendor providers, AnythingLLM's Qualcomm build, or FastFlowLM on AMD. Second, TOPS is the wrong metric — decode speed is bound by memory bandwidth, so NPUs mainly buy battery life and thermals, not speed. The realistic per-desk envelope in 2026: a ~3–4B model at 15–30 tokens/s plus real-time Whisper (which runs beautifully on NPUs — AMD's runs base models 3× faster than real time). That is a competent dictation-and-drafting assistant, but below the ~8B tool-calling floor from Section 6.2 — per-desk NPU deployment suits transcription-heavy use, not agentic PC control, until on-device models improve a generation.

### 8.2 Shared: one inference server for the whole firm (the economically dominant option)

A single RTX 5090 workstation (~£5,500 built) running vLLM serves roughly 30 concurrent users on an 8B model, or 5–10 on a 30B-class model, with sub-second first tokens. A voice assistant only needs 10–20 tokens/s per user — faster than speech playback — so batch serving fits naturally. The per-seat arithmetic is decisive: ~**£220/seat one-off** for 25 lawyers on a shared box, versus ~£1,200+/seat for AI-spec laptops, versus ~£420/seat/year forever for the incumbent cloud dictation service (Philips SpeechLive with speech recognition). A 96 GB RTX PRO 6000 box (~£10,500 at current inflated prices) runs 70B-class models for the same crowd at ~£450–700/seat. All data stays inside the building.

### 8.3 The regulatory tailwind

Local inference is not just a hobbyist preference in legal practice; it is where the guidance points. The Law Society's generative-AI guidance (updated September 2025) says plainly not to feed confidential information into tools you do not control, to know where data is processed, and never to use real client data in testing. The SRA's compliance tips (updated February 2026) require confidentiality to be maintained across cloud/AI adoption, transparency where AI interfaces with clients, UK GDPR compliance, and COLP-level governance. The ABA's Formal Opinion 512 (2024) requires informed consent before putting confidential information into self-learning tools and serious vendor diligence. A fully local model collapses most of that diligence burden — nothing leaves the premises.

> **But the microphone, not the model, is the compliance problem.** The ICO treats continuous audio capture as high-risk and more intrusive than video: it demands a compelling purpose, a Data Protection Impact Assessment, notification of everyone in range, and aggressive data minimisation. In a law office an open mic will inevitably capture other clients' privileged conversations and colleagues' unrelated matters — an information-barrier breach regardless of where the model runs. The design answers are the same ones the prototype should have anyway: wake-word gating with discard-unless-triggered buffering, push-to-talk in client meetings, transcribe-and-delete with no raw audio retention, and a DPIA before any firm-wide use.

**The market gap, for what it's worth:** desktop Dragon has stagnated since the Microsoft acquisition and its growth products are cloud; SpeechLive is cloud-only; the new local-Whisper dictation tools (superwhisper, MacWhisper, and Windows equivalents) transcribe but do not *act*. A headset + wake word + local LLM that behaves as an assistant rather than a transcriber, on ordinary office hardware, does not currently exist as a product. You are not trying to build a company — but it is pleasant to know the tinkering points somewhere real.

## 9. Phased roadmap and budget

Each phase produces something that works on its own, and no phase strands the previous one's spend. Prices are approximate mid-2026 UK.

| **Phase**                  | **Content**                                                                                                                                                                                                                                                                      | **Cost**     | **You end up with**                                                                                               |
|----------------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------|--------------|-------------------------------------------------------------------------------------------------------------------|
| 0 — This week              | Shokz OpenComm2 UC (or any BC headset with a decent mic + USB dongle). Stand up the full PC pipeline: RealtimeSTT (wake word + VAD + faster-whisper) → Ollama/llama-server with Gemma 4 or Qwen → Windows-MCP with a 5-tool allowlist → earcons + Kokoro.                        | ~£160        | The complete product experience on stock hardware. Most of the learning, none of the soldering.                   |
| 1 — Teardown + wired build | One £25–40 generic BC donor (dissect it: glue, cell, transducers) + wired custom headset from bare parts (USB sound card, lav mic, PAM8302, Adafruit \#1674, headband).                                                                                                          | ~£75         | Teardown education; a full-bandwidth wired dev headset; salvaged transducers and band.                            |
| 2 — Wireless headset       | XIAO ESP32-S3 Sense + ICS-43434 + MAX98357A + transducer + 1200 mAh LiPo + charger, 3D-printed nape pod on the salvaged band; microWakeWord on-device; Wi-Fi PCM streaming; hardware mute + LED.                                                                                 | ~£60         | The actual device: always-listening, wake-word-gated, bone-conduction AI headset.                                 |
| 3 — Optional deepenings    | Pick any: Nordic nRF5340 Audio DK for true LE Audio (~£165) · Jetson Orin Nano Super as a PC-free belt hub (~£185) · Arduino Nicla Voice for µW wake word (~£37) · Knowles bone-conduction mic experiment (~£25) · spare 5070 Ti into a second box as a dedicated speech server. | £40–185 each | Whichever frontier interests you most: better radio, PC-free operation, multi-day battery, or noise-immune input. |

Core path total (Phases 0–2): **~£295 plus ~£40 of consumables** (wire, heatshrink, filament, spare parts) — comfortably inside budget, leaving £300+ for Phase 3 choices or a benchmark-quality intact Shokz.

## 10. Honest limitations and open risks

- **Bone conduction is a speech medium, not a hi-fi one.** Thin bass, placement-sensitive volume, and clamping pressure that takes iteration to get comfortable. Perfect for an assistant; disappointing for music. Keep expectations calibrated against an intact Shokz.

- **Tool-calling reliability is the ceiling on ambition.** ~95% per step means multi-step tasks fail visibly often. Start with few, idempotent, easily-undone tools and grow slowly.

- **HFP can silently fall back to 8 kHz** with some Bluetooth radios, quietly degrading recognition. Check the endpoint sample rate whenever v0 behaves oddly.

- **The v2 firmware cliff is real.** Nordic's LE Audio kit means Zephyr, dual-core builds and genuine embedded development. Treat it as its own hobby, entered willingly, or skip it — v1.5 is a fully satisfying endpoint.

- **ESP32 battery life will disappoint without gating.** Continuous Wi-Fi duplex streaming is 100–150 mA; wake-word gating with the radio asleep between utterances is the difference between 4 hours and a working day.

- **The social factor.** Even a legally clean always-listening device changes how people around you behave. The mute switch and LED are as much social instruments as security ones.

- **Prompt injection has no full fix.** The allowlist + confirmation-gate posture is not optional; it is the design.

## 11. Phase 0–2 shopping list

| **Item**                                                   | **Qty** | **Approx.** | **Where**                        |
|------------------------------------------------------------|---------|-------------|----------------------------------|
| Shokz OpenComm2 UC (v0 + benchmark)                        | 1       | £160        | Shokz UK / Amazon                |
| Generic bone-conduction headset (teardown donor)           | 1       | £30         | AliExpress / Amazon              |
| Adafruit \#1674 bone conductor transducer                  | 2       | £14         | Pimoroni / The Pi Hut / Digi-Key |
| Dayton Audio BCE-1 (comparison transducer)                 | 1       | £11         | SoundImports EU / Parts Express  |
| MAX98357A I2S amp breakout                                 | 2       | £9          | Pimoroni / AliExpress            |
| PAM8302 mono amp                                           | 1       | £3          | Pimoroni / AliExpress            |
| Seeed XIAO ESP32-S3 Sense                                  | 2       | £28         | Seeed / Mouser / Amazon          |
| ICS-43434 or INMP441 I2S microphone                        | 2       | £8          | AliExpress / Adafruit            |
| USB-C sound card (v1 wired build)                          | 1       | £10         | Sabrent / UGREEN                 |
| Lavalier electret microphone                               | 1       | £12         | Amazon                           |
| 1200 mAh LiPo + charger board + LiPo-safe bag              | 1 set   | £20         | Pimoroni / Amazon                |
| Slide switch (hardware mute), LED, wire, heatshrink, Sugru | —       | £15         | Anywhere                         |
| Plastic spudger set + fine knife (teardown)                | 1       | £8          | iFixit / Amazon                  |

Everything on the software side — openWakeWord, faster-whisper, Gemma 4, Qwen, Ollama, llama.cpp, Windows-MCP, Kokoro, Piper, RealtimeSTT/TTS, ESPHome/Wyoming, Omi firmware — is free and open source.

## 12. Key sources

A selection of the primary sources behind this study; each section's claims trace to these.

### Teardowns and bone-conduction hardware

- iFixit — AfterShokz OpenRun teardown: ifixit.com/Teardown/Aftershoks+OpenRun+Teardown/182927

- iFixit — Trekz Titanium teardown: ifixit.com/Teardown/Aftershokz+Trekz+Titanium+Teardown/144329

- Adafruit bone conductor \#1674: adafruit.com/product/1674 · Dayton BCE-1: daytonaudio.com/product/1170

- Hackaday DIY bone-conduction glasses: hackaday.io/project/164895 · Honeycutt build: wesleythoneycutt.com/posts/diy-bone-conduction-headphones

- Omi open AI wearable: github.com/BasedHardware/omi · OpenGlass: github.com/BasedHardware/OpenGlass

### On-headset compute and analog chips

- EnCharge EN100 announcement: businesswire.com (29 May 2025) · EE Times analysis: eetimes.com/encharge-picks-the-pc-for-its-first-analog-ai-chip

- Mythic M1076: mythic.ai/products · rescue coverage: eenewseurope.com · IBM NorthPole LLM results: research.ibm.com/blog/northpole-llm-inference-results

- Aspinity AML100: aspinity.com/aml100 · Syntiant NDP120 / Arduino Nicla Voice: store.arduino.cc · ESP-SR: github.com/espressif/esp-sr

- Hailo-10H GA: hailo.ai · Jetson Orin Nano Super: developer.nvidia.com · Pi 5 LLM benchmarks: stratosphereips.org · Gemma 3n: developers.googleblog.com

- Smart-glasses thermal model: mdpi.com/1424-8220/20/5/1446 · Humane/Rabbit teardown verdicts: ifixit.com/News/95474

### Voice stack and PC control

- openWakeWord: github.com/dscripka/openWakeWord · RealtimeSTT/RealtimeVoiceChat: github.com/KoljaB

- Windows-MCP: github.com/CursorTouch/Windows-MCP · Microsoft UFO: github.com/microsoft/UFO

- Gemma 4 audio via llama-server (integration report): dev.to/mdemin729 · Unsloth Gemma 4 docs: unsloth.ai/docs/models/gemma-4

- Tool-calling reliability benchmark: promptquorum.com · BFCL leaderboard: gorilla.cs.berkeley.edu/leaderboard.html

- Kokoro-82M: huggingface.co/hexgrad/Kokoro-82M · Piper: github.com/OHF-Voice/piper1-gpl · HA Wyoming: home-assistant.io/integrations/wyoming

### Audio link

- Windows Bluetooth Classic audio (HFP rates): learn.microsoft.com · Whisper 16 kHz native: github.com/openai/whisper/discussions/870

- Windows 11 LE Audio / super wideband: windowsforum.com, techpowerup.com · Creative BT-W6: us.creative.com

- nRF5340 Audio DK: nordicsemi.com · wyoming-satellite: github.com/rhasspy/wyoming-satellite · I2S mic comparison: atomic14.com

### Office deployment, law and regulation

- Law Society, Generative AI — the essentials (Sept 2025): lawsociety.org.uk · SRA compliance tips (Feb 2026): sra.org.uk

- ABA Formal Opinion 512: americanbar.org · ICO/audio recording analysis: legalvision.co.uk, iapp.org

- RTX 5090 concurrency: gigagpu.com · SMB local-LLM serving benchmark: arxiv.org/2512.23029 · AI PC / NPU guide: digitalapplied.com

- Whisper on Ryzen AI NPUs: amd.com developer articles · FastFlowLM: fastflowlm.com · Foundry Local: learn.microsoft.com

- UK recording law: recordinglaw.com/uk-recording-laws · OWASP prompt-injection ranking: helpnetsecurity.com (June 2026)
