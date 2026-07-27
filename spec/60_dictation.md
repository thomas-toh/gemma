# Spec 60 — Dictation

**Last reconciled: 2026-07-27** · Build progress: [STATE.md](../STATE.md), Track D · Rationale:
docs/01_scoping/Reviews/2026-07-18_1643 (VoiceInk study), spec/00 D12 · D15 · D20.

Dictation is the second door (D20): a global hotkey (`ctrl+alt+2` by default) that turns speech
into text **in whatever application has focus**, with no answer and no conversation. It reuses the
capture stack the assistant already stands on — the doors (spec/40, `bridge/hotkeys.py`), the
VAD/STT pipeline (`bridge/audio/listen.py`), and the orchestrator's one event loop — and adds only
two things of its own: the `transform` cleanup verb (Contract B, spec/20) and delivery to the caret.

**Trigger is the mode (D12).** The wake word / ask key is the assistant; the dictate key is
dictation. There is no spoken command to switch — the key you press *is* the choice. Both keys are
hybrid (spec/40): tap to toggle, hold ≥ 0.5 s for push-to-talk. **The key is the endpoint** — a
keyed capture ends on the second tap or the release, not on the 1 s VAD silence cut, so you can
pause mid-thought (`capture_over`, spec/40; `--auto-end` restores the silence cut for one-tap use).

## The pipeline (D1, built)

```
dictate key ─▶ capture (VAD, key endpoint) ─▶ STT ─▶ [word-replacement] ─▶ transform cleanup ─▶ paste at caret
```

1. **Capture.** Identical to the assistant's — `_capture()` in the orchestrator, which publishes
   `listening` (the truthful mic indicator, spec/50 rule 4) and the live bars. The dictate door
   owns the endpoint.
2. **STT.** `transcribe()` (`bridge/audio/listen.py`), the same engine as the assistant path.
   *(Per-mode STT model — dictation is the stricter quality test, D12 — is deferred: the model is
   one process-wide constant today.)*
3. **Word-replacement (D15) — deferred.** A deterministic, user-curated find-and-replace table for
   known STT mishearings (names, jargon) runs before cleanup. The table is a `spec/schemas/` file
   that does not exist yet, so this step is a no-op until it lands; `bridge/config.py` already globs
   new schemas in, so adding it later is a JSON drop with no plumbing.
4. **Cleanup — `transform`, "transform, never answer" (D12/D15/S-06).** The raw transcript is
   rewritten by the `transform` verb (spec/20): fix transcription errors, drop filler and
   duplicated words, restore punctuation and capitalisation — **never** answer, summarise or
   translate. The engine is **Groq** by default (cloud, fast, cheap; key at `("gemma","groq")`),
   chosen per the D15/S-06 per-role cleanup decision. Cleanup is an **enhancement, not a gate**: if
   it is unavailable (no key, offline, error) the **raw transcript is delivered instead**, so
   dictation works with no cleanup key — and in that case nothing leaves the machine.
5. **Delivery — clipboard + synthetic Ctrl+V (D12).** Deterministic and user-initiated, **never a
   Contract-T tool**, and the model never chooses to paste (spec/50). Issued by the **daemon**, not
   the overlay: a paste lands where keyboard focus is, and the overlay is never focusable (spec/40).
   The previous clipboard **text** is restored afterwards (best-effort; non-text clipboard content
   is not preserved — see `bridge/paste.py`). Windows only for now; macOS is a D10 seam.

Where it lives: the dictation turn is `Orchestrator._dictate()` (a turn *type*, not a separate
subsystem — it shares the capture machine, STT, doors and event loop with the assistant); delivery
is `bridge/paste.py`. There is no `bridge/dictation/` package, deliberately — it would duplicate the
capture stack.

## Privacy (spec/50)

The transcript stays in RAM until delivery; raw audio is never written to disk (rule 3). The
clipboard is the delivery mechanism, not a log. The one exposure is the S-06 decision that the
**cleanup engine is cloud Groq by default** — the transcript is sent there to be cleaned. A user
who wants dictation fully local points the cleanup role at a local provider (spec/70, once the
cleanup-role config is built) or leaves the Groq key unset, in which case the raw transcript is
pasted and nothing leaves the machine.

## Overlay states

Recording reuses the assistant's feed (`spec/schemas/status.json`): `listening` (capture + bars)
covers it. After the capture closes, dictation runs **its own three states** (D2), distinct from the
assistant's: `transcribing` (STT), `transforming` (cleanup), `pasted` (the cleaned text has reached
the caret). Because dictation pastes into another app and shows no reply, the island is a **pure
status indicator** here — `transcribing`/`transforming` show a steady status word ("Transcribing…" /
"Tidying…"), and `pasted` is a brief "Pasted ✓" confirmation the overlay dwells on
(`Theme.durationPasteDwell`) then hides itself. No text body is shown; the transcript goes to the
caret, not the island, and is not broadcast, so it never joins the assistant's prompt history. These
states add to the overlay, not to this pipeline. Build progress: [STATE.md](../STATE.md).

## Deferred

- **Word-replacement table (D15)** — schema + wiring (step 3 above).
- **Per-mode STT model (D12)** — dictation may want a higher-quality model than the voice loop;
  measure `large-v3-turbo` vs `small.en` vs Parakeet before choosing.
- **Rewrite (D17/D20) — an ask-door outcome, not a mode.** Select text, invoke, speak an
  *instruction*; the selection is replaced via `transform` with the rewrite-ladder contract, pasted
  over the selection (propose-then-tap; `auto_apply` off by default, spec/70). Slice **D3**.
- **Cleanup-role config (spec/70)** — engine, model and the cleanup instruction are code constants
  (`orchestrator.CLEANUP_PROVIDER` / `CLEANUP_MODEL` / `DICTATION_CLEANUP`) until the settings
  surface exposes them; `cleanup_dictation` is declared in `settings.json` but `built:false`.
- **Streaming partials · per-app modes · voice-switch into dictation** — design-time deferrals (D12).
