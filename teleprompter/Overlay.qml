// The Teleprompter island (component P). Locked design: sandbox/teleprompter-mockup.html;
// window recipe + concave-corner path proven in sandbox/qml_spike/ (see NOTES.md).
//
// Solid black, fused to the top screen edge: bottom corners round inward, top corners flare
// OUTWARD into the edge. Built as a plain Rectangle plus two small flare pieces — only the
// outward flares need a real path, because Rectangle (like CSS border-radius) rounds inward.
//
// Everything here is driven by the `overlay` context property (teleprompter/model.py); the
// island renders what arrives and never talks back (Contract P, D19).
import QtQuick
import QtQuick.Shapes
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
    // Measured from the font, at the WIDEST reading it can ever show (both readings appear at
    // once during the acceptance run). A guessed constant undersized it; sizing to the CURRENT
    // reading would reflow the reply every time a number arrived.
    readonly property string latencyWidest: "fb 88888ms   word 88888ms"
    readonly property int latencyGutter:
        overlay.showLatency ? Math.ceil(latencyFm.advanceWidth(latencyWidest)) + 16 : 0
    // `reducedMotion` is a context property (Windows' "Show animations" setting, resolved in
    // __main__.py). Layout transitions collapse to instant; the mic bars keep their smoothing,
    // because they carry information and unsmoothed they read as jitter rather than as level.
    readonly property int moveMs: reducedMotion ? 0 : Theme.durationResize
    readonly property int scrollMs: reducedMotion ? 0 : Theme.durationScroll
    readonly property int fadeMs: reducedMotion ? 0 : Theme.durationFade
    // The family arrives as the `fontFamily` context property: QML's font.family takes ONE
    // name (there is no CSS-style chain), so __main__.py walks FONT_STACK against the fonts
    // actually installed and hands in the winner. Install Instrument Sans for the real thing.

    // --- what to show ---
    readonly property string st: overlay.state
    // The reply replaces the prompt — never stacked (locked design). A fault outranks both.
    readonly property bool isError: overlay.error !== ""
    // ...but NOT until the prompt has finished revealing. `bodyText` used to flip the instant
    // the first brain delta arrived, and the prefix test further down then read the new string
    // as "not a continuation" and reset the typewriter to zero — so any prompt longer than
    // about eleven words lost its tail, every warm turn. A *time* dwell cannot fix that: any
    // dwell shorter than the reveal truncates it exactly the same way. The invariant is
    // finish revealing → hold → swap, and only this side knows when the first part is done.
    // A fault swaps immediately: it outranks the prompt and is the more urgent thing to read.
    readonly property string prompt: overlay.transcript
    property bool promptShown: false
    onPromptChanged: promptShown = false            // a new turn earns a fresh hold
    readonly property bool replyReady: overlay.reply !== "" && (promptShown || prompt === "")
    readonly property string bodyText: isError ? overlay.error
                                     : (replyReady ? overlay.reply : prompt)
    // Has the typewriter caught up with everything it has been given?
    readonly property bool revealDone: reveal.shown >= bodyText.length

    Timer {                                   // the prompt's hold, before the reply takes over
        id: promptHold
        interval: Theme.durationPromptHold
        running: !root.promptShown && !root.isError && root.prompt !== ""
                 && root.bodyText === root.prompt && root.revealDone
        onTriggered: root.promptShown = true
    }

    // --- when the island stops showing (D24) ---
    // `idle` from the daemon means the DAEMON is finished — not "blank". How long an answer
    // stays up is a fact about the reveal, and this is the only process that can see it. The
    // daemon owned this decision for two revisions and blanked answers mid-sentence both times.
    readonly property bool busy: st === "listening" || st === "thinking"
                                 || st === "speaking" || st === "error"
    property bool hidden: false                     // dwell expired, or the user dismissed
    onBusyChanged: if (busy) hidden = false         // a new turn always brings the island back
    // `hidden` outranks `busy` deliberately: pressing Esc while Gemma is still thinking must
    // take the island away THAT INSTANT. If this read `busy || …` the island would linger
    // until the daemon got round to publishing its abort — which is the round trip D24 exists
    // to remove, and it would be longest exactly when the daemon is wedged.
    readonly property bool showing: !hidden && (busy || bodyText !== "")

    Timer {                                   // the answer's dwell — the walked-away backstop
        id: answerDwell
        objectName: "answerDwell"             // reached by name from the self-check
        interval: Theme.durationAnswerDwell
        // Restarts on every newly revealed word, so the count only ever runs from the moment
        // the last of the text actually appeared.
        running: !root.busy && !root.hidden && root.bodyText !== "" && root.revealDone
        onTriggered: root.hidden = true
    }

    // Esc, handled in __main__.py, which owns the key because it owns the window. Hiding is
    // local and immediate — the daemon is told separately and never waited on.
    Connections {
        target: overlay
        function onDismissed() { root.hidden = true }
    }
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

    // The WINDOW never moves or resizes: a fixed, fully transparent, click-through frame at the
    // island's largest possible size, with the island animating INSIDE it. Animating the window
    // means native move/resize operations that land a frame apart from the scene graph — newly
    // exposed area paints late, and the silhouette can be clipped mid-growth. Keep it fixed.
    //
    // DEPENDS on WS_EX_TRANSPARENT (stamped in __main__.py): the frame is mostly empty space, and
    // without that style it would swallow clicks across all of it. Never remove one alone.
    width: openW + 2 * flare                     // widest the island can ever be
    height: baseH + (maxLines - 1) * lineBox     // tallest it can ever be
    readonly property int islandW: (open ? openW : compactW) + 2 * flare
    // A single line is ALWAYS exactly baseH, and each extra line adds exactly one whole line
    // box, so the bottom gap stays padBottom however many lines show. Growth stops at
    // maxLines; past that the text scrolls instead.
    readonly property int shownLines: Math.max(1, Math.min(measure.lineCount, maxLines))
    readonly property int scrolled: Math.max(0, measure.lineCount - maxLines)
    // Where the next word ends (space included). Drives the measurer, so growth runs one word
    // ahead of what is on screen.
    function wordEnd(from) {
        if (from >= bodyText.length)
            return bodyText.length;
        var i = bodyText.indexOf(" ", from);
        return i < 0 ? bodyText.length : i + 1;
    }
    readonly property int pendingEnd: wordEnd(reveal.shown)
    // The pill's TARGET size. `animW`/`animH` are the live, animating values every visual is
    // drawn from — one pair of numbers, so the silhouette, the text, the bars and the readout
    // cannot disagree about where the island is on any given frame.
    readonly property int islandH: open ? baseH + (shownLines - 1) * lineBox : baseH
    property real animW: islandW
    property real animH: islandH
    Behavior on animW { NumberAnimation { duration: root.moveMs; easing.type: Easing.InOutCubic } }
    Behavior on animH { NumberAnimation { duration: root.moveMs; easing.type: Easing.InOutCubic } }
    // Centred in the fixed frame. Both edges therefore move by the same amount in the same
    // frame — the asymmetry came from this being a native window move racing a native resize.
    readonly property real islandX: (width - animW) / 2

    // Measures the text INCLUDING the word about to appear, so the island can finish growing
    // before that word is revealed rather than the word landing on a box still catching up.
    // Never drawn, and deliberately NOT inside the viewport — it is layout arithmetic, not
    // part of the clipped content.
    // Every layout property is taken FROM textItem, never restated: if the two ever wrapped
    // differently, lineCount would describe a layout that is not on screen and the gate below
    // would silently let words land early.
    Text {
        id: measure
        objectName: "measure"           // reached by name from the self-check
        visible: false
        width: textItem.width
        wrapMode: textItem.wrapMode
        font: textItem.font
        lineHeight: textItem.lineHeight
        lineHeightMode: textItem.lineHeightMode
        text: root.bodyText.substring(0, root.pendingEnd)
    }

    // How far the fade may reach before it would dim a real glyph. The first line's BOX starts
    // at padTop, but its ink starts lower: FixedHeight centres the natural line in the box, and
    // there is blank space above capitals. Derived from live metrics, so changing the Theme's
    // fontSize or lineHeight re-derives it instead of silently dimming text.
    FontMetrics { id: fm; font: textItem.font }
    readonly property real inkTop: padTop + (lineBox - fm.height) / 2 + (fm.ascent - fm.capitalHeight)
    readonly property real fadeH: Math.max(4, inkTop - 0.5)   // ~16px at 18/1.3

    // Gone = nothing to say and nothing left to read (D24 — no longer simply `st === "idle"`).
    // The tray, not the island, says "alive".
    visible: showing || entrance > 0.01
    opacity: entrance
    color: "transparent"
    flags: Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint | Qt.Tool
           | Qt.WindowDoesNotAcceptFocus
    // virtualX/Y, not 0 — Screen.width is this screen's width but x is in VIRTUAL-DESKTOP
    // coordinates, so on a multi-monitor desktop (or the Mac with an external display, D10)
    // omitting the origin puts the island on the wrong screen. Correct on a single display too.
    x: Screen.virtualX + Math.round((Screen.width - width) / 2)
    y: Screen.virtualY

    // Fades the whole window rather than wrapping the contents in a transformed Item: the
    // visuals are interleaved with the declarations they depend on, so wrapping reparents those
    // too and every `root.<prop>` breaks. `visible` lingers so the fade-out can finish.
    property real entrance: showing ? 1 : 0
    Behavior on entrance {
        NumberAnimation { duration: root.fadeMs; easing.type: Easing.OutCubic }
    }

    // ---- the silhouette: a plain box, with the two flares stuck on the sides ----
    // The moving part is a plain Rectangle — cheap, and antialiased without help. The only real
    // curves are the two flares, and those NEVER change size: the island grows and shrinks around
    // them, so they only move. Nothing re-tessellates during an animation.
    Rectangle {
        id: slab
        x: root.islandX + root.flare        // the flares live outside the body, one on each side
        width: root.animW - 2 * root.flare
        height: root.animH
        color: Theme.surface
        // Fused to the top screen edge, so only the bottom corners are round. Per-corner radius
        // is a Rectangle feature (Qt 6.7+) — no path needed for the convex half of the shape.
        bottomLeftRadius: root.botR
        bottomRightRadius: root.botR
        topLeftRadius: 0
        topRightRadius: 0
    }

    // The flares: concave fillets that flow outward from the body into the screen edge. These
    // DO need a real path — Rectangle (like CSS border-radius) can only round inward.
    // A Repeater rather than two hand-written Shapes: mirrored geometry written twice is
    // geometry that can be edited once, and the two sides would silently stop matching.
    Repeater {
        model: 2                                       // 0 = left flare, 1 = right
        Shape {
            id: flare
            required property int index
            readonly property bool isLeft: index === 0
            // Local coords, an 18x18 box: `ox` is the edge against the screen corner, `bx` the
            // edge against the body. Naming them makes one path serve both mirrorings.
            readonly property real ox: isLeft ? 0 : root.flare
            readonly property real bx: isLeft ? root.flare : 0

            x: isLeft ? slab.x - root.flare : slab.x + slab.width
            y: 0
            width: root.flare
            height: root.flare
            antialiasing: true
            // CurveRenderer, not the default GeometryRenderer: the latter antialiases by
            // multisampling the window surface, and this window is frameless/translucent with
            // no MSAA, so the curve came out hard-edged and pixellated.
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                fillColor: Theme.surface
                strokeWidth: 0
                strokeColor: "transparent"
                startX: flare.ox                                    // the screen corner
                startY: 0
                PathLine { x: flare.bx; y: 0 }                      // along the top edge
                PathLine { x: flare.bx; y: root.flare }             // down the body's side
                PathQuad {                                          // and back out, concave
                    controlX: flare.bx; controlY: 0
                    x: flare.ox;        y: 0
                }
            }
        }
    }

    // ---- thinking: a morphing status word ----
    // Ported from alfred-test (renderer/views/session-view.js, startTypewriter): a word rests,
    // then the next one wipes over it left-to-right, one column per tick. Alfred marks the
    // sweep with a block caret; that reads as monospace, so here the letters just flip — the
    // wipe carries itself. Words describe TRANSCRIBING, because that is the phase this covers:
    // it shows from end-of-speech until the transcript lands, then the prompt takes the slot.
    readonly property bool loaderOn: st === "thinking" && bodyText === ""

    // The wipe's state lives ON the timer that drives it, like the typewriter's `reveal.shown`
    // below, rather than as loose mutable properties on the Window. Only `shown` is read outside.
    Timer {                                   // the wipe: one column per tick
        id: sweep
        objectName: "sweep"                   // reached by name from the self-check
        property var words: [
            "transcribing", "deciphering", "decoding", "parsing",
            "untangling", "interpreting", "unpicking", "resolving",
        ]
        property string shown: ""             // the settled-or-mid-wipe word, bare
        property string wordFrom: ""
        property string wordTo: ""
        property int at: 0
        property string last: ""
        property bool active: false

        // The bare word only — the ellipsis is static punctuation appended at render. If it
        // took part in the wipe, a longer outgoing word would leave its own "…" trailing for a
        // tick and you'd see "Interpreting……". (Alfred hides that behind its block caret.)
        function labelFor(w) { return w.charAt(0).toUpperCase() + w.slice(1) }

        function next() {
            var w = last;
            while (w === last && words.length > 1)
                w = words[Math.floor(Math.random() * words.length)];
            last = w;
            wordFrom = shown;
            wordTo = labelFor(w);
            at = 0;
            active = true;
        }

        interval: 28
        repeat: true
        running: root.loaderOn && active
        onTriggered: {
            var span = Math.max(wordFrom.length, wordTo.length);
            if (at < span) {
                shown = wordTo.slice(0, at) + wordFrom.slice(at);
                at++;
            } else {
                shown = wordTo;               // settled: rests until the next word
                active = false;
                hold.restart();
            }
        }
    }

    Timer {                                   // dwell on a settled word
        id: hold
        interval: 1500
        onTriggered: if (root.loaderOn) sweep.next()
    }

    onLoaderOnChanged: {
        hold.stop();
        sweep.shown = "";
        if (loaderOn) {
            sweep.last = "";
            sweep.next();
        } else {
            sweep.active = false;
        }
    }

    // ---- listening: bars driven by the real mic level ----
    // Present ONLY while 'mic' messages are arriving (feed.py drops the level to 0 when they
    // stop) — spec/50's truthful indicator, never inferred from state alone.
    Row {
        id: bars
        visible: root.st === "listening"
        x: root.islandX + (root.animW - width) / 2
        y: (root.animH - height) / 2
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
        x: root.islandX + root.flare + root.padSide
        y: root.fadeTop
        width: Math.max(0, root.animW - 2 * (root.flare + root.padSide))
        height: Math.max(0, root.animH - root.fadeTop - root.padBottom)
        clip: true
        visible: root.open

        Text {
            id: textItem
            objectName: "body"              // the reveal/scroll self-check reaches it by name
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
            // EVERYTHING reveals here, prompt and reply alike — never raw. Brain deltas arrive as
            // a few fat chunks, so leaning on them to pace the text renders it as a block.
            text: root.bodyText.substring(0, reveal.shown)
        }

        // The morphing status word occupies the SAME slot the prompt will land in — same left
        // edge, same baseline — so when the transcript arrives it simply replaces the word.
        Text {
            id: statusWord
            visible: root.loaderOn
            x: 0
            y: root.padTop - root.fadeTop
            text: sweep.shown ? sweep.shown + "…" : ""
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
    // for (--latency, or the tray toggle). Targets come from spec/schemas/targets.json via the
    // `targets` context property (D25) — no longer hardcoded here, so a number cannot be quoted
    // two ways. A reading past a GATE renders at full strength so a miss is obvious at a glance.
    readonly property int fbTarget: targets.feedback.ms
    readonly property int fwTarget: targets.first_word.ms
    // first_word is 'measured', not a gate (D25): under generate-then-play it is a reply-length
    // proxy, so the readout must show it neutrally and NEVER flag it red. If targets.json ever
    // reclassifies it to a gate, this expression starts colouring it — the reclassification is
    // data, not something baked into the renderer.
    readonly property bool fwIsGate: targets.first_word.kind !== "measured"

    FontMetrics { id: latencyFm; font: latencyText.font }

    Text {
        id: latencyText
        objectName: "latency"           // reached by name from the self-check
        visible: overlay.showLatency && (overlay.feedbackMs > 0 || overlay.firstWordMs > 0)
        x: root.islandX + root.animW - root.flare - root.padSide - width
        y: root.padTop
        color: (overlay.feedbackMs > root.fbTarget
                || (root.fwIsGate && overlay.firstWordMs > root.fwTarget))
               ? Theme.textPrimary : Theme.textMuted
        font.family: fontFamily
        font.pixelSize: 11
        text: (overlay.feedbackMs > 0 ? "fb " + Math.round(overlay.feedbackMs) + "ms" : "")
              + (overlay.feedbackMs > 0 && overlay.firstWordMs > 0 ? "   " : "")
              + (overlay.firstWordMs > 0 ? "word " + Math.round(overlay.firstWordMs) + "ms" : "")
    }

    // The typewriter, for prompt AND reply. Two cases have to be told apart:
    //   GROWS  — a reply delta appends to what is already there: keep typing from where we are.
    //   CHANGES — a new prompt, or the reply replacing the prompt: start over from zero.
    // A prefix test distinguishes them without the model having to say which happened.
    property string revealedFrom: ""
    onBodyTextChanged: {
        var grew = bodyText.length >= revealedFrom.length
                   && bodyText.substring(0, revealedFrom.length) === revealedFrom;
        if (!grew)
            reveal.shown = 0;
        revealedFrom = bodyText;
    }

    Timer {
        id: reveal
        property int shown: 0
        interval: Theme.durationWord
        repeat: true
        running: shown < root.bodyText.length
        onTriggered: {
            // Hold the word back until the island has FINISHED moving — BOTH the height and the
            // scroll. `measure` already counts the pending word, so islandH and the scroll offset
            // are the targets. Gating only growth let words land mid-scroll past three lines.
            var targetY = root.padTop - root.fadeTop - root.scrolled * root.lineBox;
            if (Math.abs(root.animH - root.islandH) > 0.5
                    || Math.abs(textItem.y - targetY) > 0.5)
                return;
            reveal.shown = root.pendingEnd;
        }
    }

}
