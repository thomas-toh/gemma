# Adversarial review — settings window (D40) + model/tool interfaces (D38)

**Date:** 2026-08-02 · **Scope:** the uncommitted D40 working tree plus the committed D38 gate.
**Method:** three finder agents (secrets/gate · input surfaces · UI logic/animation), then three
independent refuters who re-reproduced every critical/major claim from scratch. Every proven
finding was reproduced offline: real `SettingsWindow.qml` driven headless
(`QT_QPA_PLATFORM=offscreen`), `GEMMA_SETTINGS` at temp files, `keyring` and `providers.probe`
faked in-process. The repo was never modified and no cloud endpoint was contacted. 33 findings;
8 rated major by finders; after verification **6 majors stand** (one downgraded, one was a
duplicate found independently by two tracks). Nothing was fixed — report only, per hard rule 1.

---

## Confirmed MAJOR (each reproduced twice, independently)

### M1. A local provider can never be added through the UI
`SettingsWindow.qml:173` — `canCommit` requires `addModel !== ""` for both cloud and local, but
on a local Add nothing can ever populate the model list: `addModelList`'s non-editing local
branch reads only `cfg.trial.models` (:141), and the only caller of `trialProvider` is the Test
button (:2004), which lives in the API-key row shown only when `addKind === "cloud"` (:1974).
`beginAdd` never probes either. So the Model dropdown has zero options forever and "Add model"
stays disabled — Ollama, LM Studio and llama.cpp are unaddable, with no message explaining the
empty picker (`addProbeMessage` returns `""` for local). Proven with a fake probe holding a live
2-model answer the sheet never asks for (0 probe calls). Regression from the uncommitted
trial-slot rework: the `modelOptions` cache branch was gated to edit-only and Test to cloud-only,
leaving local Add with no fetch path at all. Found independently by tracks B and C; confirmed by
two separate refuters.
*Guard gap:* `settings_check` walks the local Add states but sets `addModel` by `setProperty` and
invokes `commitAdd()` via metaObject — bypassing the `canCommit` gate and the disabled button. No
guard proves any catalogue entry can complete the Add flow through the real controls.

### M2. Edit → Done silently re-enables a disabled provider, can steal the default, and destroys fields the form doesn't carry
`settings_model.py:176` — `commitAdd` funnels an EDIT through `cfg.addProvider`, which rebuilds
the entry from scratch with `"on": True` hardcoded instead of merging into the stored entry.
Proven: a provider switched off comes back ON after opening its Edit sheet and pressing Done with
nothing changed; if turning it off had handed `primary` away, the `if not primary` branch (:190)
makes the re-enabled provider the **default**; and a hand-added `keep_alive` (read by
`router.resolve` at router.py:72 and fed to `ensure_local_server`, orchestrator.py:201) is
destroyed. `commitAdd` also stamps `temperature: "0.7"` — a string — onto every edited/added
provider, including ones whose catalogue declares no temperature capability. Same rebuild-not-merge
family as the addProvider QJSValue discard.
*Guard gap:* `settings_check` drives `commitAdd` only with `addEditing=False`; `settings_model`'s
selfcheck never exercises the Edit shape.

### M3. Typed text in any schema-row field is wiped by the next `changed` emission
`SettingsWindow.qml:962` — `Field`/`Area` bind `text: cfg.values[sr.key]` and commit only on
`editingFinished`. `cfg.changed` fires on **every** settings write and every background probe
landing (`settings_model.py:405`), which re-evaluates the binding and resets the field, discarding
typing mid-edit. Proven with real key events: typed "abc" into the profile field, called
`cfg.set('tts', True)` (exactly what any Toggle click does) → field text `""`. Worse, the refuter
proved a zero-interaction path: probes kicked by the Models pane keep landing up to ~6 s later, so
visiting Models and then typing on General can lose the text with no click at all. The key field
is immune only because it owns its text — the earlier fix acknowledged this exact class and was
applied to one field.
*Guard gap:* none exists — a binding legitimately re-evaluating emits no QML warning, and nothing
in the repo simulates typing into a bound field.

### M4. Typed text is lost outright on a pane switch
`SettingsWindow.qml:964, 1344` — fields commit on `editingFinished` (focus loss or Enter), but
clicking a sidebar item switches `root.section` directly: `NavItem`'s own MouseArea accepts the
press **without** calling `dropFocus()` (the title bar :1206, sidebar background :1041 and page
background :1265 all do — the NavItem is the missed spot). The Repeater destroys the delegates and
a destroyed TextField emits no `editingFinished`: the text is committed nowhere. Refuter proved it
with a real synthetic mouse click on the Triggers NavItem — uncommitted "xyz" gone from field,
`cfg.values` and the file; 0 warnings.
*Guard gap:* same blindness as M3.

