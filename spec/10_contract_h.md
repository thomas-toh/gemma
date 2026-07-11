# Spec 10 — Contract H: headset ↔ bridge

**Status: DESIGNED (no code)** · Last reconciled: 2026-07-11 · Message shapes: [schemas/messages.schema.json](schemas/messages.schema.json) (v0.2.0)

The headset is audio I/O plus wake detection and nothing else. Every physical device
generation implements this same contract via a transport adapter; nothing above the
adapter may know which transport is live.

## 1. Messages — headset → bridge

| Message | Payload | Rules |
|---------|---------|-------|
| `HELLO` | `device`, `fw_version`, `protocol_version`, `capabilities` | MUST be the first message after connect (H2+). Capabilities (wake_on_device, has_button, has_led, reports_battery, earcons_cached) let the bridge adapt per device. |
| `WAKE` | `ts`, `confidence` | Only from devices with `wake_on_device`. In H0/H1 the bridge synthesises WAKE from its own PC-side detector. |
| `AUDIO` | binary frames | 16 kHz, 16-bit signed LE, mono PCM, 20 ms frames (640 bytes). MUST be contiguous while streaming is on. |
| `MUTE` | `on: bool` | Informational — the hardware switch physically cuts the mic regardless (spec/50 rule 5). |
| `BUTTON` | `action`: single · double · hold_start · hold_end | Default bindings (spec/40): single = stop/dismiss, double = repeat last answer, hold = push-to-talk. |
| `STATUS` | `battery_pct`, `rssi` | `reports_battery` devices, every 30 s. |
| `ERROR` | `code`, `detail?` | Device-side faults: audio_underrun/overrun, mic_fault, battery_critical, internal. |

## 2. Messages — bridge → headset

| Message | Payload | Rules |
|---------|---------|-------|
| `HELLO_ACK` | `protocol_version` | Handshake reply; confirms the version the bridge will speak. |
| `STREAM` | `on: bool` | Mic streaming gate. Device starts streaming on WAKE / `hold_start`; bridge MUST send `{on:false}` at session end so the radio can sleep — this is the battery-life mechanism. |
| `AUDIO_OUT` | binary frames | 24 kHz 16-bit mono PCM, streamed (TTS). |
| `EARCON` | `id` (from [schemas/earcons.json](schemas/earcons.json)) | Device MAY hold local WAVs (declared in `earcons_cached`); MUST fall back to AUDIO_OUT if id unknown. |
| `LED` | `state`: idle·listening·thinking·speaking·error | MUST truthfully reflect pipeline state (spec/50 rule 4). |
| `VOLUME` | `level`: 0–100 | |

Control channel = JSON per schema; audio = raw binary on the transport's data path.

## 3. Transport profiles

| Profile | Device | Control path | Audio path | Status |
|---------|--------|--------------|------------|--------|
| **H0** | Stock BT headset + dongle | none (bridge-internal synthesis) | OS audio endpoints (WASAPI), HFP 16 kHz | DESIGNED — first to build (M0) |
| **H1** | Wired custom build | none / serial GPIO | USB sound card, 48 kHz | DESIGNED |
| **H2** | ESP32-S3 build | WebSocket JSON over Wi-Fi | binary WS frames (UDP fallback if latency demands) | DESIGNED — Doc 03 |
| **H3** | nRF52840 BLE (Omi-style) | BLE GATT | Opus over GATT notifications | sketch only |
| **H4** | LE Audio (nRF5340) | LE Audio | LC3 isochronous | sketch only |

**H0 semantics (normative for M0):** bridge opens the headset's Windows endpoints
directly; runs wake detection on the continuous mic stream; buffers ≤ 3 s of audio in
RAM and discards untriggered audio (spec/50 rule 3). Verify the HFP endpoint reports
16,000 Hz — 8 kHz fallback degrades STT and must be surfaced as a warning at startup.
In H0/H1 the bridge synthesises HELLO internally (a virtual device with no
capabilities) so the orchestrator sees one uniform world.

## 4. Protocol rules (how the contract stays evolvable)

1. **HELLO first.** No other control message before the handshake (H2+).
2. **Version negotiation.** Device states its `protocol_version`; bridge replies with the
   version it will speak (its own, or the device's if lower). Breaking schema changes bump
   the minor version pre-1.0.
3. **Ignore unknown types.** A receiver MUST ignore (and log once) any message type it
   does not recognise — never crash, never disconnect. This is what lets old firmware
   survive newer bridges.
4. **Strict shapes.** Known messages are validated against the schema
   (`additionalProperties: false`); malformed known messages are dropped and logged.

## 5. Considered and excluded (decisions, not oversights)

| Candidate | Why excluded |
|-----------|--------------|
| Heartbeat / PING | The transport layer already provides it (WebSocket ping/pong, BLE connection events). Duplicating it in the app protocol adds noise. |
| OTA firmware update messages | Prototype flashes over USB. OTA is a solved-elsewhere problem (ESP32 OTA libs) to adopt wholesale later if wanted — not app-protocol surface now. |
| Config push (wake sensitivity, mic gain) | Premature: no evidence yet which knobs need remote setting. Revisit after M3 field use; HELLO capabilities make adding it non-breaking. |
| Earcon asset push (bridge uploads WAVs to device cache) | Nice-to-have; prototype ships earcons in firmware. The `earcons_cached` capability already reserves the negotiation hook. |
| Text/transcript display messages | No screen on any planned build. |
