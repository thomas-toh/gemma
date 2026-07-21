// The Teleprompter island (component P). Locked design: sandbox/teleprompter-mockup.html;
// window recipe + concave-corner path proven in sandbox/qml_spike/ (see NOTES.md).
//
// Solid black, fused to the top screen edge: bottom corners round inward, top corners flare
// OUTWARD into the edge. The silhouette is a filled Canvas path because Rectangle (like CSS
// border-radius) only rounds inward — the outward flares need a real path.
//
// Everything here is driven by `model` (teleprompter/model.py); the island never talks back.
import QtQuick
import QtQuick.Window
import teleprompter                            // Theme — the design tokens (Theme.qml)

Window {
    id: root

    // --- locked geometry / palette (mockup v7) ---
    readonly property int compactW: 150
    readonly property int openW: 440
    readonly property int baseH: 46
    readonly property real flare: 18            // outward concave fillet at the top edge
    readonly property real botR: 13.5           // bottom corner radius (convex)
    // Colour, opacity, type and motion all come from the Theme singleton (Theme.qml) — see
    // the note there on why island geometry stays local while those do not.
    // Whole pixels by construction. Qt rounds the WINDOW height to integers, so a fractional
    // line box (18 * 1.3 = 23.4) left the real height short of what the layout assumed — the
    // shortfall came out of the bottom, shrinking the gap AND clipping the last line's
    // descenders by up to 0.8px at three lines. Snapping the box to a whole pixel makes every
    // derived height exact, so the bottom gap is identical at 1, 2 and 3 lines.
    readonly property int lineBox: Math.round(Theme.fontSize * Theme.lineHeight)   // 23
    readonly property int padSide: 20                    // inside the body, excluding the flare
    // padTop + lineBox + padBottom is FORCED to equal baseH — otherwise the pill would grow the
    // moment a single line of text appears. So the vertical padding can only be redistributed,
    // never added to. floor() (not round()) hands the odd pixel to the BOTTOM, so text sits a
    // hair high — the mockup's optical intent, which split 12/14 the same way.
    readonly property int padTop: Math.floor((baseH - lineBox) / 2)                // 11
    readonly property int padBottom: baseH - padTop - lineBox                      // 12
    readonly property int maxLines: 3                    // island stops growing here, then scrolls
    readonly property real fadeTop: 0                    // viewport starts at the screen edge, so
                                                         // the scrolled-off line peeks through
    // FINAL layout width — the text never reflows mid-animation. Shrinks by the gutter when
    // the latency readout is on, so an instrument can never overlap a reply.
    readonly property real textW: openW - 2 * padSide - latencyGutter
    readonly property int latencyGutter: overlay.showLatency ? 96 : 0
    // `reducedMotion` is a context property (Windows' "Show animations" setting, resolved in
    // __main__.py). Layout transitions collapse to instant; the mic bars keep their smoothing,
    // because they carry information and unsmoothed they read as jitter rather than as level.
    readonly property int moveMs: reducedMotion ? 0 : Theme.durationResize
    readonly property int scrollMs: reducedMotion ? 0 : Theme.durationScroll
    // The family arrives as the `fontFamily` context property: QML's font.family takes ONE
    // name (there is no CSS-style chain), so __main__.py walks FONT_STACK against the fonts
    // actually installed and hands in the winner. Install Instrument Sans for the real thing.

    // --- what to show ---
    readonly property string st: overlay.state
    // The reply replaces the prompt — never stacked (locked design). A fault outranks both.
    readonly property bool isError: overlay.error !== ""
    readonly property string bodyText: isError ? overlay.error
                                     : (overlay.reply !== "" ? overlay.reply : overlay.transcript)
    readonly property bool isPrompt: !isError && overlay.reply === "" && overlay.transcript !== ""
    // Two sizes, nothing else: LISTENING is the minimised pill with the wave; every other
    // visible state — thinking, prompt, reply, fault — is the standard width, with the status
    // word or the text sitting in the SAME left-aligned slot, so the handoff from
    // "Transcribing…" to your prompt has nothing to animate. Idle hides the window outright.
    // Listed positively rather than as "not listening": the orchestrator publishes the fault
    // MESSAGE before it publishes state:error, so text can arrive while the state still says
    // listening — `bodyText` has to be able to open the pill on its own or that text is lost.
    // It also keeps `idle` closed, which "not listening" would not.
    readonly property bool open: bodyText !== "" || st === "thinking"
                                 || st === "speaking" || st === "error"

    readonly property int bodyW: open ? openW : compactW
    width: bodyW + 2 * flare                     // flares live outside the body
    // A single line is ALWAYS exactly baseH, and each extra line adds exactly one whole line
    // box — so the bottom gap stays padBottom no matter how many lines show, and the blinking
    // caret cannot twitch it. Growth stops at maxLines; past that the text scrolls.
    readonly property int shownLines: Math.max(1, Math.min(textItem.lineCount, maxLines))
    readonly property int scrolled: Math.max(0, textItem.lineCount - maxLines)
    // The pill's height. Kept distinct from the window height so a future surface can hang
    // below without every island-shaped thing re-deriving itself.
    readonly property int islandH: open ? baseH + (shownLines - 1) * lineBox : baseH
    height: islandH

    // How far the fade may reach before it would dim a real glyph. The first line's BOX starts
    // at padTop, but its ink starts lower: FixedHeight centres the natural line in the box, and
    // there is blank space above capitals. Derived from live metrics, so changing the Theme's
    // fontSize or lineHeight re-derives it instead of silently dimming text.
    FontMetrics { id: fm; font: textItem.font }
    readonly property real inkTop: padTop + (lineBox - fm.height) / 2 + (fm.ascent - fm.capitalHeight)
    readonly property real fadeH: Math.max(4, inkTop - 0.5)   // ~16px at 18/1.3

    // idle = asleep = gone (spec/40, status.json). The tray, not the island, says "alive".
    visible: st !== "idle"
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
           | Qt.WindowDoesNotAcceptFocus
    // virtualX/Y, not 0 — Screen.width is this screen's width but x is in VIRTUAL-DESKTOP
    // coordinates, so on a multi-monitor desktop (or the Mac with an external display, D10)
    // omitting the origin puts the island on the wrong screen. Correct on a single display too.
    x: Screen.virtualX + Math.round((Screen.width - width) / 2)
    y: Screen.virtualY

    Behavior on width  { NumberAnimation { duration: root.moveMs; easing.type: Easing.InOutCubic } }
    Behavior on height { NumberAnimation { duration: root.moveMs; easing.type: Easing.InOutCubic } }

    // ---- the silhouette ----
    Canvas {
        id: island
        width: parent.width
        height: root.islandH
        antialiasing: true
        onPaint: {
            var ctx = getContext("2d");
            var W = width, H = height, F = root.flare, R = root.botR;
            var bl = F, br = W - F;              // body spans [flare, W-flare]
            ctx.reset();
            ctx.beginPath();
            ctx.moveTo(0, 0);                    // outer top-left, on the screen edge
            ctx.lineTo(W, 0);                    // across the top edge
            ctx.quadraticCurveTo(br, 0, br, F);  // top-right: flare outward into the edge
            ctx.lineTo(br, H - R);
            ctx.quadraticCurveTo(br, H, br - R, H);   // bottom-right: convex round
            ctx.lineTo(bl + R, H);
            ctx.quadraticCurveTo(bl, H, bl, H - R);   // bottom-left: convex round
            ctx.lineTo(bl, F);
            ctx.quadraticCurveTo(bl, 0, 0, 0);   // top-left: flare outward into the edge
            ctx.closePath();
            ctx.fillStyle = Theme.surface;
            ctx.fill();
        }
        // the path depends on the box, so repaint whenever it changes
        onWidthChanged: requestPaint()
        onHeightChanged: requestPaint()
    }

    // ---- thinking: a morphing status word ----
    // Ported from alfred-test (renderer/views/session-view.js, startTypewriter): a word rests,
    // then the next one wipes over it left-to-right, one column per tick. Alfred marks the
    // sweep with a block caret; that reads as monospace, so here the letters just flip — the
    // wipe carries itself. Words describe TRANSCRIBING, because that is the phase this covers:
    // it shows from end-of-speech until the transcript lands, then the prompt takes the slot.
    readonly property bool loaderOn: st === "thinking" && bodyText === ""
    readonly property var loaderWords: [
        "transcribing", "deciphering", "decoding", "parsing",
        "untangling", "interpreting", "unpicking", "resolving",
    ]
    property string loaderText: ""
    property string sweepFrom: ""
    property string sweepTo: ""
    property int sweepAt: 0
    property string lastWord: ""
    property bool sweeping: false

    // The bare word only — the ellipsis is static punctuation appended at render. If it took
    // part in the wipe, a longer outgoing word would leave its own "…" trailing for one tick
    // and you'd see "Interpreting……". (Alfred hides that behind its block caret; we have none.)
    function labelFor(w) { return w.charAt(0).toUpperCase() + w.slice(1) }

    function nextWord() {
        var w = lastWord;
        while (w === lastWord && loaderWords.length > 1)
            w = loaderWords[Math.floor(Math.random() * loaderWords.length)];
        lastWord = w;
        sweepFrom = loaderText;
        sweepTo = labelFor(w);
        sweepAt = 0;
        sweeping = true;
    }

    onLoaderOnChanged: {
        hold.stop();
        if (loaderOn) {
            loaderText = "";
            lastWord = "";
            nextWord();
        } else {
            sweeping = false;
            loaderText = "";
        }
    }


    Timer {                                   // the wipe: one column per tick
        id: sweep
        interval: 28
        repeat: true
        running: root.loaderOn && root.sweeping
        onTriggered: {
            var span = Math.max(root.sweepFrom.length, root.sweepTo.length);
            if (root.sweepAt < span) {
                root.loaderText = root.sweepTo.slice(0, root.sweepAt)
                                + root.sweepFrom.slice(root.sweepAt);
                root.sweepAt++;
            } else {
                root.loaderText = root.sweepTo;   // settled: rests until the next word
                root.sweeping = false;
                hold.restart();
            }
        }
    }

    Timer {                                   // dwell on a settled word
        id: hold
        interval: 1500
        repeat: false
        onTriggered: if (root.loaderOn) root.nextWord()
    }

    // ---- listening: bars driven by the real mic level ----
    // Present ONLY while 'mic' messages are arriving (feed.py drops the level to 0 when they
    // stop) — spec/50's truthful indicator, never inferred from state alone.
    Row {
        id: bars
        visible: root.st === "listening"
        x: (root.width - width) / 2
        y: (root.islandH - height) / 2
        height: 26
        spacing: 4
        Repeater {
            model: 7
            Rectangle {
                width: 3.5
                radius: 2
                color: Theme.textPrimary
                anchors.verticalCenter: parent.verticalCenter
                // a fixed per-bar weighting so the row reads as a level meter, not 7 clones
                readonly property real weight: 0.55 + 0.45 * Math.sin(1.1 * index + 0.6)
                height: Math.max(3, Math.min(26, 3 + 23 * overlay.mic * weight))
                Behavior on height { NumberAnimation { duration: Theme.durationBars; easing.type: Easing.OutQuad } }
            }
        }
    }

    // ---- transcript / reply / fault ----
    // Viewport: clips to the island's inner area, so as the island animates open (or grows a
    // line) the text is REVEALED rather than spilling outside the black. Its width follows the
    // animating island, but the Text inside is laid out at the final width — so the line count
    // never changes mid-animation and the height animates once, straight to its target.
    Item {
        id: viewport
        x: root.flare + root.padSide
        y: root.fadeTop
        width: Math.max(0, root.width - 2 * (root.flare + root.padSide))
        height: Math.max(0, root.islandH - root.fadeTop - root.padBottom)
        clip: true
        visible: root.open

        Text {
            id: textItem
            width: root.textW               // FINAL width, never the animating one
            // Top-anchored at a fixed offset and scrolled by whole lines. Deliberately does NOT
            // read the island height: that dependency is what made the text jump while the
            // height animated. The island grows downward around it instead.
            y: root.padTop - root.fadeTop - root.scrolled * root.lineBox
            Behavior on y { NumberAnimation { duration: root.scrollMs; easing.type: Easing.OutCubic } }
            wrapMode: Text.WordWrap
            color: root.isError ? Theme.textMuted : Theme.textPrimary
            font.family: fontFamily             // resolved in __main__.py, not guessed here
            font.pixelSize: Theme.fontSize
            font.weight: Theme.fontWeight
            lineHeight: root.lineBox
            lineHeightMode: Text.FixedHeight    // pixels, not a multiple of natural height
            // The reply streams in as real deltas, so it types itself. Only the prompt —
            // which lands as one block at end-of-speech (D14) — gets a cosmetic reveal.
            // The caret rides inside the string so it stays put on wrapped lines.
            readonly property bool typing: root.isPrompt && reveal.shown < root.bodyText.length
            text: root.isPrompt
                  ? root.bodyText.substring(0, reveal.shown) + (typing && blink.on ? "▌" : "")
                  : root.bodyText
        }

        // The morphing status word occupies the SAME slot the prompt will land in — same left
        // edge, same baseline — so when the transcript arrives it simply replaces the word.
        Text {
            id: statusWord
            visible: root.loaderOn
            x: 0
            y: root.padTop - root.fadeTop
            text: root.loaderText ? root.loaderText + "…" : ""
            color: Theme.textMuted                  // a status word, not content
            font.family: fontFamily
            font.pixelSize: Theme.fontSize
            font.weight: Theme.fontWeight
            lineHeight: root.lineBox
            lineHeightMode: Text.FixedHeight
        }

        // "there is more above": the tail of the scrolled-off line shows through and dissolves
        // upward. Deliberately light and gradual — it reaches transparency by `fadeH`, which is
        // derived to stop just short of the first line's ink, so nothing legible is dimmed.
        Rectangle {
            anchors.left: parent.left
            anchors.right: parent.right
            anchors.top: parent.top
            height: root.fadeH
            visible: root.scrolled > 0
            gradient: Gradient {                    // curve is local; colour + peak are tokens
                GradientStop { position: 0.00; color: Theme.scrim(1.00) }
                GradientStop { position: 0.45; color: Theme.scrim(0.59) }
                GradientStop { position: 0.75; color: Theme.scrim(0.25) }
                GradientStop { position: 1.00; color: Theme.scrim(0.00) }
            }
        }
    }

    // ---- latency readout: D13's instrument for the M0 acceptance run ----
    // status.json calls this "not user-facing chrome by default", so it is off unless asked
    // for (--latency, or the tray toggle). spec/40 targets: perceptible feedback < 1500 ms,
    // first spoken word < 4000 ms — a reading past its target renders at full strength so a
    // miss is obvious at a glance during the run.
    readonly property int fbTarget: 1500
    readonly property int fwTarget: 4000

    Text {
        visible: overlay.showLatency && (overlay.feedbackMs > 0 || overlay.firstWordMs > 0)
        x: root.width - root.flare - root.padSide - width
        y: root.padTop
        color: (overlay.feedbackMs > root.fbTarget || overlay.firstWordMs > root.fwTarget)
               ? Theme.textPrimary : Theme.textMuted
        font.family: fontFamily
        font.pixelSize: 11
        text: (overlay.feedbackMs > 0 ? "fb " + Math.round(overlay.feedbackMs) + "ms" : "")
              + (overlay.feedbackMs > 0 && overlay.firstWordMs > 0 ? "   " : "")
              + (overlay.firstWordMs > 0 ? "word " + Math.round(overlay.firstWordMs) + "ms" : "")
    }

    // cosmetic typewriter for the prompt only
    Timer {
        id: reveal
        property int shown: 0
        interval: 12
        repeat: true
        running: root.isPrompt && shown < root.bodyText.length
        onTriggered: shown = Math.min(shown + 1, root.bodyText.length)
    }

    Timer {                                       // caret blink while the prompt reveals
        id: blink
        property bool on: true
        interval: 500
        repeat: true
        running: textItem.typing && !reducedMotion
        onTriggered: on = !on
    }
    onBodyTextChanged: reveal.shown = root.isPrompt ? 0 : root.bodyText.length
}