### M5. The new `local_server_stop_on_quit` setting renders as a dead row showing the literal text "true"
`SettingsWindow.qml:1472` — the Dictate section repeats over `cfg.rowsFor("models")` with a
`CleanupRow` delegate built for provider rows. `rowsFor` excludes only type `object` and `primary`
(`settings_model.py:96-101`), so the new bool `local_server_stop_on_quit`
(`spec/schemas/settings.json:146-152`, added in this working tree) lands in it: `toggleKey=''` so
the Toggle is permanently disabled and shows OFF while the real value is True; the bool coerces to
the string `'true'`, which the dimmed Provider dropdown displays as its value; the help text is
dropped. A built, default-on setting is unreadable and unchangeable from the UI. The refuter also
showed the delegate's `picked` handler would write a provider-id string over the bool if the row
ever became interactive.
*Guard gap:* the coercion emits no QML warning, so `settings_check`'s zero-warning gate passes;
no guard checks a row's type matches its delegate.

### M6. `setKey()` reports success when the credential store refused, and no caller looks anyway
`settings_model.py:453` — the delete path wraps `keyring.delete_password` in
`except Exception: pass`, intended for keyring's "nothing stored" signal
(`PasswordDeleteError`) but swallowing a locked vault (`KeyringLocked`) and OS refusals
(`OSError`) identically, then returns True. So "Also delete the stored API key" can leave the key
in Windows Credential Manager with nothing logged and nothing shown — and re-adding the provider
resurrects it as `keyState='stored'`. On the write side a failed `keyring.set_password` correctly
returns False — but neither QML call site (`SettingsWindow.qml:239`, `:2179`) reads the result, so
a key that failed to save still closes the sheet as a success. This is the only place spec/50
rule 10 is enforced, and its failure is invisible.
*Guard gap:* no guard exercises any keyring write/delete path — `settings_model`'s selfcheck never
calls `setKey`, and `settings_check` deliberately must not touch the real store.

---

## Confirmed, downgraded to MINOR by verification

### m0. The typed API key survives every *exit* from the sheet, on a window that lives forever
`SettingsWindow.qml:247` + `__main__.py:453` — every ENTRY into the key sheet clears the key
(openAdd/beginAdd/beginEdit); no EXIT does. Cancel, the sheet's X, the scrim click and
confirm-Remove all just set `manageOpen=false`, leaving the plaintext key in `keyField.text` and
`root.addKey`; `commitAdd` clears `addKey` but not `keyField.text`; and closing the window only
hides the singleton, so the key sits in a live QML property indefinitely. Track B additionally
proved close/reopen mid-sheet preserves the open sheet, the typed key **and a live 'ok' trial
verdict** — Done would commit it. Downgraded from major: nothing reaches disk, logs or screen
(echoMode Password; every re-entry clears), so exposure is process memory + the reopen surprise —
lifetime hygiene, not a rule-10 leak. Fix shape is one-line clears on the exit paths.
*Guard gap:* `settings_check` itself plants a key in `addKey` (:376) and never asserts it clears.

---

## Proven MINOR

- **The D38 gate fails OPEN on non-boolean file values** — `bridge/tools.py:372` reads toggles as
  `bool(now.get(key))`, so a hand-edited `"connector_files": "false"` / `"0"` / `"off"` reads as
  switched **on** and the tool is offered and executed. Every other malformed shape fails closed;
  this is the one open direction, on a consent gate. Not reachable from the UI (QML bools cross as
  bools). Correct read: `now.get(key) is True`. *(Guard: tools selfcheck only writes real bools.)*
- **Nothing enforces "no secret in settings.json/logs"** — `bridge/settings.py:86` logs the whole
  `models` dict at INFO on every write, and `addProvider`/`setModel` merge/write arbitrary field
  names with no allowlist (`settings_model.py:186, 212`). Today no caller passes a key (proven:
  the real UI path leaves the file clean) — but a config dict containing `key:` would be persisted
  **and logged**, proven with a canary. The rule is a ponytail comment, not code.
