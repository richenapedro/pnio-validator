from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

from .adapters import list_adapters, resolve_iface
from .dcp import DcpClient
from .dcp_fake import FakeDcpClient
from .gsdml_parser import export_expected_model, parse_gsdml, summarize_gsdml
from .pnio_client import PnioClient, PnioClientConfig
from .pnio_client_fake import FakePnioClient, FakeScenario
from .registry import import_gsdml, list_registry, match_device_to_gsd
from .report import ReportMeta, write_report_json, write_report_pdf
from .scanner import scan_dcp
from .suite import SuiteRunConfig, run_fake_suite
from .validator import HeidenhainStrictValidator, RealPnioClientAdapter, ValidationConfig


def _print_result_dict(payload: dict, *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
    else:
        # Human-readable fallback
        print(payload)


def _print_action_result(*, ok: bool, action: str, mac: str, latency_ms: float | None, error: str | None, as_json: bool) -> None:
    payload = {
        "ok": ok,
        "action": action,
        "target_mac": mac,
        "latency_ms": latency_ms,
        "error": error,
    }
    if as_json:
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return

    s = f"OK={ok}  action={action}  mac={mac}"
    if latency_ms is not None:
        s += f"  latency_ms={latency_ms:.1f}"
    if error:
        s += f"  error={error}"
    print(s)


def _cmd_adapters(args: argparse.Namespace) -> int:
    adapters = list_adapters()
    if args.json:
        print(json.dumps([a.to_dict() for a in adapters], indent=2, ensure_ascii=False))
        return 0

    if not adapters:
        print("No adapters found.")
        return 0

    for a in adapters:
        mac = a.mac or "-"
        status = a.status or "-"
        print(f"{a.index}) {a.friendly_name}  mac={mac}  status={status}  iface={a.scapy_iface}")
    return 0


def _cmd_scan(args: argparse.Namespace) -> int:
    iface = resolve_iface(args.iface, args.adapter)
    devices = scan_dcp(iface=iface, timeout_s=args.timeout)

    if args.match_gsd:
        matched: list[dict] = []
        for d in devices:
            entry, reason, score = match_device_to_gsd(
                vendor_id=d.vendor_id,
                device_id=d.device_id,
                name=d.name,
            )
            md = d.to_dict()
            md["gsd_match"] = None if entry is None else entry.to_dict()
            md["gsd_match_reason"] = reason
            md["gsd_match_score"] = score
            matched.append(md)

        if args.json:
            print(json.dumps(matched, indent=2, ensure_ascii=False))
            return 0

        if not matched:
            print("No devices found.")
            return 0

        for md in matched:
            dname = md.get("name") or "<no-name>"
            ip = md.get("ip") or "-"
            mac = md.get("mac")
            vid = md.get("vendor_id")
            did = md.get("device_id")

            g = md["gsd_match"]
            if g:
                print(
                    f"- {dname}  ip={ip}  mac={mac}  vendor={vid}  device={did}  "
                    f"-> GSD={Path(g['file']).name} ({md['gsd_match_reason']}, score={md['gsd_match_score']})"
                )
            else:
                print(
                    f"- {dname}  ip={ip}  mac={mac}  vendor={vid}  device={did}  "
                    f"-> GSD=<none> ({md['gsd_match_reason']})"
                )
        return 0

    # Default: previous behavior (no matching)
    if args.json:
        print(json.dumps([d.to_dict() for d in devices], indent=2, ensure_ascii=False))
        return 0

    if not devices:
        print("No devices found.")
        return 0

    for d in devices:
        print(
            f"- {d.name or '<no-name>'}  ip={d.ip or '-'}  mac={d.mac}  "
            f"vendor={d.vendor_id}  device={d.device_id}"
        )
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    if not args.fake and not (args.iface or args.adapter is not None):
        print("Please provide --iface or --adapter (or use --fake).")
        return 2

    iface = None if args.fake else resolve_iface(args.iface, args.adapter)

    # Select client implementation (fake for local development, real for network usage)
    if args.fake:
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

    if args.json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
    else:
        print(result.to_text())

    meta = ReportMeta(
        generated_at=datetime.now().isoformat(timespec="seconds"),
        mode="fake" if args.fake else "real",
        scenario=args.scenario if args.fake else None,
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

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        write_report_json(out, result, meta)
        print(f"\nJSON report written: {out}")

    if args.pdf:
        pdf = Path(args.pdf)
        pdf.parent.mkdir(parents=True, exist_ok=True)
        write_report_pdf(pdf, result, meta)
        print(f"PDF report written: {pdf}")

    return 0 if result.ok else 2


def _cmd_suite(args: argparse.Namespace) -> int:
    # Suite currently supports fake mode only
    if not args.fake:
        print("Suite currently supports only --fake mode.")
        return 2

    cfg = SuiteRunConfig(
        device_name=args.device_name,
        out_dir=Path(args.out_dir),
        mode="fake",
        iface=None,
        adapter=None,
        timeout_ms=args.timeout_ms,
        retries=args.retries,
        len_aff0=args.len_aff0,
        len_f841=args.len_f841,
        min_aff0_bytes=args.min_aff0_bytes,
        min_f841_ratio=args.min_f841_ratio,
        pdf=bool(args.pdf),
        json=bool(args.json_out),
    )

    summary = run_fake_suite(
        cfg=cfg,
        base_latency_ms=float(args.base_latency_ms),
        extra_latency_ms=float(args.extra_latency_ms),
    )

    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


def _cmd_gsdml_parse(args: argparse.Namespace) -> int:
    model = parse_gsdml(args.file)

    if args.json or not args.out:
        print(model.to_json())

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        model.save_json(out)
        print(f"Written: {out}")

    return 0


def _cmd_gsdml_summarize(args: argparse.Namespace) -> int:
    model = parse_gsdml(args.file)
    print(summarize_gsdml(model))
    return 0


def _cmd_gsdml_export_expected(args: argparse.Namespace) -> int:
    model = parse_gsdml(args.file)
    expected = export_expected_model(model)

    if args.json or not args.out:
        print(json.dumps(expected, indent=2, ensure_ascii=False))

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(expected, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"Written: {out}")

    return 0


def _cmd_gsdml_import(args: argparse.Namespace) -> int:
    entry = import_gsdml(args.file)
    print(json.dumps(entry.to_dict(), indent=2, ensure_ascii=False))
    return 0


def _cmd_gsdml_list(args: argparse.Namespace) -> int:
    entries = list_registry()
    if args.json:
        print(json.dumps([e.to_dict() for e in entries], indent=2, ensure_ascii=False))
        return 0

    if not entries:
        print("Registry is empty. Import a GSDML first: pnio-validator gsdml import --file <path>")
        return 0

    for e in entries:
        print(f"- {e.vendor_id}:{e.device_id}  {e.product_name or '-'}  file={Path(e.file).name}")
    return 0


def _cmd_match(args: argparse.Namespace) -> int:
    vendor_id = int(str(args.vendor_id), 0)
    device_id = int(str(args.device_id), 0)

    entry, reason, score = match_device_to_gsd(
        vendor_id=vendor_id,
        device_id=device_id,
        name=args.name or "",
    )

    if args.json:
        payload = {
            "vendor_id": f"0x{vendor_id:x}",
            "device_id": f"0x{device_id:x}",
            "name": args.name,
            "match": None if entry is None else entry.to_dict(),
            "reason": reason,
            "score": score,
        }
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0 if entry else 2

    if entry:
        print(f"Match: {Path(entry.file).name}  ({reason}, score={score})")
        print(f"Vendor/Device: {entry.vendor_id}:{entry.device_id}")
        if entry.product_name:
            print(f"Product: {entry.product_name}")
        return 0

    print(f"No match found. ({reason})")
    return 2

def _resolve_target_mac(
    *,
    iface: str,
    mac: str | None,
    device_name: str | None,
    ip: str | None,
    timeout_s: float,
    fake: bool,
) -> str:
    """
    Resolve a target MAC address.

    Priority:
      1) explicit --mac
      2) --device-name via DCP scan (or deterministic fake MAC in --fake)
      3) --ip via DCP scan (or deterministic fake MAC in --fake)

    In fake mode, we do NOT require network scan to succeed. We generate a stable,
    deterministic MAC derived from the provided device_name/ip so the CLI can be used
    offline (useful for front-end development).
    """
    if mac:
        return mac

    # Offline-friendly behavior for --fake
    if fake:
        seed = (device_name or ip or "").strip()
        if not seed:
            # Keep explicit error: user provided neither mac nor selectors
            raise ValueError("Target not specified. Provide --mac or --device-name/--ip.")

        # Deterministic "locally administered" unicast MAC: 02:xx:xx:xx:xx:xx
        h = abs(hash(seed)) & 0xFFFFFFFFFFFF
        b = [
            0x02,  # locally administered, unicast
            (h >> 32) & 0xFF,
            (h >> 24) & 0xFF,
            (h >> 16) & 0xFF,
            (h >> 8) & 0xFF,
            h & 0xFF,
        ]
        return ":".join(f"{x:02x}" for x in b)

    devices = scan_dcp(iface=iface, timeout_s=timeout_s)

    if device_name:
        for d in devices:
            if (d.name or "").lower() == device_name.lower():
                return d.mac

    if ip:
        for d in devices:
            if (d.ip or "") == ip:
                return d.mac

    raise ValueError("Target device not found. Provide --mac or use --device-name/--ip with a reachable device.")

def _cmd_dcp_set_name(args: argparse.Namespace) -> int:
    iface = resolve_iface(args.iface, args.adapter)
    client = FakeDcpClient() if args.fake else DcpClient(iface=iface, timeout_s=float(args.timeout))

    try:
        target_mac = _resolve_target_mac(
            iface=iface,
            mac=args.mac,
            device_name=args.device_name,
            ip=args.ip,
            timeout_s=float(args.scan_timeout),
            fake=bool(args.fake),
        )
    except ValueError as e:
        print(str(e))
        return 2

    res = client.set_name(target_mac=target_mac, name=args.name, wait_response=not args.no_wait)
    _print_action_result(ok=res.ok, action=res.action, mac=res.target_mac, latency_ms=res.latency_ms, error=res.error, as_json=args.json)
    return 0 if res.ok else 2


def _cmd_dcp_set_ip(args: argparse.Namespace) -> int:
    iface = resolve_iface(args.iface, args.adapter)
    client = FakeDcpClient() if args.fake else DcpClient(iface=iface, timeout_s=float(args.timeout))

    try:
        target_mac = _resolve_target_mac(
            iface=iface,
            mac=args.mac,
            device_name=args.device_name,
            ip=args.ip,
            timeout_s=float(args.scan_timeout),
            fake=bool(args.fake),
        )
    except ValueError as e:
        print(str(e))
        return 2

    res = client.set_ip(
        target_mac=target_mac,
        ip=args.ipv4,
        mask=args.mask,
        gw=args.gw,
        wait_response=not args.no_wait,
    )
    _print_action_result(ok=res.ok, action=res.action, mac=res.target_mac, latency_ms=res.latency_ms, error=res.error, as_json=args.json)
    return 0 if res.ok else 2


def _cmd_dcp_factory_reset(args: argparse.Namespace) -> int:
    iface = resolve_iface(args.iface, args.adapter)
    client = FakeDcpClient() if args.fake else DcpClient(iface=iface, timeout_s=float(args.timeout))

    try:
        target_mac = _resolve_target_mac(
            iface=iface,
            mac=args.mac,
            device_name=args.device_name,
            ip=args.ip,
            timeout_s=float(args.scan_timeout),
            fake=bool(args.fake),
        )
    except ValueError as e:
        print(str(e))
        return 2

    res = client.factory_reset(target_mac=target_mac)
    _print_action_result(ok=res.ok, action=res.action, mac=res.target_mac, latency_ms=res.latency_ms, error=res.error, as_json=args.json)
    return 0 if res.ok else 2

def _cmd_dcp_blink(args: argparse.Namespace) -> int:
    iface = resolve_iface(args.iface, args.adapter)
    client = FakeDcpClient() if args.fake else DcpClient(iface=iface, timeout_s=float(args.timeout))

    try:
        target_mac = _resolve_target_mac(
            iface=iface,
            mac=args.mac,
            device_name=args.device_name,
            ip=args.ip,
            timeout_s=float(args.scan_timeout),
            fake=bool(args.fake),
        )
    except ValueError as e:
        print(str(e))
        return 2

    res = client.blink(
        target_mac=target_mac,
        on=bool(args.on),
        duration_s=float(args.duration),
        wait_response=not args.no_wait,
    )
    _print_action_result(ok=res.ok, action=res.action, mac=res.target_mac, latency_ms=res.latency_ms, error=res.error, as_json=args.json)
    return 0 if res.ok else 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pnio-validator", description="PROFINET IO strict validation tool (WIP).")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_ad = sub.add_parser("adapters", help="List capture-capable network adapters.")
    p_ad.add_argument("--json", action="store_true", help="Print as JSON.")
    p_ad.set_defaults(fn=_cmd_adapters)

    p_scan = sub.add_parser("scan", help="DCP discovery scan.")
    g1 = p_scan.add_mutually_exclusive_group(required=True)
    g1.add_argument("--iface", help="Scapy/Npcap interface name (e.g. \\\\Device\\\\NPF_{GUID}).")
    g1.add_argument("--adapter", type=int, help="Adapter index from `pnio-validator adapters`.")
    p_scan.add_argument("--timeout", type=float, default=5.0, help="Scan timeout in seconds.")
    p_scan.add_argument("--json", action="store_true", help="Print as JSON.")
    p_scan.add_argument("--match-gsd", action="store_true", help="Match discovered devices against imported GSDML registry.")
    p_scan.set_defaults(fn=_cmd_scan)

    p_val = sub.add_parser("validate", help="Run strict validation (stub).")
    g2 = p_val.add_mutually_exclusive_group(required=False)
    g2.add_argument("--iface", help="Scapy/Npcap interface name (e.g. \\\\Device\\\\NPF_{GUID}).")
    g2.add_argument("--adapter", type=int, help="Adapter index from `pnio-validator adapters`.")
    p_val.add_argument("--device-name", required=True, help="PROFINET station name (NameOfStation).")
    p_val.add_argument("--slot", type=int, default=0, help="Slot (default: 0).")
    p_val.add_argument("--subslot", type=int, default=1, help="Subslot (default: 1).")
    p_val.add_argument("--timeout-ms", type=int, default=3000, help="Read timeout in ms.")
    p_val.add_argument("--fake", action="store_true", help="Use fake PNIO client (no network).")
    p_val.add_argument("--scenario", default="ok", help="Fake scenario: ok, f841_timeout, aff0_timeout, f841_short, random_latency")
    p_val.add_argument("--base-latency-ms", type=float, default=15.0, help="Fake base latency in ms.")
    p_val.add_argument("--extra-latency-ms", type=float, default=0.0, help="Fake additional latency in ms.")
    p_val.add_argument("--retries", type=int, default=1, help="Retries per request.")
    p_val.add_argument("--len-aff0", type=int, default=2048, help="Requested length for 0xAFF0.")
    p_val.add_argument("--len-f841", type=int, default=24576, help="Requested length for 0xF841 (~24kB).")
    p_val.add_argument("--min-aff0-bytes", type=int, default=32, help="Minimum accepted bytes for 0xAFF0.")
    p_val.add_argument("--min-f841-ratio", type=float, default=0.90, help="Minimum accepted ratio for 0xF841 length.")
    p_val.add_argument("--out", default="", help="Write report JSON to path.")
    p_val.add_argument("--pdf", default="", help="Write report PDF to path.")
    p_val.add_argument("--json", action="store_true", help="Print as JSON.")
    p_val.set_defaults(fn=_cmd_validate)

    p_suite = sub.add_parser("suite", help="Run a predefined validation suite and write reports.")
    p_suite.add_argument("--fake", action="store_true", help="Run suite in fake mode (no network).")
    p_suite.add_argument("--device-name", required=True, help="PROFINET station name (NameOfStation).")
    p_suite.add_argument("--out-dir", default="reports", help="Output directory for suite reports.")
    p_suite.add_argument("--pdf", action="store_true", help="Generate PDF reports.")
    p_suite.add_argument("--json-out", action="store_true", help="Generate JSON reports.")
    p_suite.add_argument("--timeout-ms", type=int, default=3000, help="Read timeout in ms.")
    p_suite.add_argument("--retries", type=int, default=1, help="Retries per request.")
    p_suite.add_argument("--len-aff0", type=int, default=2048, help="Requested length for 0xAFF0.")
    p_suite.add_argument("--len-f841", type=int, default=24576, help="Requested length for 0xF841 (~24kB).")
    p_suite.add_argument("--min-aff0-bytes", type=int, default=32, help="Minimum accepted bytes for 0xAFF0.")
    p_suite.add_argument("--min-f841-ratio", type=float, default=0.90, help="Minimum accepted ratio for 0xF841 length.")
    p_suite.add_argument("--base-latency-ms", type=float, default=15.0, help="Fake base latency in ms.")
    p_suite.add_argument("--extra-latency-ms", type=float, default=0.0, help="Fake additional latency in ms.")
    p_suite.set_defaults(fn=_cmd_suite)

    p_gsdml = sub.add_parser("gsdml", help="GSDML utilities.")
    gsdml_sub = p_gsdml.add_subparsers(dest="gsdml_cmd", required=True)

    p_gsdml_parse = gsdml_sub.add_parser("parse", help="Parse a GSDML XML file and export JSON.")
    p_gsdml_parse.add_argument("--file", required=True, help="Path to GSDML XML file.")
    p_gsdml_parse.add_argument("--out", default="", help="Write parsed model as JSON to this path.")
    p_gsdml_parse.add_argument("--json", action="store_true", help="Print parsed model as JSON.")
    p_gsdml_parse.set_defaults(fn=_cmd_gsdml_parse)

    p_gsdml_sum = gsdml_sub.add_parser("summarize", help="Print a human-readable summary of a GSDML file.")
    p_gsdml_sum.add_argument("--file", required=True, help="Path to GSDML XML file.")
    p_gsdml_sum.set_defaults(fn=_cmd_gsdml_summarize)

    p_gsdml_exp = gsdml_sub.add_parser("export-expected", help="Export a compact expected model JSON for comparisons.")
    p_gsdml_exp.add_argument("--file", required=True, help="Path to GSDML XML file.")
    p_gsdml_exp.add_argument("--out", default="", help="Write expected model JSON to this path.")
    p_gsdml_exp.add_argument("--json", action="store_true", help="Print expected model as JSON.")
    p_gsdml_exp.set_defaults(fn=_cmd_gsdml_export_expected)

    p_gsdml_imp = gsdml_sub.add_parser("import", help="Import a GSDML file into the local registry.")
    p_gsdml_imp.add_argument("--file", required=True, help="Path to GSDML XML file.")
    p_gsdml_imp.set_defaults(fn=_cmd_gsdml_import)

    p_gsdml_list = gsdml_sub.add_parser("list", help="List imported GSDML entries.")
    p_gsdml_list.add_argument("--json", action="store_true", help="Print as JSON.")
    p_gsdml_list.set_defaults(fn=_cmd_gsdml_list)

    p_match = sub.add_parser("match", help="Match a (vendor_id, device_id) against imported GSDML registry.")
    p_match.add_argument("--vendor-id", required=True, help="VendorId (e.g. 0x1234 or 4660).")
    p_match.add_argument("--device-id", required=True, help="DeviceId (e.g. 0x5678 or 22136).")
    p_match.add_argument("--name", default="", help="Optional device name for heuristic matching.")
    p_match.add_argument("--json", action="store_true", help="Print as JSON.")
    p_match.set_defaults(fn=_cmd_match)

    p_dcp = sub.add_parser("dcp", help="PRONETA-like DCP configuration utilities.")
    dcp_sub = p_dcp.add_subparsers(dest="dcp_cmd", required=True)

    def _add_target(parser_: argparse.ArgumentParser) -> None:
        mg = parser_.add_mutually_exclusive_group(required=True)
        mg.add_argument("--iface", help="Scapy/Npcap interface name (e.g. \\\\Device\\\\NPF_{GUID}).")
        mg.add_argument("--adapter", type=int, help="Adapter index from `pnio-validator adapters`.")

    p_dcp_name = dcp_sub.add_parser("set-name", help="Set PROFINET NameOfStation via DCP.")
    _add_target(p_dcp_name)
    tg = p_dcp_name.add_mutually_exclusive_group(required=True)
    tg.add_argument("--mac", help="Target device MAC address.")
    tg.add_argument("--device-name", help="Target device station name (resolved via scan).")
    tg.add_argument("--ip", help="Target device IPv4 (resolved via scan).")
    p_dcp_name.add_argument("--scan-timeout", type=float, default=3.0, help="Scan timeout in seconds (for resolving device-name/ip).")
    p_dcp_name.add_argument("--name", required=True, help="New station name.")
    p_dcp_name.add_argument("--timeout", type=float, default=3.0, help="Response wait timeout in seconds.")
    p_dcp_name.add_argument("--no-wait", action="store_true", help="Do not wait for a DCP response.")
    p_dcp_name.add_argument("--fake", action="store_true", help="Use fake DCP client (offline).")
    p_dcp_name.add_argument("--json", action="store_true", help="Print as JSON.")
    p_dcp_name.set_defaults(fn=_cmd_dcp_set_name)

    p_dcp_ip = dcp_sub.add_parser("set-ip", help="Set IP/Mask/Gateway via DCP.")
    _add_target(p_dcp_ip)
    tg = p_dcp_ip.add_mutually_exclusive_group(required=True)
    tg.add_argument("--mac", help="Target device MAC address.")
    tg.add_argument("--device-name", help="Target device station name (resolved via scan).")
    tg.add_argument("--ip", help="Target device IPv4 (resolved via scan).")
    p_dcp_ip.add_argument("--scan-timeout", type=float, default=3.0, help="Scan timeout in seconds (for resolving device-name/ip).")

    p_dcp_ip.add_argument("--ipv4", required=True, help="IPv4 address to set on the device.")
    p_dcp_ip.add_argument("--mask", required=True, help="IPv4 subnet mask.")
    p_dcp_ip.add_argument("--gw", default="0.0.0.0", help="IPv4 gateway.")
    p_dcp_ip.add_argument("--timeout", type=float, default=3.0, help="Response wait timeout in seconds.")
    p_dcp_ip.add_argument("--no-wait", action="store_true", help="Do not wait for a DCP response.")
    p_dcp_ip.add_argument("--fake", action="store_true", help="Use fake DCP client (offline).")
    p_dcp_ip.add_argument("--json", action="store_true", help="Print as JSON.")
    p_dcp_ip.set_defaults(fn=_cmd_dcp_set_ip)

    p_dcp_reset = dcp_sub.add_parser("factory-reset", help="Factory reset (capability placeholder; vendor-specific).")
    _add_target(p_dcp_reset)
    tg = p_dcp_reset.add_mutually_exclusive_group(required=True)
    tg.add_argument("--mac", help="Target device MAC address.")
    tg.add_argument("--device-name", help="Target device station name (resolved via scan).")
    tg.add_argument("--ip", help="Target device IPv4 (resolved via scan).")
    p_dcp_reset.add_argument("--scan-timeout", type=float, default=3.0, help="Scan timeout in seconds (for resolving device-name/ip).")
    p_dcp_reset.add_argument("--timeout", type=float, default=3.0, help="Response wait timeout in seconds.")
    p_dcp_reset.add_argument("--fake", action="store_true", help="Use fake DCP client (offline).")
    p_dcp_reset.add_argument("--json", action="store_true", help="Print as JSON.")
    p_dcp_reset.set_defaults(fn=_cmd_dcp_factory_reset)

    p_dcp_blink = dcp_sub.add_parser("blink", help="Blink/identify device (best-effort; vendor-dependent).")
    _add_target(p_dcp_blink)
    tg = p_dcp_blink.add_mutually_exclusive_group(required=True)
    tg.add_argument("--mac", help="Target device MAC address.")
    tg.add_argument("--device-name", help="Target device station name (resolved via scan).")
    tg.add_argument("--ip", help="Target device IPv4 (resolved via scan).")
    p_dcp_blink.add_argument("--scan-timeout", type=float, default=3.0, help="Scan timeout in seconds (for resolving device-name/ip).")
    p_dcp_blink.add_argument("--on", action="store_true", help="Turn blink ON.")
    p_dcp_blink.add_argument("--off", dest="on", action="store_false", help="Turn blink OFF.")
    p_dcp_blink.set_defaults(on=True)
    p_dcp_blink.add_argument("--duration", type=float, default=10.0, help="Blink duration in seconds (hint).")
    p_dcp_blink.add_argument("--timeout", type=float, default=3.0, help="Response wait timeout in seconds.")
    p_dcp_blink.add_argument("--no-wait", action="store_true", help="Do not wait for a DCP response.")
    p_dcp_blink.add_argument("--fake", action="store_true", help="Use fake DCP client (offline).")
    p_dcp_blink.add_argument("--json", action="store_true", help="Print as JSON.")
    p_dcp_blink.set_defaults(fn=_cmd_dcp_blink)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))