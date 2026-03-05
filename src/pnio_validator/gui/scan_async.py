from __future__ import annotations

from PySide6.QtCore import QObject, Signal, Slot, QThread


class ScanWorker(QObject):
    finished = Signal(str)
    error = Signal(str)

    def __init__(self, app_service):
        super().__init__()
        self._svc = app_service
        self._iface = ""
        self._timeout = 5.0
        self._match_gsd = True

    @Slot(str, float, bool)
    def configure(self, scapy_iface: str, timeout_s: float, match_gsd: bool):
        self._iface = scapy_iface
        self._timeout = float(timeout_s)
        self._match_gsd = bool(match_gsd)

    @Slot()
    def run(self):
        try:
            txt = self._svc.scan(self._iface, self._timeout, self._match_gsd)
            self.finished.emit(txt)
        except Exception as e:
            self.error.emit(str(e))


class ScanController(QObject):
    scanStarted = Signal()
    scanFinished = Signal(str)
    scanError = Signal(str)

    def __init__(self, app_service):
        super().__init__()
        self._thread: QThread | None = None
        self._worker: ScanWorker | None = None
        self._svc = app_service

    @Slot(str, float, bool)
    def startScan(self, scapy_iface: str, timeout_s: float, match_gsd: bool):
        # evita scan concorrente
        if self._thread is not None:
            return

        self.scanStarted.emit()

        self._thread = QThread()
        self._worker = ScanWorker(self._svc)
        self._worker.moveToThread(self._thread)

        self._thread.started.connect(self._worker.run)
        self._worker.configure(scapy_iface, timeout_s, match_gsd)

        self._worker.finished.connect(self._on_finished)
        self._worker.error.connect(self._on_error)

        # cleanup
        self._worker.finished.connect(self._thread.quit)
        self._worker.error.connect(self._thread.quit)
        self._thread.finished.connect(self._thread.deleteLater)

        self._thread.start()

    @Slot(str)
    def _on_finished(self, txt: str):
        self.scanFinished.emit(txt)
        self._cleanup()

    @Slot(str)
    def _on_error(self, msg: str):
        self.scanError.emit(msg)
        self._cleanup()

    def _cleanup(self):
        self._worker = None
        self._thread = None