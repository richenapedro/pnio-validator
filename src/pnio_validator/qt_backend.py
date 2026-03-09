from __future__ import annotations

import json
from typing import Any, Dict, Optional
from types import SimpleNamespace

from PySide6.QtCore import QObject, Slot, Signal, QThread

from .cli import _build_service
from .app_service import AppService


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


class _ScanWorker(QObject):
    finished = Signal(str)
    failed = Signal(str)

    def __init__(self, service: AppService, iface: str, timeout_s: float, match_gsd: bool):
        super().__init__()
        self._service = service
        self._iface = str(iface)
        self._timeout_s = float(timeout_s)
        self._match_gsd = bool(match_gsd)

    @Slot()
    def run(self):
        try:
            devices = self._service.scan_devices(
                iface=self._iface,
                timeout_s=self._timeout_s,
                match_gsd=self._match_gsd,
            )
            txt = json.dumps(
                {"ok": True, "devices": [d.to_dict() for d in devices]},
                ensure_ascii=False,
                indent=2,
            )
            self.finished.emit(txt)
        except Exception as e:
            txt = json.dumps(
                {"ok": False, "error": "scan_failed", "details": str(e)},
                ensure_ascii=False,
                indent=2,
            )
            self.failed.emit(txt)


class QtBackend(QObject):
    scanStarted = Signal()
    scanFinished = Signal(str)
    scanError = Signal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._service: AppService = _build_service()

        self._scan_thread: Optional[QThread] = None
        self._scan_worker: Optional[_ScanWorker] = None

    def _ok(self, payload: Dict[str, Any]) -> str:
        return _json_dumps(payload)

    def _err(self, message: str, *, details: Any = None) -> str:
        return _json_dumps({"ok": False, "error": message, "details": details})

    @Slot(str, result=str)
    def importGsdmlFiles(self, files_json: str) -> str:
        return self._service.importGsdmlFiles(files_json)

    @Slot(str, result=str)
    def importGsdmlFolder(self, folder_url: str) -> str:
        return self._service.importGsdmlFolder(folder_url)

    @Slot(result=str)
    def listAdapters(self) -> str:
        try:
            return self._ok({"ok": True, "adapters": self._service.list_adapters()})
        except Exception as e:
            return self._err("list_adapters_failed", details=str(e))

    @Slot(str, float, bool)
    def scanAsync(self, iface: str, timeout_s: float = 5.0, match_gsd: bool = False) -> None:
        if self._scan_thread is not None:
            return

        self.scanStarted.emit()

        self._scan_thread = QThread()
        self._scan_worker = _ScanWorker(self._service, iface, timeout_s, match_gsd)
        self._scan_worker.moveToThread(self._scan_thread)

        self._scan_thread.started.connect(self._scan_worker.run)

        self._scan_worker.finished.connect(self._on_scan_finished)
        self._scan_worker.failed.connect(self._on_scan_failed)

        self._scan_worker.finished.connect(self._scan_thread.quit)
        self._scan_worker.failed.connect(self._scan_thread.quit)

        self._scan_worker.finished.connect(self._scan_worker.deleteLater)
        self._scan_worker.failed.connect(self._scan_worker.deleteLater)

        self._scan_thread.finished.connect(self._on_scan_thread_finished)
        self._scan_thread.finished.connect(self._scan_thread.deleteLater)

        self._scan_thread.start()

    @Slot(str)
    def _on_scan_finished(self, txt: str) -> None:
        self.scanFinished.emit(txt)

    @Slot(str)
    def _on_scan_failed(self, txt: str) -> None:
        self.scanError.emit(txt)

    @Slot()
    def _on_scan_thread_finished(self) -> None:
        self._scan_worker = None
        self._scan_thread = None

    @Slot(str, float, bool, result=str)
    def scan(self, iface: str, timeout_s: float = 5.0, match_gsd: bool = False) -> str:
        try:
            devices = self._service.scan_devices(
                iface=iface,
                timeout_s=float(timeout_s),
                match_gsd=bool(match_gsd),
            )
            return self._ok({"ok": True, "devices": [d.to_dict() for d in devices]})
        except Exception as e:
            return self._err("scan_failed", details=str(e))

    @Slot(str, str, str, result=str)
    def match(self, vendor_id: str, device_id: str, name: str = "") -> str:
        try:
            vid = int(str(vendor_id), 0)
            did = int(str(device_id), 0)
            res = self._service.match(vendor_id=vid, device_id=did, name=str(name or ""))
            return self._ok({"ok": True, **res})
        except Exception as e:
            return self._err("match_failed", details=str(e))

    @Slot(str, str, str, result=str)
    def matchGui(self, vendor_id: str, device_id: str, name: str = "") -> str:
        return self.match(vendor_id, device_id, name)

    @Slot(str, str, int, int, int, int, float, float, int, result=str)
    def validateFake(
        self,
        device_name: str,
        scenario: str = "ok",
        slot: int = 0,
        subslot: int = 1,
        timeout_ms: int = 3000,
        retries: int = 1,
        base_latency_ms: float = 15.0,
        extra_latency_ms: float = 0.0,
        len_aff0: int = 2048,
        len_f841: int = 24576,
        min_f841_ratio: float = 0.90,
        min_aff0_bytes: int = 32,
    ) -> str:
        try:
            args = SimpleNamespace(
                fake=True,
                iface=None,
                adapter=None,
                device_name=str(device_name),
                scenario=str(scenario),
                slot=int(slot),
                subslot=int(subslot),
                timeout_ms=int(timeout_ms),
                retries=int(retries),
                base_latency_ms=float(base_latency_ms),
                extra_latency_ms=float(extra_latency_ms),
                len_aff0=int(len_aff0),
                len_f841=int(len_f841),
                min_aff0_bytes=int(min_aff0_bytes),
                min_f841_ratio=float(min_f841_ratio),
            )
            payload = self._service.validate_payload(args)
            return self._ok({"ok": True, **payload})
        except Exception as e:
            return self._err("validate_failed", details=str(e))

    @Slot(str, str, result=str)
    def dcpSetNameFake(self, device_name: str, new_name: str) -> str:
        try:
            args = SimpleNamespace(
                fake=True,
                iface=None,
                adapter=None,
                mac=None,
                ip=None,
                device_name=str(device_name),
                scan_timeout=0.0,
                timeout=0.0,
                no_wait=False,
                name=str(new_name),
            )
            res = self._service.dcp_set_name(args)
            return self._ok(
                {
                    "ok": True,
                    "action": res.action,
                    "target_mac": res.target_mac,
                    "latency_ms": res.latency_ms,
                    "error": res.error,
                }
            )
        except Exception as e:
            return self._err("dcp_set_name_failed", details=str(e))

    @Slot(str, str, str, str, result=str)
    def dcpSetIpFake(self, device_name: str, ipv4: str, mask: str, gw: str = "0.0.0.0") -> str:
        try:
            args = SimpleNamespace(
                fake=True,
                iface=None,
                adapter=None,
                mac=None,
                ip=None,
                device_name=str(device_name),
                scan_timeout=0.0,
                timeout=0.0,
                no_wait=False,
                ipv4=str(ipv4),
                mask=str(mask),
                gw=str(gw),
            )
            res = self._service.dcp_set_ip(args)
            return self._ok(
                {
                    "ok": True,
                    "action": res.action,
                    "target_mac": res.target_mac,
                    "latency_ms": res.latency_ms,
                    "error": res.error,
                }
            )
        except Exception as e:
            return self._err("dcp_set_ip_failed", details=str(e))

    @Slot(str, bool, float, result=str)
    def dcpBlinkFake(self, device_name: str, on: bool = True, duration_s: float = 10.0) -> str:
        try:
            args = SimpleNamespace(
                fake=True,
                iface=None,
                adapter=None,
                mac=None,
                ip=None,
                device_name=str(device_name),
                scan_timeout=0.0,
                timeout=0.0,
                no_wait=False,
                on=bool(on),
                duration=float(duration_s),
            )
            res = self._service.dcp_blink(args)
            return self._ok(
                {
                    "ok": True,
                    "action": res.action,
                    "target_mac": res.target_mac,
                    "latency_ms": res.latency_ms,
                    "error": res.error,
                }
            )
        except Exception as e:
            return self._err("dcp_blink_failed", details=str(e))

    @Slot(str, result=str)
    def dcpFactoryResetFake(self, device_name: str) -> str:
        try:
            args = SimpleNamespace(
                fake=True,
                iface=None,
                adapter=None,
                mac=None,
                ip=None,
                device_name=str(device_name),
                scan_timeout=0.0,
                timeout=0.0,
            )
            res = self._service.dcp_factory_reset(args)
            return self._ok(
                {
                    "ok": True,
                    "action": res.action,
                    "target_mac": res.target_mac,
                    "latency_ms": res.latency_ms,
                    "error": res.error,
                }
            )
        except Exception as e:
            return self._err("dcp_factory_reset_failed", details=str(e))

    @Slot(str, str, bool, float, result=str)
    def dcpBlink(self, iface: str, target_mac: str, on: bool = True, duration_s: float = 10.0) -> str:
        try:
            return self._service.dcpBlink(
                str(iface),
                str(target_mac).strip().lower(),
                bool(on),
                float(duration_s),
            )
        except Exception as e:
            return self._err("dcp_blink_failed", details=str(e))

    @Slot(str, str, str, result=str)
    def dcpSetName(self, iface: str, target_mac: str, new_name: str) -> str:
        try:
            return self._service.dcpSetName(
                str(iface),
                str(target_mac).strip().lower(),
                str(new_name),
            )
        except Exception as e:
            return self._err("dcp_set_name_failed", details=str(e))

    @Slot(str, str, str, str, str, result=str)
    def dcpSetIp(self, iface: str, target_mac: str, ipv4: str, mask: str, gw: str = "0.0.0.0") -> str:
        try:
            return self._service.dcpSetIp(
                str(iface),
                str(target_mac).strip().lower(),
                str(ipv4),
                str(mask),
                str(gw),
            )
        except Exception as e:
            return self._err("dcp_set_ip_failed", details=str(e))

    @Slot(str, str, result=str)
    def dcpFactoryReset(self, iface: str, target_mac: str) -> str:
        try:
            return self._service.dcpFactoryReset(
                str(iface),
                str(target_mac).strip().lower(),
            )
        except Exception as e:
            return self._err("dcp_factory_reset_failed", details=str(e))
        try:
            args = SimpleNamespace(
                fake=False,
                iface=str(iface),
                adapter=None,
                mac=str(target_mac),
                ip=None,
                device_name=None,
                scan_timeout=0.0,
                timeout=0.0,
                no_wait=False,
            )
            res = self._service.dcp_factory_reset(args)
            return self._ok(
                {
                    "ok": True,
                    "action": res.action,
                    "target_mac": res.target_mac,
                    "latency_ms": res.latency_ms,
                    "error": res.error,
                }
            )
        except Exception as e:
            return self._err("dcp_factory_reset_failed", details=str(e))
        
    @Slot(str, str, int, int, int, int, int, int, float, result=str)
    def validateReal(
        self,
        iface: str,
        device_name: str,
        slot: int = 0,
        subslot: int = 1,
        timeout_ms: int = 3000,
        retries: int = 1,
        len_aff0: int = 2048,
        len_f841: int = 24576,
        min_aff0_bytes: int = 32,
        min_f841_ratio: float = 0.90,
    ) -> str:
        try:
            return self._service.validateReal(
                scapy_iface=str(iface),
                device_name=str(device_name),
                slot=int(slot),
                subslot=int(subslot),
                timeout_ms=int(timeout_ms),
                retries=int(retries),
                len_aff0=int(len_aff0),
                len_f841=int(len_f841),
                min_aff0_bytes=int(min_aff0_bytes),
                min_f841_ratio=float(min_f841_ratio),
            )
        except Exception as e:
            return self._err("validate_real_failed", details=str(e))