- **Two CI selfchecks make live authenticated cloud calls on this box** —
  `python -m teleprompter.settings_model` and `python -m teleprompter.settings_check` both call
  `addProvider` → `refreshModels` → `probe(key="")` → falls back to the **real credential store**
  → authenticated GETs to Anthropic/Groq/OpenAI. CI passes only because runners have no
  credentials. (Neither can *write* the store or the real profile — verified.)
- **`python -m bridge.tools --selfcheck` opens the real Outlook inbox + clipboard here** — the
  comment at tools.py:600 ("no profile exists on this box") is stale: the registry shows one
  Outlook profile, so `_mail_profile_exists()` is True and the no-criteria `search_email` call
  (:607) enumerates the eight most recent real messages (discarded, not logged) and can block
  ~30 s on a cold Outlook start. Agents deliberately did **not** run it here.
- **`cfg.set` / `cfg.setModel` silently discard composite values from QML** — the unfixed siblings
  of the addProvider QJSValue bug: `json.dumps` raises on the QJSValue, the write vanishes, no
  signal. Latent (all current call sites pass scalars). `addProvider`'s own `toVariant` fix is
  complete, nested structures included — but it also persists unknown keys wholesale (see above).
- **KeyRecorder keeps its danger-red border at rest** — `stop()` (focus-loss/click-away/Esc path)
  clears `recording` but not `invalid` (`KeyRecorder.qml:54`); after a rejected bare-key capture
  the field sits at rest, holding a valid combo, with a red border until the next click. Found by
  B and C independently. *(settings_check drives this exact sequence and stops one assertion
  short.)*
