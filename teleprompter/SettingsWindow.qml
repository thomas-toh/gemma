// The settings window (spec/70, D29 — re-cut by D40) — the only surface besides the island the
// user ever sees.
//
// D40's brief: read as PART OF THE SYSTEM, not as an app with a look of its own. What that gave
// up, deliberately — the coded SEC.0n bands, the card rosters in scrolling bands, the three-way
// top-bar nav, the cool-neutral field, and Martian Mono on every machine value. What it keeps:
// every value, every default, and the `built: false` dimming rule.
//
// Still generated from `spec/schemas/settings.json` (hard rule 3): `cfg.panes` names the sidebar,
// `cfg.rowsFor`/`rowsInGroup` its rows, `cfg.meta[key]` each row's label, help, type and whether
// its consumer exists yet, `cfg.toolsFor` the tools behind a connector. Adding a knob is a JSON
// edit. Palette and type live in Theme.qml.
//
// Controls are drawn here rather than taken from Quick Controls' styled set: restyling stock
// controls to this austerity costs more than drawing a switch. Controls.Basic is imported for the
// three things worth borrowing — text entry, scrolling and popup dismissal.
import QtQuick
import QtQuick.Controls.Basic
import teleprompter

Window {
    id: root
    title: "Gemma — Settings"
    width: 1080
    height: 760
    minimumWidth: 900
    minimumHeight: 600
    color: Theme.surfaceShell

    // No native title bar: this file owns what the OS was doing — `startSystemMove` for dragging
    // (Aero Snap keeps working, because Windows is still the one moving the window) and
    // `startSystemResize` on the edges. The host asks DWM for rounded corners.
    flags: Qt.Window | Qt.FramelessWindowHint

    // The visible page. A PANE id now (D40), not one of three hand-named sections — the sidebar is
    // generated from the schema, so the nav and this property share one vocabulary.
    property string section: "general"
    property bool manageOpen: false
    property bool confirmOpen: false

    // Is a modal surface up? Every modal ORs into this ONE property, and the page below binds its
    // `enabled` to it — so the page cannot be scrolled, dragged or clicked out from under an open
    // sheet. A scrim that only swallows clicks does NOT cover this: Qt Quick's MouseArea has no
    // wheel signal at all, so the wheel goes straight past it to the Flickable behind (Thomas,
    // 2026-07-31). A disabled item receives no input of ANY kind — nothing a future input type can
    // slip through.
    readonly property bool modalOpen: manageOpen || confirmOpen

    readonly property int topH: 60          // the header row (Thomas)
    readonly property int grip: 6           // resize edge thickness
    readonly property int fadeHeight: 17    // the scroller's top clearance
    readonly property int sideW: 204
    readonly property int padX: 34          // the content's side margin

    // The Models table's right-hand columns, measured in from the right edge. Header labels and
    // row controls both read these, so the two cannot drift apart.
    readonly property int colKebabW: 30
    readonly property int colGap:    18
    readonly property int colActiveR: colKebabW + colGap                 // toggle's right edge
    readonly property int colKeyR:    colActiveR + 40 + colGap           // key text's right edge

    // Reduced motion is the machine's "show animations" setting, mirrored by the host (U-01).
    readonly property int t: reducedMotion ? 0 : Theme.durationControl

    // Release whatever holds the keyboard. A text field keeps its focus ring — and its cursor —
    // until something takes focus away, and clicking blank space is the gesture everyone expects
    // to do that. Called from the surfaces a press actually reaches: the page behind the rows,
    // the sidebar, and the header bar.
    function dropFocus() {
        if (activeFocusItem && activeFocusItem !== contentItem)
            activeFocusItem.focus = false
    }

    // Panes that draw themselves rather than a list of rows.
    function customPane(id) { return id === "models" || id === "connectors" }

    // The page's single header action, or "" for none.
    readonly property string pageAction: section === "models" ? "Add model" : ""

    readonly property string pageTitle: {
        for (var i = 0; i < cfg.panes.length; i++)
            if (cfg.panes[i].id === section)
                return cfg.panes[i].label
        return ""
    }

    // ── Add-a-model state ────────────────────────────────────────────────────
    // Held on the window rather than in the sheet so it survives the sheet being rebuilt, and so
    // `commitAdd` has one place to read from. Nothing here is written to disk until Save.
    property int addStep: 1
    property string addKind: "cloud"
    property string addProviderId: ""
    property string addKey: ""
    property bool addHasKey: false
    property string addModel: ""
    property string addEffort: ""
    property bool addThinking: false
    property string addTemperature: "0.7"
    property string addEndpoint: ""
    property bool addEditing: false
    property string confirmTarget: ""

    // The live probe outcome for the provider being added, and how to say it. Read off a tracked
    // property (cfg.probeStates) so this re-evaluates when a background fetch lands.
    readonly property string addProbe: addProviderId !== ""
                                       && cfg.probeStates[addProviderId] !== undefined
                                       ? cfg.probeStates[addProviderId] : "untested"
    readonly property string addProbeMessage: {
        var n = cfg.modelOptions[addProviderId] !== undefined
                ? cfg.modelOptions[addProviderId].length : 0
        switch (addProbe) {
        case "fetching":    return "Asking the provider…"
        case "ok":          return n + (n === 1 ? " model available" : " models available")
        case "auth":        return "The provider rejected that key."
        case "nokey":       return "No key saved yet."
        case "unreachable": return "Could not reach the provider. Check the connection."
        case "empty":       return "The key works, but this account has no usable models."
        case "error":       return "That did not work. See logs/gemma.log."
        default:            return ""
        }
    }

    function openAdd() {
        addStep = 1
        addEditing = false
        manageOpen = true
    }

    function beginAdd(pid) {
        var cat = cfg.catalog[pid]
        addKind = cat.where
        addEditing = false
        addProviderId = pid
        addKey = ""
        addHasKey = false
        addModel = ""
        addEffort = ""
        addThinking = false
        addTemperature = "0.7"
        addEndpoint = cat.endpoint !== undefined ? cat.endpoint : ""
        addStep = 2
    }

    function beginEdit(pid) {
        var cat = cfg.catalog[pid]
        var st = cfg.models[pid]
        addKind = cat.where
        addEditing = true
        addProviderId = pid
        addKey = ""
        // A stored key counts as present: the form is asking whether it can go on, not whether
        // you typed something just now.
        addHasKey = cat.auth !== "key" || cfg.keys[pid] === "stored"
        addModel = st && st.model ? st.model : ""
        addEffort = st && st.effort ? st.effort : ""
        addThinking = st ? st.thinking === true : false
        addTemperature = st && st.temperature !== undefined ? String(st.temperature) : "0.7"
        addEndpoint = st && st.endpoint !== undefined ? st.endpoint
                      : (cat.endpoint !== undefined ? cat.endpoint : "")
        addStep = 2
        manageOpen = true
        // Fill the picker from the stored key without waiting for a Test press. Cheap — a list
        // already held is not re-fetched.
        cfg.refreshModels(pid)
    }

    function commitAdd() {
        if (addProviderId === "")
            return
        // The key goes to the credential store, never into the settings file (spec/50 rule 10).
        // An empty box on an edit means "leave the stored key alone", not "clear it".
        if (addKind === "cloud" && addKey !== "")
            cfg.setKey(addProviderId, addKey)
        cfg.addProvider(addProviderId, {
            "model": addModel,
            "effort": addEffort !== "" ? addEffort : null,
            "thinking": addThinking,
            "temperature": addTemperature,
            "endpoint": addKind === "local" ? addEndpoint : null
        })
        addKey = ""
        addStep = 1
        manageOpen = false
    }

    // Material Symbols Outlined, bundled FULL rather than subset (Thomas, 2026-08-01), so an
    // icon is now one line here and nothing else — no re-cutting the font, no tofu risk.
    // NOTE the codepoints are the Symbols mapping, which differs from the older Material Icons
    // one the previous 14-glyph subset used (check E5CA not E668, close E14C not E5CD, edit
    // E150 not F097): every glyph had to be re-mapped when the file was swapped, not just the
    // new ones. Chevrons are the iOS pair (arrow_back_ios / arrow_forward_ios) plus
    // keyboard_arrow_down — bigger and evenly weighted, where expand_more's wide shallow V
    // read small beside 14px text (Thomas).
    QtObject {
        id: ico
        readonly property string cloud:     "\uE2BD"   // cloud               — a provider-hosted model
        readonly property string chip:      "\uE322"   // memory              — a local model
        readonly property string sparkle:   "\uE65F"   // auto_awesome        — the Ask brain
        readonly property string kebab:     "\uE5D4"   // more_vert           — a row's ⋯
        readonly property string check:     "\uE5CA"   // check               — selected option, stored key
        readonly property string chevron:   "\uE313"   // keyboard_arrow_down — a dropdown's indicator
        readonly property string plus:      "\uE145"   // add                 — add a model
        readonly property string trash:     "\uE872"   // delete              — remove a model
        readonly property string close:     "\uE14C"   // close               — dismiss a sheet / the window
        readonly property string minimize:  "\uE15B"   // remove              — window minimise
        readonly property string maximize:  "\uE3C1"   // crop_square         — window maximise
        readonly property string restore:   "\uE3E0"   // filter_none         — window restore
        readonly property string back:      "\uE5E0"   // arrow_back_ios      — step 2 → step 1
        readonly property string forward:   "\uE5E1"   // arrow_forward_ios   — a catalogue row
        readonly property string edit:      "\uE150"   // edit                — configure a model
        readonly property string search:    "\uE8B6"   // search              — the sidebar field
        readonly property string mic:       "\uE029"   // mic                 — the mic status mark
        readonly property string settings:  "\uE8B8"   // settings            — nav: General
        readonly property string plug:      "\uF102"   // electrical_services — nav: Connectors
        readonly property string box:       "\uF720"   // deployed_code       — nav: Model selection
        readonly property string keyboard:  "\uE312"   // keyboard            — nav: Triggers
        readonly property string lines:     "\uE8D2"   // subject             — nav: Dictation
        readonly property string info:      "\uE88E"   // info                — nav: About (unbuilt)
        readonly property string sun:       "\uE518"   // light_mode          — theme: light
        readonly property string moon:      "\uE51C"   // dark_mode           — theme: dark
        readonly property string monitor:   "\uE30A"   // computer            — theme: system
        readonly property string folder:    ""   // folder_open         — connector: Files
        readonly property string mail:      ""   // mail                — connector: Email
        readonly property string paste:     ""   // content_paste       — connector: Clipboard
        readonly property string globe:     ""   // public              — connector: Web
        readonly property string apps:      ""   // widgets             — connector: Apps & media
        readonly property string hub:       ""   // database            — connector: MCP servers
    }

    // ── building blocks ───────────────────────────────────────────────────────

    // An icon, drawn as one Material Symbols glyph. `d` is the glyph char (an `ico.*`); `px` is
    // the box the glyph is centred in, fed to the font's optical-size axis so it stays crisp.
    component Glyph: Item {
        id: g
        property string d: ""
        property int px: Theme.iconMd
        property color tint: Theme.uiText
        property int weight: 400
        property int spin: 0        // the only way to get a chevron the subset does not carry
        implicitWidth: px
        implicitHeight: px
        Text {
            anchors.centerIn: parent
            rotation: g.spin
            text: g.d
            color: g.tint
            font.family: Theme.fontIcon
            font.pixelSize: g.px
            font.variableAxes: ({ "wght": g.weight, "opsz": g.px, "FILL": 0, "GRAD": 0 })
            renderType: Text.QtRendering
        }
    }

    component Toggle: Item {
        id: sw
        property bool on: false
        property bool enabled: true
        signal toggled(bool value)
        implicitWidth: 40
        implicitHeight: 23
        opacity: enabled ? 1 : 0.55
        Rectangle {
            anchors.fill: parent
            radius: height / 2
            color: sw.on ? Theme.accent : Theme.uiTrackOff
            border.width: sw.on ? 0 : 1
            border.color: Theme.hairline
            Behavior on color { ColorAnimation { duration: root.t } }
            Rectangle {
                width: 17; height: 17; radius: 8.5
                y: 3
                x: sw.on ? parent.width - width - 3 : 3
                color: sw.on ? Theme.surfaceShell : Theme.uiTextDim
                Behavior on x { NumberAnimation { duration: root.t; easing.type: Easing.OutCubic } }
                Behavior on color { ColorAnimation { duration: root.t } }
            }
        }
        MouseArea {
            anchors.fill: parent
            enabled: sw.enabled
            cursorShape: Qt.PointingHandCursor
            onClicked: sw.toggled(!sw.on)
        }
    }

    // A dropdown with no box — value + chevron. ONE class now (D40): the mono variant is gone with
    // the rest of the mono, so there is no size for a call site to pick and none to get wrong.
    component Dropdown: Item {
        id: dd
        property var options: []
        property var labels: ({})
        property string value: ""
        property string placeholder: "—"
        property bool alignRight: false
        // 0 = hug the value. Otherwise the value elides at this width, while the popup stays as
        // wide as its longest option — truncating the thing you opened the menu to read would be
        // the wrong half to save space on.
        property int maxValueWidth: 0
        property bool enabled: true
        signal picked(string value)
        function shown(v) { return labels[v] !== undefined ? labels[v] : v }

        implicitWidth: row.implicitWidth + 16
        implicitHeight: 30
        opacity: enabled ? 1 : 0.55

        Rectangle {
            anchors.fill: parent
            radius: Theme.radiusControl
            color: (hov.hovered || menu.visible) ? Theme.uiHover : "transparent"
            Behavior on color { ColorAnimation { duration: root.t } }
        }
        HoverHandler { id: hov; enabled: dd.enabled; cursorShape: Qt.PointingHandCursor }
        Row {
            id: row
            anchors.left: dd.alignRight ? undefined : parent.left
            anchors.leftMargin: 8
            anchors.right: dd.alignRight ? parent.right : undefined
            anchors.rightMargin: 8
            anchors.verticalCenter: parent.verticalCenter
            spacing: 7
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: dd.value !== "" ? dd.shown(dd.value) : dd.placeholder
                color: dd.value !== "" ? Theme.uiText : Theme.uiTextFaint
                font.family: fontFamily
                font.pixelSize: Theme.fontBase
                width: dd.maxValueWidth > 0
                       ? Math.min(implicitWidth, dd.maxValueWidth) : implicitWidth
                elide: Text.ElideRight
            }
            Glyph {
                anchors.verticalCenter: parent.verticalCenter
                d: ico.chevron; px: Theme.iconMd; tint: Theme.uiTextDim
            }
        }
        property double closedAt: 0
        MouseArea {
            anchors.fill: parent
            enabled: dd.enabled
            onClicked: {
                if (menu.visible) { menu.close(); return }
                if (Date.now() - dd.closedAt > 120)
                    menu.open()
            }
        }

        TextMetrics {
            id: metrics
            font.family: fontFamily; font.pixelSize: Theme.fontBase
            text: {
                var longest = ""
                for (var i = 0; i < dd.options.length; i++) {
                    var t = dd.shown(dd.options[i])
                    if (t.length > longest.length) longest = t
                }
                return longest
            }
        }

        Popup {
            id: menu
            onClosed: dd.closedAt = Date.now()
            x: dd.alignRight ? dd.width - width : 0
            // Placed when it OPENS, not bound: a menu near the foot of the window has to flip
            // above the button, and if it fits in neither direction it takes the taller side and
            // scrolls. Bindings cannot do this — mapToItem is a one-shot measurement, and the
            // answer depends on where the row happens to be scrolled to.
            onAboutToShow: {
                var pt = dd.mapToItem(null, 0, 0)
                var margin = 12
                var below = root.height - (pt.y + dd.height) - margin
                var above = pt.y - margin
                var want = Math.min(dd.options.length * 32 + 10, 320)
                if (below >= want) {
                    menu.height = want; menu.y = dd.height + 4
                } else if (above >= want) {
                    menu.height = want; menu.y = -want - 4
                } else if (below >= above) {
                    menu.height = Math.max(96, below); menu.y = dd.height + 4
                } else {
                    var h = Math.max(96, above)
                    menu.height = h; menu.y = -h - 4
                }
            }
            width: Math.min(Math.max(200, dd.width, metrics.advanceWidth + 60), 460)
            padding: 5
            background: Rectangle {
                color: Theme.surfacePop
                radius: 10
                border.width: 1; border.color: Theme.hairlineStrong
            }
            contentItem: ListView {
                id: list
                clip: true
                model: dd.options
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ThemedScrollBar {
                    policy: list.contentHeight > list.height + 1
                            ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff
                }
                delegate: Rectangle {
                    required property string modelData
                    width: list.width - (list.contentHeight > list.height + 1
                                         ? Theme.scrollThickness + 6 : 0)
                    height: 32
                    radius: 6
                    color: oh.hovered ? Theme.uiSelected : "transparent"
                    HoverHandler { id: oh; cursorShape: Qt.PointingHandCursor }
                    // The tick sits in a fixed gutter so options stay aligned whether or not they
                    // are the selected one.
                    Glyph {
                        id: tick
                        anchors.left: parent.left; anchors.leftMargin: 9
                        anchors.verticalCenter: parent.verticalCenter
                        d: ico.check; px: Theme.iconSm; tint: Theme.uiText
                        opacity: modelData === dd.value ? 1 : 0
                    }
                    Text {
                        anchors.left: tick.right; anchors.leftMargin: 9
                        anchors.right: parent.right; anchors.rightMargin: 10
                        anchors.verticalCenter: parent.verticalCenter
                        text: dd.shown(modelData)
                        color: modelData === dd.value ? Theme.uiText : Theme.uiTextDim
                        font.family: fontFamily
                        font.pixelSize: Theme.fontBase
                        elide: Text.ElideRight
                    }
                    MouseArea {
                        anchors.fill: parent
                        onClicked: { dd.picked(modelData); menu.close() }
                    }
                }
            }
        }
    }

    component Field: TextField {
        id: fld
        implicitHeight: Theme.controlHeight
        leftPadding: 11; rightPadding: 11
        color: Theme.uiText
        font.family: fontFamily
        font.pixelSize: Theme.fontBase
        placeholderTextColor: Theme.uiTextFaint
        selectionColor: Theme.accent
        selectedTextColor: Theme.surfaceShell
        background: Rectangle {
            radius: Theme.radiusControl
            color: Theme.surfaceLift
            border.width: 1
            border.color: fld.activeFocus ? Theme.accent : Theme.hairline
            Behavior on border.color { ColorAnimation { duration: root.t } }
        }
    }

    // Every text button in the window, at ONE height (Theme.controlHeight) shared with the three
    // window controls — "the same size" must not depend on two paddings agreeing.
    component Area: TextArea {
        id: ta
        leftPadding: 11; rightPadding: 11; topPadding: 9; bottomPadding: 9
        color: Theme.uiText
        font.family: fontFamily
        font.pixelSize: Theme.fontBase
        placeholderTextColor: Theme.uiTextFaint
        selectionColor: Theme.accent
        selectedTextColor: Theme.surfaceShell
        wrapMode: TextArea.Wrap
        background: Rectangle {
            radius: Theme.radiusControl
            color: Theme.surfaceLift
            border.width: 1
            border.color: ta.activeFocus ? Theme.accent : Theme.hairline
            Behavior on border.color { ColorAnimation { duration: root.t } }
        }
    }

    component Btn: Rectangle {
        id: b
        property string label: ""
        property bool primary: false
        property bool danger: false
        property bool enabled: true
        signal clicked()
        implicitWidth: lbl.implicitWidth + 26
        implicitHeight: Theme.controlHeight
        radius: Theme.radiusControl
        opacity: enabled ? 1 : 0.5
        color: danger ? (bh.hovered ? Qt.lighter(Theme.danger, 1.15) : Theme.danger)
             : primary ? (bh.hovered ? "#ffffff" : Theme.uiInk)
             : (bh.hovered ? Qt.lighter(Theme.surfaceLift, 1.28) : Theme.surfaceLift)
        border.width: (danger || primary) ? 0 : 1
        border.color: bh.hovered ? Theme.hairlineStrong : Theme.hairline
        Behavior on color { ColorAnimation { duration: root.t } }
        HoverHandler { id: bh; enabled: b.enabled; cursorShape: Qt.PointingHandCursor }
        TapHandler { enabled: b.enabled; onTapped: b.clicked() }
        Text {
            id: lbl
            anchors.centerIn: parent
            text: b.label
            color: b.danger ? "#ffffff" : (b.primary ? Theme.surfaceShell : Theme.uiText)
            font.family: fontFamily
            font.pixelSize: Theme.fontBase
            font.weight: Font.Medium
        }
    }

    component IconBtn: Rectangle {
        id: ib
        property string d: ""
        property bool danger: false
        signal clicked()
        implicitWidth: 30; implicitHeight: 30
        radius: 7
        color: ih.hovered ? (danger ? Theme.danger : Theme.uiHoverStrong) : "transparent"
        Behavior on color { ColorAnimation { duration: root.t } }
        HoverHandler { id: ih; cursorShape: Qt.PointingHandCursor }
        Glyph {
            anchors.centerIn: parent
            d: ib.d; px: Theme.iconMd
            tint: (ib.danger && ih.hovered) ? "#ffffff"
                                            : (ih.hovered ? Theme.uiText : Theme.uiTextDim)
        }
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: ib.clicked() }
    }

    // Mutually exclusive, equally weighted choices shown at once rather than hidden behind a
    // dropdown. Words or glyphs; `glyphs` switches which the model is read as.
    // Effort as DOTS, not words (Thomas): one dot, two, a pyramid, a square, two-over-
    // three — a cluster that grows, in the same tight box the theme picker uses. Recovered
    // from D29 rather than rewritten.
    component EffortDots: Rectangle {
        id: eff
        property var options: []
        property string value: ""
        signal picked(string v)
        readonly property int cell: Theme.iconMd + 12       // the same cell the theme picker uses
        implicitWidth: options.length * cell + Math.max(0, options.length - 1) * 2 + 4
        implicitHeight: cell + 4
        radius: 9
        color: Theme.surfaceLift
        border.width: 1
        border.color: Theme.hairline
        // dots per row for a cluster of n: 1 · 2 · pyramid · square · 2-over-3
        function rows(n) {
            switch (n) {
            case 1: return [1]
            case 2: return [2]
            case 3: return [1, 2]
            case 4: return [2, 2]
            case 5: return [2, 3]
            }
            return [n]
        }
        Row {
            anchors.fill: parent
            anchors.margins: 2
            spacing: 2
            Repeater {
                model: eff.options
                delegate: Rectangle {
                    id: seg
                    required property string modelData
                    required property int index
                    readonly property bool active: modelData === eff.value
                    width: eff.cell
                    height: parent.height
                    radius: 7
                    color: active ? Theme.surfaceCard : "transparent"
                    Behavior on color { ColorAnimation { duration: root.t } }
                    Column {
                        anchors.centerIn: parent
                        spacing: 2
                        Repeater {
                            model: eff.rows(seg.index + 1)
                            delegate: Row {
                                required property int modelData
                                anchors.horizontalCenter: parent.horizontalCenter
                                spacing: 2
                                Repeater {
                                    model: modelData
                                    delegate: Rectangle {
                                        width: 4; height: 4; radius: 2
                                        color: seg.active ? Theme.uiText : Theme.uiTextFaint
                                    }
                                }
                            }
                        }
                    }
                    MouseArea {
                        anchors.fill: parent
                        cursorShape: Qt.PointingHandCursor
                        onClicked: eff.picked(seg.modelData)
                    }
                }
            }
        }
    }

    component Segmented: Rectangle {
        id: seg
        property var options: []
        property var icons: []
        property string value: ""
        property bool enabled: true
        signal picked(string value)
        // A tight square package: the track hugs its cells, and an icon cell is as tall as it
        // is wide. Wrapping the set closely is what makes it read as one control rather than as
        // three loose buttons (Thomas).
        readonly property int cell: Theme.iconMd + 12
        implicitWidth: segRow.implicitWidth + 4
        implicitHeight: cell + 4
        radius: 9
        color: Theme.surfaceLift
        border.width: 1; border.color: Theme.hairline
        opacity: enabled ? 1 : 0.55
        Row {
            id: segRow
            anchors.centerIn: parent
            spacing: 2
            Repeater {
                model: seg.options
                delegate: Rectangle {
                    required property string modelData
                    required property int index
                    readonly property bool on: modelData === seg.value
                    width: seg.icons.length > 0 ? seg.cell : (segLbl.implicitWidth + 22)
                    height: seg.cell
                    radius: 7
                    color: on ? Theme.surfaceCard : (sh.hovered ? Theme.uiNavHover : "transparent")
                    Behavior on color { ColorAnimation { duration: root.t } }
                    HoverHandler { id: sh; enabled: seg.enabled; cursorShape: Qt.PointingHandCursor }
                    Glyph {
                        anchors.centerIn: parent
                        visible: seg.icons.length > 0
                        d: seg.icons.length > index ? seg.icons[index] : ""
                        px: Theme.iconMd
                        tint: parent.on ? Theme.uiText : Theme.uiTextFaint
                    }
                    Text {
                        id: segLbl
                        anchors.centerIn: parent
                        visible: seg.icons.length === 0
                        text: modelData
                        color: parent.on ? Theme.uiText : Theme.uiTextFaint
                        font.family: fontFamily
                        font.pixelSize: Theme.fontSmall
                        font.weight: parent.on ? Font.Medium : Font.Normal
                    }
                    MouseArea {
                        anchors.fill: parent
                        enabled: seg.enabled
                        cursorShape: Qt.PointingHandCursor
                        onClicked: seg.picked(modelData)
                    }
                }
            }
        }
    }

    // A shortcut, in a FIXED box. Two things made it wobble: the field sized itself to its
    // contents, and the UI face's figures are proportional — "1" is narrower than "2", so two
    // otherwise identical bindings rendered at different widths and read as a mistake. A fixed
    // centred box hides both. Wide enough for "Ctrl + Shift + Alt + F12".
    component Kbd: Rectangle {
        property alias text: kt.text
        implicitWidth: 168
        implicitHeight: Theme.controlHeight
        radius: 6
        color: Theme.surfaceLift
        border.width: 1; border.color: Theme.hairlineStrong
        Text {
            id: kt
            anchors.centerIn: parent
            color: Theme.uiText
            font.family: fontFamily
            font.pixelSize: Theme.fontBase
        }
    }

    // ── the row: the atom of every page ───────────────────────────────────────
    // Label, description under it, control at the right, hairline between — CENTRED, so a row with
    // a description and one without read as the same horizontal line. The description takes the
    // SIZE of its label; weight and colour separate them, not scale.
    component Row_: Item {
        id: r
        default property alias control: ctl.data
        property string label: ""
        property string desc: ""
        property bool built: true
        property bool stack: false      // a control that is a SET, not a value, drops below the text
        property bool divider: true
        width: parent ? parent.width : 0
        implicitHeight: stack
            ? txt.implicitHeight + ctlRow.implicitHeight + 11 + 30
            : Math.max(txt.implicitHeight, ctlRow.implicitHeight) + 30

        Column {
            id: txt
            y: 15
            anchors.left: parent.left
            width: r.stack ? parent.width
                           : Math.max(60, parent.width - ctlRow.implicitWidth - 24)
            spacing: 2
            Text {
                width: parent.width
                text: r.label
                visible: r.label !== ""
                color: r.built ? Theme.uiText : Theme.uiTextFaint
                font.family: fontFamily
                font.pixelSize: Theme.fontBase
                font.weight: Font.Medium
                wrapMode: Text.WordWrap
            }
            Text {
                width: parent.width
                text: r.desc
                visible: r.desc !== ""
                color: r.built ? Theme.uiTextDim : Theme.uiTextFaint
                font.family: fontFamily
                font.pixelSize: Theme.fontBase
                wrapMode: Text.WordWrap
                lineHeight: Theme.lineBox(Theme.fontBase)
                lineHeightMode: Text.FixedHeight
            }
        }
        Item {
            id: ctlRow
            implicitWidth: ctl.implicitWidth
            implicitHeight: ctl.implicitHeight
            anchors.right: r.stack ? undefined : parent.right
            anchors.left: r.stack ? parent.left : undefined
            y: r.stack ? txt.y + txt.implicitHeight + 11
                       : txt.y + txt.implicitHeight / 2 - implicitHeight / 2
            opacity: r.built ? 1 : Theme.opacityDim
            enabled: r.built
            Row {
                id: ctl
                spacing: 12
            }
        }
        Rectangle {
            visible: r.divider
            anchors.bottom: parent.bottom
            width: parent.width; height: 1
            color: Theme.hairline
        }
    }

    component SectionHeading: Text {
        property bool first: false
        color: Theme.uiText
        font.family: fontFamily
        font.pixelSize: Theme.fontHeading
        font.weight: Font.DemiBold
        topPadding: first ? 0 : 30
        bottomPadding: 2
    }

    component Lede: Text {
        width: parent ? parent.width : 0
        color: Theme.uiTextDim
        font.family: fontFamily
        font.pixelSize: Theme.fontBase
        wrapMode: Text.WordWrap
        lineHeight: Theme.lineBox(Theme.fontBase)
        lineHeightMode: Text.FixedHeight
        bottomPadding: 6
    }

    // ── one schema-driven row ─────────────────────────────────────────────────
    // Renders whatever `type` the schema declares. A pane that is only rows needs nothing else.
    component SettingRow: Row_ {
        id: sr
        property string key: ""
        readonly property var m: cfg.meta[key]
        label: m !== undefined ? m.label : ""
        desc: (m !== undefined && m.help !== undefined) ? m.help : ""
        built: m !== undefined && m.built === true
        stack: m !== undefined && m.type === "textarea"

        Loader {
            active: sr.m !== undefined
            sourceComponent: {
                if (sr.m === undefined) return null
                switch (sr.m.type) {
                case "bool":     return boolCtl
                case "text":     return textCtl
                case "textarea": return areaCtl
                case "binding":  return bindingCtl
                case "enum":     return sr.m.control === "segmented" ? segCtl : enumCtl
                default:         return null
                }
            }
        }
        Component {
            id: boolCtl
            Toggle {
                on: cfg.values[sr.key] === true
                enabled: sr.built
                onToggled: function (v) { cfg.set(sr.key, v) }
            }
        }
        Component {
            id: textCtl
            Field {
                implicitWidth: 260
                text: cfg.values[sr.key] !== undefined ? cfg.values[sr.key] : ""
                enabled: sr.built
                onEditingFinished: cfg.set(sr.key, text)
            }
        }
        Component {
            id: areaCtl
            Area {
                implicitWidth: sr.width
                implicitHeight: 86
                text: cfg.values[sr.key] !== undefined ? cfg.values[sr.key] : ""
                placeholderText: "E.g., explain things to me in an ordered way, using headings; "
                               + "don't use metaphors, and answer directly without technical jargon."
                enabled: sr.built
                onEditingFinished: cfg.set(sr.key, text)
            }
        }
        Component {
            id: enumCtl
            Dropdown {
                alignRight: true
                options: sr.m.choices !== undefined ? sr.m.choices : []
                value: cfg.values[sr.key] !== undefined ? cfg.values[sr.key] : ""
                enabled: sr.built
                onPicked: function (v) { cfg.set(sr.key, v) }
            }
        }
        Component {
            id: segCtl
            Segmented {
                options: sr.m.choices !== undefined ? sr.m.choices : []
                // Light · dark · system, as glyphs — three states you recognise faster by picture.
                icons: sr.key === "theme" ? [ico.sun, ico.moon, ico.monitor] : []
                value: cfg.values[sr.key] !== undefined ? cfg.values[sr.key] : ""
                enabled: sr.built
                onPicked: function (v) { cfg.set(sr.key, v) }
            }
        }
        // KeyRecorder IS the field: it shows the binding at rest and records in place, so there is
        // no separate Change button and no floating capture surface. Given a fixed width, because
        // a box that sizes to its contents changes width with the shortcut — and the UI face's
        // figures are proportional, so "…+1" and "…+2" came out different widths and read as a
        // mistake. Wide enough for "Ctrl + Shift + Alt + F12".
        // The box shows the shortcut; the button starts the capture — the sandbox's shape. The
        // box is still clickable (same action), but Change is what says so.
        Component {
            id: bindingCtl
            KeyRecorder {
                // Fixed box, click to change: no separate button (Thomas). Width and height are
                // set explicitly so recording cannot resize it — the shift was the giveaway that
                // it was sizing to its own text.
                width: 168
                height: Theme.controlHeight
                animMs: root.t
                enabled: sr.built
                value: cfg.values[sr.key] !== undefined ? cfg.values[sr.key] : ""
                onCommitted: function (combo) { cfg.set(sr.key, combo) }
            }
        }
    }

    // ── layout ────────────────────────────────────────────────────────────────
    Item {
        anchors.fill: parent
        enabled: !root.modalOpen

        // ── sidebar ──
        Rectangle {
            id: side
            anchors.top: parent.top; anchors.bottom: parent.bottom; anchors.left: parent.left
            width: root.sideW
            color: Theme.surfaceRail
            Rectangle {
                anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom
                width: 1; color: Theme.hairline
            }
            // The sidebar drags the window: it has no controls of its own between the nav rows.
            MouseArea {
                anchors.fill: parent
                onPressed: { root.dropFocus(); root.startSystemMove() }
            }

            // Present but DISABLED: nothing searches yet, and a box that takes typing and does
            // nothing with it is the same species of lie as an indicator that lights when the mic
            // is shut. Dimmed is this window's own idiom for "decided, not built" — the same
            // treatment every `built: false` row gets. Building it is folded into the
            // absent-settings design session (STATE).
            Field {
                id: search
                anchors.top: parent.top; anchors.topMargin: 12
                anchors.left: parent.left; anchors.leftMargin: 10
                anchors.right: parent.right; anchors.rightMargin: 10
                implicitHeight: 30
                // 9px + the 1px border puts the glyph on the same column as the nav icons, and
                // the padding puts the placeholder on the same column as their labels.
                leftPadding: 9 + Theme.iconMd + 10
                placeholderText: "Search"
                enabled: false
                opacity: Theme.opacityDim
                Glyph {
                    x: 9
                    anchors.verticalCenter: parent.verticalCenter
                    d: ico.search; tint: Theme.uiTextFaint
                }
            }

            Flickable {
                id: navScroll
                anchors.top: search.bottom; anchors.topMargin: 8
                anchors.left: parent.left; anchors.right: parent.right
                anchors.bottom: sideFoot.top
                contentWidth: width
                contentHeight: navCol.implicitHeight
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ThemedScrollBar {
                    policy: navScroll.contentHeight > navScroll.height + 1
                            ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff
                }

                Column {
                    id: navCol
                    x: 10
                    width: parent.width - 20

                    // One item per schema pane, then the two panes that are decided but unbuilt.
                    // They are rendered and NOT clickable (Thomas): the sidebar shows where they
                    // are going without pretending they exist.
                    Repeater {
                        model: cfg.panes
                        delegate: NavItem {
                            required property var modelData
                            pane: modelData.id
                            label: modelData.label
                            glyph: {
                                switch (modelData.id) {
                                case "models":     return ico.box
                                case "connectors": return ico.plug
                                case "triggers":   return ico.keyboard
                                default:           return ico.settings
                                }
                            }
                        }
                    }
                    Text {
                        text: "Voice"
                        color: Theme.uiTextFaint
                        font.family: fontFamily; font.pixelSize: Theme.fontSmall
                        topPadding: 13; bottomPadding: 4; leftPadding: 9
                    }
                    // Decided, unbuilt, and NOT clickable (Thomas): the sidebar shows where the
                    // four absent settings are going (spec/70 §3) without pretending they exist.
                    NavItem { label: "Speech";    glyph: ico.mic;   soon: true }
                    NavItem { label: "Dictation"; glyph: ico.lines; soon: true }
                }
            }

            // The foot: the mic at the left, Gem in the corner. Both sit on the sidebar's own
            // 10px padding line, so the pair reads as balanced rather than as two loose objects.
            Item {
                id: sideFoot
                anchors.bottom: parent.bottom
                anchors.left: parent.left; anchors.right: parent.right
                height: 52

                // Not a button: it reports, it does not act — exactly what the "Mic closed" text
                // it replaced did. spec/50 rule 4: it whitens and fills ONLY on real capture.
                Item {
                    id: micMark
                    width: 20; height: 20
                    x: 10
                    anchors.bottom: parent.bottom; anchors.bottomMargin: 10
                    readonly property bool capturing: overlay.state === "listening"
                    readonly property real level: capturing ? overlay.mic : 0
                    // The Material Symbols mic, not a drawing (Thomas): every icon in this
                    // window comes from the font. The level fills it by CLIPPING a second copy
                    // drawn in the bright ink over the dim one — so the shape is always the
                    // font's, and the fill can never leave the glyph's own silhouette.
                    Glyph {
                        anchors.centerIn: parent
                        d: ico.mic; px: Theme.iconMd
                        tint: Theme.uiTextFaint
                    }
                    Item {
                        anchors.fill: parent
                        clip: true
                        Item {
                            anchors.left: parent.left; anchors.right: parent.right
                            anchors.bottom: parent.bottom
                            height: parent.height * Math.max(0, Math.min(1, micMark.level))
                            clip: true
                            Glyph {
                                width: micMark.width; height: micMark.height
                                y: -(micMark.height - parent.height)
                                d: ico.mic; px: Theme.iconMd
                                tint: Theme.uiText
                            }
                        }
                    }
                    // Capturing at all reads as white even at silence, so an open mic is never
                    // invisible (spec/50 rule 4 — the indicator is about the WINDOW being open).
                    Glyph {
                        anchors.centerIn: parent
                        visible: micMark.capturing
                        d: ico.mic; px: Theme.iconMd
                        tint: Theme.uiText
                        opacity: 0.45
                    }
                }

                // 52px = 2× the kit's 26px cell; integer scales only (a fractional one makes some
                // pixel-cells wider than their neighbours). Both offsets cancel the empty cells the
                // FRAME carries around her ink — measured from the kit by gem.py, never nudged — so
                // what gets positioned is Gem herself and her base lands on the window's own edge.
                Image {
                    id: gemCorner
                    width: 52; height: 52
                    sourceSize: Qt.size(52, 52)
                    smooth: false
                    source: gemPlayer.source
                    anchors.right: parent.right
                    anchors.rightMargin: 10 - gemPlayer.padRight * 2
                    anchors.bottom: parent.bottom
                    // Cancel the frame's empty rows, less 1px so her base clears the window's
                    // rounded corner (Thomas).
                    anchors.bottomMargin: -gemPlayer.padBottom * 2 + 1
                }
            }
        }

        // ── content ──
        Item {
            anchors.top: parent.top; anchors.bottom: parent.bottom
            anchors.left: side.right; anchors.right: parent.right

            // The header row: page title, the page's one action, and the window controls. Same
            // colour as the body with no rule beneath it — the fade below is what separates them,
            // so content dissolves as it scrolls up rather than being clipped by a line.
            Item {
                id: topBar
                anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
                height: root.topH
                MouseArea {
                    anchors.fill: parent
                    onPressed: { root.dropFocus(); root.startSystemMove() }
                    onDoubleClicked: root.visibility = root.visibility === Window.Maximized
                                     ? Window.Windowed : Window.Maximized
                }
                Text {
                    anchors.left: parent.left; anchors.leftMargin: root.padX
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.pageTitle
                    color: Theme.uiText
                    font.family: fontFamily
                    font.pixelSize: Theme.fontTitle
                    font.weight: Font.DemiBold
                }
                Btn {
                    anchors.right: parent.right; anchors.rightMargin: 46 * 3 + 12
                    anchors.verticalCenter: parent.verticalCenter
                    visible: root.pageAction !== ""
                    label: root.pageAction
                    onClicked: root.openAdd()
                }
                // Windows' own three: square, flush to the top-right corner, filling the header's
                // height, hover-filled grey with red only on close. Copying the platform beats
                // having a look of our own here — these three are muscle memory, and a rounded
                // inset pill reads as a web page's idea of a window button.
                Row {
                    anchors.right: parent.right
                    anchors.top: parent.top
                    spacing: 0
                    CaptionButton { d: ico.minimize; onActivated: root.showMinimized() }
                    CaptionButton {
                        d: root.visibility === Window.Maximized ? ico.restore : ico.maximize
                        onActivated: root.visibility = root.visibility === Window.Maximized
                                     ? Window.Windowed : Window.Maximized
                    }
                    CaptionButton { d: ico.close; danger: true; onActivated: root.close() }
                }
            }

            Item {
                anchors.top: topBar.bottom; anchors.left: parent.left
                anchors.right: parent.right; anchors.bottom: parent.bottom

                Flickable {
                    id: scroller
                    // Named for findChild, which sees objectName and never a QML id: settings_check
                    // asserts this goes inert behind an open sheet (the scroll lock).
                    objectName: "scroller"
                    anchors.fill: parent
                    contentWidth: width
                    contentHeight: pageLoader.implicitHeight + root.fadeHeight * 2 + 40
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ThemedScrollBar {
                        policy: scroller.contentHeight > scroller.height + 1
                                ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff
                    }
                    MouseArea {
                        width: scroller.width
                        height: Math.max(scroller.height, pageLoader.height + root.fadeHeight * 2)
                        onPressed: function (mouse) { root.dropFocus(); mouse.accepted = false }
                    }
                    Loader {
                        id: pageLoader
                        x: root.padX
                        y: root.fadeHeight
                        width: parent.width - root.padX * 2
                        height: implicitHeight
                        sourceComponent: root.section === "models" ? modelsPage
                                       : root.section === "connectors" ? connectorsPage
                                       : rowsPage
                    }
                    Connections {
                        target: root
                        function onSectionChanged() { scroller.contentY = 0 }
                    }
                }
                // The fade the header row sits on. Exactly `fadeHeight` tall, and the content's
                // top padding matches it, so at rest the first line starts undimmed.
                Rectangle {
                    anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
                    height: root.fadeHeight
                    gradient: Gradient {
                        GradientStop { position: 0.0; color: Theme.surfaceShell }
                        GradientStop { position: 1.0; color: "transparent" }
                    }
                }
            }
        }
    }

    component NavItem: Rectangle {
        id: ni
        property string pane: ""
        property string label: ""
        property string glyph: ""
        property bool soon: false
        readonly property bool active: !soon && root.section === pane
        width: parent ? parent.width : 0
        height: 32
        radius: 7
        // Shade only — the white outline read as a focus ring on something that is merely
        // selected (Thomas).
        color: active ? Theme.surfaceLift
             : (nh.hovered && !soon ? Theme.uiNavHover : "transparent")
        HoverHandler { id: nh; enabled: !ni.soon; cursorShape: Qt.PointingHandCursor }
        Glyph {
            id: nig
            x: 9
            anchors.verticalCenter: parent.verticalCenter
            d: ni.glyph
            tint: ni.soon ? Theme.uiTextFaint
                          : (ni.active || nh.hovered ? Theme.uiText : Theme.uiTextDim)
        }
        Text {
            anchors.left: nig.right; anchors.leftMargin: 10
            anchors.verticalCenter: parent.verticalCenter
            text: ni.label
            color: ni.soon ? Theme.uiTextFaint
                           : (ni.active || nh.hovered ? Theme.uiText : Theme.uiTextDim)
            font.family: fontFamily
            font.pixelSize: Theme.fontBase
            font.weight: ni.active ? Font.Medium : Font.Normal
        }
        Rectangle {
            visible: ni.soon
            anchors.right: parent.right; anchors.rightMargin: 9
            anchors.verticalCenter: parent.verticalCenter
            width: soonLbl.implicitWidth + 10; height: 16
            radius: 5
            color: "transparent"
            border.width: 1; border.color: Theme.hairlineStrong
            Text {
                id: soonLbl
                anchors.centerIn: parent
                text: "soon"
                color: Theme.uiTextFaint
                font.family: fontFamily; font.pixelSize: 10
            }
        }
        MouseArea {
            anchors.fill: parent
            enabled: !ni.soon
            cursorShape: Qt.PointingHandCursor
            onClicked: root.section = ni.pane
        }
    }

    component CaptionButton: Rectangle {
        id: cb
        property string d: ""
        property bool danger: false
        signal activated()
        // Windows' own caption metrics: 46 wide, filling the bar's height, square corners.
        width: 46
        height: root.topH
        radius: 0
        color: cbh.hovered ? (danger ? Theme.danger : Theme.uiHoverStrong) : "transparent"
        Behavior on color { ColorAnimation { duration: root.t } }
        HoverHandler { id: cbh; cursorShape: Qt.PointingHandCursor }
        Glyph {
            anchors.centerIn: parent
            // Optical size, not nominal: a 45° cross reads smaller than the bar and the square at
            // the same em, so close overrides this upward.
            d: cb.d; px: cb.d === ico.close ? 18 : 14
            tint: cbh.hovered ? (cb.danger ? "#ffffff" : Theme.uiText) : Theme.uiTextDim
        }
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: cb.activated() }
    }

    // ── pages ─────────────────────────────────────────────────────────────────

    // Any pane that is a list of rows: General (grouped) and Triggers (flat). Nothing about what a
    // pane CONTAINS lives here — it is all in the schema.
    Component {
        id: rowsPage
        Column {
            width: parent ? parent.width : 0
            Repeater {
                model: cfg.groupsFor(root.section)
                delegate: Column {
                    required property var modelData
                    required property int index
                    width: parent.width
                    SectionHeading { text: modelData.label; first: index === 0 }
                    Repeater {
                        model: cfg.rowsInGroup(root.section, modelData.id)
                        delegate: SettingRow {
                            required property string modelData
                            required property int index
                            key: modelData
                        }
                    }
                }
            }
            // A flat pane declares no groups; its rows render directly.
            Repeater {
                model: cfg.groupsFor(root.section).length === 0 ? cfg.rowsFor(root.section) : []
                delegate: SettingRow {
                    required property string modelData
                    key: modelData
                }
            }
        }
    }

    // ── Models: two tables' worth of roster, then the cleanup roles ──
    Component {
        id: modelsPage
        Column {
            width: parent ? parent.width : 0
            readonly property var ids: Object.keys(cfg.models)

            SectionHeading { text: "Ask"; first: true }

            // Header. Column widths are shared with the rows below through `colModel`/`colKey`
            // so the two cannot drift.
            Item {
                width: parent.width
                height: 30
                readonly property int colName: Math.round(parent.width * 0.34)
                Text {
                    x: 0; anchors.bottom: parent.bottom; bottomPadding: 9
                    text: "Provider"; color: Theme.uiTextFaint
                    font.family: fontFamily; font.pixelSize: Theme.fontSmall
                }
                Text {
                    x: parent.colName; anchors.bottom: parent.bottom; bottomPadding: 9
                    text: "Model"; color: Theme.uiTextFaint
                    font.family: fontFamily; font.pixelSize: Theme.fontSmall
                }
                Text {
                    anchors.right: parent.right; anchors.rightMargin: root.colKeyR
                    anchors.bottom: parent.bottom; bottomPadding: 9
                    text: "Key"; color: Theme.uiTextFaint
                    font.family: fontFamily; font.pixelSize: Theme.fontSmall
                }
                Text {
                    anchors.right: parent.right; anchors.rightMargin: root.colActiveR
                    anchors.bottom: parent.bottom; bottomPadding: 9
                    text: "Active"; color: Theme.uiTextFaint
                    font.family: fontFamily; font.pixelSize: Theme.fontSmall
                }
                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width; height: 1; color: Theme.hairline
                }
            }

            Repeater {
                model: parent.ids
                delegate: ModelRow {
                    required property string modelData
                    pid: modelData
                }
            }

            Text {
                width: parent.width
                visible: parent.ids.length === 0
                text: "No models yet. Add one to give Gemma a brain."
                color: Theme.uiTextFaint
                font.family: fontFamily; font.pixelSize: Theme.fontBase
                topPadding: 22; bottomPadding: 22
                horizontalAlignment: Text.AlignHCenter
            }

            SectionHeading { text: "Dictate" }
            Repeater {
                model: cfg.rowsFor("models")
                delegate: CleanupRow {
                    required property string modelData
                    key: modelData
                }
            }
        }
    }

    component ModelRow: Item {
        id: mr
        property string pid: ""
        readonly property var cat: cfg.catalog[pid] !== undefined ? cfg.catalog[pid] : ({})
        readonly property var st: cfg.models[pid] !== undefined ? cfg.models[pid] : ({})
        readonly property bool isDefault: cfg.values["primary"] === pid
        width: parent ? parent.width : 0
        height: 56
        Component.onCompleted: cfg.refreshModels(pid)
        readonly property int colName: Math.round(width * 0.34)

        Glyph {
            id: mrIcon
            x: 0
            anchors.verticalCenter: parent.verticalCenter
            d: mr.cat.where === "local" ? ico.chip : ico.cloud
            px: Theme.iconMd; tint: Theme.uiTextDim
        }
        Column {
            anchors.left: mrIcon.right; anchors.leftMargin: 11
            anchors.verticalCenter: parent.verticalCenter
            spacing: 1
            Row {
                spacing: 7
                Text {
                    text: mr.cat.name !== undefined ? mr.cat.name : mr.pid
                    color: Theme.uiText
                    font.family: fontFamily; font.pixelSize: Theme.fontBase
                    font.weight: Font.Medium
                }
                // Exactly one provider holds the default, so the roster REPORTS it and the sheet
                // is where it moves. A per-row toggle could be switched on three times, which is
                // not what a default is.
                Rectangle {
                    visible: mr.isDefault
                    anchors.verticalCenter: parent.verticalCenter
                    width: defLbl.implicitWidth + 14; height: 18
                    radius: 5
                    color: Theme.surfaceLift
                    border.width: 1; border.color: Theme.hairlineStrong
                    Text {
                        id: defLbl
                        anchors.centerIn: parent
                        text: "Default"
                        color: Theme.uiText
                        font.family: fontFamily; font.pixelSize: 11
                    }
                }
            }
            Text {
                text: mr.cat.where === "local" ? "Local" : "Cloud"
                color: Theme.uiTextFaint
                font.family: fontFamily; font.pixelSize: Theme.fontSmall
            }
        }
        Dropdown {
            x: mr.colName
            anchors.verticalCenter: parent.verticalCenter
            maxValueWidth: Math.max(140, mr.width * 0.26)
            options: cfg.modelOptions[mr.pid] !== undefined ? cfg.modelOptions[mr.pid] : []
            value: mr.st.model !== undefined ? mr.st.model : ""
            onPicked: function (v) { cfg.setModel(mr.pid, "model", v) }
        }
        Text {
            anchors.right: parent.right; anchors.rightMargin: root.colKeyR
            anchors.verticalCenter: parent.verticalCenter
            text: mr.cat.auth === "key" ? (cfg.keys[mr.pid] === "stored" ? "Stored" : "No key")
                                        : "N/A"
            color: Theme.uiTextFaint
            font.family: fontFamily; font.pixelSize: Theme.fontSmall
        }
        Toggle {
            id: activeSw
            anchors.right: parent.right; anchors.rightMargin: root.colActiveR
            anchors.verticalCenter: parent.verticalCenter
            on: mr.st.on === true
            onToggled: function (v) { cfg.setModel(mr.pid, "on", v) }
        }
        IconBtn {
            id: mrKebab
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            implicitWidth: root.colKebabW
            d: ico.kebab
            onClicked: root.beginEdit(mr.pid)
        }
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width; height: 1; color: Theme.hairline
        }
    }

    // Provider, model and the switch in ONE row: they are three parts of a single decision —
    // whether to tidy, and with what. Splitting the model onto its own row left it looking like an
    // unrelated setting that had drifted in.
    // Everything on one line: label, the two pickers, the switch. The pickers are DIMMED rather
    // than hidden when tidying is off (Thomas) — you can still see what is configured, and the
    // stored choice is never cleared, so switching back on returns it.
    component CleanupRow: Item {
        id: cr
        property string key: ""
        readonly property var m: cfg.meta[key]
        readonly property string toggleKey: (m !== undefined && m.toggledBy !== undefined)
                                            ? m.toggledBy : ""
        readonly property string modelKey: (m !== undefined && m.modelKey !== undefined)
                                           ? m.modelKey : ""
        readonly property string pid: cfg.values[key] !== undefined ? cfg.values[key] : ""
        readonly property bool built: m !== undefined && m.built === true
        readonly property bool on: toggleKey !== "" && cfg.values[toggleKey] === true
        width: parent ? parent.width : 0
        height: 30 + Math.max(lab.implicitHeight, pickers.implicitHeight)
        onPidChanged: if (pid !== "") cfg.refreshModels(pid)

        Text {
            id: lab
            anchors.left: parent.left
            anchors.verticalCenter: parent.verticalCenter
            text: cr.m !== undefined ? cr.m.label : ""
            color: cr.built ? Theme.uiText : Theme.uiTextFaint
            font.family: fontFamily; font.pixelSize: Theme.fontBase
            font.weight: Font.Medium
        }
        Row {
            id: pickers
            anchors.right: sw.left; anchors.rightMargin: 14
            anchors.verticalCenter: parent.verticalCenter
            spacing: 12
            opacity: (cr.built && cr.on) ? 1 : Theme.opacityDim
            enabled: cr.built && cr.on
            Behavior on opacity { NumberAnimation { duration: root.t } }
            Dropdown {
                options: cfg.addedProviders
                labels: cfg.providerNames
                value: cr.pid
                placeholder: "Provider"
                // Changing the provider CLEARS the model: a model id belongs to one provider, and
                // leaving it behind offered Fable 5 from Ollama (Thomas).
                onPicked: function (v) {
                    if (v !== cr.pid && cr.modelKey !== "")
                        cfg.set(cr.modelKey, "")
                    cfg.set(cr.key, v)
                }
            }
            Dropdown {
                visible: cr.modelKey !== ""
                maxValueWidth: 200
                options: cfg.modelOptions[cr.pid] !== undefined ? cfg.modelOptions[cr.pid] : []
                placeholder: "Model"
                // Empty MEANS "whatever the provider's own row says"; picking here overrides it.
                value: cfg.values[cr.modelKey] !== undefined && cfg.values[cr.modelKey] !== ""
                       ? cfg.values[cr.modelKey]
                       : (cfg.models[cr.pid] !== undefined && cfg.models[cr.pid].model
                          ? cfg.models[cr.pid].model : "")
                onPicked: function (v) { cfg.set(cr.modelKey, v) }
            }
        }
        Toggle {
            id: sw
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            on: cr.on
            enabled: cr.built && cr.toggleKey !== ""
            opacity: cr.built ? 1 : Theme.opacityDim
            onToggled: function (v) { cfg.set(cr.toggleKey, v) }
        }
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width; height: 1; color: Theme.hairline
        }
    }

    // ── Connectors: the consent table (D38) ──
    Component {
        id: connectorsPage
        Column {
            width: parent ? parent.width : 0

            Lede { text: "Restrict what Gemma can see and have access to." }

            Item {
                width: parent.width
                height: 30
                Text {
                    x: 0; anchors.bottom: parent.bottom; bottomPadding: 9
                    text: "Connector"; color: Theme.uiTextFaint
                    font.family: fontFamily; font.pixelSize: Theme.fontSmall
                }
                Text {
                    x: Math.round(parent.width * 0.30)
                    anchors.bottom: parent.bottom; bottomPadding: 9
                    text: "Enables"; color: Theme.uiTextFaint
                    font.family: fontFamily; font.pixelSize: Theme.fontSmall
                }
                Text {
                    anchors.right: parent.right; anchors.bottom: parent.bottom; bottomPadding: 9
                    text: "Status"; color: Theme.uiTextFaint
                    font.family: fontFamily; font.pixelSize: Theme.fontSmall
                }
                Rectangle {
                    anchors.bottom: parent.bottom
                    width: parent.width; height: 1; color: Theme.hairline
                }
            }

            Repeater {
                model: cfg.rowsFor("connectors")
                delegate: ConnectorRow {
                    required property string modelData
                    key: modelData
                }
            }
        }
    }

    component ConnectorRow: Item {
        id: cn
        property string key: ""
        readonly property var m: cfg.meta[key]
        readonly property var tools: (m !== undefined && m.connector !== undefined)
                                     ? cfg.toolsFor(m.connector) : []
        readonly property bool built: m !== undefined && m.built === true
        width: parent ? parent.width : 0
        height: Math.max(56, toolCol.implicitHeight + 26)

        Glyph {
            id: cnIcon
            x: 0
            anchors.verticalCenter: parent.verticalCenter
            // One icon per connector, not one for all: the row is naming a DIFFERENT thing each
            // time, and a repeated plug says the opposite. Keyed on the connector id from the
            // schema, so a new connector picks its own (falling back to the pane's own plug).
            d: {
                switch (cn.m !== undefined ? cn.m.connector : "") {
                case "system":     return ico.monitor
                case "files":      return ico.folder
                case "email":      return ico.mail
                case "clipboard":  return ico.paste
                case "web":        return ico.globe
                case "apps_media": return ico.apps
                case "mcp":        return ico.hub
                default:           return ico.plug
                }
            }
            tint: cn.built ? Theme.uiTextDim : Theme.uiTextFaint
        }
        Row {
            anchors.left: cnIcon.right; anchors.leftMargin: 11
            anchors.verticalCenter: parent.verticalCenter
            spacing: 7
            Text {
                anchors.verticalCenter: parent.verticalCenter
                text: cn.m !== undefined ? cn.m.label : ""
                color: cn.built ? Theme.uiText : Theme.uiTextFaint
                font.family: fontFamily; font.pixelSize: Theme.fontBase
                font.weight: Font.Medium
            }
            Rectangle {
                visible: !cn.built
                anchors.verticalCenter: parent.verticalCenter
                width: nbLbl.implicitWidth + 12; height: 18
                radius: 5
                color: "transparent"
                border.width: 1; border.color: Theme.hairlineStrong
                Text {
                    id: nbLbl
                    anchors.centerIn: parent
                    text: "Not built"
                    color: Theme.uiTextDim
                    font.family: fontFamily; font.pixelSize: 11
                }
            }
        }
        // One line per tool once there is more than one. Dot-separating them read as a run-on
        // sentence, and a connector GAINING tools is the expected case (D38).
        Column {
            id: toolCol
            x: Math.round(cn.width * 0.30)
            anchors.verticalCenter: parent.verticalCenter
            width: cn.width * 0.55
            spacing: 3
            Repeater {
                model: cn.tools
                delegate: Text {
                    required property var modelData
                    width: toolCol.width
                    text: modelData.label
                    color: (cn.built && modelData.ready) ? Theme.uiTextDim : Theme.uiTextFaint
                    font.family: fontFamily; font.pixelSize: Theme.fontBase
                    wrapMode: Text.WordWrap
                }
            }
            Text {
                visible: cn.tools.length === 0
                text: "No tools yet"
                color: Theme.uiTextFaint
                font.family: fontFamily; font.pixelSize: Theme.fontBase
            }
        }
        Toggle {
            anchors.right: parent.right
            anchors.verticalCenter: parent.verticalCenter
            on: cfg.values[cn.key] === true
            enabled: cn.built
            onToggled: function (v) { cfg.set(cn.key, v) }
        }
        Rectangle {
            anchors.bottom: parent.bottom
            width: parent.width; height: 1; color: Theme.hairline
        }
    }

    // ── the sheets ────────────────────────────────────────────────────────────
    // A task you finish and leave, not a place you navigate to — so a sheet over a scrim, with the
    // page below disabled (see `modalOpen`).
    Rectangle {
        id: scrim
        anchors.fill: parent
        color: Qt.rgba(0, 0, 0, 0.55)
        visible: root.manageOpen
        MouseArea { anchors.fill: parent; onClicked: root.manageOpen = false }

        Rectangle {
            id: sheet
            anchors.centerIn: parent
            width: 560
            height: Math.min(parent.height * 0.86, sheetHead.height + sheetBody.contentHeight
                             + sheetFoot.height + 24)
            radius: 14
            color: Theme.surfaceShell
            border.width: 1; border.color: Theme.hairlineStrong
            // Swallow clicks so they do not reach the scrim behind and close the sheet.
            MouseArea { anchors.fill: parent }

            Item {
                id: sheetHead
                anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
                height: 54
                IconBtn {
                    id: backBtn
                    visible: root.addStep === 2 && !root.addEditing
                    x: 12
                    anchors.verticalCenter: parent.verticalCenter
                    d: ico.back
                    onClicked: root.addStep = 1
                }
                Text {
                    anchors.left: backBtn.visible ? backBtn.right : parent.left
                    anchors.leftMargin: backBtn.visible ? 6 : 20
                    anchors.verticalCenter: parent.verticalCenter
                    text: root.addEditing
                          ? (cfg.catalog[root.addProviderId] !== undefined
                             ? cfg.catalog[root.addProviderId].name : root.addProviderId)
                          : (root.addStep === 1 ? "Add a model"
                             : "Add " + (cfg.catalog[root.addProviderId] !== undefined
                                         ? cfg.catalog[root.addProviderId].name : ""))
                    color: Theme.uiText
                    font.family: fontFamily; font.pixelSize: Theme.fontHeading
                    font.weight: Font.DemiBold
                }
                IconBtn {
                    anchors.right: parent.right; anchors.rightMargin: 12
                    anchors.verticalCenter: parent.verticalCenter
                    d: ico.close
                    onClicked: root.manageOpen = false
                }
            }

            Flickable {
                id: sheetBody
                anchors.top: sheetHead.bottom
                anchors.left: parent.left
                anchors.right: parent.right; anchors.rightMargin: 6
                anchors.bottom: sheetFoot.top
                contentWidth: width
                contentHeight: sheetCol.implicitHeight
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                ScrollBar.vertical: ThemedScrollBar {
                    policy: sheetBody.contentHeight > sheetBody.height + 1
                            ? ScrollBar.AsNeeded : ScrollBar.AlwaysOff
                }

                Column {
                    id: sheetCol
                    x: 20
                    width: parent.width - 34

                    // ── step 1: the catalogue ──
                    Column {
                        width: parent.width
                        visible: root.addStep === 1 && !root.addEditing
                        Lede {
                            text: "Pick where the model runs. A cloud provider needs an API key; "
                                + "one on this computer needs the address it is serving on."
                        }
                        Repeater {
                            model: ["cloud", "local"]
                            delegate: Column {
                                required property string modelData
                                width: parent.width
                                Text {
                                    text: modelData === "cloud" ? "Cloud" : "On this computer"
                                    color: Theme.uiTextFaint
                                    font.family: fontFamily; font.pixelSize: Theme.fontSmall
                                    topPadding: 14; bottomPadding: 6
                                }
                                Repeater {
                                    model: cfg.providersFor(modelData)
                                    delegate: Rectangle {
                                        required property string modelData
                                        width: parent.width
                                        height: 42
                                        radius: Theme.radiusControl
                                        color: ch.hovered ? Theme.uiNavHover : "transparent"
                                        HoverHandler { id: ch; cursorShape: Qt.PointingHandCursor }
                                        Glyph {
                                            id: cgi
                                            x: 10
                                            anchors.verticalCenter: parent.verticalCenter
                                            d: cfg.catalog[modelData].where === "local"
                                               ? ico.chip : ico.cloud
                                            px: Theme.iconMd; tint: Theme.uiTextDim
                                        }
                                        Text {
                                            anchors.left: cgi.right; anchors.leftMargin: 11
                                            anchors.verticalCenter: parent.verticalCenter
                                            text: cfg.catalog[modelData].name
                                            color: Theme.uiText
                                            font.family: fontFamily
                                            font.pixelSize: Theme.fontBase
                                            font.weight: Font.Medium
                                        }
                                        Glyph {
                                            anchors.right: parent.right; anchors.rightMargin: 10
                                            anchors.verticalCenter: parent.verticalCenter
                                            d: ico.forward
                                            px: Theme.iconSm; tint: Theme.uiTextFaint
                                        }
                                        MouseArea {
                                            anchors.fill: parent
                                            cursorShape: Qt.PointingHandCursor
                                            onClicked: root.beginAdd(modelData)
                                        }
                                    }
                                }
                            }
                        }
                    }

                    // ── step 2 / the per-model sheet ──
                    Column {
                        id: formCol
                        width: parent.width
                        visible: root.addStep === 2 || root.addEditing
                        readonly property var cat: cfg.catalog[root.addProviderId] !== undefined
                                                   ? cfg.catalog[root.addProviderId] : ({})
                        readonly property var caps: cat.capabilities !== undefined
                                                    ? cat.capabilities : ({})
                        // Nothing below the key can be truthful until the provider can be asked
                        // what it has, so the form stops there until there is one.
                        readonly property bool ready: root.addKind === "local" || root.addHasKey

                        Row_ {
                            visible: root.addEditing
                            label: "Use this as the default model"
                            Loader {
                                sourceComponent: cfg.values["primary"] === root.addProviderId
                                                 ? isDefaultChip : setDefaultBtn
                            }
                        }
                        Row_ {
                            visible: formCol.ready
                            label: "Model"
                            Dropdown {
                                alignRight: true
                                options: cfg.modelOptions[root.addProviderId] !== undefined
                                         ? cfg.modelOptions[root.addProviderId] : []
                                value: root.addModel
                                onPicked: function (v) { root.addModel = v }
                            }
                        }
                        Row_ {
                            visible: root.addKind === "cloud"
                            label: "API key"
                            Field {
                                implicitWidth: 240
                                echoMode: TextInput.Password
                                placeholderText: root.addHasKey ? "Replace the stored key"
                                                                : "Paste a key"
                                onTextChanged: { root.addKey = text; root.addHasKey = text.length > 0 }
                            }
                            // Fetching the model list IS the key test, so one button does both. It
                            // passes the TYPED key: nothing is stored until you commit, so probing
                            // the credential store would test the old one.
                            Btn {
                                label: root.addProbe === "fetching" ? "Testing…" : "Test"
                                enabled: root.addProbe !== "fetching"
                                onClicked: cfg.testProvider(root.addProviderId, root.addKey)
                            }
                        }
                        // What the provider actually said. Without this a wrong key and a dropped
                        // connection look identical — both just leave the picker empty.
                        Text {
                            width: parent.width
                            visible: root.addKind === "cloud" && root.addProbeMessage !== ""
                            text: root.addProbeMessage
                            color: root.addProbe === "ok" ? Theme.uiText : Theme.uiTextFaint
                            font.family: fontFamily; font.pixelSize: Theme.fontSmall
                            topPadding: 8; bottomPadding: 8
                            wrapMode: Text.WordWrap
                        }
                        Row_ {
                            visible: root.addKind === "local"
                            label: "Address"
                            desc: "Where the local server is listening."
                            Field {
                                implicitWidth: 240
                                text: root.addEndpoint
                                onTextChanged: root.addEndpoint = text
                            }
                        }
                        Row_ {
                            visible: formCol.ready && formCol.caps.effort !== undefined
                            divider: formCol.caps.thinking === true
                            label: "Effort"
                            EffortDots {
                                options: formCol.caps.effort !== undefined ? formCol.caps.effort : []
                                value: root.addEffort
                                onPicked: function (v) { root.addEffort = v }
                            }
                        }
                        Row_ {
                            visible: formCol.ready && formCol.caps.thinking === true
                            label: "Extended thinking"
                            divider: false
                            Toggle {
                                on: root.addThinking
                                onToggled: function (v) { root.addThinking = v }
                            }
                        }
                        Text {
                            width: parent.width
                            visible: !formCol.ready
                            text: "Add a key to load this provider's models"
                            color: Theme.uiTextFaint
                            font.family: fontFamily; font.pixelSize: Theme.fontBase
                            horizontalAlignment: Text.AlignHCenter
                            topPadding: 22; bottomPadding: 22
                        }
                    }
                }
            }

            // Remove sits bottom-LEFT, away from the button you press on the way out: a
            // destructive action and a dismissal should never be neighbours.
            Item {
                id: sheetFoot
                anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right
                height: 62
                Rectangle {
                    anchors.top: parent.top
                    width: parent.width; height: 1; color: Theme.hairline
                }
                Btn {
                    visible: root.addEditing
                    x: 20
                    anchors.verticalCenter: parent.verticalCenter
                    label: "Remove"
                    danger: true
                    onClicked: { root.confirmTarget = root.addProviderId; root.confirmOpen = true }
                }
                Row {
                    anchors.right: parent.right; anchors.rightMargin: 20
                    anchors.verticalCenter: parent.verticalCenter
                    spacing: 8
                    Btn {
                        visible: !root.addEditing
                        label: "Cancel"
                        onClicked: root.manageOpen = false
                    }
                    Btn {
                        visible: root.addStep === 2 || root.addEditing
                        label: root.addEditing ? "Done" : "Add model"
                        primary: !root.addEditing
                        onClicked: root.commitAdd()
                    }
                }
            }
        }
    }

    Component { id: isDefaultChip
        Rectangle {
            implicitWidth: dcl.implicitWidth + 20; implicitHeight: 28
            radius: 6
            color: "transparent"
            border.width: 1; border.color: Theme.hairlineStrong
            Text {
                id: dcl
                anchors.centerIn: parent
                text: "Current default"
                color: Theme.uiTextDim
                font.family: fontFamily; font.pixelSize: Theme.fontSmall
            }
        }
    }
    Component { id: setDefaultBtn
        Btn {
            label: "Set as default"
            onClicked: cfg.setPrimary(root.addProviderId)
        }
    }

    // ── the confirmation ──
    // Stacks OVER the sheet rather than replacing it, so Cancel returns you where you were. It
    // NAMES what it will remove: a confirmation you can answer without reading is not one.
    Rectangle {
        anchors.fill: parent
        color: Qt.rgba(0, 0, 0, 0.55)
        visible: root.confirmOpen
        MouseArea { anchors.fill: parent; onClicked: root.confirmOpen = false }
        Rectangle {
            anchors.centerIn: parent
            width: 380
            height: cfCol.implicitHeight + 30
            radius: 14
            color: Theme.surfaceShell
            border.width: 1; border.color: Theme.hairlineStrong
            MouseArea { anchors.fill: parent }
            Column {
                id: cfCol
                x: 20; y: 15
                width: parent.width - 40
                spacing: 8
                Text {
                    width: parent.width
                    text: "Remove " + (cfg.catalog[root.confirmTarget] !== undefined
                                       ? cfg.catalog[root.confirmTarget].name
                                       : root.confirmTarget) + "?"
                    color: Theme.uiText
                    font.family: fontFamily; font.pixelSize: Theme.fontHeading
                    font.weight: Font.DemiBold
                }
                Text {
                    width: parent.width
                    text: "Removing this model prevents Gemma from accessing the API key but does not delete it from your system's credential store. You would have to delete it manually."
                    color: Theme.uiTextDim
                    font.family: fontFamily; font.pixelSize: Theme.fontBase
                    wrapMode: Text.WordWrap
                }
                Item { width: 1; height: 6 }
                Row {
                    anchors.right: parent.right
                    spacing: 8
                    Btn { label: "Cancel"; onClicked: root.confirmOpen = false }
                    Btn {
                        label: "Remove"
                        danger: true
                        onClicked: {
                            cfg.removeProvider(root.confirmTarget)
                            root.confirmOpen = false
                            root.manageOpen = false
                        }
                    }
                }
            }
        }
    }

    // ── resize grips ──────────────────────────────────────────────────────────
    // Frameless means the edges are ours; `startSystemResize` hands the drag back to Windows, so
    // the snap-to-edge feedback is the OS's own.
    component Grip: MouseArea {
        property int edges: 0
        acceptedButtons: Qt.LeftButton
        onPressed: root.startSystemResize(edges)
    }
    Grip { edges: Qt.LeftEdge; width: root.grip
           anchors.left: parent.left; anchors.top: parent.top; anchors.bottom: parent.bottom
           cursorShape: Qt.SizeHorCursor }
    Grip { edges: Qt.RightEdge; width: root.grip
           anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom
           cursorShape: Qt.SizeHorCursor }
    Grip { edges: Qt.TopEdge; height: root.grip
           anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
           cursorShape: Qt.SizeVerCursor }
    Grip { edges: Qt.BottomEdge; height: root.grip
           anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right
           cursorShape: Qt.SizeVerCursor }
    Grip { edges: Qt.LeftEdge | Qt.TopEdge; width: root.grip * 2; height: root.grip * 2
           anchors.left: parent.left; anchors.top: parent.top; cursorShape: Qt.SizeFDiagCursor }
    Grip { edges: Qt.RightEdge | Qt.TopEdge; width: root.grip * 2; height: root.grip * 2
           anchors.right: parent.right; anchors.top: parent.top; cursorShape: Qt.SizeBDiagCursor }
    Grip { edges: Qt.LeftEdge | Qt.BottomEdge; width: root.grip * 2; height: root.grip * 2
           anchors.left: parent.left; anchors.bottom: parent.bottom; cursorShape: Qt.SizeBDiagCursor }
    Grip { edges: Qt.RightEdge | Qt.BottomEdge; width: root.grip * 2; height: root.grip * 2
           anchors.right: parent.right; anchors.bottom: parent.bottom; cursorShape: Qt.SizeFDiagCursor }
}
