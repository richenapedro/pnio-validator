from __future__ import annotations

import json
from typing import Any, Dict, Optional
from types import SimpleNamespace
from PySide6.QtCore import QObject, Slot

from .cli import _build_service  # keep single source of wiring
from .app_service import AppService


def _json_dumps(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


class QtBackend(QObject):
    """Qt/QML bridge for AppService.

    All methods return JSON strings to keep QML integration minimal.
    """

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._service: AppService = _build_service()

    # -------- Helpers --------

    def _ok(self, payload: Dict[str, Any]) -> str:
        return _json_dumps(payload)

    def _err(self, message: str, *, details: Any = None) -> str:
        return _json_dumps({"ok": False, "error": message, "details": details})

    # -------- Adapters --------

    @Slot(result=str)
    def listAdapters(self) -> str:
        try:
            return self._ok({"ok": True, "adapters": self._service.list_adapters()})
        except Exception as e:
            return self._err("list_adapters_failed", details=str(e))

    # -------- Scan --------

    @Slot(str, float, bool, result=str)
    def scan(self, iface: str, timeout_s: float = 5.0, match_gsd: bool = False) -> str:
        try:
            devices = self._service.scan_devices(iface=iface, timeout_s=float(timeout_s), match_gsd=bool(match_gsd))
            return self._ok({"ok": True, "devices": [d.to_dict() for d in devices]})
        except Exception as e:
            return self._err("scan_failed", details=str(e))

    # -------- Match --------

    @Slot(str, str, str, result=str)
    def match(self, vendor_id: str, device_id: str, name: str = "") -> str:
        try:
            vid = int(str(vendor_id), 0)
            did = int(str(device_id), 0)
            res = self._service.match(vendor_id=vid, device_id=did, name=str(name or ""))
            return self._ok({"ok": True, **res})
        except Exception as e:
            return self._err("match_failed", details=str(e))

    # -------- Validate --------

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
        """Validate in fake mode without network."""
        try:
            # Build a minimal args-like object compatible with AppService.validate_payload
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

    # -------- DCP (fake-friendly) --------

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
            return self._ok({"ok": True, "action": res.action, "target_mac": res.target_mac, "latency_ms": res.latency_ms, "error": res.error})
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
            return self._ok({"ok": True, "action": res.action, "target_mac": res.target_mac, "latency_ms": res.latency_ms, "error": res.error})
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
            return self._ok({"ok": True, "action": res.action, "target_mac": res.target_mac, "latency_ms": res.latency_ms, "error": res.error})
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
            return self._ok({"ok": True, "action": res.action, "target_mac": res.target_mac, "latency_ms": res.latency_ms, "error": res.error})
        except Exception as e:
            return self._err("dcp_factory_reset_failed", details=str(e))