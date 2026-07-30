// The settings window (spec/70, D29) — the only surface besides the island the user ever sees.
//
// Two sections behind a top-bar toggle (the sandbox "data page"): Models is a card roster
// (Ask / Dictate doors), Config folds Profile, Preferences and Triggers into one coded list.
// Both are built from `spec/schemas/settings.json` — `cfg.panes`/`cfg.groupsFor` name the
// Config bands, `cfg.rowsFor`/`rowsInGroup` name their rows, `cfg.models` the roster, and
// `cfg.meta[key]` carries each row's label, help, type and whether its consumer exists yet.
// Adding a knob is a JSON edit. Palette is the Marathon set (Theme.qml, D29 re-skin).
//
// Controls are drawn here rather than taken from Quick Controls' styled set: the island's look
// is austere and monochrome, and restyling stock controls to match costs more than drawing a
// switch. Controls.Basic is imported for the three things worth borrowing — text entry,
// scrolling and popup dismissal — because those are fiddly and boring, which is the whole test.
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Shapes
import teleprompter

Window {
    id: root
    title: "Gemma — Settings"
    width: 1000
    height: 690
    minimumWidth: 840
    minimumHeight: 560
    color: Theme.surfaceShell

    // No native title bar. It carried three things the design has no use for — a caption
    // strip, Qt's placeholder icon and the window title — and none of them earn their height
    // next to a sidebar that already says "Gemma". Frameless means this file owns what the OS
    // was doing: `startSystemMove` for dragging (Aero Snap keeps working, because Windows is
    // still the one moving the window) and `startSystemResize` on the edges. The host asks
    // DWM for rounded corners, so the shape still looks native.
    flags: Qt.Window | Qt.FramelessWindowHint

    property string section: "models"             // the top-bar nav: "models" | "config"
    property bool manageOpen: false
    readonly property int topH: 58                // the top bar
    readonly property int grip: 6                 // resize edge thickness
    readonly property int fadeHeight: 22          // the scroller's top clearance

    // ── Add-a-model state ────────────────────────────────────────────────────
    // Held on the window rather than in the sheet so it survives the sheet being rebuilt, and
    // so `commitAdd` has one place to read from. Nothing here is written to disk until Save.
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
        manageOpen = true
    }

    function beginAdd(kind) {
        var ids = cfg.providersFor(kind)
        addKind = kind
        addEditing = false
        addProviderId = ids.length > 0 ? ids[0] : ""
        addKey = ""
        addHasKey = false
        addModel = ""
        addEffort = ""
        addThinking = false
        addTemperature = "0.7"
        addEndpoint = addProviderId !== "" && cfg.catalog[addProviderId].endpoint !== undefined
                      ? cfg.catalog[addProviderId].endpoint : ""
        addStep = 2
    }

    function beginEdit(pid) {
        var cat = cfg.catalog[pid]
        var st = cfg.models[pid]
        addKind = cat.where
        addEditing = true
        addProviderId = pid
        addKey = ""
        // A stored key counts as present: the form is asking whether it can go on, not
        // whether you typed something just now.
        addHasKey = cat.auth !== "key" || cfg.keys[pid] === "stored"
        addModel = st && st.model ? st.model : ""
        addEffort = st && st.effort ? st.effort : ""
        addThinking = st ? st.thinking === true : false
        addTemperature = st && st.temperature !== undefined ? String(st.temperature) : "0.7"
        addEndpoint = st && st.endpoint !== undefined ? st.endpoint
                      : (cat.endpoint !== undefined ? cat.endpoint : "")
        addStep = 2
        // Editing an existing provider: fill the picker from the stored key without waiting for
        // a Test press. Cheap — a list already held is not re-fetched.
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
    }
    // Reduced motion is the machine's "show animations" setting, mirrored by the host (U-01).
    readonly property int t: reducedMotion ? 0 : Theme.durationControl

    // ── glyphs ────────────────────────────────────────────────────────────────
    // Stroked 24×24 paths, kept here rather than shipped as files: they are one line each and
    // never need to be edited by anything but this window.
    // Material Symbols Outlined codepoints (the font is bundled + subset to exactly these). Each
    // value is the glyph char; the Glyph component renders it as font text. Add an icon here AND
    // add its codepoint to the subset step in fonts/ (an unsubsetted glyph renders as tofu).
    QtObject {
        id: ico
        readonly property string cloud:   "\uf15c"   // cloud            — a provider-hosted model
        readonly property string chip:    "\ue322"   // memory          — a local model
        readonly property string sparkle: "\ue65f"   // auto_awesome    — the Ask brain
        readonly property string kebab:   "\ue5d4"   // more_vert       — a card's configure/⋮ affordance
        readonly property string check:   "\ue668"   // check           — selected row
        readonly property string chevron: "\ue5cf"   // expand_more     — a dropdown's open indicator
        readonly property string plus:    "\ue145"   // add             — add a model
        readonly property string trash:   "\ue92e"   // delete          — remove a model
        readonly property string close:   "\ue5cd"   // close           — dismiss the sheet
        readonly property string minimize:"\ue15b"   // remove          — caption: minimise
        readonly property string maximize:"\ue3c6"   // crop_square     — caption: maximise
        readonly property string restore: "\ue3e0"   // filter_none     — caption: restore (maximised)
        readonly property string back:    "\ue5cb"   // chevron_left    — step 2 → step 1
        readonly property string edit:    "\uf097"   // edit            — configure a listed model
    }

    // ── building blocks ───────────────────────────────────────────────────────

    // An icon, drawn as one Material Symbols glyph. `d` is the glyph char (an `ico.*`); `px` is
    // the box the glyph is centred in, fed to the font's optical-size axis so it stays crisp at
    // any size. Weight is a real font axis now, so there is no stroke to fudge.
    component Glyph: Item {
        id: g
        property string d: ""
        property color tint: Theme.uiText
        property real px: 18
        property int weight: Theme.iconWeight
        implicitWidth: px
        implicitHeight: px
        Text {
            anchors.centerIn: parent
            text: g.d
            color: g.tint
            font.family: Theme.fontIcon
            font.pixelSize: g.px
            // opsz clamps to the font's axis range (20–48); FILL 0 / GRAD 0 keep it outlined.
            font.variableAxes: ({ "wght": g.weight, "opsz": g.px, "FILL": 0, "GRAD": 0 })
            renderType: Text.QtRendering
        }
    }

    // Monochrome by default. `accent: true` fills with the lamp amber — used by exactly one
    // switch in the app, the one that opens the microphone.
    component Toggle: Item {
        id: sw
        property bool on: false
        property bool enabled: true
        signal toggled(bool value)
        implicitWidth: 46
        implicitHeight: 26
        opacity: enabled ? 1 : 0.55
        Rectangle {
            id: track
            anchors.fill: parent
            radius: height / 2
            color: sw.on ? Theme.accent : Theme.uiTrackOff
            border.width: sw.on ? 0 : 1
            border.color: Theme.hairline
            Behavior on color { ColorAnimation { duration: root.t } }
            Rectangle {
                width: 20; height: 20; radius: 10
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
        focus: false
        Keys.onSpacePressed: if (sw.enabled) sw.toggled(!sw.on)
    }

    // One row inside a card: icon well, label + optional help, and a control on the right.
    component CardRow: Item {
        id: r
        property string glyph: ""
        property string label: ""
        property string help: ""
        property bool divider: false
        property bool sunken: false        // sub-rows of a provider card sit a shade lower
        property int inset: 17             // 17 inside a card; ~0 for a plain list row
        property bool strong: false        // a card's own title; never an ordinary row
        default property alias control: slot.data
        width: parent ? parent.width : 0
        implicitHeight: Math.max(72, body.implicitHeight + 34)
        Rectangle {
            anchors.fill: parent
            color: r.sunken ? Qt.rgba(0, 0, 0, 0.14) : "transparent"
        }
        Rectangle {
            visible: r.divider
            width: parent.width; height: 1
            color: Theme.hairline
        }
        Item {
            anchors.fill: parent
            anchors.leftMargin: r.inset
            anchors.rightMargin: r.inset
            Rectangle {
                id: well
                visible: r.glyph !== ""
                width: 36; height: 36; radius: 10
                anchors.verticalCenter: parent.verticalCenter
                color: Theme.uiHover
                Glyph { anchors.centerIn: parent; d: r.glyph }
            }
            Column {
                id: body
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: well.visible ? well.right : parent.left
                anchors.leftMargin: well.visible ? 14 : 0
                anchors.right: slot.left
                anchors.rightMargin: 14
                spacing: Theme.rowGap
                Text {
                    width: parent.width
                    text: r.label
                    color: Theme.uiText
                    font.family: fontFamily
                    font.pixelSize: Theme.fontBase
                    font.weight: r.strong ? Font.DemiBold : Font.Normal
                    elide: Text.ElideRight
                    lineHeight: Theme.lineBox(Theme.fontBase)
                    lineHeightMode: Text.FixedHeight
                }
                Text {
                    width: parent.width
                    visible: r.help !== ""
                    text: r.help
                    color: Theme.uiTextDim
                    font.family: fontFamily
                    font.pixelSize: Theme.fontBase
                    wrapMode: Text.WordWrap
                    lineHeight: Theme.lineBox(Theme.fontBase)
                    lineHeightMode: Text.FixedHeight
                }
            }
            Item {
                id: slot
                anchors.right: parent.right
                anchors.verticalCenter: parent.verticalCenter
                implicitWidth: childrenRect.width
                implicitHeight: childrenRect.height
                width: implicitWidth
                height: implicitHeight
            }
        }
    }

    component Field: TextField {
        property bool mono: false
        implicitWidth: 190
        implicitHeight: 38
        padding: 0
        leftPadding: 11
        rightPadding: 11
        color: Theme.uiText
        selectionColor: Theme.accent
        selectedTextColor: Theme.surfaceShell
        font.family: mono ? "Consolas" : fontFamily
        font.pixelSize: Theme.fontBase
        verticalAlignment: Text.AlignVCenter
        background: Rectangle {
            radius: Theme.radiusControl
            color: Theme.surfaceSunk
            border.width: 1
            border.color: parent.activeFocus ? Theme.uiText : Theme.hairlineStrong
            Behavior on border.color { ColorAnimation { duration: root.t } }
        }
    }

    component TextBox: Rectangle {
        id: tb
        property alias text: area.text
        property string placeholderText: ""
        property bool enabled: true
        signal edited(string value)
        implicitHeight: 92
        radius: Theme.radiusControl
        color: Theme.surfaceSunk
        border.width: 1
        border.color: area.activeFocus ? Theme.uiText : Theme.hairlineStrong
        opacity: enabled ? 1 : 0.55
        Behavior on border.color { ColorAnimation { duration: root.t } }
        TextArea {
            id: area
            anchors.fill: parent
            anchors.margins: 9
            enabled: tb.enabled
            wrapMode: TextArea.Wrap
            color: Theme.uiText
            selectionColor: Theme.accent
            selectedTextColor: Theme.surfaceShell
            placeholderText: tb.placeholderText
            placeholderTextColor: Theme.uiTextFaint
            font.family: fontFamily
            font.pixelSize: Theme.fontBase
            background: null
            onEditingFinished: tb.edited(text)
        }
    }

    // A dropdown drawn to match the rest of the window — Popup is borrowed only for its
    // dismiss-on-outside-click behaviour, which is not worth hand-rolling.
    component Dropdown: Item {
        id: dd
        property var options: []
        property string value: ""
        property bool enabled: true
        property color bg: Theme.surfaceSunk      // the card "well" variant passes surfaceDeep (pure black)
        property int fontPx: Theme.fontBase
        property bool mono: false                 // model-id pickers set true; words (language) stay sans
        // Nothing to choose (no options yet, or still fetching) → the whole control greys out and is
        // inert, instead of opening to a placeholder item. One rule, every dropdown (Thomas 2026-07-28).
        readonly property bool active: enabled && options.length > 0
        signal picked(string value)
        implicitWidth: 230
        implicitHeight: 38
        opacity: active ? 1 : 0.55
        Rectangle {
            id: trigger
            anchors.fill: parent
            radius: Theme.radiusControl
            color: dd.bg
            border.width: 1
            border.color: menu.opened ? Theme.uiText
                                      : (th.hovered ? Theme.uiEdgeHover
                                                    : Theme.hairlineStrong)
            Behavior on border.color { ColorAnimation { duration: root.t } }
            HoverHandler { id: th; enabled: dd.active }
            Text {
                anchors.left: parent.left; anchors.leftMargin: 11
                anchors.right: chev.left; anchors.rightMargin: 8
                anchors.verticalCenter: parent.verticalCenter
                text: dd.value === "" ? "—" : dd.value
                color: dd.active ? Theme.uiText : Theme.uiTextFaint
                font.family: dd.mono ? Theme.fontMono : fontFamily
                font.pixelSize: dd.fontPx
                elide: Text.ElideRight
            }
            Glyph {
                id: chev
                anchors.right: parent.right; anchors.rightMargin: 10
                anchors.verticalCenter: parent.verticalCenter
                d: ico.chevron; px: 13; tint: Theme.uiTextFaint
                rotation: menu.opened ? 180 : 0
                Behavior on rotation { NumberAnimation { duration: root.t } }
            }
            MouseArea {
                anchors.fill: parent
                enabled: dd.active
                cursorShape: Qt.PointingHandCursor
                onClicked: menu.opened ? menu.close() : menu.open()
            }
        }
        Popup {
            id: menu
            y: parent.height + 6
            width: Math.max(parent.width, 216)
            padding: 5
            background: Rectangle {
                radius: 10
                color: Theme.surfacePop
                border.width: 1
                border.color: Theme.hairlineStrong
            }
            contentItem: Item {
                implicitWidth: menu.availableWidth
                implicitHeight: Math.min(list.contentHeight, Theme.dropdownRows * 37)
                ListView {
                    id: list
                    anchors.fill: parent
                    visible: dd.options.length > 0
                    model: dd.options
                    clip: true
                    spacing: 1
                    boundsBehavior: Flickable.StopAtBounds
                    currentIndex: dd.options.indexOf(dd.value)
                    ScrollBar.vertical: ThemedScrollBar {}
                    delegate: Rectangle {
                        required property string modelData
                        width: list.width
                        height: 36
                        radius: 6
                        color: oh.hovered ? Theme.uiSelected : "transparent"
                        HoverHandler { id: oh }
                        Glyph {
                            id: tick
                            anchors.left: parent.left; anchors.leftMargin: 10
                            anchors.verticalCenter: parent.verticalCenter
                            d: ico.check; px: 13
                            opacity: modelData === dd.value ? 1 : 0
                        }
                        Text {
                            anchors.left: tick.right; anchors.leftMargin: 9
                            anchors.right: parent.right; anchors.rightMargin: 10
                            anchors.verticalCenter: parent.verticalCenter
                            text: modelData
                            color: modelData === dd.value ? Theme.uiText : Theme.uiTextDim
                            font.family: dd.mono ? Theme.fontMono : fontFamily
                            font.pixelSize: dd.fontPx
                            elide: Text.ElideRight
                        }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: { dd.picked(modelData); menu.close() }
                        }
                    }
                }
            }
        }
    }

    // Effort is an ordered scale, so it reads as one rather than hiding in a dropdown.
    component Segmented: Rectangle {
        id: seg
        property var options: []
        property string value: ""
        property bool enabled: true
        signal picked(string value)
        implicitWidth: strip.width + 4
        implicitHeight: 38
        radius: Theme.radiusControl
        color: Theme.surfaceSunk
        border.width: 1
        border.color: Theme.hairlineStrong
        Row {
            id: strip
            anchors.centerIn: parent
            spacing: 0
            Repeater {
                model: seg.options
                delegate: Rectangle {
                    required property string modelData
                    readonly property bool active: modelData === seg.value
                    width: lbl.width + 24
                    height: 32
                    radius: 6
                    color: active ? Theme.uiSelected
                                  : "transparent"
                    Behavior on color { ColorAnimation { duration: root.t } }
                    Text {
                        id: lbl
                        anchors.centerIn: parent
                        text: modelData
                        color: active ? Theme.uiText : (sh.hovered ? Theme.uiText : Theme.uiTextFaint)
                        font.family: fontFamily
                        font.pixelSize: Theme.fontSmall
                        font.weight: Font.Medium
                    }
                    HoverHandler { id: sh }
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

    component TextButton: Rectangle {
        id: btn
        property string label: ""
        property string glyph: ""
        property bool primary: false      // the one affirmative action on a sheet
        signal clicked()
        implicitWidth: brow.width + 28
        implicitHeight: 36
        radius: Theme.radiusControl
        color: btn.primary ? (bh.hovered ? Theme.navTextActive : Theme.uiInk)
                           : (bh.hovered ? Theme.uiHoverStrong
                                         : Theme.uiNavHover)
        border.width: btn.primary ? 0 : 1
        border.color: bh.hovered ? Theme.uiEdgeHover
                                 : Theme.hairlineStrong
        Behavior on color { ColorAnimation { duration: root.t } }
        HoverHandler { id: bh }
        Row {
            id: brow
            anchors.centerIn: parent
            spacing: 7
            Glyph {
                visible: btn.glyph !== ""
                d: btn.glyph; px: 14
                anchors.verticalCenter: parent.verticalCenter
            }
            Text {
                text: btn.label
                color: btn.primary ? Theme.surfaceShell : Theme.uiText
                font.family: fontFamily
                font.pixelSize: Theme.fontBase
                font.weight: Font.Medium
                anchors.verticalCenter: parent.verticalCenter
            }
        }
        MouseArea {
            anchors.fill: parent
            cursorShape: Qt.PointingHandCursor
            onClicked: btn.clicked()
        }
    }

    component GroupLabel: Text {
        property bool first: false         // the pane's top clearance is its gap instead
        color: Theme.uiText
        font.family: fontFamily
        font.pixelSize: Theme.fontHeading
        font.weight: Font.DemiBold
        topPadding: first ? 0 : Theme.groupGapTop
        bottomPadding: Theme.groupGapBottom
        leftPadding: 2
    }

    // ── data-page building blocks (D29 re-skin) ───────────────────────────────

    // The display face for headings and names — bold Archivo, normal case (Thomas, 2026-07-26:
    // the wide all-caps read as a sports app). Used for the door headers, the Config band titles
    // and the model-card names; never body copy.
    component Display: Text {
        color: Theme.uiText
        font.family: fontFamily
        font.weight: Font.Bold
        font.letterSpacing: -0.4
    }

    // A faint machine code — LLM_ASK, SEC.01, P.01, a model id. Below the window's 14 px floor on
    // purpose: a code is a stamp, not prose, so it reads as a mark rather than a size in the scale.
    component CodeLabel: Text {
        color: Theme.uiTextFaint
        font.family: Theme.fontMono
        font.pixelSize: 11
        font.letterSpacing: -0.2
    }

    // The Gemma mark from its 1024 path — kept out of `ico` (a 24-unit set the glyph check clamps)
    // and drawn via `path:` so that check never sees it. Two fills in one tint, as the sandbox does.
    component Mark: Item {
        id: mk
        property color tint: Theme.flare
        property real px: 24
        implicitWidth: px
        implicitHeight: px
        Shape {
            anchors.centerIn: parent
            width: 1024; height: 1024
            scale: mk.px / 1024
            preferredRendererType: Shape.CurveRenderer
            ShapePath {
                fillColor: mk.tint; strokeColor: "transparent"
                PathSvg { path: "M960,512 L512,512 L512,960 A448,448 0 1 1 960,512 Z" }
            }
            ShapePath {
                fillColor: mk.tint; strokeColor: "transparent"
                PathSvg { path: "M930.301,512L960,512L960,960L512,960L512,512C512,512 512,830.29 512.005,930.301C512.005,930.565 512.217,930.78 512.481,930.784C512.745,930.788 512.963,930.578 512.97,930.315C527.628,706.686 706.686,527.628 930.315,512.974C930.577,512.962 930.783,512.743 930.779,512.481C930.775,512.218 930.564,512.005 930.301,512Z" }
            }
        }
    }

    // ── Config: one coded setting row ─ [ code ][ label + help ][ control ] ────
    // A textarea drops its box to a full-width row under the code. The control is chosen by the
    // schema `type`, so a new knob is a JSON edit and nothing here.
    component ConfigRow: Item {
        id: cr
        property string key: ""
        property string code: ""
        property bool first: false
        readonly property var m: cfg.meta[key]
        readonly property bool isArea: m.type === "textarea"
        readonly property int pad: 15
        width: parent ? parent.width : 0
        opacity: m.built ? 1 : Theme.opacityDim
        implicitHeight: cr.pad + (isArea ? areaCol.implicitHeight : body.implicitHeight) + cr.pad
        Rectangle {
            visible: !cr.first
            width: parent.width; height: 1
            color: Theme.hairline
        }
        CodeLabel {
            text: cr.code
            x: 0; y: cr.pad + 1
            width: 42
        }
        Item {
            id: body
            visible: !cr.isArea
            x: 48; y: cr.pad
            width: parent.width - 48
            implicitHeight: Math.max(labelCol.implicitHeight, ctlSlot.height)
            height: implicitHeight
            Column {
                id: labelCol
                width: Math.max(0, parent.width - ctlSlot.width - 16)
                spacing: Theme.rowGap
                Text {
                    width: parent.width
                    text: cr.m.label
                    color: Theme.uiText
                    font.family: fontFamily
                    font.pixelSize: Theme.fontBase
                    elide: Text.ElideRight
                    lineHeight: Theme.lineBox(Theme.fontBase)
                    lineHeightMode: Text.FixedHeight
                }
                Text {
                    width: parent.width
                    visible: cr.m.help !== undefined && cr.m.help !== ""
                    text: cr.m.help !== undefined ? cr.m.help : ""
                    color: Theme.uiTextDim
                    font.family: fontFamily
                    font.pixelSize: Theme.fontBase
                    wrapMode: Text.WordWrap
                    lineHeight: Theme.lineBox(Theme.fontBase)
                    lineHeightMode: Text.FixedHeight
                }
            }
            Item {
                id: ctlSlot
                anchors.right: parent.right
                y: Math.max(0, Theme.lineBox(Theme.fontBase) / 2 - height / 2)
                implicitWidth: ctl.implicitWidth
                implicitHeight: ctl.implicitHeight
                width: implicitWidth; height: implicitHeight
                Loader {
                    id: ctl
                    sourceComponent: cr.m.type === "bool" ? boolCtl
                                   : cr.m.type === "binding" ? bindingCtl
                                   : cr.m.type === "text" ? textCtl
                                   : cr.m.type === "enum"
                                     ? (cr.m.control === "segmented" ? segCtl : enumCtl)
                                   : providerCtl
                }
            }
        }
        Column {
            id: areaCol
            visible: cr.isArea
            x: 48; y: cr.pad
            width: parent.width - 48
            spacing: 9
            Text {
                text: cr.m.label
                color: Theme.uiText
                font.family: fontFamily
                font.pixelSize: Theme.fontBase
                lineHeight: Theme.lineBox(Theme.fontBase)
                lineHeightMode: Text.FixedHeight
            }
            TextBox {
                width: parent.width
                text: cfg.values[cr.key]
                enabled: cr.m.built
                placeholderText: "Anything Gemma should always keep in mind"
                onEdited: function (v) { cfg.set(cr.key, v) }
            }
        }
        Component { id: boolCtl
            Toggle { on: cfg.values[cr.key] === true; enabled: cr.m.built
                     onToggled: function (v) { cfg.set(cr.key, v) } } }
        Component { id: bindingCtl
            KeyRecorder { value: cfg.values[cr.key]; enabled: cr.m.built; animMs: root.t
                          onCommitted: function (combo) { cfg.set(cr.key, combo) } } }
        Component { id: textCtl
            Field { implicitWidth: 240; text: cfg.values[cr.key]; enabled: cr.m.built
                    onEditingFinished: cfg.set(cr.key, text) } }
        Component { id: enumCtl
            Dropdown { value: cfg.values[cr.key]
                       options: cr.m.choices !== undefined ? cr.m.choices : []
                       enabled: cr.m.built
                       onPicked: function (v) { cfg.set(cr.key, v) } } }
        Component { id: segCtl
            Segmented { options: cr.m.choices !== undefined ? cr.m.choices : []
                        value: cfg.values[cr.key]; enabled: cr.m.built
                        onPicked: function (v) { cfg.set(cr.key, v) } } }
        Component { id: providerCtl
            Dropdown { value: cfg.values[cr.key]; options: cfg.addedProviders
                       enabled: cr.m.built
                       onPicked: function (v) { cfg.set(cr.key, v) } } }
    }

    // ── Config: a numbered band ─ header column left (SEC.0n · title · count), rows right ──
    component ConfigBand: Item {
        id: band
        property string sec: ""
        property string title: ""
        property string prefix: "P"
        property string pane: ""
        property string group: ""
        property bool first: false
        readonly property var rows: group !== "" ? cfg.rowsInGroup(pane, group) : cfg.rowsFor(pane)
        readonly property real headW: Math.max(150, band.width * 0.22)
        width: parent ? parent.width : 0
        implicitHeight: Math.max(headCol.implicitHeight + 30, rowsCol.implicitHeight + 22) + 30
        Rectangle {
            visible: !band.first
            width: parent.width; height: 1
            color: Theme.hairline
        }
        Column {
            id: headCol
            x: 0; y: 30
            width: band.headW
            spacing: 7
            CodeLabel { text: band.sec; font.pixelSize: 10 }
            Display { text: band.title; font.pixelSize: 22; width: parent.width; wrapMode: Text.WordWrap }
            CodeLabel {
                text: band.rows.length + (band.rows.length === 1 ? " setting" : " settings")
                font.pixelSize: 10
            }
        }
        Column {
            id: rowsCol
            x: band.headW + 30
            y: 22
            width: band.width - x
            Repeater {
                model: band.rows
                delegate: ConfigRow {
                    required property string modelData
                    required property int index
                    key: modelData
                    code: band.prefix + "." + ("0" + (index + 1)).slice(-2)
                    first: index === 0
                }
            }
        }
    }

    // Effort as toggle boxes — each box's label is a tight dot cluster (1 · 2 · pyramid · square ·
    // 2-over-3), the count being the level's rank. Replaces the word segmented (Thomas 2026-07-27).
    component EffortDots: Rectangle {
        id: eff
        property var options: []
        property string value: ""
        signal picked(string v)
        implicitWidth: 200
        implicitHeight: 28
        radius: Theme.radiusControl
        color: Theme.surfaceSunk
        border.width: 1
        border.color: Theme.hairlineStrong
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
                    width: (eff.width - 4 - (eff.options.length - 1) * 2) / Math.max(1, eff.options.length)
                    height: parent.height
                    radius: 5
                    color: active ? Theme.surfaceLift : "transparent"
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

    // ── Models: one editor card ─ flag · name · model well · the dials the provider has · footer ──
    // A card is a small editor (Thomas 2026-07-27): the model well opens the picker; effort and
    // extended thinking appear only where the provider offers them, else a Notes line fills the
    // space; on/off is the header toggle, primary is set from the card, and the deep bits (key,
    // temperature) sit behind the footer gear, which opens the Add/Edit sheet.
    component ModelCard: Rectangle {
        id: mc
        property string pid: ""
        property real cardH: 322
        readonly property var cat: cfg.catalog[pid]
        readonly property var st: cfg.models[pid]
        readonly property var caps: cat !== undefined && cat.capabilities !== undefined ? cat.capabilities : ({})
        readonly property bool isPrimary: cfg.values.primary === pid
        readonly property bool on: st !== undefined && st.on === true
        readonly property bool hasEffort: caps.effort !== undefined
        readonly property bool hasThinking: caps.thinking === true
        width: 246; height: cardH
        radius: Theme.radiusCard
        color: hovM.hovered ? Theme.surfaceLift : Theme.surfaceCard
        border.width: 1
        border.color: isPrimary ? Theme.accent : (hovM.hovered ? Theme.hairlineStrong : Theme.hairline)
        opacity: on ? 1 : 0.55
        clip: true
        Behavior on color { ColorAnimation { duration: root.t } }
        HoverHandler { id: hovM }

        Column {
            anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
            anchors.margins: 15
            spacing: 12

            // header — flag · on/off
            Item {
                width: parent.width; height: 18
                Row {
                    anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter; spacing: 6
                    Glyph { d: mc.cat.where === "cloud" ? ico.cloud : ico.chip; px: Theme.iconMd
                            tint: Theme.uiTextFaint; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: mc.cat.where === "cloud" ? "Cloud" : "Local"
                           color: Theme.uiTextFaint; font.family: fontFamily; font.pixelSize: Theme.fontSmall
                           anchors.verticalCenter: parent.verticalCenter }
                }
                Toggle {
                    anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                    scale: 0.9
                    on: mc.on
                    onToggled: function (v) { cfg.setModel(mc.pid, "on", v) }
                }
            }

            // name · primary
            Item {
                width: parent.width; height: 28
                Display {
                    anchors.left: parent.left; anchors.right: prim.left; anchors.rightMargin: 8
                    anchors.verticalCenter: parent.verticalCenter
                    text: mc.cat.name
                    font.pixelSize: Theme.fontCardName
                    fontSizeMode: Text.HorizontalFit; minimumPixelSize: 14
                    elide: Text.ElideRight
                }
                Rectangle {
                    id: prim
                    anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                    visible: mc.on
                    width: pl.width + 18; height: 24; radius: 5
                    color: mc.isPrimary ? Theme.accent : "transparent"
                    border.width: mc.isPrimary ? 0 : 1
                    border.color: Theme.hairlineStrong
                    Behavior on color { ColorAnimation { duration: root.t } }
                    Text {
                        id: pl
                        anchors.centerIn: parent
                        text: mc.isPrimary ? "Primary" : "Set primary"
                        color: mc.isPrimary ? Theme.surfaceShell : Theme.uiTextFaint
                        font.family: fontFamily; font.pixelSize: Theme.fontSmall
                        font.weight: mc.isPrimary ? Font.DemiBold : Font.Medium
                    }
                    MouseArea {
                        anchors.fill: parent
                        enabled: !mc.isPrimary
                        cursorShape: Qt.PointingHandCursor
                        onClicked: cfg.setPrimary(mc.pid)
                    }
                }
            }

            // model well
            Column {
                width: parent.width; spacing: 5
                Text { text: "Model"; color: Theme.uiTextFaint; font.family: fontFamily
                       font.pixelSize: Theme.fontCardLabel; font.weight: Font.DemiBold }
                Dropdown {
                    width: parent.width; implicitHeight: 34
                    bg: Theme.surfaceDeep; fontPx: Theme.fontCardMeta; mono: true
                    value: mc.st !== undefined && mc.st.model ? mc.st.model : ""
                    options: cfg.modelOptions[mc.pid] !== undefined ? cfg.modelOptions[mc.pid] : []
                    onPicked: function (v) { cfg.setModel(mc.pid, "model", v) }
                    Component.onCompleted: cfg.refreshModels(mc.pid)
                }
            }

            // effort — only if the provider has it
            Column {
                width: parent.width; spacing: 5
                visible: mc.hasEffort
                height: visible ? implicitHeight : 0
                Text { text: "Effort"; color: Theme.uiTextFaint; font.family: fontFamily
                       font.pixelSize: Theme.fontCardLabel; font.weight: Font.DemiBold }
                EffortDots {
                    width: parent.width
                    options: mc.caps.effort !== undefined ? mc.caps.effort : []
                    value: mc.st !== undefined && mc.st.effort ? mc.st.effort : ""
                    onPicked: function (v) { cfg.setModel(mc.pid, "effort", v) }
                }
            }

            // extended thinking — inline, only if the provider has it
            Item {
                width: parent.width; height: mc.hasThinking ? 24 : 0
                visible: mc.hasThinking
                Text { text: "Extended thinking"; color: Theme.uiTextFaint
                       anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter
                       font.family: fontFamily; font.pixelSize: Theme.fontCardLabel; font.weight: Font.DemiBold }
                Toggle {
                    anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                    scale: 0.82
                    on: mc.st !== undefined && mc.st.thinking === true
                    onToggled: function (v) { cfg.setModel(mc.pid, "thinking", v) }
                }
            }

            // notes — only for a provider with no dials, so the card is never an empty box
            Column {
                width: parent.width; spacing: 5
                visible: !mc.hasEffort && !mc.hasThinking
                height: visible ? implicitHeight : 0
                Text { text: "Notes"; color: Theme.uiTextFaint; font.family: fontFamily
                       font.pixelSize: Theme.fontCardLabel; font.weight: Font.DemiBold }
                Text {
                    width: parent.width
                    text: mc.cat.name + " runs the model as-is — no effort or thinking dials. Choose the model above."
                    color: Theme.uiTextDim; font.family: fontFamily; font.pixelSize: Theme.fontSmall
                    wrapMode: Text.WordWrap
                    lineHeight: Theme.lineBox(Theme.fontSmall); lineHeightMode: Text.FixedHeight
                }
            }
        }

        // footer — key status · gear (deep bits), pinned to the bottom
        Item {
            anchors.left: parent.left; anchors.right: parent.right; anchors.bottom: parent.bottom
            height: 44
            Rectangle { anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
                        height: 1; color: Theme.hairline }
            Row {
                visible: mc.cat.auth === "key"
                anchors.left: parent.left; anchors.leftMargin: 15
                anchors.verticalCenter: parent.verticalCenter; spacing: 7
                Rectangle { width: 7; height: 7; radius: 3.5; anchors.verticalCenter: parent.verticalCenter
                    color: cfg.keys[mc.pid] === "stored" ? "#5fbf7a" : Theme.uiTextFaint }
                Text { text: cfg.keys[mc.pid] === "stored" ? "key stored" : "no key"
                       color: Theme.uiTextFaint; font.family: fontFamily; font.pixelSize: Theme.fontCardMeta
                       anchors.verticalCenter: parent.verticalCenter }
            }
            Rectangle {
                anchors.right: parent.right; anchors.rightMargin: 11
                anchors.verticalCenter: parent.verticalCenter
                width: 30; height: 30; radius: 7
                color: gh.hovered ? Theme.uiHoverStrong : "transparent"
                HoverHandler { id: gh }
                Glyph { anchors.centerIn: parent; d: ico.kebab; px: Theme.iconLg
                        tint: gh.hovered ? Theme.uiText : Theme.uiTextFaint }
                MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                    onClicked: root.beginEdit(mc.pid) }
            }
        }
    }

    // The "+" tile that opens the Add sheet — sized to match the editor cards.
    component AddCard: Rectangle {
        id: ac
        property string label: "Add model"
        property real cardH: 322
        signal clicked()
        width: 246; height: cardH
        radius: Theme.radiusCard
        color: hovA.hovered ? Theme.uiNavHover : "transparent"
        border.width: 1
        border.color: hovA.hovered ? Theme.hairlineStrong : Theme.hairline
        Behavior on color { ColorAnimation { duration: root.t } }
        HoverHandler { id: hovA }
        Column {
            anchors.centerIn: parent
            spacing: 8
            Glyph { d: ico.plus; px: 22; tint: hovA.hovered ? Theme.uiText : Theme.uiTextFaint
                    anchors.horizontalCenter: parent.horizontalCenter }
            Text { text: ac.label; color: hovA.hovered ? Theme.uiText : Theme.uiTextFaint
                   font.family: fontFamily; font.pixelSize: Theme.fontCardLabel
                   anchors.horizontalCenter: parent.horizontalCenter }
        }
        MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor; onClicked: ac.clicked() }
    }

    // Dictate: a cleanup role, an editor card that stays dim until its consumer is built.
    component CleanupCard: Rectangle {
        id: cc
        property string key: ""
        property real cardH: 322
        readonly property var m: cfg.meta[key]
        readonly property string shortName: key === "cleanup_dictation" ? "Dictation"
                                          : key === "cleanup_prompts" ? "Prompts" : m.label
        width: 246; height: cardH
        radius: Theme.radiusCard
        color: Theme.surfaceCard
        border.width: 1; border.color: Theme.hairline
        opacity: m.built ? 1 : Theme.opacityDim
        clip: true
        Column {
            anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
            anchors.margins: 15
            spacing: 12
            Item {
                width: parent.width; height: 18
                Row {
                    anchors.left: parent.left; anchors.verticalCenter: parent.verticalCenter; spacing: 6
                    Glyph { d: ico.sparkle; px: Theme.iconMd; tint: Theme.uiTextFaint; anchors.verticalCenter: parent.verticalCenter }
                    Text { text: "Tidy"; color: Theme.uiTextFaint; font.family: fontFamily
                           font.pixelSize: Theme.fontSmall; anchors.verticalCenter: parent.verticalCenter }
                }
                Toggle {
                    anchors.right: parent.right; anchors.verticalCenter: parent.verticalCenter
                    scale: 0.82
                    on: cfg.values[cc.m.toggledBy] === true
                    enabled: cc.m.built
                    onToggled: function (v) { cfg.set(cc.m.toggledBy, v) }
                }
            }
            Display {
                width: parent.width
                text: cc.shortName; font.pixelSize: Theme.fontCardName
                fontSizeMode: Text.HorizontalFit; minimumPixelSize: 14; elide: Text.ElideRight
            }
            Column {
                width: parent.width; spacing: 5
                Text { text: "Engine"; color: Theme.uiTextFaint; font.family: fontFamily
                       font.pixelSize: Theme.fontCardLabel; font.weight: Font.DemiBold }
                Dropdown {
                    width: parent.width; implicitHeight: 34
                    bg: Theme.surfaceDeep; fontPx: Theme.fontCardMeta
                    value: cfg.values[cc.key] ? cfg.values[cc.key] : ""
                    options: cfg.addedProviders
                    enabled: cc.m.built
                    onPicked: function (v) { cfg.set(cc.key, v) }
                }
            }
            Column {
                width: parent.width; spacing: 5
                Text { text: "Notes"; color: Theme.uiTextFaint; font.family: fontFamily
                       font.pixelSize: Theme.fontCardLabel; font.weight: Font.DemiBold }
                Text {
                    width: parent.width
                    text: cc.key === "cleanup_dictation" ? "Which model tidies dictated text before it's pasted."
                        : "Cleans a spoken prompt before it reaches the assistant."
                    color: Theme.uiTextDim; font.family: fontFamily; font.pixelSize: Theme.fontSmall
                    wrapMode: Text.WordWrap
                    lineHeight: Theme.lineBox(Theme.fontSmall); lineHeightMode: Text.FixedHeight
                }
            }
        }
    }

    // ── layout ────────────────────────────────────────────────────────────────
    Item {
        anchors.fill: parent

        // ── top bar: brand · nav · on-air lamp (the caption buttons are a separate Row) ──
        Item {
            id: topBar
            anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
            height: root.topH
            // Drag handle, declared first so the brand, nav and lamp take their own clicks.
            MouseArea {
                anchors.fill: parent
                onPressed: root.startSystemMove()
                onDoubleClicked: root.visibility = root.visibility === Window.Maximized
                                 ? Window.Windowed : Window.Maximized
            }
            // segmented nav — Models | Config, CENTRED in the top bar. The orange brand Mark and
            // the "Gemma" wordmark were removed (Thomas, 2026-07-28): Gem — the mic indicator at
            // left — is the page's only mark now.
            Rectangle {
                anchors.horizontalCenter: parent.horizontalCenter
                anchors.verticalCenter: parent.verticalCenter
                width: navRow.width + 6; height: 40; radius: 9
                color: Theme.surfaceCard
                border.width: 1; border.color: Theme.hairline
                Row {
                    id: navRow
                    anchors.centerIn: parent
                    spacing: 2
                    Repeater {
                        model: [{ v: "models", l: "Models" }, { v: "config", l: "Config" }]
                        delegate: Rectangle {
                            required property var modelData
                            readonly property bool active: root.section === modelData.v
                            width: nlbl.width + 30; height: 32; radius: 6
                            color: active ? Theme.surfaceLift
                                          : (nvh.hovered ? Theme.uiNavHover : "transparent")
                            Behavior on color { ColorAnimation { duration: root.t } }
                            HoverHandler { id: nvh }
                            Text {
                                id: nlbl
                                anchors.centerIn: parent
                                text: modelData.l
                                color: active || nvh.hovered ? Theme.uiText : Theme.uiTextFaint
                                font.family: fontFamily; font.pixelSize: Theme.fontBase
                                font.weight: Font.DemiBold
                            }
                            MouseArea {
                                anchors.fill: parent
                                cursorShape: Qt.PointingHandCursor
                                onClicked: root.section = modelData.v
                            }
                        }
                    }
                }
            }
            // ── Gem: the mascot as the honest mic indicator (spec/50 rule 4), at the far LEFT of
            //    the top bar (the only mark on the page now — the brand Mark + "Gemma" were removed).
            //    She shows `listening` ONLY while the mic is actually capturing — never inferred —
            //    and otherwise mimes the turn: `working` while the brain composes, `speaking` for
            //    as long as the island's typewriter is laying the answer down, `done` once it has
            //    landed, `idle` between turns. The kit owns the animation: `gemPlayer` (gem.py)
            //    runs the kit's own script — the idle fidgets, the enters, the exits and the holds
            //    — and hands QML one URL to bind, so nothing here counts frames. ──
            Row {
                id: gemRow
                anchors.left: parent.left; anchors.leftMargin: 20
                anchors.verticalCenter: parent.verticalCenter
                spacing: 10
                readonly property bool capturing: overlay.state === "listening"
                // 2× the kit's 26px cell. Integer scales only (kit rule): a fractional factor makes
                // some pixel-cells wider than their neighbours. The next rung up, 3×, is 78px —
                // taller than this bar, and it needed the cell cropped to fit. The whole cell fits
                // here, so no crop: the guitar and the phone get their full run of the margin.
                Image {
                    anchors.verticalCenter: parent.verticalCenter
                    width: 52; height: 52
                    sourceSize: Qt.size(52, 52)
                    smooth: false                              // nearest-neighbour: keep the cells crisp
                    source: gemPlayer.source
                }
                Text {
                    anchors.verticalCenter: parent.verticalCenter
                    text: gemRow.capturing ? "Listening" : "Mic closed"
                    color: gemRow.capturing ? Theme.flare : Theme.uiTextFaint
                    font.family: fontFamily; font.pixelSize: Theme.fontSmall
                    font.weight: Font.DemiBold
                }
                // Neither the state nor the clock is bound here: `gemPlayer` follows the turn
                // itself (gem.py) and the island shows the same player, so two windows writing
                // one property would fight. This row just renders it.
            }
            Rectangle {
                anchors.bottom: parent.bottom
                width: parent.width; height: 1
                color: Theme.hairline
            }
        }

        // ── content: the active view, scrolling under a top fade ──
        Item {
            anchors.top: topBar.bottom; anchors.left: parent.left
            anchors.right: parent.right; anchors.bottom: parent.bottom

            Flickable {
                id: scroller
                anchors.fill: parent
                contentWidth: width
                // Both views are built ONCE and toggled by visibility, so switching sections is
                // instant — a single Loader that swapped sourceComponent rebuilt the whole view on
                // every click (the visible lag). Content height follows whichever is showing.
                contentHeight: (root.section === "models" ? mLoader.implicitHeight
                                                          : cLoader.implicitHeight) + root.fadeHeight + 44
                clip: true
                boundsBehavior: Flickable.StopAtBounds
                Loader {
                    id: mLoader
                    x: 30; y: root.fadeHeight; width: parent.width - 60; height: implicitHeight
                    visible: root.section === "models"
                    sourceComponent: modelsView
                }
                Loader {
                    id: cLoader
                    x: 30; y: root.fadeHeight; width: parent.width - 60; height: implicitHeight
                    visible: root.section === "config"
                    sourceComponent: configView
                }
                Connections { target: root; function onSectionChanged() { scroller.contentY = 0 } }
                ScrollBar.vertical: ThemedScrollBar {}
            }
            // top fade, so content dissolves under the top bar rather than cutting at it
            Rectangle {
                anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
                height: root.fadeHeight; z: 1
                gradient: Gradient {
                    GradientStop { position: 0.0; color: Theme.surfaceShell }
                    GradientStop { position: 1.0; color: "transparent" }
                }
            }
        }
    }

    // ── the two views ─────────────────────────────────────────────────────────
    // Models: the Ask / Dictate doors, a card roster. Config: the numbered bands. The top-bar
    // toggle loads one into the content scroller; both read the same schema the old panes did.
    Component {
        id: modelsView
        Item {
            id: mv
            width: parent ? parent.width : 0
            implicitHeight: col.implicitHeight + 24
            height: implicitHeight
            readonly property var ids: Object.keys(cfg.models)
            readonly property int cardH: 322
            // A horizontal band: cards overflow and scroll rather than wrap. A right-edge fade
            // hints there's more. Full-width, so ~4 cards show before any scrolling is needed.
            component Band: Item {
                default property alias content: bandRow.data
                width: parent ? parent.width : 0
                height: mv.cardH + 14        // room for the horizontal scrollbar below the cards
                Flickable {
                    id: flick
                    anchors.fill: parent
                    contentWidth: bandRow.width
                    contentHeight: height
                    flickableDirection: Flickable.HorizontalFlick
                    clip: true
                    boundsBehavior: Flickable.StopAtBounds
                    Row { id: bandRow; height: mv.cardH; spacing: 14 }
                    ScrollBar.horizontal: ThemedScrollBar {}
                }
                // Margin-width fades, one per side, each shown only when there is content off that
                // way — so a fade never sits over the first/last card once you scroll to that end.
                Rectangle {
                    anchors.left: parent.left; anchors.top: parent.top; height: mv.cardH; width: 30
                    visible: flick.contentX > 1
                    gradient: Gradient { orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: Theme.surfaceShell }
                        GradientStop { position: 1.0; color: "transparent" } }
                }
                Rectangle {
                    anchors.right: parent.right; anchors.top: parent.top; height: mv.cardH; width: 30
                    visible: flick.contentX < flick.contentWidth - flick.width - 1
                    gradient: Gradient { orientation: Gradient.Horizontal
                        GradientStop { position: 0.0; color: "transparent" }
                        GradientStop { position: 1.0; color: Theme.surfaceShell } }
                }
            }
            Column {
                id: col
                width: parent.width
                y: 6
                spacing: 26
                // ── Ask: the answer models + the Add card ──
                Column {
                    width: parent.width
                    spacing: 14
                    // Title + an always-visible Add, so a full band never buries the Add card off
                    // the right edge behind a scroll.
                    Item {
                        width: parent.width
                        height: askHdr.implicitHeight
                        Display { id: askHdr; text: "Ask"; font.pixelSize: 32
                                  anchors.verticalCenter: parent.verticalCenter }
                        Rectangle {
                            anchors.right: parent.right
                            anchors.verticalCenter: parent.verticalCenter
                            height: 34; radius: 8
                            width: addLbl.width + 30
                            color: addBtnH.hovered ? Theme.surfaceLift : Theme.surfaceCard
                            border.width: 1
                            border.color: addBtnH.hovered ? Theme.hairlineStrong : Theme.hairline
                            Behavior on color { ColorAnimation { duration: root.t } }
                            HoverHandler { id: addBtnH }
                            Row {
                                id: addLbl
                                anchors.centerIn: parent
                                spacing: 7
                                Glyph { d: ico.plus; px: 16; anchors.verticalCenter: parent.verticalCenter
                                        tint: addBtnH.hovered ? Theme.uiText : Theme.uiTextDim }
                                Display { text: "Add model"; font.pixelSize: Theme.fontBase
                                          anchors.verticalCenter: parent.verticalCenter
                                          color: addBtnH.hovered ? Theme.uiText : Theme.uiTextDim }
                            }
                            MouseArea { anchors.fill: parent; cursorShape: Qt.PointingHandCursor
                                        onClicked: root.openAdd() }
                        }
                    }
                    Band {
                        Repeater {
                            model: mv.ids
                            delegate: ModelCard { required property string modelData; pid: modelData }
                        }
                        AddCard { onClicked: root.openAdd() }
                    }
                }
                Rectangle { width: parent.width; height: 1; color: Theme.hairline }
                // ── Dictate: the cleanup roles ──
                Column {
                    width: parent.width
                    spacing: 14
                    Display { text: "Dictate"; font.pixelSize: 32 }
                    Band {
                        Repeater {
                            model: cfg.rowsFor("models")
                            delegate: CleanupCard { required property string modelData; key: modelData }
                        }
                    }
                }
            }
        }
    }

    Component {
        id: configView
        Item {
            id: cv
            width: parent ? parent.width : 0
            implicitHeight: bandsCol.implicitHeight + 10
            height: implicitHeight
            // Bands come from the schema: every pane but Models, its groups expanded. The row-code
            // prefix is a small fixed map (Profile→P, Preferences→S, Triggers→T), first letter else.
            readonly property var bands: {
                var out = []
                var n = 0
                var pm = { profile: "P", preferences: "S", triggers: "T" }
                for (var i = 0; i < cfg.panes.length; i++) {
                    var p = cfg.panes[i]
                    if (p.id === "models")
                        continue
                    var gs = p.groups
                    if (gs && gs.length) {
                        for (var g = 0; g < gs.length; g++) {
                            n += 1
                            out.push({ sec: "SEC." + ("0" + n).slice(-2), title: gs[g].label,
                                       prefix: pm[gs[g].id] !== undefined ? pm[gs[g].id] : gs[g].label.charAt(0),
                                       pane: p.id, group: gs[g].id })
                        }
                    } else {
                        n += 1
                        out.push({ sec: "SEC." + ("0" + n).slice(-2), title: p.label,
                                   prefix: pm[p.id] !== undefined ? pm[p.id] : p.label.charAt(0),
                                   pane: p.id, group: "" })
                    }
                }
                return out
            }
            Column {
                id: bandsCol
                width: parent.width
                Repeater {
                    model: cv.bands
                    delegate: ConfigBand {
                        required property var modelData
                        required property int index
                        sec: modelData.sec; title: modelData.title; prefix: modelData.prefix
                        pane: modelData.pane; group: modelData.group; first: index === 0
                    }
                }
            }
        }
    }

    // ── window chrome ────────────────────────────────────────────────────────
    // Frameless in the Edge/Chrome sense: the OS caption is gone (with its title text and Qt's
    // stand-in icon), and this file draws what was worth keeping — the three window buttons —
    // at Windows' own proportions, so they read as native rather than invented. Rounded
    // corners and the drop shadow are asked of DWM by the host; dragging and resizing go back
    // to Windows through startSystemMove/startSystemResize, so Aero Snap still works.

    // The three window buttons, top-right over the top bar (which owns dragging). They stay a
    // separate root child so they sit above the bar's drag handle and take their own clicks.
    Row {
        id: caption
        anchors.top: parent.top
        anchors.right: parent.right
        spacing: 0
        // Windows' own caption-button metrics (46×32) — the one place copying the platform
        // beats having a look of our own, because these three are muscle memory.
        component CaptionButton: Rectangle {
            id: cb
            property string d: ""
            property bool danger: false
            signal activated()
            width: 48
            height: root.topH        // full top-bar height, down to the border
            color: cbh.hovered ? (danger ? Theme.danger
                                         : Theme.uiHoverStrong)
                               : "transparent"
            Behavior on color { ColorAnimation { duration: root.t } }
            HoverHandler { id: cbh }
            Glyph {
                anchors.centerIn: parent
                d: cb.d
                px: 17
                tint: cbh.hovered && cb.danger ? Theme.navTextActive : Theme.uiTextDim
            }
            MouseArea { anchors.fill: parent; onClicked: cb.activated() }
        }
        CaptionButton {
            d: ico.minimize
            onActivated: root.showMinimized()
        }
        CaptionButton {
            d: root.visibility === Window.Maximized ? ico.restore : ico.maximize
            onActivated: root.visibility = root.visibility === Window.Maximized
                         ? Window.Windowed : Window.Maximized
        }
        CaptionButton {
            d: ico.close
            danger: true
            onActivated: root.close()
        }
    }

    // ── Add a model ──────────────────────────────────────────────────────────
    // Two steps, because there is no honest single-screen version: which models a provider has
    // — and which settings those models support — is something only the provider can answer,
    // and it cannot answer until it has a key. So: pick cloud or local, then fill a form that
    // grows as it learns. Replaces a sheet that listed three hardcoded providers as though
    // those were the only three in existence.
    Rectangle {
        id: scrim
        anchors.fill: parent
        color: Qt.rgba(0, 0, 0, 0.55)
        visible: root.manageOpen
        opacity: root.manageOpen ? 1 : 0
        Behavior on opacity { NumberAnimation { duration: root.t } }
        MouseArea { anchors.fill: parent; onClicked: root.manageOpen = false }

        Rectangle {
            anchors.centerIn: parent
            width: Math.min(560, parent.width - 52)
            height: Math.min(sheetInner.implicitHeight, parent.height - 52)
            radius: 13
            color: Theme.surfacePop
            border.width: 1
            border.color: Theme.hairlineStrong
            clip: true
            MouseArea { anchors.fill: parent }      // swallow clicks so the scrim does not close

            Column {
                id: sheetInner
                width: parent.width

                Item {
                    width: parent.width; height: 56
                    Rectangle {
                        id: backBtn
                        visible: root.addStep === 2
                        anchors.left: parent.left; anchors.leftMargin: 12
                        anchors.verticalCenter: parent.verticalCenter
                        width: 30; height: 30; radius: 7
                        color: bkh.hovered ? Theme.uiHoverStrong
                                           : "transparent"
                        HoverHandler { id: bkh }
                        Glyph { anchors.centerIn: parent; d: ico.back; px: 16; tint: Theme.uiTextDim }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.addStep = 1
                        }
                    }
                    Text {
                        anchors.left: backBtn.visible ? backBtn.right : parent.left
                        anchors.leftMargin: backBtn.visible ? 10 : 18
                        anchors.verticalCenter: parent.verticalCenter
                        text: root.addStep === 1 ? "Add a model"
                            : root.addEditing ? "Edit model"
                            : (root.addKind === "cloud" ? "Add a cloud model" : "Add a local model")
                        color: Theme.uiText
                        font.family: fontFamily; font.pixelSize: Theme.fontHeading
                        font.weight: Font.DemiBold
                    }
                    Rectangle {
                        anchors.right: parent.right; anchors.rightMargin: 14
                        anchors.verticalCenter: parent.verticalCenter
                        width: 30; height: 30; radius: 7
                        color: xh.hovered ? Theme.uiHoverStrong
                                          : "transparent"
                        HoverHandler { id: xh }
                        Glyph { anchors.centerIn: parent; d: ico.close; px: 16; tint: Theme.uiTextDim }
                        MouseArea {
                            anchors.fill: parent
                            cursorShape: Qt.PointingHandCursor
                            onClicked: root.manageOpen = false
                        }
                    }
                    Rectangle {
                        anchors.bottom: parent.bottom
                        width: parent.width; height: 1
                        color: Theme.hairline
                    }
                }

                // ── step 1: cloud or local, then what is already in play ──
                Column {
                    width: parent.width
                    visible: root.addStep === 1
                    padding: 14
                    spacing: 12
                    Row {
                        spacing: 12
                        Repeater {
                            model: [
                                { k: "cloud", n: "Cloud",
                                  d: "A provider you reach over the internet. Needs an API key." },
                                { k: "local", n: "Local",
                                  d: "A model running on this machine. No key, no internet." }
                            ]
                            delegate: Rectangle {
                                required property var modelData
                                width: (sheetInner.width - 40) / 2
                                height: tileCol.implicitHeight + 36
                                radius: Theme.radiusCard
                                color: tileH.hovered ? Theme.surfaceLift : Theme.surfaceCard
                                border.width: 1
                                border.color: tileH.hovered ? Theme.hairlineStrong : Theme.hairline
                                Behavior on color { ColorAnimation { duration: root.t } }
                                HoverHandler { id: tileH }
                                Column {
                                    id: tileCol
                                    anchors.left: parent.left; anchors.right: parent.right
                                    anchors.top: parent.top
                                    anchors.margins: 18
                                    spacing: 4
                                    Rectangle {
                                        width: 36; height: 36; radius: 10
                                        color: Theme.uiHover
                                        Glyph {
                                            anchors.centerIn: parent
                                            d: modelData.k === "cloud" ? ico.cloud : ico.chip
                                        }
                                    }
                                    Text {
                                        text: modelData.n
                                        color: Theme.uiText
                                        topPadding: 9
                                        font.family: fontFamily; font.pixelSize: Theme.fontBase
                                        font.weight: Font.DemiBold
                                    }
                                    Text {
                                        width: parent.width
                                        text: modelData.d
                                        color: Theme.uiTextDim
                                        wrapMode: Text.WordWrap
                                        font.family: fontFamily; font.pixelSize: Theme.fontBase
                                        lineHeight: Theme.lineBox(Theme.fontBase)
                                        lineHeightMode: Text.FixedHeight
                                    }
                                }
                                MouseArea {
                                    anchors.fill: parent
                                    cursorShape: Qt.PointingHandCursor
                                    onClicked: root.beginAdd(modelData.k)
                                }
                            }
                        }
                    }

                    GroupLabel { text: "Active models"; visible: cfg.addedProviders.length > 0 }
                    Repeater {
                        model: cfg.addedProviders
                        delegate: Rectangle {
                            required property string modelData
                            readonly property var cat: cfg.catalog[modelData]
                            width: sheetInner.width - 28
                            height: 62
                            radius: 10
                            color: rowH.hovered ? Theme.uiNavHover
                                                : "transparent"
                            HoverHandler { id: rowH }
                            Rectangle {
                                id: aWell
                                anchors.left: parent.left; anchors.leftMargin: 12
                                anchors.verticalCenter: parent.verticalCenter
                                width: 38; height: 38; radius: 9
                                color: Theme.uiHover
                                Glyph {
                                    anchors.centerIn: parent; px: 21
                                    d: cat.where === "cloud" ? ico.cloud : ico.chip
                                }
                            }
                            Column {
                                anchors.left: aWell.right; anchors.leftMargin: 12
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 2
                                Text {
                                    text: cat.name
                                    color: Theme.uiText
                                    font.family: fontFamily; font.pixelSize: Theme.fontBase
                                    font.weight: Font.DemiBold
                                }
                                Text {
                                    text: {
                                        var st = cfg.models[modelData]
                                        var bits = [st && st.model ? st.model : "no model"]
                                        if (cat.auth === "key")
                                            bits.push(cfg.keys[modelData] === "stored" ? "key stored" : "no key")
                                        return bits.join("  \u00b7  ")
                                    }
                                    color: Theme.uiTextFaint
                                    font.family: "Consolas"; font.pixelSize: Theme.fontSmall
                                }
                            }
                            Row {
                                anchors.right: parent.right; anchors.rightMargin: 10
                                anchors.verticalCenter: parent.verticalCenter
                                spacing: 4
                                Rectangle {
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 34; height: 34; radius: 8
                                    color: eh.hovered ? Theme.uiHoverStrong
                                                      : "transparent"
                                    HoverHandler { id: eh }
                                    Glyph {
                                        anchors.centerIn: parent; px: 19
                                        tint: eh.hovered ? Theme.uiText : Theme.uiTextFaint
                                        d: ico.edit
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: root.beginEdit(modelData)
                                    }
                                }
                                Rectangle {
                                    anchors.verticalCenter: parent.verticalCenter
                                    width: 34; height: 34; radius: 8
                                    color: dh.hovered ? Theme.uiHoverStrong
                                                      : "transparent"
                                    HoverHandler { id: dh }
                                    Glyph {
                                        anchors.centerIn: parent; px: 19
                                        tint: dh.hovered ? Theme.uiText : Theme.uiTextFaint
                                        d: ico.trash
                                    }
                                    MouseArea {
                                        anchors.fill: parent
                                        cursorShape: Qt.PointingHandCursor
                                        onClicked: cfg.removeProvider(modelData)
                                    }
                                }
                            }
                        }
                    }
                }

                // ── step 2: the form ──
                Column {
                    id: addForm
                    width: parent.width
                    visible: root.addStep === 2
                    readonly property var cat: cfg.catalog[root.addProviderId] !== undefined
                                               ? cfg.catalog[root.addProviderId] : ({})
                    readonly property var caps: cat.capabilities !== undefined ? cat.capabilities : ({})
                    // Nothing below the key can be truthful until the provider can be asked what
                    // it has, so the form stops there until there is one.
                    readonly property bool ready: root.addKind === "local" || root.addHasKey

                    CardRow {
                        label: "Provider"
                        Dropdown {
                            options: cfg.providersFor(root.addKind)
                            value: root.addProviderId
                            onPicked: function (v) { root.addProviderId = v; root.addModel = "" }
                        }
                    }
                    CardRow {
                        visible: root.addKind === "cloud"
                        height: visible ? implicitHeight : 0
                        divider: true
                        label: "API key"
                        Row {
                            spacing: 8
                            Field {
                                mono: true
                                implicitWidth: 230
                                echoMode: TextInput.Password
                                placeholderText: root.addHasKey ? "Replace the stored key" : "Paste a key"
                                placeholderTextColor: Theme.uiTextFaint
                                onTextChanged: { root.addKey = text; root.addHasKey = text.length > 0 }
                            }
                            // Fetching the model list IS the key test, so one button does both.
                            // It passes the TYPED key: in this flow nothing is stored until you
                            // commit, so probing the credential store would test the old key.
                            // No verticalCenter anchor: this sits in a Row inside a slot sized by
                            // childrenRect, and anchoring to a parent whose height comes from its
                            // children is a binding loop. Matching the Field's height instead.
                            TextButton {
                                height: 38
                                label: root.addProbe === "fetching" ? "Testing…" : "Test"
                                enabled: root.addProbe !== "fetching"
                                opacity: enabled ? 1 : 0.55
                                onClicked: cfg.testProvider(root.addProviderId, root.addKey)
                            }
                        }
                    }
                    // What the provider actually said. Without this a wrong key and a dropped
                    // connection look identical — both just leave the picker empty.
                    CardRow {
                        visible: root.addKind === "cloud" && root.addProbeMessage !== ""
                        height: visible ? implicitHeight : 0
                        divider: true
                        label: ""
                        Text {
                            text: root.addProbeMessage
                            color: root.addProbe === "ok" ? Theme.uiText : Theme.uiTextFaint
                            font.family: fontFamily; font.pixelSize: Theme.fontBase
                        }
                    }
                    CardRow {
                        visible: root.addKind === "local"
                        height: visible ? implicitHeight : 0
                        divider: true
                        label: "Address"
                        Field {
                            mono: true
                            implicitWidth: 230
                            text: root.addEndpoint
                            onTextChanged: root.addEndpoint = text
                        }
                    }

                    Text {
                        visible: !addForm.ready
                        width: parent.width
                        horizontalAlignment: Text.AlignHCenter
                        padding: 22
                        text: "Add a key to load this provider's models"
                        color: Theme.uiTextFaint
                        font.family: fontFamily; font.pixelSize: Theme.fontBase
                    }

                    CardRow {
                        visible: addForm.ready
                        height: visible ? implicitHeight : 0
                        divider: true
                        label: "Model"
                        Dropdown {
                            mono: true
                            options: cfg.modelOptions[root.addProviderId] !== undefined
                                     ? cfg.modelOptions[root.addProviderId] : []
                            value: root.addModel
                            onPicked: function (v) { root.addModel = v }
                        }
                    }
                    CardRow {
                        visible: addForm.ready && addForm.caps.effort !== undefined
                        height: visible ? implicitHeight : 0
                        divider: true
                        label: "Effort"
                        help: "Higher settings think longer and cost more."
                        Segmented {
                            options: addForm.caps.effort !== undefined ? addForm.caps.effort : []
                            value: root.addEffort
                            onPicked: function (v) { root.addEffort = v }
                        }
                    }
                    CardRow {
                        visible: addForm.ready && addForm.caps.thinking === true
                        height: visible ? implicitHeight : 0
                        divider: true
                        label: "Extended thinking"
                        Toggle {
                            on: root.addThinking
                            onToggled: function (v) { root.addThinking = v }
                        }
                    }
                    CardRow {
                        visible: addForm.ready && addForm.caps.temperature === true
                        height: visible ? implicitHeight : 0
                        divider: true
                        label: "Temperature"
                        Field {
                            mono: true; implicitWidth: 110
                            horizontalAlignment: Text.AlignRight
                            text: root.addTemperature
                            onTextChanged: root.addTemperature = text
                        }
                    }
                }

                Item {
                    width: parent.width; height: 58
                    Rectangle {
                        anchors.top: parent.top
                        width: parent.width; height: 1
                        color: Theme.hairline
                    }
                    Text {
                        anchors.left: parent.left; anchors.leftMargin: 16
                        anchors.verticalCenter: parent.verticalCenter
                        visible: root.addStep === 1 || root.addKind === "cloud"
                        text: "Keys are stored in Windows Credential Manager."
                        color: Theme.uiTextFaint
                        font.family: fontFamily; font.pixelSize: Theme.fontSmall
                    }
                    Row {
                        anchors.right: parent.right; anchors.rightMargin: 14
                        anchors.verticalCenter: parent.verticalCenter
                        spacing: 9
                        visible: root.addStep === 2
                        TextButton { label: "Cancel"; onClicked: root.addStep = 1 }
                        TextButton { label: "Save"; primary: true; onClicked: root.commitAdd() }
                    }
                }
            }
        }
    }

    // ── resize grips ─────────────────────────────────────────────────────────
    // A frameless window has no edges the OS will grab, so eight invisible strips hand the
    // drag straight back to Windows. Declared last, above everything including the Manage
    // scrim — a sheet being open must not trap the window at one size.
    component Grip: MouseArea {
        property int edges: 0
        acceptedButtons: Qt.LeftButton
        onPressed: root.startSystemResize(edges)
    }
    Grip {
        edges: Qt.TopEdge; cursorShape: Qt.SizeVerCursor
        anchors.top: parent.top; anchors.left: parent.left; anchors.right: parent.right
        anchors.leftMargin: root.grip; anchors.rightMargin: root.grip; height: root.grip
    }
    Grip {
        edges: Qt.BottomEdge; cursorShape: Qt.SizeVerCursor
        anchors.bottom: parent.bottom; anchors.left: parent.left; anchors.right: parent.right
        anchors.leftMargin: root.grip; anchors.rightMargin: root.grip; height: root.grip
    }
    Grip {
        edges: Qt.LeftEdge; cursorShape: Qt.SizeHorCursor
        anchors.left: parent.left; anchors.top: parent.top; anchors.bottom: parent.bottom
        anchors.topMargin: root.grip; anchors.bottomMargin: root.grip; width: root.grip
    }
    Grip {
        edges: Qt.RightEdge; cursorShape: Qt.SizeHorCursor
        anchors.right: parent.right; anchors.top: parent.top; anchors.bottom: parent.bottom
        anchors.topMargin: root.grip; anchors.bottomMargin: root.grip; width: root.grip
    }
    Grip {
        edges: Qt.TopEdge | Qt.LeftEdge; cursorShape: Qt.SizeFDiagCursor
        anchors.top: parent.top; anchors.left: parent.left
        width: root.grip * 2; height: root.grip * 2
    }
    Grip {
        edges: Qt.TopEdge | Qt.RightEdge; cursorShape: Qt.SizeBDiagCursor
        anchors.top: parent.top; anchors.right: parent.right
        width: root.grip * 2; height: root.grip * 2
    }
    Grip {
        edges: Qt.BottomEdge | Qt.LeftEdge; cursorShape: Qt.SizeBDiagCursor
        anchors.bottom: parent.bottom; anchors.left: parent.left
        width: root.grip * 2; height: root.grip * 2
    }
    Grip {
        edges: Qt.BottomEdge | Qt.RightEdge; cursorShape: Qt.SizeFDiagCursor
        anchors.bottom: parent.bottom; anchors.right: parent.right
        width: root.grip * 2; height: root.grip * 2
    }
}
