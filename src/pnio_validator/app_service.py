# app_service.py

from __future__ import annotations

import inspect
import json
import re
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Dict, List
from urllib.parse import unquote


def _parse_int_auto(x: Any) -> int:
    """Parse int from '0x1234' / '1234' / int."""
    if isinstance(x, int):
        return x
    s = str(x).strip()
    if s.lower().startswith("0x"):
        return int(s, 16)
    return int(s, 10)


def _qurl_to_path(s: str) -> str:
    """
    QML often sends urls like:
      file:///C:/path/to/file.xml
    Convert to a usable filesystem path on Windows.
    """
    if not s:
        return ""
    t = str(s).strip()

    if t.startswith("file:///"):
        t = t[len("file:///") :]
    elif t.startswith("file://"):
        t = t[len("file://") :]

    t = unquote(t)

    # If it still looks like /C:/..., drop leading slash
    if re.match(r"^/[A-Za-z]:/", t):
        t = t[1:]

    return t


def _to_json_ok(**payload) -> str:
    return json.dumps({"ok": True, **payload}, indent=2, ensure_ascii=False)


def _to_json_err(action: str, err: Exception, raw: Any = None) -> str:
    d: Dict[str, Any] = {"ok": False, "action": action, "error": str(err)}
    if raw is not None:
        d["raw"] = raw
    return json.dumps(d, indent=2, ensure_ascii=False)


