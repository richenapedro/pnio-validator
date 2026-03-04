from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from .device_model import DeviceModel


@dataclass(slots=True)
class AppService:
    """Facade service for CLI/GUI.

    Orchestrates existing modules without changing their internals.
    """

    adapters: Any
    scanner: Any
    registry: Any
    validator: Any
    dcp_real: Any
    dcp_fake: Any

    def _call(self, fn, /, **kwargs):
        """Call a function filtering kwargs by its signature.

        This keeps AppService compatible across Real DCP client and Fake DCP client
        even if their parameter names differ.
        """
        sig = inspect.signature(fn)
        accepted = {k: v for k, v in kwargs.items() if k in sig.parameters}
        return fn(**accepted)

    # -------- Adapters / Scan / Match --------

    def list_adapters(self) -> List[Dict[str, Any]]:
        adapters = self.adapters.list_adapters()
        return [a.to_dict() for a in adapters]

    def scan_devices(self, *, iface: str, timeout_s: float, match_gsd: bool) -> List[DeviceModel]:
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
        """Match a (vendor_id, device_id) against imported GSDML registry.

        Normalized return shape (stable for CLI/GUI):
        {
        "gsd_match": {...} | None,
        "gsd_match_reason": str,
        "gsd_match_score": float | None
        }
        """
        entry, reason, score = self.registry.match_device_to_gsd(
            vendor_id=vendor_id,
            device_id=device_id,
            name=name,
        )

        # entry may be a dataclass/object (e.g. GsdEntry). Convert to dict if possible.
        if entry is None:
            gsd_match = None
        elif hasattr(entry, "to_dict") and callable(entry.to_dict):
            gsd_match = entry.to_dict()
        elif isinstance(entry, dict):
            gsd_match = entry
        else:
            # Fallback: best-effort conversion
            gsd_match = {"repr": repr(entry)}

        return {
            "gsd_match": gsd_match,
            "gsd_match_reason": str(reason or ""),
            "gsd_match_score": None if score is None else float(score),
        }

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

    # -------- DCP actions --------

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