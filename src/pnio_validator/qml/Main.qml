import QtQuick 2.12
import QtQuick.Controls 2.12
import QtQuick.Controls.Material 2.12
import QtQuick.Layouts 1.12

ApplicationWindow {
    id: win
    width: 1100
    height: 760
    visible: true
    title: "PNIO-Validator"

    // --- force maximized + fixed size ---
    visibility: Window.Maximized
    minimumWidth: Screen.width
    minimumHeight: Screen.height
    maximumWidth: Screen.width
    maximumHeight: Screen.height

    // ---- Theme ----
    property bool darkMode: true

    Material.theme: darkMode ? Material.Dark : Material.Light
    Material.accent: Material.Cyan
    Material.primary: Material.BlueGrey

    property color cBg: darkMode ? "#0f1218" : "#f3f5f8"
    property color cCard: darkMode ? "#171c25" : "#ffffff"
    property color cTop: darkMode ? "#141a24" : "#ffffff"
    property color cBorder: darkMode ? "#262d3b" : "#d7dde7"
    property color cText: darkMode ? "#e9edf6" : "#111827"
    property color cMuted: darkMode ? "#a9b4c7" : "#4b5563"
    property color cFieldBg: darkMode ? "#111722" : "#f7f9fc"
    property color cFieldBd: darkMode ? "#2a3a55" : "#cbd5e1"
    property color cFocus: "#3aa0ff"

    color: cBg

    ListModel {
        id: adaptersLm
    }

    property var adaptersModel: []

    function refreshAdapters() {
        const txt = backend.listAdapters();
        logArea.text = txt;
        adaptersLm.clear();
        adaptersModel = [];
        try {
            const obj = JSON.parse(txt);
            const arr = obj.adapters || [];
            adaptersModel = arr;
            for (let i = 0; i < arr.length; i++) {
                adaptersLm.append(arr[i]);   // mantém fields: friendly_name, scapy_iface, etc.
            }
            adapterCombo.model = adaptersLm;
            adapterCombo.textRole = "friendly_name";
            if (adaptersLm.count > 0) {
                adapterCombo.currentIndex = 0;
            } else {
                adapterCombo.currentIndex = -1;
            }
        } catch (e) {
            // se o JSON quebrar, você vai ver isso no output
            logArea.text = "ERROR parsing adapters JSON: " + e + "\n\nRaw:\n" + txt;
            adapterCombo.model = adaptersLm;
            adapterCombo.currentIndex = -1;
        }
    }

    Component.onCompleted: refreshAdapters()

    // ---- Components ----
    component PillButton: Button {
        id: control
        height: 34
        font.pixelSize: 12
        implicitWidth: Math.max(96, contentItem.implicitWidth + 28)
        opacity: enabled ? 1.0 : 0.45

        background: Rectangle {
            radius: 10
            color: control.down ? (win.darkMode ? "#1a2536" : "#e8eef8") : (control.hovered ? (win.darkMode ? "#1b2a3f" : "#eef3fb") : (win.darkMode ? "#182131" : "#e9eff9"))
            border.color: control.enabled ? win.cFieldBd : win.cBorder
            border.width: 1
        }

        contentItem: Text {
            text: control.text
            font.pixelSize: control.font.pixelSize
            font.weight: Font.DemiBold
            color: win.cText
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
        }
    }

    component Field: TextField {
        id: control
        height: 34
        font.pixelSize: 12

        background: Rectangle {
            radius: 10
            color: win.cFieldBg
            border.color: control.activeFocus ? win.cFocus : win.cFieldBd
            border.width: 1
        }

        color: win.cText
        selectionColor: win.cFocus
        selectedTextColor: win.darkMode ? "#0b0f15" : "#ffffff"
        placeholderTextColor: win.darkMode ? "#7b879a" : "#6b7280"
    }

    component SmallSpin: SpinBox {
        id: control
        height: 34
        font.pixelSize: 12
        editable: true

        background: Rectangle {
            radius: 10
            color: win.cFieldBg
            border.color: control.activeFocus ? win.cFocus : win.cFieldBd
            border.width: 1
        }

        contentItem: TextInput {
            text: control.textFromValue(control.value, control.locale)
            color: win.cText
            font.pixelSize: 12
            horizontalAlignment: Text.AlignHCenter
            verticalAlignment: Text.AlignVCenter
            readOnly: !control.editable
            validator: control.validator
            inputMethodHints: Qt.ImhFormattedNumbersOnly
        }
    }

    component CardFrame: Item {
        id: card
        property string title: ""
        default property alias content: body.data

        clip: true
        implicitWidth: layout.implicitWidth
        implicitHeight: layout.implicitHeight + 40   // folga pequena p/ não cortar

        Rectangle {
            anchors.fill: parent
            radius: 14
            color: win.cCard
            border.color: win.cBorder
            border.width: 1
        }

        ColumnLayout {
            id: layout
            anchors.fill: parent
            anchors.margins: 14
            spacing: 10

            RowLayout {
                Layout.fillWidth: true
                Label {
                    text: card.title
                    font.pixelSize: 14
                    font.weight: Font.DemiBold
                    color: win.cText
                }
            }

            Rectangle {
                Layout.fillWidth: true
                height: 1
                color: win.cBorder
            }

            ColumnLayout {
                id: body
                Layout.fillWidth: true
                spacing: 10
            }
        }
    }

    // ---- Main Layout ----
    ScrollView {
        id: pageScroll
        anchors.fill: parent
        anchors.margins: 14
        clip: true

        ScrollBar.vertical.policy: ScrollBar.AsNeeded
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

        contentWidth: availableWidth

        ColumnLayout {
            id: page
            width: pageScroll.availableWidth
            spacing: 12

            // Top bar
            Rectangle {
                Layout.fillWidth: true
                height: 54
                radius: 14
                color: cTop
                border.color: cBorder
                border.width: 1

                RowLayout {
                    anchors.fill: parent
                    anchors.margins: 14
                    spacing: 10

                    Label {
                        text: "PNIO-Validator"
                        font.pixelSize: 16
                        font.weight: Font.Bold
                        color: cText
                    }

                    Label {
                        text: "MVP"
                        font.pixelSize: 11
                        color: cMuted
                        padding: 6
                        background: Rectangle {
                            radius: 8
                            color: cBg
                            border.color: cFieldBd
                            border.width: 1
                        }
                    }

                    Item {
                        Layout.fillWidth: true
                    }

                    Label {
                        text: darkMode ? "Dark" : "Light"
                        color: cMuted
                        font.pixelSize: 11
                    }

                    Switch {
                        id: themeSwitch
                        checked: true
                        onToggled: win.darkMode = checked
                    }

                    PillButton {
                        text: "Reload adapters"
                        onClicked: refreshAdapters()
                    }
                }
            }

            Loader {
                Layout.fillWidth: true
                sourceComponent: wideLayout   // fixo wide (já que vai ficar maximizado)
            }

            // Output
            CardFrame {
                title: "Output (JSON)"
                Layout.fillWidth: true
                Layout.preferredHeight: Math.max(260, Math.min(520, win.height * 0.55))

                RowLayout {
                    Layout.fillWidth: true
                    Item {
                        Layout.fillWidth: true
                    }
                    PillButton {
                        text: "Clear"
                        onClicked: logArea.text = ""
                    }
                }

                ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true

                    TextArea {
                        id: logArea
                        readOnly: true
                        wrapMode: TextArea.NoWrap
                        font.family: "Consolas"
                        font.pixelSize: 12
                        color: cText
                        selectionColor: cFocus
                        selectedTextColor: darkMode ? "#0b0f15" : "#ffffff"
                        background: Rectangle {
                            radius: 12
                            color: cBg
                            border.color: cFieldBd
                            border.width: 1
                        }
                        text: ""
                    }
                }
            }
        }
    }

    // ---- Shared content blocks ----
    Component {
        id: discoveryCard
        CardFrame {
            title: "Discovery / Match"

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Label {
                    text: "Adapter"
                    color: cMuted
                    font.pixelSize: 11
                }

                ComboBox {
                    id: adapterCombo
                    Layout.preferredWidth: 280
                    height: 100
                    font.pixelSize: 12
                    model: adaptersLm
                    textRole: "friendly_name"
                    background: Rectangle {
                        radius: 10
                        color: cFieldBg
                        border.color: cFieldBd
                        border.width: 1
                    }
                }

                Label {
                    text: "Timeout (s)"
                    color: cMuted
                    font.pixelSize: 11
                }
                SmallSpin {
                    id: scanTimeout
                    from: 1
                    to: 30
                    value: 5
                    Layout.preferredWidth: 90
                }

                CheckBox {
                    id: matchGsd
                    text: "Match GSD"
                    checked: true
                }

                // container do botão da direita (evita “grudar” na borda)
                Item {
                    Layout.fillWidth: true
                }

                Item {
                    Layout.preferredWidth: 160
                    Layout.minimumWidth: 160
                    Layout.maximumWidth: 160
                    Layout.alignment: Qt.AlignRight
                    Layout.rightMargin: 6     // <<< margem interna do card
                    height: 34

                    PillButton {
                        anchors.fill: parent
                        text: "Scan"
                        onClicked: {
                            if (adapterCombo.currentIndex < 0)
                                return;
                            const a = adaptersModel[adapterCombo.currentIndex];
                            const txt = backend.scan(a.scapy_iface, scanTimeout.value, matchGsd.checked);
                            logArea.text = txt;
                        }
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Label {
                    text: "VendorId"
                    color: cMuted
                    font.pixelSize: 11
                }
                Field {
                    id: vendorId
                    text: "0x1234"
                    Layout.preferredWidth: 140
                }

                Label {
                    text: "DeviceId"
                    color: cMuted
                    font.pixelSize: 11
                }
                Field {
                    id: deviceId
                    text: "0x5678"
                    Layout.preferredWidth: 140
                }

                Label {
                    text: "Name hint"
                    color: cMuted
                    font.pixelSize: 11
                }
                Field {
                    id: nameHint
                    text: ""
                    Layout.fillWidth: true
                }

                Rectangle {
                    Layout.preferredWidth: 150
                    Layout.minimumWidth: 150
                    height: 34
                    radius: 10
                    color: "transparent"
                    Item {
                        Layout.preferredWidth: 160
                        Layout.minimumWidth: 160
                        Layout.maximumWidth: 160
                        Layout.alignment: Qt.AlignRight
                        Layout.rightMargin: 6
                        height: 34

                        PillButton {
                            anchors.fill: parent
                            text: "Match"
                            onClicked: logArea.text = backend.match(vendorId.text, deviceId.text, nameHint.text)
                        }
                    }
                }
            }
        }
    }

    Component {
        id: validateCard
        CardFrame {
            title: "Validate / DCP (Fake)"

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Label {
                    text: "Device"
                    color: cMuted
                    font.pixelSize: 11
                }
                Field {
                    id: devName
                    text: "em31-new"
                    Layout.fillWidth: true
                }

                Label {
                    text: "Scenario"
                    color: cMuted
                    font.pixelSize: 11
                }
                ComboBox {
                    id: scenario
                    Layout.preferredWidth: 170
                    height: 34
                    font.pixelSize: 12
                    model: ["ok", "f841_timeout", "aff0_timeout", "f841_short", "random_latency"]
                    background: Rectangle {
                        radius: 10
                        color: cFieldBg
                        border.color: cFieldBd
                        border.width: 1
                    }
                }

                Rectangle {
                    Layout.preferredWidth: 150
                    Layout.minimumWidth: 150
                    height: 34
                    radius: 10
                    color: "transparent"
                    PillButton {
                        anchors.fill: parent
                        text: "Validate"
                        onClicked: logArea.text = backend.validateFake(devName.text, scenario.currentText)
                    }
                }
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Label {
                    text: "New name"
                    color: cMuted
                    font.pixelSize: 11
                }
                Field {
                    id: newStation
                    text: "foo"
                    Layout.preferredWidth: 140
                }

                Rectangle {
                    Layout.preferredWidth: 150
                    Layout.minimumWidth: 150
                    height: 34
                    radius: 10
                    color: "transparent"
                    PillButton {
                        anchors.fill: parent
                        text: "SetName"
                        onClicked: logArea.text = backend.dcpSetNameFake(devName.text, newStation.text)
                    }
                }

                Item {
                    Layout.fillWidth: true
                }
            }

            Flow {
                Layout.fillWidth: true
                spacing: 10

                RowLayout {
                    spacing: 10
                    Label {
                        text: "IP"
                        color: cMuted
                        font.pixelSize: 11
                    }
                    Field {
                        id: ip
                        text: "192.168.0.10"
                        Layout.preferredWidth: 170
                    }
                }
                RowLayout {
                    spacing: 10
                    Label {
                        text: "Mask"
                        color: cMuted
                        font.pixelSize: 11
                    }
                    Field {
                        id: mask
                        text: "255.255.255.0"
                        Layout.preferredWidth: 170
                    }
                }
                RowLayout {
                    spacing: 10
                    Label {
                        text: "GW"
                        color: cMuted
                        font.pixelSize: 11
                    }
                    Field {
                        id: gw
                        text: "192.168.0.1"
                        Layout.preferredWidth: 170
                    }
                }

                Rectangle {
                    width: 150
                    height: 34
                    radius: 10
                    color: "transparent"
                    PillButton {
                        anchors.fill: parent
                        text: "SetIP"
                        onClicked: logArea.text = backend.dcpSetIpFake(devName.text, ip.text, mask.text, gw.text)
                    }
                }
            }

            // Botões finais: todos dentro de boxes (sem empurrar pra fora)
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Rectangle {
                    width: 150
                    height: 34
                    radius: 10
                    color: "transparent"
                    PillButton {
                        anchors.fill: parent
                        text: "Blink ON"
                        onClicked: logArea.text = backend.dcpBlinkFake(devName.text, true, 10.0)
                    }
                }
                Rectangle {
                    width: 150
                    height: 34
                    radius: 10
                    color: "transparent"
                    PillButton {
                        anchors.fill: parent
                        text: "Blink OFF"
                        onClicked: logArea.text = backend.dcpBlinkFake(devName.text, false, 10.0)
                    }
                }

                Item {
                    Layout.fillWidth: true
                }

                Rectangle {
                    width: 170
                    height: 34
                    radius: 10
                    color: "transparent"
                    PillButton {
                        anchors.fill: parent
                        text: "Factory Reset"
                        onClicked: logArea.text = backend.dcpFactoryResetFake(devName.text)
                    }
                }
            }
        }
    }

    // ---- Layout fixo wide (já que está maximizado) ----
    Component {
        id: wideLayout
        RowLayout {
            Layout.fillWidth: true
            spacing: 12

            Loader {
                Layout.fillWidth: true
                Layout.minimumWidth: 520
                Layout.preferredWidth: win.width * 0.62
                sourceComponent: discoveryCard
            }

            Loader {
                Layout.fillWidth: true
                Layout.minimumWidth: 360
                Layout.preferredWidth: win.width * 0.38
                sourceComponent: validateCard
            }
        }
    }

    Component {
        id: narrowLayout
        ColumnLayout {
            Layout.fillWidth: true
            spacing: 12
            Loader {
                Layout.fillWidth: true
                sourceComponent: discoveryCard
            }
            Loader {
                Layout.fillWidth: true
                sourceComponent: validateCard
            }
        }
    }
}