@dataclass(slots=True)
class AppService:
    """Facade service for CLI/GUI.

    - CLI methods: accept an args-like object and return python objects.
    - GUI methods: accept primitives (str/bool/float) and return JSON strings.
    """

    adapters: Any
    scanner: Any
    registry: Any
    validator: Any
    dcp_real: Any  # factory/callable: dcp_real(iface=..., timeout_s=...)
    dcp_fake: Any  # factory/callable: dcp_fake()

    # ----------------- internal helpers -----------------

    def _call(self, fn, /, **kwargs):
        """Call a function filtering kwargs by its signature."""
        sig = inspect.signature(fn)
        accepted = {k: v for k, v in kwargs.items() if k in sig.parameters}
        return fn(**accepted)

    # ======================================================================
    # GUI FRIENDLY API (QML calls these)
    # ======================================================================

    def listAdapters(self) -> str:
        try:
            adapters = self.list_adapters()
            return _to_json_ok(adapters=adapters)
        except Exception as e:
            return _to_json_err("listAdapters", e)

    def scan(self, scapy_iface: str, timeout_s: float, match_gsd: bool) -> str:
        try:
            discovered = self.scanner.scan_dcp(iface=str(scapy_iface), timeout_s=float(timeout_s))

            devices_out: List[Dict[str, Any]] = []
            for d in discovered:
                name = getattr(d, "name", None)
                ip = getattr(d, "ip", None)
                mac = getattr(d, "mac", None)
                vendor_id = getattr(d, "vendor_id", None)
                device_id = getattr(d, "device_id", None)

                vendor_name = getattr(d, "vendor_name", None) or getattr(d, "vendor", None) or ""
                device_type = getattr(d, "device_type", None) or getattr(d, "product_name", None) or ""

                item: Dict[str, Any] = {
                    "name": name or "",
                    "ip": ip or "",
                    "mac": (mac or "").lower(),
                    "vendor_id": "" if vendor_id is None else str(vendor_id),
                    "device_id": "" if device_id is None else str(device_id),
                    "vendor_name": vendor_name,
                    "device_type": device_type,
                    "gsd_match": {},  # QML-friendly (never null)
                    "gsd_match_reason": "no_match",
                    "gsd_match_score": 0.0,
                }

                if bool(match_gsd) and vendor_id is not None and device_id is not None:
                    try:
                        vid = _parse_int_auto(vendor_id)
                        did = _parse_int_auto(device_id)
                        m = self.match(vendor_id=vid, device_id=did, name=str(name or ""))
                        item["gsd_match"] = m.get("gsd_match") or {}
                        item["gsd_match_reason"] = m.get("gsd_match_reason", "") or ""
                        item["gsd_match_score"] = float(m.get("gsd_match_score") or 0.0)
                    except Exception as e:
                        item["gsd_match"] = {}
                        item["gsd_match_reason"] = f"match_error: {e}"
                        item["gsd_match_score"] = 0.0

                devices_out.append(item)

            return _to_json_ok(devices=devices_out)

        except Exception as e:
            return _to_json_err("scan", e, raw={"iface": scapy_iface, "timeout_s": timeout_s, "match_gsd": match_gsd})

    def matchGui(self, vendor_id_text: str, device_id_text: str, name_hint: str = "") -> str:
        try:
            vendor_id = _parse_int_auto(vendor_id_text)
            device_id = _parse_int_auto(device_id_text)
            out = self.match(vendor_id=vendor_id, device_id=device_id, name=str(name_hint or ""))
            return _to_json_ok(**out)
        except Exception as e:
            return _to_json_err(
                "matchGui",
                e,
                raw={"vendor_id": vendor_id_text, "device_id": device_id_text, "name": name_hint},
            )
        
    def importGsdmlFiles(self, files_json: str) -> str:
        """GUI: import multiple GSDML files. `files_json` is a JSON list of file URLs/paths."""
        try:
            import json
            from pathlib import Path

            # input can be: ["file:///C:/a.xml", "C:\\b.xml", ...]
            raw = json.loads(files_json) if files_json else []
            if not isinstance(raw, list):
                raise ValueError("files_json must be a JSON list of file paths/urls")

            imported = []
            errors = []

            def _to_path(s: str) -> str:
                s = str(s or "")
                if s.startswith("file:///"):
                    # QML file url -> windows path
                    s = s[8:]
                    # keep leading slash handling: /C:/... may appear
                    if len(s) >= 3 and s[0] == "/" and s[2] == ":":
                        s = s[1:]
                return s

            for item in raw:
                fp = _to_path(item)
                try:
                    entry = self.registry.import_gsdml(fp)  # see note below
                    imported.append(entry.to_dict() if hasattr(entry, "to_dict") and callable(entry.to_dict) else entry)
                except Exception as e:
                    errors.append({"file": fp, "error": str(e)})

            return _to_json_ok(imported=imported, errors=errors)

        except Exception as e:
            return _to_json_err("importGsdmlFiles", e, raw={"files_json": files_json})

    def importGsdmlFolder(self, folder_url: str) -> str:
        """GUI: import all *.xml in a folder. `folder_url` can be file:///..."""
        try:
            from pathlib import Path

            s = str(folder_url or "")
            if s.startswith("file:///"):
                s = s[8:]
                if len(s) >= 3 and s[0] == "/" and s[2] == ":":
                    s = s[1:]

            folder = Path(s)
            if not folder.exists() or not folder.is_dir():
                raise FileNotFoundError(str(folder))

            xmls = sorted(folder.glob("*.xml"))

            imported = []
            errors = []

            for f in xmls:
                try:
                    entry = self.registry.import_gsdml(f)  # see note below
                    imported.append(entry.to_dict() if hasattr(entry, "to_dict") and callable(entry.to_dict) else entry)
                except Exception as e:
                    errors.append({"file": str(f), "error": str(e)})

            return _to_json_ok(folder=str(folder), imported=imported, errors=errors)

        except Exception as e:
            return _to_json_err("importGsdmlFolder", e, raw={"folder_url": folder_url})

    def validateFake(self, device_name: str, scenario: str) -> str:
        try:
            args = SimpleNamespace(
                fake=True,
                scenario=str(scenario),
                base_latency_ms=0.0,
                extra_latency_ms=0.0,
                iface=None,
                adapter=None,
                device_name=str(device_name),
                slot=0,
                subslot=1,
                len_aff0=4096,
                len_f841=24576,
                retries=1,
                timeout_ms=2000,
                min_aff0_bytes=256,
                min_f841_ratio=0.90,
            )

            payload = self.validate_payload(args)
            return _to_json_ok(**payload)

        except Exception as e:
            return _to_json_err("validateFake", e, raw={"device_name": device_name, "scenario": scenario})
        
    def dcpSetName(self, scapy_iface: str, target_mac: str, new_name: str) -> str:
        try:
            client = self.dcp_real(iface=str(scapy_iface), timeout_s=3.0)
            res = self._call(
                client.set_name,
                target_mac=str(target_mac).lower(),
                name=str(new_name),
                wait_response=True,
                no_wait=False,
            )
            payload = self._result_to_payload(res)
            return _to_json_ok(action="dcpSetName", result=payload)
        except Exception as e:
            return _to_json_err("dcpSetName", e, raw={"iface": scapy_iface, "mac": target_mac, "name": new_name})

    def dcpSetIp(self, scapy_iface: str, target_mac: str, ip: str, mask: str, gw: str) -> str:
        try:
            client = self.dcp_real(iface=str(scapy_iface), timeout_s=3.0)
            res = self._call(
                client.set_ip,
                target_mac=str(target_mac).lower(),
                ipv4=str(ip),
                ip=str(ip),
                mask=str(mask),
                gw=str(gw),
                gateway=str(gw),
                wait_response=True,
                no_wait=False,
            )
            payload = self._result_to_payload(res)
            return _to_json_ok(action="dcpSetIp", result=payload)
        except Exception as e:
            return _to_json_err("dcpSetIp", e, raw={"iface": scapy_iface, "mac": target_mac, "ip": ip, "mask": mask, "gw": gw})

    def dcpBlink(self, scapy_iface: str, target_mac: str, on: bool, duration_s: float) -> str:
        try:
            client = self.dcp_real(iface=str(scapy_iface), timeout_s=3.0)
            res = self._call(
                client.blink,
                target_mac=str(target_mac).lower(),
                on=bool(on),
                duration_s=float(duration_s),
                duration=float(duration_s),
                wait_response=True,
                no_wait=False,
            )
            payload = self._result_to_payload(res)
            return _to_json_ok(action="dcpBlink", result=payload)
        except Exception as e:
            return _to_json_err("dcpBlink", e, raw={"iface": scapy_iface, "mac": target_mac, "on": on, "duration_s": duration_s})

    def dcpFactoryReset(self, scapy_iface: str, target_mac: str) -> str:
        try:
            client = self.dcp_real(iface=str(scapy_iface), timeout_s=3.0)
            res = self._call(
                client.factory_reset,
                target_mac=str(target_mac).lower(),
                wait_response=True,
                no_wait=False,
            )
            payload = self._result_to_payload(res)
            return _to_json_ok(action="dcpFactoryReset", result=payload)
        except Exception as e:
            return _to_json_err("dcpFactoryReset", e, raw={"iface": scapy_iface, "mac": target_mac})
    # ======================================================================
    # CLI API (kept as-is)
    # ======================================================================

    def list_adapters(self) -> List[Dict[str, Any]]:
        adapters = self.adapters.list_adapters()
        return [a.to_dict() for a in adapters]

    def scan_devices(self, *, iface: str, timeout_s: float, match_gsd: bool):
        from .device_model import DeviceModel  # local import to avoid cycles

        discovered = self.scanner.scan_dcp(iface=iface, timeout_s=timeout_s)
        out: List[DeviceModel] = []

        for d in discovered:
            dev = DeviceModel(
                name=d.name,
                ip=d.ip,
                mac=d.mac,
                vendor_id=d.vendor_id,
                device_id=d.device_id,
                gsd=None,
                gsd_match=None,
                gsd_match_reason="",
                gsd_match_score=None,
                capabilities=DeviceModel.default_capabilities(),
            )

            if match_gsd and dev.vendor_id is not None and dev.device_id is not None:
                m = self.match(vendor_id=dev.vendor_id, device_id=dev.device_id, name=dev.name or "")
                dev.gsd_match = m.get("gsd_match")
                dev.gsd_match_reason = m.get("gsd_match_reason", "")
                dev.gsd_match_score = m.get("gsd_match_score")
                dev.gsd = m

            out.append(dev)

        return out

    def match(self, *, vendor_id: int, device_id: int, name: str = "") -> Dict[str, Any]:
        entry, reason, score = self.registry.match_device_to_gsd(
            vendor_id=vendor_id,
            device_id=device_id,
            name=name,
        )

        if entry is None:
            gsd_match = None
        elif hasattr(entry, "to_dict") and callable(entry.to_dict):
            gsd_match = entry.to_dict()
        elif isinstance(entry, dict):
            gsd_match = entry
        else:
            gsd_match = {"repr": repr(entry)}

        return {
            "gsd_match": gsd_match,
            "gsd_match_reason": str(reason or ""),
            "gsd_match_score": None if score is None else float(score),
        }

    def _resolve_dcp_iface(self, args: Any) -> str:
        if bool(args.fake):
            return ""
        return self.adapters.resolve_iface(args.iface, args.adapter)

    def _resolve_target_mac_for_dcp(self, args: Any, iface: str) -> str:
        from .util.mac import deterministic_fake_mac

        if getattr(args, "mac", None):
            return str(args.mac).lower()

        if bool(args.fake):
            seed = getattr(args, "device_name", None) or getattr(args, "ip", None)
            if not seed:
                raise ValueError("In --fake you must provide --device-name or --ip (or --mac).")
            return deterministic_fake_mac(str(seed))

        discovered = self.scanner.scan_dcp(iface=str(iface), timeout_s=float(args.scan_timeout))

        if getattr(args, "device_name", None):
            for d in discovered:
                if d.name == args.device_name:
                    return str(d.mac).lower()

        if getattr(args, "ip", None):
            for d in discovered:
                if d.ip == args.ip:
                    return str(d.mac).lower()

        raise ValueError("Target device not found. Provide --mac or use --device-name/--ip with a reachable device.")

    def dcp_set_name(self, args: Any):
        iface = self._resolve_dcp_iface(args)
        client = self.dcp_fake() if bool(args.fake) else self.dcp_real(iface=iface, timeout_s=float(args.timeout))
        target_mac = self._resolve_target_mac_for_dcp(args, iface)
        return self._call(
            client.set_name,
            target_mac=target_mac,
            name=args.name,
            wait_response=not bool(args.no_wait),
            no_wait=bool(args.no_wait),
        )

    def dcp_set_ip(self, args: Any):
        iface = self._resolve_dcp_iface(args)
        client = self.dcp_fake() if bool(args.fake) else self.dcp_real(iface=iface, timeout_s=float(args.timeout))
        target_mac = self._resolve_target_mac_for_dcp(args, iface)
        return self._call(
            client.set_ip,
            target_mac=target_mac,
            ipv4=args.ipv4,
            ip=args.ipv4,
            mask=args.mask,
            gw=args.gw,
            gateway=args.gw,
            wait_response=not bool(args.no_wait),
            no_wait=bool(args.no_wait),
        )

    def dcp_blink(self, args: Any):
        iface = self._resolve_dcp_iface(args)
        client = self.dcp_fake() if bool(args.fake) else self.dcp_real(iface=iface, timeout_s=float(args.timeout))
        target_mac = self._resolve_target_mac_for_dcp(args, iface)
        return self._call(
            client.blink,
            target_mac=target_mac,
            on=bool(args.on),
            duration_s=float(args.duration),
            duration=float(args.duration),
            wait_response=not bool(args.no_wait),
            no_wait=bool(args.no_wait),
        )

    def dcp_factory_reset(self, args: Any):
        iface = self._resolve_dcp_iface(args)
        client = self.dcp_fake() if bool(args.fake) else self.dcp_real(iface=iface, timeout_s=float(args.timeout))
        target_mac = self._resolve_target_mac_for_dcp(args, iface)
        return self._call(
            client.factory_reset,
            target_mac=target_mac,
            wait_response=True,
            no_wait=False,
        )

    def validate_device(self, args: Any):
        from datetime import datetime

        from .pnio_client import PnioClient, PnioClientConfig
        from .pnio_client_fake import FakePnioClient, FakeScenario
        from .report import ReportMeta
        from .validator import HeidenhainStrictValidator, RealPnioClientAdapter, ValidationConfig

        iface = None if bool(args.fake) else self.adapters.resolve_iface(args.iface, args.adapter)

        if bool(args.fake):
            client = FakePnioClient(
                FakeScenario(
                    name=args.scenario,
                    base_latency_ms=float(args.base_latency_ms),
                    extra_latency_ms=float(args.extra_latency_ms),
                )
            )
        else:
            real = PnioClient(PnioClientConfig(iface=str(iface), timeout_ms=args.timeout_ms))
            client = RealPnioClientAdapter(real)

        vcfg = ValidationConfig(
            device_name=args.device_name,
            slot=args.slot,
            subslot=args.subslot,
            read_len_aff0=args.len_aff0,
            read_len_f841=args.len_f841,
            retries=args.retries,
            timeout_ms=args.timeout_ms,
            min_aff0_bytes=args.min_aff0_bytes,
            min_f841_ratio=args.min_f841_ratio,
        )

        validator = HeidenhainStrictValidator(client=client, config=vcfg)
        result = validator.run()

        meta = ReportMeta(
            generated_at=datetime.now().isoformat(timespec="seconds"),
            mode="fake" if bool(args.fake) else "real",
            scenario=args.scenario if bool(args.fake) else None,
            iface=str(iface) if iface else None,
            adapter=args.adapter,
            device_name=args.device_name,
            timeout_ms=args.timeout_ms,
            retries=args.retries,
            len_aff0=args.len_aff0,
            len_f841=args.len_f841,
            min_aff0_bytes=args.min_aff0_bytes,
            min_f841_ratio=args.min_f841_ratio,
        )

        return result, meta

    def validate_payload(self, args: Any) -> Dict[str, Any]:
        result, meta = self.validate_device(args)

        result_d = result.to_dict() if hasattr(result, "to_dict") and callable(result.to_dict) else result

        if hasattr(meta, "to_dict") and callable(meta.to_dict):
            meta_d = meta.to_dict()
        elif isinstance(meta, dict):
            meta_d = meta
        else:
            meta_d = meta.__dict__ if hasattr(meta, "__dict__") else {"repr": repr(meta)}

        return {"result": result_d, "meta": meta_d}
    
    def _result_to_payload(self, obj):
        return obj.to_dict() if hasattr(obj, "to_dict") and callable(obj.to_dict) else obj

    def validateReal(
        self,
        scapy_iface: str,
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
            args = SimpleNamespace(
                fake=False,
                iface=str(scapy_iface),
                adapter=None,
                device_name=str(device_name),
                scenario=None,
                slot=int(slot),
                subslot=int(subslot),
                timeout_ms=int(timeout_ms),
                retries=int(retries),
                base_latency_ms=0.0,
                extra_latency_ms=0.0,
                len_aff0=int(len_aff0),
                len_f841=int(len_f841),
                min_aff0_bytes=int(min_aff0_bytes),
                min_f841_ratio=float(min_f841_ratio),
            )

            payload = self.validate_payload(args)
            return _to_json_ok(**payload)

        except Exception as e:
            return _to_json_err(
                "validateReal",
                e,
                raw={
                    "iface": scapy_iface,
                    "device_name": device_name,
                    "slot": slot,
                    "subslot": subslot,
                    "timeout_ms": timeout_ms,
                    "retries": retries,
                    "len_aff0": len_aff0,
                    "len_f841": len_f841,
                    "min_aff0_bytes": min_aff0_bytes,
                    "min_f841_ratio": min_f841_ratio,
                },
            )