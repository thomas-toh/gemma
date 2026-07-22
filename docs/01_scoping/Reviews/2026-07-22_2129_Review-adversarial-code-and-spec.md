# Review: adversarial code & spec audit — bridge/, teleprompter/, spec/*, D10–D23

> **Execution status lives in [STATE.md](../../../STATE.md), not here** — this file is a frozen
> point-in-time record (hard rule 2), and STATE is the sole record of progress (hard rule 1).
> As of 2026-07-22, **D24** (spec/00) discharged G-01, G-02, G-04 and S-01 by removing the code
> they lived in; G-08 was adjudicated *keep as-is*. The rest are being worked in severity order.

*Prepared 2026-07-22 21:29. Scope: working tree of branch `teleprompter` as-is (uncommitted at review time: `spec/00_overview.md`, `spec/40_interaction.md`, `teleprompter/Overlay.qml`, `teleprompter/__main__.py`). Pass 1: adversarial code review of `bridge/` and `teleprompter/` (bugs, threading hazards, jank). Pass 2: spec audit — `spec/*` + `CLAUDE.md` + `STATE.md` — contradictions, code-vs-spec drift, headset-era residue, and a pairwise check of the D10–D23 decision tail. Items are numbered for line-item execution; each ends with one question to adjudicate. Hotkey-module findings are filed under G (bridge-side input).*

*Frozen `docs/` were read for orientation only and are not audited (hard rule 2).*

---

## Summary index

| ID | Severity | Title |
|----|----------|-------|
| G-01 | **High** | Esc is armed but dead for the entire answer dwell — and consumed system-wide |
| G-02 | **High** | "Nothing heard" leaves Contract P stuck in `listening` (spec/50 rule 4 breach) + ghost dwell from stale `self.shown` |
| G-03 | Medium | `_working_ping` timer thread can sound the earcon *after* a dismiss cut |
| G-04 | Medium | `Hotkeys.arm()` vs `_pump`: unsynchronised shared state + the hotkey id derived in two places |
| G-05 | Low | Hold-PTT blocks the message pump — Esc and arm/disarm queue until release |
| G-06 | Low | `Door.close()` can wipe a press landing in the close window |
| G-07 | Low | Stale constant comment: `NOSPEECH_CHUNKS` "93 (~3 s)" is actually 156 (~5 s) |
| G-08 | Low | Keyed turn still gives up 5 s before the first word — tension with "the key owns the endpoint" |
| P-01 | Medium | The port lives in three places and the env override splits daemon and overlay silently |
| P-02 | Medium | No snapshot on connect: a (re)connecting overlay renders nothing mid-turn |
| P-03 | Low | `Decoder` buffer never reset across reconnects — first line of a new session can be eaten |
| P-04 | Low | `_send` holds the client lock through a blocking `sendall`; bind-failure leaks the socket |
| U-01 | Low | Reduced-motion is sampled once at startup and never again |
| U-02 | Low | `fadeTop` is a dead knob (always 0) threaded through four expressions |
| B-01 | **High** | A fresh `AsyncAnthropic` client (new TCP+TLS) is built for every turn — the likely source of the unexplained 4.6–6.0 s first-word outliers |
| B-02 | Low | `_classify_badrequest` substring match over-classifies 400s as "context" |
| S-01 | **High** | `status.json` descriptions teach the *reverted* behaviour (follow-up window; `listening` clears the reply) |
| S-02 | **High** | Tier-3 "spoken confirmation" cannot execute in the D23 default product — headset/voice-era residue in a BINDING rule |
| S-03 | Medium | "read it" is retired in STATE but alive in spec/40 narration and `earcons.json`; "survives across wakes" is now incoherent |
| S-04 | Medium | D20 / spec/40 §Triggers still say answers "speak (D16)" — unamended by D23 |
| S-05 | Medium | spec/40 §Visual output opens with the pre-lock design (dot · spinner · status icons) it contradicts two bullets later; header carries build status |
| S-06 | Medium | D15 mandates a *local* cleanup model; the recorded decision is Groq (cloud) — never reconciled |
| S-07 | Medium | Headset-era naming: `pyproject` still says "headset <-> LLM brains"; CLAUDE.md says "always-listening"; the name "bridge" itself |
| S-08 | Low | Residue sweep: eight smaller stale references (list inside) |
| S-09 | Low | CLAUDE.md repo map omits `teleprompter/`, `tests/`, `scripts/` |
| X-01 | Medium | `checks.yml`'s PySide6 comment is now false — CI installs Qt but never runs `overlay_check` |

D-tail verification (D10–D23, pairwise): the amendment chains D11→D16→D23 and D14→D22/D23 are annotated correctly in place. The contradictions found are S-02, S-03, S-04, S-06 (all "a later decision changed this and one restatement was never told" — the same one-fact-two-places shape STATE names for the code). No numbering defects; the missing M3 is D18's doing but the milestone table doesn't say so (S-08).

---

## Pass 1 — code

### G-01 · Esc is armed but dead for the entire answer dwell — and consumed system-wide

**Severity:** High
**Location:** `bridge/orchestrator.py:527-545` (the IDLE/dwell loop), `bridge/orchestrator.py:250-259` (`_publish_state` arming), `bridge/orchestrator.py:344` (stale-press drop)

**Description.** `_publish_state` arms the transient Esc door whenever state ≠ `idle` — which includes the whole answer dwell (state stays `speaking`, or `thinking` for a held answer, until `blank_at` fires; 8 s to ~90 s). But `serve()`'s IDLE loop — the code actually running during the dwell — never polls `self._dismissed()`; the only dismiss checks live inside `_capture_loop`, `_drive` and `_speak`, all inside the `try`. So during exactly the window STATE calls "dismissal is the intended exit," pressing Esc does nothing: the flag sits set, is dropped as "a stale press from a past turn" when the next capture opens, and — because the door is *armed* — the OS delivers and consumes every Esc press, so Esc is also broken in every other app for the duration. A second-order problem: arming keys off *daemon* state, not off the island actually rendering — if the overlay process is dead or disconnected, Esc is still swallowed while nothing at all is on screen (interacts with P-02).

