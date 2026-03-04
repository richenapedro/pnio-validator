from __future__ import annotations

import inspect
import json
from dataclasses import dataclass
from typing import Any, Dict, List

from types import SimpleNamespace


def _parse_int_auto(x: Any) -> int:
    """Parse int from '0x1234' / '1234' / int."""
    if isinstance(x, int):
        return x
    s = str(x).strip()
    if s.lower().startswith("0x"):
        return int(s, 16)
    return int(s, 10)


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
    dcp_real: Any   # factory/callable: dcp_real(iface=..., timeout_s=...)
    dcp_fake: Any   # factory/callable: dcp_fake()

    # ----------------- internal helpers -----------------

    def _call(self, fn, /, **kwargs):
        """Call a function filtering kwargs by its signature.

        Keeps compatibility between Real/Fake DCP client even if parameter names differ.
        """
        sig = inspect.signature(fn)
        accepted = {k: v for k, v in kwargs.items() if k in sig.parameters}
        return fn(**accepted)

    # ======================================================================
    # GUI FRIENDLY API (QML calls these)
    # ======================================================================

    def listAdapters(self) -> str:
        """GUI: list adapters as JSON string."""
        try:
            adapters = self.list_adapters()
            return _to_json_ok(adapters=adapters)
        except Exception as e:
            return _to_json_err("listAdapters", e)

    def scan(self, scapy_iface: str, timeout_s: float, match_gsd: bool) -> str:
        """GUI: scan devices via DCP identify; returns JSON string."""
        try:
            devs = self.scan_devices(iface=str(scapy_iface), timeout_s=float(timeout_s), match_gsd=bool(match_gsd))

            devices_out: List[Dict[str, Any]] = []
            for d in devs:
                devices_out.append(
                    {
                        "name": d.name,
                        "ip": d.ip,
                        "mac": d.mac,
                        "vendor_id": d.vendor_id,
                        "device_id": d.device_id,
                        "gsd_match": d.gsd_match,
                        "gsd_match_reason": d.gsd_match_reason,
                        "gsd_match_score": d.gsd_match_score,
                    }
                )

            return _to_json_ok(devices=devices_out)
        except Exception as e:
            return _to_json_err("scan", e, raw={"iface": scapy_iface, "timeout_s": timeout_s, "match_gsd": match_gsd})

    def matchGui(self, vendor_id_text: str, device_id_text: str, name_hint: str = "") -> str:
        """GUI: match GSDML using string inputs."""
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

    def validateFake(self, device_name: str, scenario: str) -> str:
        """GUI: run strict validation in fake mode; returns JSON string."""
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
        """GUI: DCP set station name REAL; returns JSON string."""
        try:
            client = self.dcp_real(iface=str(scapy_iface), timeout_s=3.0)
            res = self._call(
                client.set_name,
                target_mac=str(target_mac).lower(),
                name=str(new_name),
                wait_response=True,
                no_wait=False,
            )
            return _to_json_ok(action="dcpSetName", result=res)
        except Exception as e:
            return _to_json_err("dcpSetName", e, raw={"iface": scapy_iface, "mac": target_mac, "name": new_name})

    def dcpSetIp(self, scapy_iface: str, target_mac: str, ip: str, mask: str, gw: str) -> str:
        """GUI: DCP set IPv4/mask/gw REAL; returns JSON string."""
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
            return _to_json_ok(action="dcpSetIp", result=res)
        except Exception as e:
            return _to_json_err("dcpSetIp", e, raw={"iface": scapy_iface, "mac": target_mac, "ip": ip, "mask": mask, "gw": gw})

    def dcpBlink(self, scapy_iface: str, target_mac: str, on: bool, duration_s: float) -> str:
        """GUI: DCP blink/identify REAL; returns JSON string."""
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
            return _to_json_ok(action="dcpBlink", result=res)
        except Exception as e:
            return _to_json_err("dcpBlink", e, raw={"iface": scapy_iface, "mac": target_mac, "on": on, "duration_s": duration_s})

    def dcpFactoryReset(self, scapy_iface: str, target_mac: str) -> str:
        """GUI: DCP factory reset REAL (if supported by your real client)."""
        try:
            client = self.dcp_real(iface=str(scapy_iface), timeout_s=3.0)
            res = self._call(
                client.factory_reset,
                target_mac=str(target_mac).lower(),
                wait_response=True,
                no_wait=False,
            )
            return _to_json_ok(action="dcpFactoryReset", result=res)
        except Exception as e:
            return _to_json_err("dcpFactoryReset", e, raw={"iface": scapy_iface, "mac": target_mac})

    # ======================================================================
    # CLI API (kept as-is)
    # ======================================================================

    # -------- Adapters / Scan / Match --------

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

    # -------- DCP actions (CLI style) --------

    def _resolve_dcp_iface(self, args: Any) -> str:
        """Resolve iface only when needed (real mode)."""
        if bool(args.fake):
            return ""
        return self.adapters.resolve_iface(args.iface, args.adapter)

    def _resolve_target_mac_for_dcp(self, args: Any, iface: str) -> str:
        """Resolve target MAC for DCP actions.

        - If --mac provided: use it
        - If --fake: derive deterministic MAC from device-name (preferred) or ip
        - Else: resolve via scan (device-name / ip)
        """
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
        """DCP: set station name."""
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
        """DCP: set IPv4/Mask/Gateway."""
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
        """DCP: blink/identify device (best-effort)."""
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
        """DCP: factory reset (placeholder)."""
        iface = self._resolve_dcp_iface(args)
        client = self.dcp_fake() if bool(args.fake) else self.dcp_real(iface=iface, timeout_s=float(args.timeout))

        target_mac = self._resolve_target_mac_for_dcp(args, iface)

        return self._call(
            client.factory_reset,
            target_mac=target_mac,
            wait_response=True,
            no_wait=False,
        )

    # -------- Validation --------

    def validate_device(self, args: Any):
        """Run strict validation using either fake or real PNIO client.

        Returns: (result, meta)
        """
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
        """GUI-friendly validation call.

        Returns a single JSON-serializable dict:
        { "result": <validator result dict>, "meta": <report meta dict> }
        """
        result, meta = self.validate_device(args)

        result_d = result.to_dict() if hasattr(result, "to_dict") else result

        if hasattr(meta, "to_dict") and callable(meta.to_dict):
            meta_d = meta.to_dict()
        elif isinstance(meta, dict):
            meta_d = meta
        else:
            meta_d = meta.__dict__ if hasattr(meta, "__dict__") else {"repr": repr(meta)}

        return {"result": result_d, "meta": meta_d}