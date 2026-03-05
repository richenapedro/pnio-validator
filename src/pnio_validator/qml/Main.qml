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
    property int actionBtnW: 160
    property int actionBtnH: 34
    color: cBg
    property int selectedAdapterIndex: -1

    function selectedAdapter() {
        if (selectedAdapterIndex < 0 || selectedAdapterIndex >= adaptersLm.count)
            return null;
        return adaptersLm.get(selectedAdapterIndex);
    }
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
    property bool scanning: false

    function refreshAdapters() {
        const txt = backend.listAdapters();
        logArea.text = txt;
        adaptersLm.clear();
        adaptersModel = [];
        try {
            const obj = JSON.parse(txt);
            const arr = obj.adapters || [];
            adaptersModel = arr;
            for (let i = 0; i < arr.length; i++)
                adaptersLm.append(arr[i]);
        } catch (e) {
            logArea.text = "ERROR parsing adapters JSON: " + e + "\n\nRaw:\n" + txt;
        }
    }

    Component.onCompleted: refreshAdapters()
    // ---- Components ----
    component PillButton: Button {
        id: control
        implicitHeight: win.actionBtnH
        height: implicitHeight
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

                    currentIndex: selectedAdapterIndex
                    onCurrentIndexChanged: selectedAdapterIndex = currentIndex
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
                    Layout.preferredWidth: win.actionBtnW
                    Layout.minimumWidth: win.actionBtnW
                    Layout.maximumWidth: win.actionBtnW
                    Layout.alignment: Qt.AlignRight
                    Layout.rightMargin: 6     // <<< margem interna do card
                    height: win.actionBtnH

                    BusyIndicator {
                        anchors.verticalCenter: parent.verticalCenter
                        // mantém posição horizontal atual (ex.: canto esquerdo)
                        anchors.left: parent.left
                        anchors.leftMargin: 12
                        running: scanning
                        visible: scanning
                        implicitWidth: 22
                        implicitHeight: 22
                    }
                    PillButton {
                        anchors.fill: parent
                        text: scanning ? "Scanning..." : "Scan"
                        enabled: !scanning
                        onClicked: {
                            if (adapterCombo.currentIndex < 0)
                                return;
                            const a = selectedAdapter();
                            if (!a || !a.scapy_iface)
                                return;
                            logArea.text = "Scanning... " + (new Date()).toLocaleString() + "\n";
                            devicesLm.clear();
                            selectedDeviceIndex = -1;
                            backend.scanAsync(a.scapy_iface, scanTimeout.value, matchGsd.checked);
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
                    Layout.preferredWidth: win.actionBtnW
                    Layout.minimumWidth: win.actionBtnW
                    Layout.maximumWidth: win.actionBtnW
                    height: win.actionBtnH
                    Layout.alignment: Qt.AlignRight
                    Layout.rightMargin: 6

                    PillButton {
                        anchors.fill: parent
                        text: "Match"
                        onClicked: logArea.text = backend.matchGui(vendorId.text, deviceId.text, nameHint.text)
                    }
                }
            }
            CardFrame {
                title: "Devices Found"
                Layout.fillWidth: true
                Layout.preferredHeight: 320

                // Header
                Rectangle {
                    Layout.fillWidth: true
                    height: 32
                    radius: 10
                    color: win.darkMode ? "#121826" : "#eef3fb"
                    border.color: win.cBorder
                    border.width: 1

                    RowLayout {
                        anchors.fill: parent
                        anchors.leftMargin: 10
                        anchors.rightMargin: 10
                        spacing: 10

                        Label {
                            text: "Name"
                            color: cMuted
                            font.pixelSize: 11
                            Layout.preferredWidth: 160
                        }
                        Label {
                            text: "IP"
                            color: cMuted
                            font.pixelSize: 11
                            Layout.preferredWidth: 140
                        }
                        Label {
                            text: "MAC"
                            color: cMuted
                            font.pixelSize: 11
                            Layout.preferredWidth: 170
                        }
                        Label {
                            text: "VendorID"
                            color: cMuted
                            font.pixelSize: 11
                            Layout.preferredWidth: 90
                        }
                        Label {
                            text: "DeviceID"
                            color: cMuted
                            font.pixelSize: 11
                            Layout.preferredWidth: 90
                        }
                        Label {
                            text: "GSD"
                            color: cMuted
                            font.pixelSize: 11
                            Layout.preferredWidth: 50
                        }
                        Item {
                            Layout.fillWidth: true
                        }
                        Label {
                            text: "Action"
                            color: cMuted
                            font.pixelSize: 11
                            Layout.preferredWidth: 90
                        }
                    }
                }

                ScrollView {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    clip: true
                    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

                    ListView {
                        id: devicesList
                        width: parent.width
                        model: devicesLm
                        clip: true
                        spacing: 6

                        currentIndex: selectedDeviceIndex
                        onCurrentIndexChanged: selectedDeviceIndex = currentIndex

                        delegate: Rectangle {
                            width: devicesList.width
                            height: 38
                            radius: 10
                            color: (index === devicesList.currentIndex) ? (win.darkMode ? "#182133" : "#e7effb") : (win.darkMode ? "#0f1218" : "#ffffff")
                            border.color: (index === devicesList.currentIndex) ? win.cFocus : win.cBorder
                            border.width: 1

                            MouseArea {
                                anchors.fill: parent
                                onClicked: devicesList.currentIndex = index
                            }

                            RowLayout {
                                anchors.fill: parent
                                anchors.leftMargin: 10
                                anchors.rightMargin: 10
                                spacing: 10

                                Text {
                                    text: model.name
                                    color: cText
                                    font.pixelSize: 12
                                    elide: Text.ElideRight
                                    Layout.preferredWidth: 160
                                    verticalAlignment: Text.AlignVCenter
                                }
                                Text {
                                    text: model.ip
                                    color: cText
                                    font.pixelSize: 12
                                    elide: Text.ElideRight
                                    Layout.preferredWidth: 140
                                    verticalAlignment: Text.AlignVCenter
                                }
                                Text {
                                    text: model.mac
                                    color: cText
                                    font.pixelSize: 12
                                    font.family: "Consolas"
                                    elide: Text.ElideRight
                                    Layout.preferredWidth: 170
                                    verticalAlignment: Text.AlignVCenter
                                }
                                Text {
                                    text: model.vendor_id
                                    color: cText
                                    font.pixelSize: 12
                                    font.family: "Consolas"
                                    Layout.preferredWidth: 90
                                    verticalAlignment: Text.AlignVCenter
                                }
                                Text {
                                    text: model.device_id
                                    color: cText
                                    font.pixelSize: 12
                                    font.family: "Consolas"
                                    Layout.preferredWidth: 90
                                    verticalAlignment: Text.AlignVCenter
                                }
                                Text {
                                    text: (model.gsd_match_score !== "" && model.gsd_match_score !== "null") ? "✓" : "-"
                                    color: cMuted
                                    font.pixelSize: 12
                                    Layout.preferredWidth: 50
                                    verticalAlignment: Text.AlignVCenter
                                }

                                Item {
                                    Layout.fillWidth: true
                                }

                                Item {
                                    Layout.preferredWidth: 90
                                    height: 34

                                    PillButton {
                                        anchors.fill: parent
                                        text: "Blink"
                                        enabled: model.mac !== ""
                                        onClicked: {
                                            // garante seleção ao clicar no blink
                                            devicesList.currentIndex = index;
                                            if (adapterCombo.currentIndex < 0)
                                                return;
                                            const a = adaptersModel[adapterCombo.currentIndex];
                                            if (!a || !a.scapy_iface)
                                                return;
                                            if (!model.mac)
                                                return;
                                            logArea.text = backend.dcpBlink(a.scapy_iface, model.mac, true, 10.0);
                                        }
                                    }
                                }
                            }
                        }

                        // Empty state
                        footer: Item {
                            width: devicesList.width
                            height: (devicesLm.count === 0) ? 80 : 0
                            visible: devicesLm.count === 0

                            Text {
                                anchors.centerIn: parent
                                text: "No devices found. Click Scan."
                                color: cMuted
                                font.pixelSize: 12
                            }
                        }
                    }
                }
            }
        }
    }

    Component {
        id: validateCard

        CardFrame {
            title: "Validate / DCP"

            // -------- Row 1: Target + MAC (mais compacto e “encaixado” no painel direito)
            GridLayout {
                Layout.fillWidth: true
                columns: 4
                columnSpacing: 10
                rowSpacing: 8

                // Target
                Label {
                    text: "Target"
                    color: cMuted
                    font.pixelSize: 11
                }
                ComboBox {
                    id: deviceCombo
                    Layout.fillWidth: true
                    Layout.columnSpan: 3
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

                // MAC
                Label {
                    text: "MAC"
                    color: cMuted
                    font.pixelSize: 11
                }
                Field {
                    Layout.fillWidth: true
                    Layout.columnSpan: 3
                    text: selectedDevice() ? selectedDevice().mac : ""
                    readOnly: true
                }
            }

            // -------- Row 2: Scenario + Validate (botão fixo à direita)
            GridLayout {
                Layout.fillWidth: true
                columns: 4
                columnSpacing: 10
                rowSpacing: 8

                Label {
                    text: "Scenario"
                    color: cMuted
                    font.pixelSize: 11
                }

                ComboBox {
                    id: scenario
                    Layout.fillWidth: true
                    Layout.columnSpan: 2
                    implicitHeight: 34
                    height: 34
                    font.pixelSize: 12
                    model: ["ok", "f841_timeout", "aff0_timeout", "f841_short", "random_latency"]

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
                    Layout.preferredWidth: win.actionBtnW
                    Layout.minimumWidth: win.actionBtnW
                    Layout.maximumWidth: win.actionBtnW
                    height: win.actionBtnH

                    PillButton {
                        anchors.fill: parent
                        text: "Validate"
                        onClicked: logArea.text = backend.validateFake((selectedDevice() ? selectedDevice().name : ""), scenario.currentText)
                    }
                }
            }

            // -------- Row 3: SetName
            GridLayout {
                Layout.fillWidth: true
                columns: 4
                columnSpacing: 10
                rowSpacing: 8

                Label {
                    text: "New name"
                    color: cMuted
                    font.pixelSize: 11
                }
                Field {
                    id: newStation
                    Layout.fillWidth: true
                    Layout.columnSpan: 2
                    text: "foo"
                }

                Item {
                    Layout.preferredWidth: win.actionBtnW
                    Layout.minimumWidth: win.actionBtnW
                    Layout.maximumWidth: win.actionBtnW
                    height: win.actionBtnH

                    PillButton {
                        anchors.fill: parent
                        text: "SetName"
                        onClicked: {
                            if (adapterCombo.currentIndex < 0)
                                return;
                            const a = adaptersModel[adapterCombo.currentIndex];
                            const d = selectedDevice();
                            if (!a || !a.scapy_iface)
                                return;
                            if (!d || !d.mac)
                                return;
                            logArea.text = backend.dcpSetName(a.scapy_iface, d.mac, newStation.text);
                        }
                    }
                }
            }
            // -------- Row 4+5: IP/Mask/GW na esquerda + SetIP na direita (ocupando altura dos 3 campos)
            RowLayout {
                Layout.fillWidth: true
                spacing: 10

                // Left column: IP / Mask / GW
                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    columnSpacing: 10
                    rowSpacing: 8

                    Label {
                        text: "IP"
                        color: cMuted
                        font.pixelSize: 11
                    }
                    Field {
                        id: ip
                        Layout.fillWidth: true
                        text: "192.168.0.10"
                    }

                    Label {
                        text: "Mask"
                        color: cMuted
                        font.pixelSize: 11
                    }
                    Field {
                        id: mask
                        Layout.fillWidth: true
                        text: "255.255.255.0"
                    }

                    Label {
                        text: "GW"
                        color: cMuted
                        font.pixelSize: 11
                    }
                    Field {
                        id: gw
                        Layout.fillWidth: true
                        text: "192.168.0.1"
                    }
                }

                // Right column: SetIP button fills the height of the 3 rows
                Item {
                    Layout.preferredWidth: win.actionBtnW
                    Layout.minimumWidth: win.actionBtnW
                    Layout.maximumWidth: win.actionBtnW

                    // altura = 3 campos (34) + 2 gaps (8)  -> 34*3 + 8*2 = 118
                    // se você mudar heights/spacings, ajusta aqui também
                    height: 34 * 3 + 8 * 2

                    PillButton {
                        anchors.fill: parent
                        text: "SetIP"
                        onClicked: {
                            if (adapterCombo.currentIndex < 0)
                                return;
                            const a = adaptersModel[adapterCombo.currentIndex];
                            const d = selectedDevice();
                            if (!a || !a.scapy_iface)
                                return;
                            if (!d || !d.mac)
                                return;
                            logArea.text = backend.dcpSetIp(a.scapy_iface, d.mac, ip.text, mask.text, gw.text);
                        }
                    }
                }
            }

            // -------- Row 6: Blink + Factory Reset (grid limpo, sem “buracos”)
            GridLayout {
                Layout.fillWidth: true
                columns: 2
                columnSpacing: 10
                rowSpacing: 10

                PillButton {
                    Layout.fillWidth: true
                    text: "Blink ON"
                    onClicked: {
                        if (adapterCombo.currentIndex < 0)
                            return;
                        const a = adaptersModel[adapterCombo.currentIndex];
                        const d = selectedDevice();
                        if (!a || !a.scapy_iface)
                            return;
                        if (!d || !d.mac)
                            return;
                        logArea.text = backend.dcpBlink(a.scapy_iface, d.mac, true, 10.0);
                    }
                }

                PillButton {
                    Layout.fillWidth: true
                    text: "Blink OFF"
                    onClicked: {
                        if (adapterCombo.currentIndex < 0)
                            return;
                        const a = adaptersModel[adapterCombo.currentIndex];
                        const d = selectedDevice();
                        if (!a || !a.scapy_iface)
                            return;
                        if (!d || !d.mac)
                            return;
                        logArea.text = backend.dcpBlink(a.scapy_iface, d.mac, false, 10.0);
                    }
                }

                PillButton {
                    Layout.fillWidth: true
                    Layout.columnSpan: 2
                    text: "Factory Reset"
                    onClicked: {
                        if (adapterCombo.currentIndex < 0)
                            return;
                        const a = adaptersModel[adapterCombo.currentIndex];
                        const d = selectedDevice();
                        if (!a || !a.scapy_iface)
                            return;
                        if (!d || !d.mac)
                            return;
                        logArea.text = backend.dcpFactoryReset(a.scapy_iface, d.mac);
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
    Connections {
        target: backend

        function onScanStarted() {
            scanning = true;
        }

        function onScanFinished(txt) {
            scanning = false;
            logArea.text = txt;
            devicesLm.clear();
            selectedDeviceIndex = -1;
            try {
                const obj = JSON.parse(txt);
                const devs = obj.devices || [];
                for (let i = 0; i < devs.length; i++) {
                    devicesLm.append({
                        name: s(devs[i].name),
                        ip: s(devs[i].ip),
                        mac: (devs[i].mac === null || devs[i].mac === undefined) ? "" : String(devs[i].mac).toLowerCase(),
                        vendor_id: s(devs[i].vendor_id),
                        device_id: s(devs[i].device_id),
                        vendor_name: s(devs[i].vendor_name),
                        device_type: s(devs[i].device_type),
                        gsd_match_score: s(devs[i].gsd_match_score)
                    });
                }
                if (devicesLm.count > 0)
                    selectedDeviceIndex = 0;
            } catch (e) {}
        }

        function onScanError(txt) {
            scanning = false;
            logArea.text = txt;
        }
    }
}