**Evidence.**
```python
while True:
    # IDLE: wake watch
    block, _ = mic.read(BLOCK_SAMPLES)
    ...
    if blank_at is not None and time.perf_counter() >= blank_at:
        blank_at = None
        self._ev("idle", show="[idle]")
    door = self._pressed()               # ← polls ask/dictate, never dismiss
```
and at capture open: `self._dismissed()  # drop a stale press from a past turn`.

**Options.**
1. *(Root cause)* Make the dwell a first-class waiting state like the others: extract the dismiss check into the IDLE loop (`if blank_at is not None and self._dismissed(): blank_at = None; …handle as dismissed…`), routed through the same `_ev("dismissed")` path so the trace, the earcon-free blank and the door reset behave identically to a mid-turn Esc. One dismiss semantics, every waiting state.
2. Narrow the arming: `hk.arm("dismiss", …)` only for states where the flag is actually polled (listening/thinking/speaking), so during the dwell Esc is at least handed back to the system. Fixes the swallowing, not the dead key — the answer then can't be Esc-dismissed at all, contradicting STATE's direction.
3. Fold into the already-decided option ③ refactor (overlay owns the blank/reveal state): the daemon still owns Esc registration, but a dwell-dismiss becomes "publish idle now" — smallest delta once that refactor lands, but leaves the bug live until then.

