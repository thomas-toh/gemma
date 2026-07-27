// Keyboard-shortcut recorder (D29). At rest it shows the shortcut; hover invites "Record"; a
// click captures live keystrokes (Ctrl → "ctrl", Ctrl+Alt → "ctrl+alt", …) and commits the
// combo on release. The recorded string is validated against the daemon's own parser
// (cfg.validateBinding) before it is kept, so the window never stores a binding hotkeys.py
// will refuse — a bare key, an unknown key, or two non-modifiers are rejected here.
//
// Its own file, not an inline component: it is a self-contained control with a testable state
// machine, so it is guarded standalone (teleprompter/settings_check.py drives it with synthetic
// key events) rather than hunted for in a live window's tree.
import QtQuick
import teleprompter

Rectangle {
    id: rec
    property string value: ""
    property bool enabled: true
    property int animMs: Theme.durationControl        // caller passes root.t (reduced-motion aware)
    signal committed(string combo)

    // built while recording
    property var mods: []                      // held modifiers, in display order
    property string keyName: ""                // the one non-modifier key, once pressed
    property bool recording: false
    property bool invalid: false

    // ctrl → 0x01000021, etc. (Qt.Key_*). The order in `order` is the display order.
    readonly property var modName: ({ 16777249: "ctrl", 16777251: "alt",
                                      16777248: "shift", 16777250: "win" })
    readonly property var order: ["ctrl", "alt", "shift", "win"]

    function keyToken(k, text) {
        if (k >= 0x30 && k <= 0x39) return String.fromCharCode(k)          // 0-9
        if (k >= 0x41 && k <= 0x5a) return String.fromCharCode(k + 32)     // A-Z -> a-z
        if (k >= 0x01000030 && k <= 0x0100003b) return "f" + (k - 0x0100002f)  // F1-F12
        switch (k) {
        case 0x20: return "space"
        case 0x01000000: return "esc"
        case 0x01000001: return "tab"
        case 0x01000004: case 0x01000005: return "enter"
        }
        return (text && text.trim().length === 1) ? text.trim().toLowerCase() : ""
    }
    function combo() {
        var live = order.filter(function (m) { return mods.indexOf(m) >= 0 })
        if (keyName !== "") live.push(keyName)
        return live.join("+")
    }
    function start() {
        mods = []; keyName = ""; invalid = false; recording = true
        rec.forceActiveFocus()
    }
    function stop() { recording = false; mods = []; keyName = "" }
    function finish() {
        var c = combo()
        if (keyName !== "" && cfg.validateBinding(c)) {
            rec.committed(c)
            stop()
        } else {
            invalid = true                    // e.g. a bare key: flash, keep listening
            keyName = ""
        }
    }

    implicitWidth: 190
    implicitHeight: 38
    radius: Theme.radiusControl
    color: Theme.surfaceSunk
    border.width: 1
    border.color: rec.invalid ? Theme.danger
                : rec.recording ? Theme.lamp
                : (rh.hovered ? Theme.uiEdgeHover : Theme.hairlineStrong)
    opacity: enabled ? 1 : 0.55
    Behavior on border.color { ColorAnimation { duration: rec.animMs } }
    HoverHandler { id: rh; enabled: rec.enabled && !rec.recording }

    Text {
        anchors.centerIn: parent
        width: parent.width - 22
        horizontalAlignment: Text.AlignHCenter
        elide: Text.ElideRight
        text: rec.recording
                ? (rec.combo() === "" ? "Press a shortcut…" : rec.combo())
              : rh.hovered ? "Record"
              : (rec.value === "" ? "Not set" : rec.value)
        color: rec.recording ? (rec.invalid ? Theme.danger : Theme.lamp)
             : rh.hovered ? Theme.uiText
             : (rec.value === "" ? Theme.uiTextFaint : Theme.uiText)
        font.family: (rec.recording && rec.combo() !== "") || (!rec.recording && rec.value !== "")
                     ? "Consolas" : fontFamily
        font.pixelSize: Theme.fontBase
    }

    MouseArea {
        anchors.fill: parent
        enabled: rec.enabled && !rec.recording
        cursorShape: Qt.PointingHandCursor
        onClicked: rec.start()
    }

    focus: rec.recording
    // Clicking away or tabbing off abandons a half-pressed recording, restoring the old value.
    onActiveFocusChanged: if (!activeFocus) rec.stop()

    Keys.onPressed: function (event) {
        if (!rec.recording || event.isAutoRepeat) return
        event.accepted = true
        var m = rec.modName[event.key]
        if (m !== undefined) {
            if (rec.mods.indexOf(m) < 0) { var a = rec.mods.slice(); a.push(m); rec.mods = a }
            rec.invalid = false
            return
        }
        // Bare Esc cancels; Esc with a modifier is a real key and falls through.
        if (event.key === 0x01000000 && rec.mods.length === 0) { rec.stop(); return }
        var tok = rec.keyToken(event.key, event.text)
        if (tok !== "") { rec.keyName = tok; rec.invalid = false }
    }
    Keys.onReleased: function (event) {
        if (!rec.recording || event.isAutoRepeat) return
        event.accepted = true
        // The first release after a non-modifier key is captured commits the combo.
        if (rec.keyName !== "") { rec.finish(); return }
        var m = rec.modName[event.key]
        if (m !== undefined) {
            var a = rec.mods.filter(function (x) { return x !== m }); rec.mods = a
        }
    }
}
