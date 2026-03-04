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
    function s(x) {
        return (x === null || x === undefined) ? "" : String(x);
    }
    function i(x) {
        return (x === null || x === undefined) ? -1 : Number(x);
    }
    ListModel {
        id: adaptersLm
    }
    ListModel {
        id: devicesLm
    }   // itens: { name, mac, ip }
    property int selectedDeviceIndex: -1
    function selectedDevice() {
        if (selectedDeviceIndex < 0 || selectedDeviceIndex >= devicesLm.count)
            return null;
        return devicesLm.get(selectedDeviceIndex);
    }

    property var adaptersModel: []

    function refreshAdapters() {
        const txt = backend.listAdapters();
        logArea.text = txt;
        adaptersLm.clear();
        adaptersModel = [];

        // Seed roles (cria roles mesmo se depois vier null)
        adaptersLm.append({
            friendly_name: "",
            mac: "",
            guid: "",
            scapy_iface: "",
            index: -1
        });
        adaptersLm.remove(0, 1);
        try {
            const obj = JSON.parse(txt);
            const arr = obj.adapters || [];
            adaptersModel = arr;
            for (let i = 0; i < arr.length; i++) {
                const a = arr[i] || {};
                // garante roles sempre com string (nunca null)
                adaptersLm.append({
                    friendly_name: s(a.friendly_name),
                    mac: s(a.mac),
                    guid: s(a.guid),
                    scapy_iface: s(a.scapy_iface),
                    index: i(a.index)
                });
            }
        } catch (e) {
            logArea.text = "ERROR parsing adapters JSON: " + e + "\n\nRaw:\n" + txt;
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
            // Top bar
            Rectangle {
                Layout.fillWidth: true
                height: 56
                radius: 14
                color: cTop
                border.color: cBorder
                border.width: 1
                clip: true

                RowLayout {
                    anchors.fill: parent
                    anchors.leftMargin: 16
                    anchors.rightMargin: 16
                    anchors.topMargin: 10
                    anchors.bottomMargin: 10
                    spacing: 12

                    // Left: title + badge
                    RowLayout {
                        Layout.alignment: Qt.AlignVCenter
                        spacing: 10

                        Label {
                            text: "PNIO-Validator"
                            font.pixelSize: 16
                            font.weight: Font.Bold
                            color: cText
                            verticalAlignment: Text.AlignVCenter
                        }

                        Rectangle {
                            radius: 8
                            color: cBg
                            border.color: cFieldBd
                            border.width: 1
                            implicitHeight: 22
                            implicitWidth: badgeText.implicitWidth + 14

                            Text {
                                id: badgeText
                                anchors.centerIn: parent
                                text: "MVP"
                                font.pixelSize: 11
                                color: cMuted
                                font.weight: Font.DemiBold
                            }
                        }
                    }

                    Item {
                        Layout.fillWidth: true
                    }

                    // Right: theme + button (grouped)
                    RowLayout {
                        Layout.alignment: Qt.AlignVCenter
                        spacing: 10

                        Label {
                            text: darkMode ? "Dark" : "Light"
                            color: cMuted
                            font.pixelSize: 11
                            verticalAlignment: Text.AlignVCenter
                        }

                        Switch {
                            id: themeSwitch
                            Layout.alignment: Qt.AlignVCenter
                            checked: true
                            implicitHeight: 28
                            implicitWidth: 52
                            onToggled: win.darkMode = checked
                        }

                        PillButton {
                            text: "Reload adapters"
                            Layout.alignment: Qt.AlignVCenter
                            implicitHeight: 34
                            implicitWidth: 160
                            onClicked: refreshAdapters()
                        }
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
                Flickable {
                    id: logFlick
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true

                    boundsBehavior: Flickable.StopAtBounds
                    ScrollBar.vertical: ScrollBar {
                        policy: ScrollBar.AsNeeded
                    }
                    ScrollBar.horizontal: ScrollBar {
                        policy: ScrollBar.AsNeeded
                    }

                    // área "visível" do flick
                    contentWidth: Math.max(width, logArea.implicitWidth)
                    contentHeight: Math.max(height, logArea.implicitHeight)

                    TextArea {
                        id: logArea
                        readOnly: true
                        wrapMode: TextArea.NoWrap
                        font.family: "Consolas"
                        font.pixelSize: 12
                        color: cText
                        selectionColor: cFocus
                        selectedTextColor: darkMode ? "#0b0f15" : "#ffffff"

                        // importante: o TextArea precisa ter tamanho real dentro do Flickable
                        x: 0
                        y: 0
                        width: Math.max(logFlick.width, implicitWidth)
                        height: Math.max(logFlick.height, implicitHeight)

                        // padding pra não colar nas bordas
                        leftPadding: 10
                        rightPadding: 10
                        topPadding: 8
                        bottomPadding: 8

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

                    // força tamanho real (Layout às vezes ignora preferred)
                    Layout.preferredWidth: 280
                    Layout.minimumWidth: 280
                    Layout.maximumWidth: 280
                    implicitWidth: 280
                    width: 280

                    // altura: use implicitHeight (Controls2 respeita melhor)
                    implicitHeight: 34
                    height: 34

                    font.pixelSize: 12
                    model: adaptersLm
                    textRole: "friendly_name"

                    contentItem: Text {
                        text: adapterCombo.displayText
                        color: cText
                        font.pixelSize: 12
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                        leftPadding: 12
                        rightPadding: 28   // espaço da seta
                    }

                    indicator: Canvas {
                        id: arrow
                        width: 24
                        height: 24
                        anchors.right: parent.right
                        anchors.rightMargin: 10
                        anchors.verticalCenter: parent.verticalCenter
                        onPaint: {
                            var ctx = getContext("2d");
                            ctx.clearRect(0, 0, width, height);
                            ctx.fillStyle = win.cMuted;
                            ctx.beginPath();
                            ctx.moveTo(6, 9);
                            ctx.lineTo(18, 9);
                            ctx.lineTo(12, 15);
                            ctx.closePath();
                            ctx.fill();
                        }
                    }

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

                            // update devices model for GUI
                            devicesLm.clear();
                            selectedDeviceIndex = -1;
                            try {
                                const obj = JSON.parse(txt);
                                const devs = obj.devices || obj.found || obj.results || [];   // aceita nomes diferentes
                                for (let i = 0; i < devs.length; i++) {
                                    devicesLm.append({
                                        name: (devs[i].name || devs[i].station_name || ""),
                                        mac: (devs[i].mac || devs[i].mac_addr || ""),
                                        ip: (devs[i].ip || devs[i].ip_addr || "")
                                    });
                                }
                                if (devicesLm.count > 0)
                                    selectedDeviceIndex = 0;
                            } catch (e)
                            // não quebra UI se JSON mudar
                            {}
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
                        onClicked: logArea.text = backend.matchGui(vendorId.text, deviceId.text, nameHint.text)
                    }
                }
            }
        }
    }

    Component {
        id: validateCard

        CardFrame {
            title: "Validate / DCP"

            // -----------------------------
            // Line 1: Target + MAC
            // -----------------------------
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Label {
                    text: "Target"
                    color: cMuted
                    font.pixelSize: 11
                }

                ComboBox {
                    id: deviceCombo
                    Layout.fillWidth: true
                    model: devicesLm
                    textRole: "name"
                    currentIndex: selectedDeviceIndex
                    onCurrentIndexChanged: selectedDeviceIndex = currentIndex

                    implicitHeight: 34
                    height: 34

                    background: Rectangle {
                        radius: 10
                        color: cFieldBg
                        border.color: cFieldBd
                        border.width: 1
                    }
                }

                Label {
                    text: "MAC"
                    color: cMuted
                    font.pixelSize: 11
                }

                Field {
                    text: selectedDevice() ? selectedDevice().mac : ""
                    readOnly: true
                    Layout.preferredWidth: 210
                }
            }

            // -----------------------------
            // Line 2: Scenario + Validate
            // (removido "Device/devName" pra não “colar” texto e não ter lixo visual)
            // -----------------------------
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Label {
                    text: "Scenario"
                    color: cMuted
                    font.pixelSize: 11
                }

                ComboBox {
                    id: scenario

                    Layout.fillWidth: true
                    implicitHeight: 34
                    height: 34

                    font.pixelSize: 12
                    model: ["ok", "f841_timeout", "aff0_timeout", "f841_short", "random_latency"]

                    // mantém o estilo de texto/arrow consistente
                    contentItem: Text {
                        text: scenario.displayText
                        color: cText
                        font.pixelSize: 12
                        verticalAlignment: Text.AlignVCenter
                        elide: Text.ElideRight
                        leftPadding: 12
                        rightPadding: 28
                    }

                    indicator: Canvas {
                        width: 24
                        height: 24
                        anchors.right: parent.right
                        anchors.rightMargin: 10
                        anchors.verticalCenter: parent.verticalCenter
                        onPaint: {
                            var ctx = getContext("2d");
                            ctx.clearRect(0, 0, width, height);
                            ctx.fillStyle = win.cMuted;
                            ctx.beginPath();
                            ctx.moveTo(6, 9);
                            ctx.lineTo(18, 9);
                            ctx.lineTo(12, 15);
                            ctx.closePath();
                            ctx.fill();
                        }
                    }

                    background: Rectangle {
                        radius: 10
                        color: cFieldBg
                        border.color: cFieldBd
                        border.width: 1
                    }
                }

                Item {
                    Layout.fillWidth: true
                }

                Item {
                    Layout.preferredWidth: 150
                    Layout.minimumWidth: 150
                    Layout.maximumWidth: 150
                    height: 34

                    PillButton {
                        anchors.fill: parent
                        text: "Validate"
                        // por enquanto segue fake (até ligar validate real)
                        onClicked: logArea.text = backend.validateFake((selectedDevice() ? selectedDevice().name : ""), scenario.currentText)
                    }
                }
            }

            // -----------------------------
            // Line 3: SetName
            // -----------------------------
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
                    Layout.preferredWidth: 220
                }

                Item {
                    Layout.preferredWidth: 150
                    Layout.minimumWidth: 150
                    Layout.maximumWidth: 150
                    height: 34

                    PillButton {
                        anchors.fill: parent
                        text: "SetName"
                        onClicked: {
                            if (adapterCombo.currentIndex < 0)
                                return;
                            const a = adaptersModel[adapterCombo.currentIndex];
                            const d = selectedDevice();
                            if (!d || !d.mac)
                                return;
                            logArea.text = backend.dcpSetName(a.scapy_iface, d.mac, newStation.text);
                        }
                    }
                }

                Item {
                    Layout.fillWidth: true
                }
            }

            // -----------------------------
            // Line 4: SetIP (wrap-friendly)
            // -----------------------------
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

                Item {
                    width: 150
                    height: 34

                    PillButton {
                        anchors.fill: parent
                        text: "SetIP"
                        onClicked: {
                            if (adapterCombo.currentIndex < 0)
                                return;
                            const a = adaptersModel[adapterCombo.currentIndex];
                            const d = selectedDevice();
                            if (!d || !d.mac)
                                return;
                            logArea.text = backend.dcpSetIp(a.scapy_iface, d.mac, ip.text, mask.text, gw.text);
                        }
                    }
                }
            }

            // -----------------------------
            // Line 5: Blink + Factory Reset
            // -----------------------------
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                Item {
                    width: 150
                    height: 34
                    PillButton {
                        anchors.fill: parent
                        text: "Blink ON"
                        onClicked: {
                            if (adapterCombo.currentIndex < 0)
                                return;
                            const a = adaptersModel[adapterCombo.currentIndex];
                            const d = selectedDevice();
                            if (!d || !d.mac)
                                return;
                            logArea.text = backend.dcpBlink(a.scapy_iface, d.mac, true, 10.0);
                        }
                    }
                }

                Item {
                    width: 150
                    height: 34
                    PillButton {
                        anchors.fill: parent
                        text: "Blink OFF"
                        onClicked: {
                            if (adapterCombo.currentIndex < 0)
                                return;
                            const a = adaptersModel[adapterCombo.currentIndex];
                            const d = selectedDevice();
                            if (!d || !d.mac)
                                return;
                            logArea.text = backend.dcpBlink(a.scapy_iface, d.mac, false, 10.0);
                        }
                    }
                }

                Item {
                    Layout.fillWidth: true
                }

                Item {
                    width: 170
                    height: 34
                    PillButton {
                        anchors.fill: parent
                        text: "Factory Reset"
                        onClicked: {
                            if (adapterCombo.currentIndex < 0)
                                return;
                            const a = adaptersModel[adapterCombo.currentIndex];
                            const d = selectedDevice();
                            if (!d || !d.mac)
                                return;
                            logArea.text = backend.dcpFactoryReset(a.scapy_iface, d.mac);
                        }
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