- **Writer/reader drift across the settings file seam** — `temperature` is written as the string
  `'0.7'` on every provider (no control edits it; `build_for_role` never forwards it, so it's dead
  today — and `CompatBrain` expects `float|None` the day it's wired). Mirror image: `keep_alive`
  is read by the router and consumed by the orchestrator but no UI writes it — and M2's Edit
  rebuild destroys a hand-added one.
- **Removing a provider leaves stale role pointers** — `removeProvider` (`settings_model.py:195`)
  reassigns `primary` but not `cleanup_dictation`/`cleanup_prompts`; the router falls back cleanly
  (None, proven) but the file keeps `cleanup_dictation='openai'` and the Dictate row still
  *displays* OpenAI as the tidy engine while dictation actually runs on the daemon default. The
  "fact on both sides of a seam, one side not told" class.
- **Escape closes nothing** — neither sheet has key handling and the hand-rolled Dropdown's Popup
  never takes focus, so its close-on-Escape policy never applies. The only Escape consumer in the
  window is a recording KeyRecorder; everything else is mouse-only dismissal (and a popup also
  survives a window resize).
- **Window chrome is dead while a sheet is open** — the `enabled: !root.modalOpen` Item (:1026)
  wraps the entire page including all three caption buttons and both drag surfaces: with a sheet
  up the window cannot be closed, minimized, maximized or moved. A native window never loses its
  caption buttons to an in-app sheet — against the D40 brief.
- **The close button's danger hover breaks Theme's own alpha rule** — `:1361` animates opaque
  `#d93b33` against `"transparent"` (= transparent BLACK): the red arrives through muddy dark red,
  exactly the class of the three fixed hover flashes. `IconBtn` carries an identical dormant
  branch (:627) for the first caller that sets `danger`.
- **Measured column collisions** — at the window's own minimum width the "Apps & media" connector
  label row runs 11 px into the Enables column ("MCP servers" by 5 px); at the *default* width a
  long model id crosses the Key column by 3 px (the dropdown's width slack is smaller than its
  chrome). Measured with the bundled Inter face, not estimated.
- **An empty dropdown opens as a 10 px blank sliver** — `want = length*32+10` with zero options;
  reachable from the local-Add dead end (M1) and any model dropdown before a fetch lands.

## Notes (recorded, low stakes or deliberate-adjacent)

- **decode reducer trusts schema-required fields** — `{"type":"tool"}` with no `name` raises
  KeyError inside the feed slot and drops the rest of that read; only reachable from a non-Gemma
  feed (a local process can squat port 8990 first — spec/50 rule 12 reasons only about the
  upstream verb). Also `done` is truthiness: `"done":"false"` clears the indicator.
- **The tool `done` message is droppable** — publish() drops on a full queue by design, but
  spec/30 states the around-every-call guarantee as absolute; the indicator (unrendered today)
  could outlive the work. `_run_tool_seen`'s `finally` itself is sound — proven through ok,
  refusals, raising backends, even KeyboardInterrupt/SystemExit.
- **Out-of-tier registry tools audit as `refused:unknown_tool`** — the `refused:tier_N` branch is
  unreachable for every existing tool; deliberate (the selfcheck pins it) but becomes wrong the
  day a Tier-2 backend lands before MAX_TIER rises.
- **Mid-turn connector toggle asymmetry** — OFF mid-turn: stale spec list, execute() refuses
  (correct, proven). ON mid-turn: execute() runs a tool the brain was never offered that turn.
  Not a bypass (the user consented by then); recorded because this snapshot-vs-fresh-read shape is
  what a real bypass would look like if the directions ever swapped.
- **Design-intent trio for Thomas to rule on:** "Set as default" commits instantly inside an
  otherwise-transactional, dismissable Edit sheet; a good key typed after a failed Test is
  silently dropped on Done (correct per the only-ok-writes rule, but no feedback at Done); the
  delete-key checkbox shows (checked) for key-auth providers even when no key is stored.
- **Sheet trailing dividers** — the effort/thinking rows handle the last-row case; the key,
  Address and Model rows don't, so e.g. Edit-Groq ends in a floating hairline ~24 px above the
  sheet foot's own rule.
- **Header scroll-fade fades to transparent BLACK** — the gradient sibling of the Theme rule; a
  ~3.7 %-luminance dark band at the midpoint. Subtle on this shell.
- **Dead vocabulary** — `Kbd` component instantiated nowhere; `Theme.dropdownRows` (8) referenced
  nowhere while the popup hardcodes 32 px rows capped at 320 px (~10 rows) — constant and
  behaviour already disagree.
- **Unproven, needs one on-screen check** — header double-click-to-maximize may never fire:
  `startSystemMove()` runs in `onPressed`, and on real Windows the OS move loop can eat the
  double-click. Offscreen cannot reproduce it (startSystemMove is a no-op there).

---

## The guard-gap pattern (why nothing caught these)

1. **The zero-warning gate can only see what throws.** M5's bool→string coercion, M3/M4's text
   loss, every layout overlap and every animation fault emit no QML warning. The check's own scope
   note ("nothing asserts looks right") is the finding, systematized.
2. **settings_check drives properties, not controls.** It sets `addModel` by `setProperty` and
   calls `commitAdd()` by metaObject — so the `canCommit` gate, disabled buttons, and the real
   click paths (M1) are structurally outside its reach.
3. **No guard exercises a keyring write/delete** (M6) — both checks deliberately avoid the real
   store and nothing substitutes a fake.
4. **CI-parity is not box-parity.** Two selfchecks are only offline on an *empty* runner; on this
   box they read real credentials and make live calls, and `bridge.tools --selfcheck` reads the
   real inbox. The divergence is precisely what kept it invisible.
5. **Fixes were applied at the symptom site, not the class.** The key Field owns its text; every
   other field doesn't (M3). Entry points clear the key; exit points don't (m0). Effort/thinking
   rows handle last-row dividers; key/Address/Model rows don't.

## Known-fix verification (all HOLD)

Trial-slot split (warm cache offers nothing untested; failed Edit trial touches nothing; every
hostile ordering behaves — only an 'ok' verdict on the *current* text writes, exactly once) ·
empty-box Test lockout on Add (and Edit's empty-box probe of the stored key is by design) ·
addProvider QJSValue unwrap incl. nested structures · `_fetch` generation counter ·
KeyRecorder placement · the three hover-flash fixes (one new sibling: the close button, above) ·
no conditional font.weight anywhere · row centering on the ROW throughout · zero
TapHandler/DragHandler in teleprompter QML · no positioner read-only assignments · singleton
window is truly single (but reopen state is unreset — m0).

## Not checked (honest edges)

Real on-screen rendering, hit-testing and the OS window manager (drag, snap, the double-click
race); the live daemon side of the router seam across real turns; a real keyring backend failure
against the actual vault (proven via in-process fakes on the same code path); whether the
Anthropic API accepts a history carrying tool_use blocks when `tools` is empty (would cost live
quota; fallout is an apology line, not a gate weakness); `bridge.tools --selfcheck`,
`settings_model` and `settings_check` were deliberately **not** run bare on this box — see the
selfcheck findings.

*Full repro harnesses (a_/b_/c_/v_ prefixed) live in the session scratchpad; every finding above
names its script. Verification transcripts: workflow `wf_49ca24f1-e7b`.*