**Recommendation.** Option 1 now (it is ~5 lines and makes STATE's "Esc built but unverified live" actually true), noting that option 3's refactor later subsumes the blank half but not the arming half.

**Question.** Fix now via option 1, or park until the option-③ dwell refactor? (A: now / B: park)

---

### G-02 · "Nothing heard" leaves Contract P stuck in `listening` + ghost dwell from stale `self.shown`

**Severity:** High
**Location:** `bridge/orchestrator.py:548-551, 566-568` (serve), `bridge/orchestrator.py:232` (`_EVENT_STATE`)

**Description.** When a capture ends with no speech, `_capture` returns `None` and serve emits `_ev("nothing-heard")` — which maps to no Contract P state. The last published state remains `listening` (from `_capture`), with the mic now closed. That is a direct breach of spec/50 rule 4 ("`listening` ⇔ audio is being captured", BINDING): the island shows the compact listening pill (bars at zero via the feed watchdog) while nothing is listening. Worse, serve still sets `blank_at = now + answer_dwell(self.shown)` — and `self.shown` is only assigned inside `_turn`, so on this path it still holds the *previous* turn's answer. After a 200-word answer followed by an accidental tap-and-silence, the ghost listening pill sits on screen (and Esc is armed-but-dead, G-01) for ~90 seconds. Same stale-`shown` problem on any chain ending in a silent keyed/barge capture. This is precisely the duplicated-state class STATE's refactor brief names: `self.shown` is the daemon guessing what the island displays, and here the guess is wrong.

**Evidence.**
```python
utt = self._capture(...)          # published "listening"; returned None
...
if utt is None:
    self._ev("nothing-heard", show="[nothing heard]")   # no state change
...
blank_at = time.perf_counter() + answer_dwell(self.shown)  # stale shown
```

**Options.**
1. *(Minimal)* On the `utt is None` path: publish `idle` immediately (`self._ev("idle")`) and skip the dwell (`blank_at = None`); also set `self.shown = ""` whenever a chain ends without a new answer.
2. *(Root cause)* Kill `self.shown` entirely: the dwell length is a fact about what the island is revealing, which only the overlay knows — the decided option ③ (overlay owns the blank) removes both the stale-shown and the wrong-state bug in one move, with a Contract P change.
3. Add a distinct `state: "idle"`-with-reason or a `nothing_heard` message so the island can show a brief "didn't catch that" affordance before hiding — a UX improvement, but a schema addition for a case option 1 handles adequately.

**Recommendation.** Option 1 now (rule 4 is BINDING; this is a two-line breach), with option 2 as the standing destination already chosen in STATE.

**Question.** Should "nothing heard" blank the island instantly (option 1), or show a brief cue first (option 3's schema addition)? (A: instant / B: brief cue)

---

### G-03 · `_working_ping` can sound the earcon after a dismiss cut

**Severity:** Medium
**Location:** `bridge/orchestrator.py:289-294` (`_working_ping`), `bridge/orchestrator.py:556-559` (Dismissed handler)

**Description.** The working earcon runs on a `threading.Timer` thread. The Dismissed handler does `self.working.cancel()` then `pump.cut()` — but `cancel()` is a no-op if the timer callback has already started. Interleaving: timer fires at 1.4 s; user's Esc lands the same instant; handler cancels (too late), cuts the pump; timer thread then executes `self.pump.play(tone_samples("working"))` — enqueuing a "thinking" earcon *after* the turn was dismissed, plus a `working` trace/broadcast event stamped into a turn that no longer exists. Same shape at normal turn end via `_mark_audible` (acknowledged as benign for the double-log; the post-cut earcon is not benign — it is audible). The deeper issue is that a turn-scoped deadline is implemented as a free-running OS thread with no turn identity.

**Evidence.**
```python
def _working_ping(self) -> None:
    # Timer thread — pump.play is thread-safe. ...
    self.pump.play(tone_samples("working"))
```

**Options.**
1. *(Root cause)* Remove the Timer: the deadline is state, not a thread. Give the turn a generation counter (`self.turn_id += 1` at `_turn` entry and on dismiss) and check it in the ping; or better, fold the working-deadline into the single-threaded flow once the long-lived async loop lands (B-01's refactor) — `asyncio.call_later` on the owning loop cancels deterministically.
2. Keep the Timer but make dismissal safe: a `threading.Event` (`turn_dead`) set before `pump.cut()`, checked first thing in `_working_ping`. Small, honest, still leaves a thread whose only job is to be raced.

**Recommendation.** Option 2 now (three lines), with the Timer's removal folded into the B-01 loop refactor rather than done standalone.

**Question.** OK to fold the proper fix into the async-loop refactor and take the small guard now? (yes/no)

---

### G-04 · `Hotkeys.arm()` vs `_pump`: unsynchronised shared state, and the hotkey id derived twice

**Severity:** Medium
**Location:** `bridge/hotkeys.py:187-201` (`arm`), `bridge/hotkeys.py:210-233` (`_pump`)

**Description.** `self._armed` is mutated by non-atomic read-modify-write from two threads: the orchestrator thread in `arm()` (`self._armed = self._armed | {name}`) and the pump thread on registration failure (`self._armed -= {door.name}`). A lost update leaves `_armed` believing Esc is armed when registration failed (subsequent `arm(True)` calls short-circuit on `(name in self._armed) == on`, so it never retries) — Esc presses silently vanish for the session. Separately, `arm()` computes the Win32 hotkey id as `list(self.doors).index(name) + 1` while `_pump` builds `by_id` from `enumerate(self.doors.values(), start=1)` — the same fact derived independently in two places, exactly the seam-duplication class STATE's refactor brief targets; any reordering of `self.doors` between them desynchronises silently.

**Evidence.**
```python
self._armed = self._armed | {name} if on else self._armed - {name}
ctypes.windll.user32.PostThreadMessageW(
    self._tid, _WM_ARM, list(self.doors).index(name) + 1, int(on))
```

**Options.**
1. *(Root cause)* Single-owner: `_armed` and the id map live on the pump thread only. `arm()` posts the *name* (or a pre-assigned id stored on the Door at construction); the pump updates `_armed` when it actually (un)registers. `arm()` keeps a cheap desired-state set solely for its idempotence check, or drops the check (posting is cheap; the pump can dedupe).
2. A `threading.Lock` around every `_armed` touch, ids left as-is. Fixes the race, keeps the duplicated derivation.

**Recommendation.** Option 1 — assign each Door its id at construction (one fact, one place) and let the pump own `_armed`.

**Question.** Agree the id belongs on the `Door` object? (yes/no)

---

### G-05 · Hold-PTT blocks the message pump — Esc and arm/disarm queue until release

**Severity:** Low
**Location:** `bridge/hotkeys.py:155-163` (`_fire` hold loop)

**Description.** `_fire` runs on the pump thread and busy-polls key release for the whole of a hold. The ponytail note acknowledges "the other door is deaf" — but the pump is also deaf to `_WM_ARM` (Esc arming/disarming lags a hold by its full duration) and to Esc's own `WM_HOTKEY`. Pressing Esc while holding the ask key does nothing until release. Arguably academic (you are holding a capture you control), but it means dismiss semantics differ by entrance, and a third transient door would inherit the deafness.

**Options.**
1. *(Root cause)* Move the release-watch off the pump thread: `_fire` records press-time and spawns nothing; a tiny watcher (the existing per-door state machine, driven by a 25 ms timer thread or folded into the orchestrator's poll) detects release via `GetAsyncKeyState`. Pump returns to `GetMessageW` immediately.
2. Extend the ponytail note to name the Esc/arm deafness explicitly and accept it until a third door lands (the note's own revisit condition).

**Recommendation.** Option 2 — the cost is real but bounded and the revisit trigger is already written down; just make the note honest.

**Question.** Accept-and-document (A) or fix now (B)?

---

### G-06 · `Door.close()` can wipe a press landing in the close window

**Severity:** Low
**Location:** `bridge/hotkeys.py:114-126` (`close`), `bridge/orchestrator.py:347-351` (`_capture` finally)

**Description.** `close()` clears `start` and `end` unconditionally from the orchestrator thread. A press that lands between the capture's real end and the `finally` running is recorded by `_fire` (`start.set()`) and then erased — a silently lost press. Millisecond window, low impact (the user presses again), but it is the third instance of the press-counter-vs-orchestrator duplicated state that STATE's pattern section names, surviving the fix that introduced `close()`.

**Options.**
1. *(Root cause)* Replace the two Events + `open` flag with a single monotonically increasing press counter owned by the hotkeys module; the orchestrator remembers the count it has consumed. Lost updates become impossible by construction; `close()` stops existing.
2. Accept: the race window is ~ms and the failure is one swallowed press. Document it beside `close()`.

**Recommendation.** Option 2 for now; option 1 belongs on the refactor-session list STATE already opened (it is the same brief).

**Question.** Add the press-counter redesign to the refactor session's candidate list? (yes/no)

---

### G-07 · Stale constant comment: `NOSPEECH_CHUNKS` "93 (~3 s)"

**Severity:** Low
**Location:** `bridge/audio/listen.py:44`

**Description.** `NOSPEECH_MS = 5000` (spec/40's 5 s, correct) but the derived-constant comment still reads `# 93 (~3 s)` from an earlier value; actual is 156 (~5 s). Pure comment drift, but this file is the reference for the timing constants.

**Evidence.** `NOSPEECH_CHUNKS = NOSPEECH_MS // VAD_CHUNK_MS  # 93 (~3 s)`

**Options.** 1. Fix the comment. 2. Drop the hand-computed values from all four derivation comments (they exist to rot).

**Recommendation.** Option 2 — the formulas are self-evident; the literals are the only part that can lie.

**Question.** Delete all four literal annotations rather than just correcting one? (yes/no)

---

### G-08 · Keyed turn still gives up 5 s before the first word

**Severity:** Low (design tension, not a defect against spec)
**Location:** `bridge/orchestrator.py:71-85` (`capture_over`), spec/40 §Triggers

**Description.** Spec'd behaviour, faithfully implemented: on a keyed turn the silence cut is disabled but the 5 s no-speech give-up survives. Adversarial reading: D20's rationale is "the key is the endpoint — the mic stays yours until you tap or release," yet a user who taps and *then* composes their thought for six seconds before speaking loses the mic to a timeout tuned for the wake-word door (where a false accept must self-heal). The two entrances have different failure modes: wake needs the give-up; a deliberate keypress arguably doesn't (the user has an explicit close gesture, and the 30 s cap still bounds runaway).

**Options.**
1. Lengthen or disable the no-speech give-up on keyed turns (keep the 30 s cap as the only survivor); wake path unchanged.
2. Keep as-is — the give-up doubles as accidental-press recovery, which is real for a global hotkey.

**Recommendation.** No strong recommendation; this is a taste call the acceptance-run experience should decide. Slight lean to option 2 until a real "it hung up on me while I was thinking" occurs.

**Question.** Keep the 5 s give-up on keyed turns? (yes/no)

---

### P-01 · The port lives in three places; the env override splits daemon and overlay

**Severity:** Medium
**Location:** `bridge/broadcaster.py:41-43`, `teleprompter/decode.py:25-26`

**Description.** The broadcaster honours `GEMMA_STATUS_PORT`; the teleprompter hardcodes 8990 and reads no env. Set the env (its stated purpose: a busy port) and the daemon publishes on the new port while the overlay reconnects to 8990 forever, silently — the overlay just looks dead. The mirroring comment justifies not importing from `bridge/` (D21's front/back split, sound), but the *value* is Contract P transport truth with no single home: it lives in `broadcaster.py`, `decode.py`, and prose in D19 — while `status.json`, the designated Contract P truth-file, does not carry it.

**Evidence.** `PORT = int(os.environ.get("GEMMA_STATUS_PORT", "8990"))` vs `PORT = 8990  # Mirrored here rather than imported`.

**Options.**
1. *(Root cause)* Put the transport (host, default port, env-var name) in `status.json` (hard rule 3: it is contract truth); both sides load it — the front-end already reads that file directly, so no `bridge/` import is introduced.
2. Mirror the env override into `decode.py` (one line) and leave the duplication.
3. Delete the env override — one number, no config, until spec/70's config source exists.

**Recommendation.** Option 1: it is the only one that removes the class rather than the instance, and it uses a dependency the front-end already has.

**Question.** Transport constants into `status.json` (A), or delete the override until spec/70 (B)?

---

### P-02 · No snapshot on connect: a (re)connecting overlay renders nothing mid-turn

**Severity:** Medium
**Location:** `bridge/broadcaster.py:123-138` (`_accept`), `teleprompter/feed.py:59-64`

**Description.** A client that connects (or reconnects after a blip) receives only messages published after the connect. Start the overlay during a turn, or have it restart during a dwell, and the island stays blank while the daemon dwells an answer it believes is shown (`self.shown`), with Esc armed against nothing (G-01 interaction). The reconnect design ("start either side first, both just work") is honest only at session boundaries; mid-turn it silently loses the turn. D19's crash-isolation rationale makes the overlay restartable — which is exactly the client that needs a snapshot.

**Options.**
1. *(Root cause)* The broadcaster keeps the last-published state/transcript/reply/error (it is a ~10-line reducer, the daemon-side twin of `OverlayState`) and replays it as normal Contract P messages to each new client on accept. No schema change — the client cannot tell a replay from a live stream.
2. Add a `hello`/snapshot message type to `status.json` and send a single composite state. Cleaner on the wire, but a schema version bump and a second message shape for the same facts.
3. Accept the gap: the overlay is decorative-ish and the next turn resyncs. (Contradicts D23 "the Teleprompter is the spine".)

**Recommendation.** Option 1 — replaying ordinary messages keeps the dumb-subscriber property and needs no contract change.

**Question.** Snapshot as replayed ordinary messages (A) or a new `hello` message type (B)?

---

### P-03 · `Decoder` buffer never reset across reconnects

**Severity:** Low
**Location:** `teleprompter/feed.py` (one `Decoder` for the object's life), `teleprompter/decode.py:49-52`

**Description.** `Feed` constructs one `Decoder`; a connection that dies mid-line leaves the partial in `_buf`, and the first line of the *next* connection is glued to it — producing one malformed, dropped message (warn-once). With P-02 fixed this would eat the first snapshot line. One line to fix.

**Options.** 1. Reset the decoder on `connected` (`self._dec = Decoder()`). 2. Reset in `_on_closed`.

**Recommendation.** Option 1 (reset at the start of a stream, where the invariant belongs).

**Question.** Fine to fold into the P-02 change? (yes/no)

---

### P-04 · `_send` holds the client lock through a blocking `sendall`; bind failure leaks the socket

**Severity:** Low
**Location:** `bridge/broadcaster.py:144-152` (`_send`), `bridge/broadcaster.py:96-106` (`start`)

**Description.** The ponytail note covers "a wedged client slows only the FEED" — but `_send` holds `self._lock` across `sendall`, and `_accept` needs that lock to admit clients; one wedged subscriber therefore also blocks *healthy* subscribers and all new connections, not just its own delivery. With one intended client this is theoretical, but the note under-describes the blast radius. Separately, `start()`'s bind-failure path returns without `srv.close()` — a leaked socket object (GC saves it eventually; still sloppy for a path that exists to be hit).

**Options.**
1. *(Root cause)* Per-client send queues drained by per-client threads (the note's own "if it ever actually bites" design); the lock then only guards set membership.
2. Copy the client set under the lock, `sendall` outside it, re-take to discard the dead; add `srv.close()` on the bind-failure path. ~6 lines, removes the accept-blocking without new threads.

**Recommendation.** Option 2 now (cheap, honest), option 1 remains the documented ceiling.

**Question.** Take option 2 now? (yes/no)

---

### U-01 · Reduced-motion is sampled once at startup

**Severity:** Low
**Location:** `teleprompter/__main__.py:91-102, 154-157`

**Description.** `reduced_motion()` queries the Windows "show animations" setting once and bakes it into a context property. Toggling the accessibility setting while the overlay runs has no effect until restart — the HTML mockup's `prefers-reduced-motion` was live. Accessibility settings are exactly the kind users change and expect to take effect.

**Options.** 1. Listen for `WM_SETTINGCHANGE` in a native event filter and update the context property. 2. Re-query on each `visibleChanged` show (the island re-appears constantly; near-live for free, no native filter). 3. Accept restart-to-apply.

**Recommendation.** Option 2 — two lines in the existing `restamp` slot, no new machinery.

**Question.** Is restart-to-apply acceptable instead? (yes/no)

---

### U-02 · `fadeTop` is a dead knob threaded through four expressions

**Severity:** Low
**Location:** `teleprompter/Overlay.qml:40-41, 326-327, 338, 434`

**Description.** `fadeTop` is a `readonly property real` fixed at 0, yet it participates in the viewport y/height, the text y, and the reveal-gate target — four expressions carrying a term that cannot vary, each a place a future reader must reason about. If the knob is a deliberate future affordance it should say so; if not it is jank a simpler expression replaces.

**Options.** 1. Delete it and simplify the four expressions. 2. Keep it with a one-line comment stating what design change would ever set it non-zero.

**Recommendation.** Option 1 unless there is a concrete planned use (the comment beside it — "viewport starts at the screen edge, so the scrolled-off line peeks through" — reads like a fact, not a knob).

**Question.** Delete (A) or document (B)?

---

### B-01 · A fresh `AsyncAnthropic` client is built for every turn

**Severity:** High
**Location:** `bridge/brains/claude.py:105`, `bridge/orchestrator.py:401` (`asyncio.run` per turn)

**Description.** `converse` constructs `anthropic.AsyncAnthropic(...)` on every call, and the orchestrator runs each turn in its own `asyncio.run` loop — so every single turn pays a fresh TCP + TLS handshake to the API (and abandons the client unclosed; the loop teardown reaps it). Connection reuse across turns is *impossible* in the current shape, because an httpx AsyncClient is bound to the loop it was created on and the loop dies with the turn. This is the most plausible mechanism for the acceptance run's unexplained warm-turn outliers (STATE: turns 4 and 10 at 4631/5992 ms, "NOT cold and unexplained") — every turn is a cold connection; the variance is the network's. The fix is the same long-lived-async-daemon refactor NOTES already flags as due before tools/streaming, and the same seam STATE's dismiss-decision ② made load-bearing — three owners now want this one refactor.

**Evidence.**
```python
client = anthropic.AsyncAnthropic(api_key=self._api_key)   # per converse() call
...
reply, err = asyncio.run(_drive(...))                       # per turn
```

**Options.**
1. *(Root cause)* The long-lived event loop: `serve()` becomes async (or hosts a persistent loop on a dedicated thread), `ClaudeBrain` creates its client once in `__init__` (or lazily on first turn) and reuses it; `_wait_flag`'s 50 ms poll becomes a real `loop.call_soon_threadsafe` bridge; G-03's timer folds in. This is the refactor NOTES/STATE already scheduled — this finding just moves it from "due before tools" to "due now, it is costing seconds per turn".
2. *(Containment)* Keep the per-turn loop but hoist client construction into `ClaudeBrain.__init__` with `http_client=httpx.AsyncClient(...)` recreated per loop — does not actually get reuse (loop-bound), so really the only containment is measuring: log connection-establishment time per turn to confirm the mechanism before refactoring.
3. Do nothing until the M0-close gate; accept the outliers.

**Recommendation.** Option 1. It is three findings' shared root (B-01, G-03, STATE's dismiss-cancellation seam), NOTES already commits to it, and it has a measurable success criterion: warm-turn first-word variance collapses.

**Question.** Promote the async-daemon refactor to the top of the refactor session (A), or measure first with a connection-time log line and decide on the number (B)?

---

### B-02 · `_classify_badrequest` substring match over-classifies

**Severity:** Low
**Location:** `bridge/brains/claude.py:60-63`

**Description.** Any 400 whose message contains "context" or "too long" is spoken as "This conversation got too long for me. Wake me afresh to reset it." A 400 about, say, an invalid `context` field or a "tool description too long" would be mis-narrated, telling the user to reset a session that isn't the problem. Low likelihood, wrong-explanation cost. (Also: "Wake me afresh" is wake-word framing — see S-08.)

**Options.** 1. Match tighter (e.g. `"prompt is too long"`, `"exceed context"` — the two shapes the selfcheck already encodes). 2. Accept; the selfcheck documents the two real phrasings and the SDK may grow a typed error to switch on later.

**Recommendation.** Option 1, keeping the selfcheck cases as the fixture.

**Question.** Tighten now? (yes/no)

---

## Pass 2 — spec audit

### S-01 · `status.json` descriptions teach the reverted behaviour

**Severity:** High
**Location:** `spec/schemas/status.json:18` (`state`), `:39` (`response`), `:50` (`mic`)

**Description.** Three descriptions in the Contract P truth-file still describe the pre-2026-07-22 world: `state` says "'listening' also covers the follow-up window (mic open, spec/40)" — the follow-up window is removed; `mic` says levels are emitted "while a capture window is open (LISTENING / FOLLOW-UP)"; and `response` says clearing happens on "a 'state' that starts a new turn (**'listening'**, 'thinking')" — the *exact opposite* of `CLEARS_TURN = {thinking, idle}`, i.e. the schema documents the held-answer-wipe bug as the contract. Hard rule 3 makes this file the single source of truth; right now the truth-file specifies the bug the day was spent fixing, and a future implementer (or the Rust port D21 plans, which names the QML overlay as its behaviour oracle) would faithfully reintroduce it. spec/40 was updated; the schema was not — same-commit spec discipline (hard rule 1) missed the schema.

**Evidence.** `"description": "... Clearing: a 'state' that starts a new turn ('listening', 'thinking') or ends the session ('idle') clears the reply ..."` vs `decode.py`: `CLEARS_TURN = frozenset({"thinking", "idle"})`.

**Options.**
1. Correct the three descriptions, bump to v0.2.2, same commit as nothing else (a pure reconciliation commit).
2. *(Root cause, additive)* Also make the clearing rule *executable* rather than prose: a top-level `"clearsTurn": ["thinking", "idle"]` array in the schema that `decode.py` loads (hard rule 3 applied to the rule itself, not just the message shapes) — then this class of drift cannot recur silently.

**Recommendation.** Option 2 — it converts the exact drift that happened into a load-time impossibility, which is the standard the repo already holds for field names.

**Question.** Prose fix only (A) or promote `CLEARS_TURN` into the schema (B)?

---

### S-02 · Tier-3 spoken confirmation cannot execute in the D23 default product

**Severity:** High
**Location:** `spec/30_contract_t.md` (Tiers table + binding rules), `CLAUDE.md` hard rule 4, `spec/schemas/earcons.json:8` (`ask`), `spec/40_interaction.md` narration ("Tier 3: `ask` earcon + spoken one-line summary")

**Description.** The Tier-3 gate — BINDING, restated in CLAUDE.md as a hard rule — is "orchestrator plays the `ask` earcon, requires the user to **say 'confirm'** within 8 s, else cancels." Under D23 the default product ships with the mic opening only on a keypress and speech off: there is no channel on which to say "confirm" (no always-on mic; a capture window belongs to the turn) and possibly no earcon either (the earcon-gating question is open). The binding safety mechanism of the default configuration is thus unexecutable as specified. This is voice-era residue in the most safety-critical rule the spec has, and D20 already invented the desk-native equivalent: propose-then-tap (a proposal renders on the Teleprompter; a keypress applies). Nothing was decided wrongly — Tier 3 was written 2026-07-12, before D20/D23 existed — but Tier 3 was never revisited when the interaction model changed underneath it.

**Options.**
1. *(Root cause)* A new D-number: Tier-3 confirmation becomes **render-then-confirm** — the proposal renders on the Teleprompter and confirmation is a keypress (the D20 propose-then-tap gesture), with spoken "confirm" as the equivalent gate when speech/listen-for-me are on. Updates spec/30, CLAUDE.md rule 4, earcons.json `ask` meaning, spec/40 narration in one commit.
2. Leave Tier 3 as spoken-only and accept that Tier-3 tools are simply unavailable with speech off (a coherent posture — but it makes the default product permanently incapable of Tier-3 actions, which M1's roadmap does not intend, and it leaves a hard rule that most sessions can't exercise).

**Recommendation.** Option 1. It is a decision, not a cleanup — it wants the D-number and Thomas's sign-off, but the direction is already implied by D20's own pattern.

**Question.** Adopt keypress confirmation as the Tier-3 gate (spoken as the speech-on alternative)? (yes/no)

---

### S-03 · "read it" retired in STATE, alive in spec/40 and earcons.json; "survives across wakes" now incoherent

**Severity:** Medium
**Location:** `spec/40_interaction.md:49-52` (narration), `spec/schemas/earcons.json:9` (`answer-ready`), `STATE.md:38-41`

**Description.** STATE (2026-07-22): "'read it' readback is **retired** … whether anything speaks a long answer on request folds into the TTS switch decision." But spec/40 narration still says "the spoken channel plays `answer-ready` and **speaks on 'read it'**," and earcons.json still defines `answer-ready` as "long answer held; **say 'read it'** to hear it." The code has no read-it handling (nothing parses utterances for it, and the follow-up window that would have caught the phrase is gone). Compounding it, spec/40's parenthetical "(the held answer now survives across wakes, since with no follow-up window a re-wake is the only way to reach it)" is incoherent post-removal: a re-wake *clears* the island (binding invariant, same file), and the session dies at IDLE — nothing can "reach" a held answer at all. Current truth (spec) contradicts the sole record of the retirement (STATE) and itself.

**Options.**
1. Reconcile spec/40: the hold means SHOWN, not spoken (STATE's wording); delete the read-it clause and the survives-across-wakes parenthetical; earcons.json `answer-ready` meaning becomes "long answer held — shown on the Teleprompter, not spoken" (version bump). Park spoken-on-request explicitly with the TTS-switch design as STATE already does.
2. Keep "read it" in spec as *(planned, with "listen for me")* — but that pre-empts the very design STATE deliberately deferred.

**Recommendation.** Option 1 — spec should say what is true now; the deferred question already has a home in STATE.

**Question.** Also keep the `answer-ready` earcon at all while speech is off by default, or fold its meaning into the overlay-only world and revisit with the earcon-gating question? (A: keep earcon / B: fold into earcon-gating decision)

---

### S-04 · D20 / spec/40 §Triggers still say answers "speak (D16)" — unamended by D23

**Severity:** Medium
**Location:** `spec/00_overview.md` D20 ("Answers render on the Teleprompter and speak (D16)"), `spec/40_interaction.md:99-100` (same sentence in §Triggers)

**Description.** D23 amended D16(1) ("both, always" → "display always, speech by choice") and back-annotated D11, D14 and D16 with italic amendment notes — but D20's restatement of the same ruling was missed in both files where it appears. A reader of D20 alone (the interaction-model record Track D will build from) inherits mandatory speech. The annotation practice is otherwise consistent; this is the one loose thread in the D-tail, and it matters because D20 is the record the dictate/rewrite work is about to be built against.

**Options.**
1. Add the standard italic amendment note to D20 and reword spec/40 §Triggers ("render on the Teleprompter and, with speech enabled, speak — D16 as amended by D23").
2. Fold into a general "speech-conditional" sweep with S-03's edits (one reconciliation commit for spec/40 + spec/00 + earcons).

**Recommendation.** Option 2 — S-03, S-04 and S-05 are one editing session over the same two files.

**Question.** One combined reconciliation commit for S-03/04/05 (A), or separate commits per finding for cleaner history (B)?

---

### S-05 · spec/40 §Visual output opens with the design it contradicts; header carries build status

**Severity:** Medium
**Location:** `spec/40_interaction.md:164-171`

**Description.** The section header still reads "(component P; D13/D19; **v0 planned, pre-M0-run**)" — build status in a spec file (hard rule 1 assigns that to STATE exclusively; and it is stale — the Teleprompter is built and passed the acceptance run). The opening paragraph then describes "A **supplementary** on-screen indicator … pulsing dot = awake/listening · spinner = thinking … small **status icons** (mute, tool activity, error)" — the pre-lock, eyes-free-era sketch. Two bullets later the same section says "**The spine, not a supplement** (D23)," and the locked design (STATE Track P) has no dot, no spinner, no status icons, no state labels — bars, typewriter text, morphing status word. A spec section that opens by contradicting itself and the shipped design will mislead exactly the future session it exists for (e.g. the mac renderer, which D13 says "consumes the same feed").

**Options.**
1. Rewrite the opening paragraph to describe the locked design (island fused to the top edge; bars driven by real mic level; typewriter reveal; no controls — D22), drop "planned, pre-M0-run" from the header, and keep the build-order bullet's content in STATE only.
2. Minimal: delete the stale sentence and header fragment, add a pointer to STATE Track P's design-locked entry.

**Recommendation.** Option 1 — §Visual output is the one place the design *should* be normatively described, and right now the only accurate description lives in STATE (which rule 1 says must not be the spec).

**Question.** Should the locked visual design move fully into spec/40 (A) or stay summarised in STATE with spec/40 pointing at it (B)?

---

### S-06 · D15 mandates a local cleanup model; the recorded decision is Groq (cloud)

**Severity:** Medium
**Location:** `spec/00_overview.md` D15 ("Engine: a small local model once the Ollama groundwork (Track B) exists — **not the cloud brain**"), `spec/40_interaction.md:133-135` ("via a small local model"), `STATE.md` Track D ("Cleanup engine chosen this session = **Groq** (cloud, fast/cheap; … revises D15's local-model note)"), D19 (Groq key in the tray, `("gemma","groq")`)

**Description.** The Groq revision is real and even has shipped code (the tray's Groq-key dialog exists solely for it) — but it is recorded only in STATE prose and a D19 aside. D15 itself, and spec/40's transcript-hygiene section, still say local-model, uncorrected and unannotated. A future session reading the D-tail (as CLAUDE.md instructs) gets the wrong engine. Note the nuance: D15 covers *two* things — the `--clean-prompts` assistant-path experiment (where "not the cloud brain" was a latency/privacy argument) and dictation cleanup; the Groq decision was made for dictation. Whether `--clean-prompts` also moves to Groq or stays local is genuinely undecided, which is exactly why this wants an explicit annotation rather than a quiet edit.

**Options.**
1. Annotate D15 with the standard italic note ("Amended 2026-07-18/D19: dictation cleanup engine = Groq (cloud); the `--clean-prompts` engine choice remains open") and align spec/40 §Transcript hygiene.
2. Give the engine-routing question its own D-number now (it borders the multi-provider routing item parked in STATE).

**Recommendation.** Option 1 — the decision already happened and just needs recording where readers look; the routing D-number can wait for the settings gate where STATE already parks it.

**Question.** Does `--clean-prompts` (assistant path) stay local-model as D15 argued, or follow dictation to Groq? (A: local / B: Groq)

---

### S-07 · Headset-era naming: "headset <-> LLM brains" in pyproject; "always-listening" in CLAUDE.md; the name "bridge"

**Severity:** Medium
**Location:** `pyproject.toml:8`, `CLAUDE.md:3-6`, package `bridge/` throughout

**Description.** D18 cancelled the headset and D23 settled the identity ("a UI-first desk assistant … hotkey-driven and screen-only out of the box"), but the two files a newcomer reads first still carry the old product: `pyproject.toml` — `description = "Bridge daemon for Project Gemma (**headset <-> LLM brains**)"` — names the cancelled hardware outright; CLAUDE.md's opening line — "an **always-listening** voice assistant + dictation **bridge**" — is doubly wrong (always-listening is now an opt-in switch, default off; and it contradicts D23's identity paragraph verbatim). The name **bridge** itself is the deepest residue: it meant the thing that *bridged* the headset to the brains; with the headset excised, the package is simply the daemon/engine, and every doc that says "the bridge" carries a dead metaphor the specs then have to re-explain ("the bridge (G) is the hub"). Renaming is real churn — imports, spec references, docs (frozen, so they'd stay), CI, muscle memory — which is why it is a question, not a recommendation. The letter G survives either way (it is "Gemma", not "bridge", in the legend).

**Options.**
1. Fix the prose only: pyproject description ("The Gemma daemon: audio pipeline, orchestrator, brains — see spec/"), CLAUDE.md intro rewritten from D23's identity paragraph. Zero churn, kills the two worst instances today.
2. *(Root cause)* Also rename the package `bridge/` → `daemon/` (or `engine/`/`core/`) in one mechanical commit: imports, `pyproject` packages, `checks.yml`, README, spec/00 legend ("**G** — the Gemma daemon"), leaving frozen docs untouched per hard rule 2 with the existing terminology-note mechanism covering the old name.
3. Option 1 now; park the rename with a note in STATE until a naturally-churny moment (e.g. the spec/70 config build or a pre-Track-D tidy).

**Recommendation.** Option 3. The prose fixes are overdue and free; the rename is worth doing but deserves its own moment, not a rider on a review.

**Question.** Rename `bridge/` eventually (A: yes, park it / B: no, "bridge" stays as a legacy proper noun)?

---

### S-08 · Residue sweep — eight smaller stale references

**Severity:** Low (individually; collectively they are the drift-rate signal)
**Location & items:**

1. `spec/schemas/status.json` `transcript` description: "the **expandable** session history (D14…)" → the ⌄ expandable mechanism was cut by D22; say "the expanded view (D22)".
2. `spec/schemas/earcons.json` `working` meaning: "thinking has exceeded **1.5 s**" — the code fires at 1.4 s by design (inside the budget). The truth-file should state the design ("fired just before the 1.5 s feedback deadline"), or the meaning reads as a measurement the code contradicts.
3. `spec/00_overview.md` component inventory: hotkeys at "`bridge/hotkeys/`" — it is a module, `bridge/hotkeys.py` (STATE noted the deviation; spec/00 didn't get the memo). Same row: "60_dictation (owed)" is fine; the code-location column is the drift.
4. `spec/00_overview.md` milestone table: M3 is silently absent (D18 removed it). One footnote — "M3 was the headset milestone, removed by D18" — spares every future reader the archaeology.
5. `spec/50_security.md` rule 5: "the tray exposes a software mute" — no mute exists in either tray (`teleprompter/tray.py` has key/latency/quit; spec/70's menu sketch lists it as planned). BINDING file stating an unbuilt control as present; tag it *(planned)* per hard rule 1's convention.
6. `README.md`: `python -m tests.replay --record wake_short` — that case was removed 2026-07-22 (cases are now `key_*`); also the orchestrator line leads with "say 'hey jarvis'" though the hotkey is the primary door and the wake word is default-off per D23. Update both lines.
7. `bridge/orchestrator.py` `SPOKEN_ERRORS["context"]`: "**Wake me afresh** to reset it" — wake-word framing spoken to a user whose wake word is off by default; "Start a new turn to reset me" (or similar) is door-neutral.
8. `spec/schemas/status.json` top description: "shows 'listening' only while audio is actually being captured" — correct, but see G-02: the code currently violates it on the nothing-heard path; when fixing G-02, no schema change is needed (the schema is right; flagged here so the pair is closed together).

**Options.** 1. One sweep commit for items 1–7 (item 8 rides with G-02). 2. Fold into the S-03/04/05 reconciliation commit.

**Recommendation.** Option 1 — a single "residue sweep" commit is greppable later and keeps the S-03/04/05 commit about substance.

**Question.** Any of the eight you'd rather *keep* as-is? (yes — name them / no)

---

### S-09 · CLAUDE.md repo map omits `teleprompter/`, `tests/`, `scripts/`

**Severity:** Low
**Location:** `CLAUDE.md:10-26`

**Description.** The repo map — "you are here; keep THIN (index…)" — predates Track P: it maps `bridge/` but not `teleprompter/`, which D23 declares the spine of the product, nor `tests/` (the replay harness, one of the repo's best assets) nor `scripts/`. The index no longer indexes the repo; a fresh session following CLAUDE.md's own instructions would not know the front-end exists until spec/00.

**Options.** 1. Add three lines (`teleprompter/` ← the overlay, Contract P front-end, D19; `tests/` ← replay harness, WAVs untracked; `scripts/` ← one-off smoke tests). 2. Fold into the S-07 CLAUDE.md intro rewrite.

**Recommendation.** Option 2 — one CLAUDE.md commit covering intro + map.

**Question.** OK to combine with S-07's CLAUDE.md edit? (yes/no)

---

### X-01 · `checks.yml`'s PySide6 comment is now false — CI installs Qt but never runs `overlay_check`

**Severity:** Medium
**Location:** `.github/workflows/checks.yml:30-33`, `pyproject.toml:31`

**Description.** The workflow comment says "PySide6 is an optional `[ui]` extra and is NOT installed here (and QML needs a display), so the renderer can't be tested in CI." All three claims are now wrong: D23 made PySide6 a core dependency, so CI's `pip install -e .` already downloads and installs Qt on every push (the cost is being paid); `teleprompter.overlay_check` runs headless (`QT_QPA_PLATFORM=offscreen`, no display); and it is precisely the check guarding the module where, per STATE, "every bug this week" lived. The one component with a purpose-built regression harness is the one component CI doesn't exercise. STATE flags this as an open question; the factual comment error makes it decidable now rather than later.

**Options.**
1. Add `python -m teleprompter.overlay_check` (and `- run: python -m teleprompter.decode --selfcheck` already there) to the workflow; fix the comment. The install cost is already sunk.
2. If CI weight is the concern, the *coherent* alternative is reverting PySide6 to an `[ui]` extra — but that re-litigates D23 ("the Teleprompter is not optional"), which the anti-relitigation instinct of D21 argues against.

**Recommendation.** Option 1 — one workflow line plus a truthful comment; there is no remaining reason not to.

**Question.** Wire `overlay_check` into CI now? (yes/no)

---

## Closing note

The strongest single pattern across both passes is the one STATE already diagnosed on 2026-07-22: *a fact living on two sides of a seam, one side not told.* Pass 1's G-01/G-02/G-04/G-06 are that pattern in code (dwell vs dismiss flag · daemon's `shown` vs island's reveal · `_armed` vs the pump · press counter vs capture); Pass 2's S-01/S-03/S-04/S-06 are the same pattern in prose (schema vs reducer · spec vs STATE · D20 vs D23 · D15 vs the Groq decision). The refactor session STATE proposes and the reconciliation commits proposed here are the same brief applied to two media. B-01 (one shared long-lived loop) and S-01 option 2 (executable `clearsTurn`) are the two fixes that remove a *class* rather than an instance, and are the two this review would fight for.
