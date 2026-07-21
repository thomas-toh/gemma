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
    // 600, not the mockup's 500: that 500 was Instrument Sans. Inter reads optically lighter
    // at the same number (and Qt renders a touch thinner than a browser), so matching the
    // mockup's WEIGHT would not match its LOOK. Inter is variable, so 550 also works if 600
    // is a shade heavy.
    readonly property int  fontWeight: Font.DemiBold // 600
    readonly property real lineHeight: 1.3

    // A point on the scrim ramp: f is the fraction of full strength (1.0 = opaquest). Lets a
    // gradient keep its own CURVE while the colour and peak strength stay tokenised.
    function scrim(f) { return Qt.rgba(surface.r, surface.g, surface.b, opacityScrim * f) }

    // ── motion ──────────────────────────────────────────────────────────────
    readonly property int durationResize: 340        // pill open/close
    readonly property int durationScroll: 200        // teleprompter glide
    readonly property int durationBars: 90           // mic bar smoothing
}
