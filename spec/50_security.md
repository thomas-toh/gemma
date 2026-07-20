# Spec 50 — Security & privacy posture

**Status: BINDING (design constants, not preferences)** · Last reconciled: 2026-07-10 · Rationale: docs/01 §7, docs/02 §7

1. **Tool containment is the defence, not model cleverness.** Assume everything a brain
   reads (web, files, screen contents) is hostile (prompt injection is unsolved).
   Registry allowlist + tiers + Tier 3 spoken confirmation per spec/30.
2. **Audit everything.** Every tool invocation logged per spec/30 rule 2.
3. **No raw audio at rest.** Untriggered audio lives only in a ≤ 3 s RAM ring buffer and
   is discarded. Triggered-session audio is processed in memory; never written to disk.
   Transcripts are logged locally and are user-purgeable in one action.
4. **Truthful signalling.** The overlay's listening indicator must reflect actual pipeline
   state; `listening` ⇔ audio is being captured/processed. No dark listening, ever.
5. **Mute is software (desk product).** With commodity audio gear there is no hardware mute
   line; the tray exposes a software mute that stops capture — honestly weaker than the
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
