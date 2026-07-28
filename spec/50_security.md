# Spec 50 — Security & privacy posture

**Status: BINDING (design constants, not preferences)** · Last reconciled: 2026-07-28 · Rationale: docs/01 §7, docs/02 §7

1. **Tool containment is the defence, not model cleverness.** Assume everything a brain
   reads (web, files, screen contents) is hostile (prompt injection is unsolved).
   Registry allowlist + tiers + Tier 3 spoken confirmation per spec/30.
2. **Audit everything.** Every tool invocation logged per spec/30 rule 2.
3. **No raw audio at rest.** Untriggered audio lives only in a ≤ 3 s RAM ring buffer and
   is discarded. Triggered-session audio is processed in memory; the daemon never writes it to
   disk. That is enforceable by inspection: `bridge/`'s only audio file handle is the *read* of
   a pre-rendered earcon (`audio/speak.py`), and nothing in the package may acquire a write path
   for audio.
   Transcripts are logged locally and are user-purgeable in one action — they reach
   `logs/gemma.log` (rotating, gitignored) via the daemon's turn events, so deleting the
   `logs/` folder is that one action. **User-initiated export is allowed (D27):** a person may
   Copy or Save an on-screen answer to a file they pick — that text is already in `logs/gemma.log`,
   so exporting a copy is strictly less exposure than the existing log. The system never exports on
   its own; only a keypress or click does, and no answer is written to disk unbidden.
   **The replay harness is the only writer of audio, and only when asked** (Track G step 7):
   `python -m tests.replay --record <case>` captures a fixture WAV to `tests/replay/wav/` so a
   real utterance can be replayed through the real pipeline. It sits outside `bridge/` — no
   product path reaches it — it prompts before it records, and the directory is gitignored so
   fixtures stay on the machine that made them. A recording tool the operator invokes is a
   different thing from a system that retains audio; this rule governs the second.
4. **Truthful signalling.** The overlay's listening indicator must reflect actual pipeline
   state; `listening` ⇔ audio is being captured/processed. No dark listening, ever.
5. **Mute is software (desk product).** With commodity audio gear there is no hardware mute
   line; the tray exposes a software mute that stops capture *(planned — not in either tray
   yet; spec/70 lists it)* — honestly weaker than the
   excised headset's physical switch (spec/00 D18), and truthfully reflected by rule 4.
6. **`local_only` flag.** Per-session; forces B2, refuses B1/B3 with a spoken error if
   unavailable. Invoked by config or the "private mode" utterance. This is the
   privileged-content switch.
7. **Acoustic injection accepted as residual risk** for the personal prototype (anyone
   audible can wake it). Mitigations available if needed later: speaker verification
   (e.g. Picovoice Eagle), push-to-talk mode. Tier gates bound the blast radius.
8. **Least privilege later:** bridge runs under the normal user account until Tier 3
   tools exist; then move to a limited Windows account.
9. **No telemetry.** Nothing leaves the machine except brain API calls (B1/B3) — and
   those only when `local_only` is off.
10. **Secrets live in the OS credential store** (decided 2026-07-10): API keys go in
    Windows Credential Manager / macOS Keychain under service `gemma`, read via the
    `keyring` library and passed to SDKs explicitly. Never `setx`/persistent env vars
    (inherited by every process, plaintext in the registry), never files in the repo.
    A session-scoped env var is an accepted fallback (CI, one-off shells). Every key
    is dedicated to this project and carries a monthly spend cap set in the provider
    console — the cap, not the hiding place, bounds the blast radius.
11. **No keystroke stream** (decided 2026-07-22). The two doors (spec/40) register their
    combos with the OS (Win32 `RegisterHotKey`), which delivers *only* those combos and
    consumes them. The obvious alternative — a system-wide low-level keyboard hook, what
    `pynput` and friends install — would put every keystroke on the machine through
    Gemma's process, which is the same posture problem as rule 3 in a different medium.
    Key *state* may be queried for the key we registered (release detection); nothing
    else is observed. The macOS peer, when built, uses Carbon `RegisterEventHotKey` for
    the same reason. Since D24 the **Teleprompter** registers bare `Esc` under this same rule,
    and only while the island is on screen.
12. **The upstream channel cancels, never commands** (decided 2026-07-22, D24). Contract P was
    strictly one-way until the overlay had to own dismissal. It may now send the daemon
    **exactly one** message, `dismiss`, allowlisted from `spec/schemas/status.json` and
    rejected by name if anything else arrives. The invariant, not the message count, is what
    makes this acceptable: an upstream message may only **stop work already in flight** — drop
    a capture, cut TTS, cancel an in-flight brain call. It may never start a turn, invoke a
    tool, alter a setting, or put words on the screen. Any future upstream verb must satisfy
    the same test or it does not belong on this channel. Threat note: the socket is
    localhost-only but unauthenticated, so any local process can send `dismiss` — a nuisance,
    bounded by the invariant, and strictly smaller than the exposure already accepted, which is
    that the same process can *read* every prompt and reply on the feed.
