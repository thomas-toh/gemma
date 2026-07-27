pragma Singleton
import QtQuick

// Design tokens — the single source of colour, opacity and type for every Teleprompter
// surface (the island today; the expanded view later). The QML analogue of alfred-test's
// renderer/design/tokens.css: values live HERE and are referenced BY ROLE, never restated as
// a literal at the point of use. A `pragma Singleton` is used rather than a plain component
// so there is exactly one instance and the values cannot drift between files.
//
// Island *geometry* deliberately stays in Overlay.qml — widths, the flare and the corner radii
// describe that one shape, not the design system.
QtObject {
    // ── palette ─────────────────────────────────────────────────────────────
    readonly property color surface: "#000000"       // the island body
    readonly property color inkBase: "#f4f6f8"       // white, before any opacity is applied

    // ── opacity scale, named by ROLE not by value ──────────────────────────
    // Two levels, not three: the status word and fault text sit at the same recessive weight,
    // so they share one token rather than two that happen to match. Split them again only if
    // they ever need to differ.
    readonly property real opacityPrimary: 1.00      // content: the prompt, the reply
    readonly property real opacityMuted:   0.35      // status word, fault text, hints
    readonly property real opacityScrim:   0.88      // peak of the "more above" fade

    // ── derived text colours — use these, never an ad-hoc Qt.rgba() ────────
    readonly property color textPrimary: Qt.rgba(inkBase.r, inkBase.g, inkBase.b, opacityPrimary)
    readonly property color textMuted:   Qt.rgba(inkBase.r, inkBase.g, inkBase.b, opacityMuted)

    // ── type ────────────────────────────────────────────────────────────────
    // CSS semantics: the line box is lineHeight * fontSize (Overlay applies it via
    // Text.FixedHeight). Keep lineHeight above ~1.2 or descenders start to clip.
    readonly property int  fontSize: 18
    readonly property int  fontSizePrompt: 16        // peek prompt (context) — one step under the reply (D27)
    readonly property int  fontSizeSmall: 12         // quiet controls: peek more/less toggle, generating cue (D27)
    // 600, not the mockup's 500: a grotesque UI face at 500 reads too light against the black
    // island, and Qt renders a touch thinner than a browser. Archivo (the app face since 2026-07-25;
    // Inter → Hanken → Archivo) is variable, so 550 also works if 600 is a shade heavy.
    readonly property int  fontWeight: Font.DemiBold // 600
    readonly property real lineHeight: 1.3
    readonly property real lineHeightTight: 1.15     // wrapped quiet context (peek prompt) — D27

    // A point on the scrim ramp: f is the fraction of full strength (1.0 = opaquest). Lets a
    // gradient keep its own CURVE while the colour and peak strength stay tokenised.
    function scrim(f) { return Qt.rgba(surface.r, surface.g, surface.b, opacityScrim * f) }

    // ── motion ──────────────────────────────────────────────────────────────
    readonly property int durationResize: 340        // pill open/close
    readonly property int durationScroll: 200        // teleprompter glide
    readonly property int durationBars: 90           // mic bar smoothing
    readonly property int durationFade: 220          // the island's entrance / exit
    readonly property int durationPeek: 200          // expanded-view (peek) open/close — snappier than a turn resize (D27)
    readonly property int durationHint: 120          // hover-hint nudge (D27)
    // One WORD per tick, not one character: this is a teleprompter to be read, not a chat
    // stream to be skimmed. Matched to the scripted feed's cadence, which read well.
    readonly property int durationWord: 90

    // ── dwells: how long finished content stays put (D24) ───────────────────
    // Both start from the moment the text has FINISHED revealing, which is why they can be
    // flat numbers. Their predecessors lived in the daemon and had to scale with word count,
    // because the daemon was estimating this side's typing speed — it guessed 0.45 s a word
    // and still blanked long answers mid-sentence. Measured from the right clock, a constant
    // is enough, and "N seconds after it finishes appearing" is a knob you can reason about.
    readonly property int durationPromptHold: 700     // prompt sits before the reply takes over
    readonly property int durationAnswerDwell: 20000  // answer sits before the island hides
    readonly property int durationPasteDwell: 2500    // dictation's "Pasted ✓" beat before hiding (D2)

    // ── settings window (D29) ───────────────────────────────────────────────
    // A second surface, not a second design system: the face and motion above are shared. A cool
    // near-black set (Thomas, 2026-07-26 — the olive read as warm espresso; B ≥ G on every step so
    // the field reads cool-neutral). The UI accent is white and the secondary colours are muted —
    // see below. Every fill refers to a ROLE, so a palette change is this block alone. The island's
    // pure black is its own token (`surface`); the window borrows pure black only for the card
    // model-id wells (`surfaceDeep`, Thomas 2026-07-26).
    readonly property color surfaceShell: "#0d0e11"   // window body
    readonly property color surfaceRail:  "#0d0e11"   // the top-bar shares the body
    readonly property color surfaceCard:  "#1a1c21"
    readonly property color surfaceLift:  "#23262d"   // card hover
    readonly property color surfaceSunk:  "#0a0b0d"   // inset fields, a step below the shell
    readonly property color surfaceDeep:  "#000000"   // pure black — the card model-id wells
    readonly property color surfacePop:   "#1f232b"   // dropdowns, sheets
    readonly property color hairline:       "#2a2d33"
    readonly property color hairlineStrong: "#3a3e46"

    readonly property color bone: "#f4f2e9"           // the window's white (warmer than the island's)
    readonly property color uiInk:      bone                                    // strong fills
    readonly property color uiText:     bone
    readonly property color uiTextDim:  "#c6c7bb"                               // mist
    readonly property color uiTextFaint: "#7a7c6e"                             // ash
    readonly property color navText:       uiTextFaint
    readonly property color navTextActive: uiText

    readonly property color uiHover:       Qt.rgba(bone.r, bone.g, bone.b, 0.06)
    readonly property color uiHoverStrong: Qt.rgba(bone.r, bone.g, bone.b, 0.09)
    readonly property color uiNavHover:    Qt.rgba(bone.r, bone.g, bone.b, 0.04)
    readonly property color uiSelected:    Qt.rgba(bone.r, bone.g, bone.b, 0.075)
    readonly property color uiEdgeHover:   Qt.rgba(bone.r, bone.g, bone.b, 0.24)
    readonly property color uiTrackOff:    Qt.rgba(bone.r, bone.g, bone.b, 0.10)

    // The UI accent is now WHITE (Thomas, 2026-07-26 — the lime read as sporty): toggles, the
    // primary model, focus, text selection all use `accent`. The secondary colours are firmed
    // down from the neon sandbox set into muted, editorial tones — coral for the mark + on-air,
    // berry for faults (so red never means "the mic can hear you"); teal is reserved, unused.
    readonly property color accent: bone              // white
    readonly property color flare:  "#cf6142"         // muted coral — mark, on-air
    readonly property color vapor:  "#40988c"         // muted teal (reserved)
    readonly property color pulse:  "#c2506f"         // muted berry — faults
    readonly property color danger: pulse
    readonly property color lamp: flare               // the on-air lamp (name kept for callers)
    readonly property color lampSoft: Qt.rgba(0.81, 0.38, 0.26, 0.18)

    readonly property real opacityDim: 0.55          // a decided setting whose consumer is unbuilt
    readonly property int radiusCard: 12
    readonly property int radiusControl: 8
    readonly property int durationControl: 180       // switch travel, hover, menu open

    // Type scale for the settings window — THREE sizes, named by role (standardised 2026-07-25).
    // The island's sizes above are its own. Fewer steps than before on purpose: a window earns
    // hierarchy from weight and spacing, not from a size for every occasion, and the old
    // 28/17/16/15/14/13/12 ladder read as "a lot of small fonts". Now:
    //   heading 18 — every title and section heading (pane title, sheet title, group heading)
    //   base    16 — everything readable: labels, help text, controls, free text
    //   small   14 — the floor: chips, machine values, the effort scale, captions
    // Bold + sentence case carry the heading; there is no uppercase-eyebrow tier. QML wants
    // ints here — a fractional pixelSize is rejected outright.
    readonly property int fontHeading: 18
    readonly property int fontBase:    16
    readonly property int fontSmall:   14
    // Coded labels and machine values (model ids, SEC.01, keycaps) — Martian Mono, bundled in
    // teleprompter/fonts and registered at startup (falls back silently if the file is missing).
    readonly property string fontMono: "Martian Mono"
    // Instrument Serif is bundled and registered too, but DEPLOYED NOWHERE yet — reserved for a
    // serif accent on Thomas's explicit say-so. Do not reference this token until then.
    readonly property string fontSerif: "Instrument Serif"

    // Model editor card — a denser scale than the window's 18/16/14 (a card packs many controls
    // into one tile). Named by role so the sizes live here, not scattered as literals.
    readonly property int fontCardName:  22   // the provider name
    readonly property int fontCardLabel: 13   // Model / Effort / Extended thinking / Notes
    readonly property int fontCardMeta:  12   // mono model ids, the key-status footer

    // Icons — Material Symbols Outlined (bundled in teleprompter/fonts, subset to the glyphs the
    // window uses). Drawn as font text, not hand-authored paths, so weight/optical-size are real
    // font axes, not stroke fudges (Thomas, 2026-07-27). A call site picks a size by role; the
    // Glyph component feeds `iconWeight` to the font's `wght` axis (light, per Thomas).
    readonly property string fontIcon: "Material Symbols Outlined"
    readonly property int iconWeight: 300
    readonly property int iconSm: 16
    readonly property int iconMd: 19
    readonly property int iconLg: 24
    // Dropdown popup: show at most this many rows, then scroll (a fetched model list can be 100+).
    readonly property int dropdownRows: 8

    // ── vertical rhythm ─────────────────────────────────────────────────────
    // ONE ratio for every wrapped string in the window, applied as a FIXED line box (the mode
    // Overlay.qml uses). Qt's proportional `lineHeight` multiplies the font's natural height
    // and inflates a SINGLE line too, which is what made a one-line description sit taller
    // than the gap above it — the label/description pair looked wrong at some widths and
    // right at others. A fixed box makes the same string occupy the same height everywhere.
    readonly property real lineHeightUi: 1.35
    readonly property int rowGap: 4                  // a label to its description
    // Group rhythm. ONE rule for the space above every heading and below it, so "Profile" and
    // "Preferences" cannot drift apart. The first heading in a pane takes no top gap — the
    // scroll area's own top clearance already gives it room.
    readonly property int groupGapTop: 34
    readonly property int groupGapBottom: 6
    function lineBox(px) { return Math.round(px * lineHeightUi) }
}
