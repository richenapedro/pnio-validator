from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

from .adapters import list_adapters, resolve_iface
from .scanner import scan_dcp
from .pnio_client import PnioClient, PnioClientConfig
from .validator import HeidenhainStrictValidator, ValidationConfig, RealPnioClientAdapter
from .pnio_client_fake import FakePnioClient, FakeScenario
from .report import write_report_json, write_report_pdf, ReportMeta
from .suite import run_fake_suite, SuiteRunConfig


def _cmd_adapters(args: argparse.Namespace) -> int:
    adapters = list_adapters()
    if args.json:
        print(json.dumps([a.to_dict() for a in adapters], indent=2))
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

    if args.json:
        print(json.dumps([d.to_dict() for d in devices], indent=2))
    else:
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
    # If running fake mode, no network interface is required
    iface = None if args.fake else resolve_iface(args.iface, args.adapter)

    # Select client implementation (fake for local development, real for network usage)
    if args.fake:
        fake = FakePnioClient(
            FakeScenario(
                name=args.scenario,
                base_latency_ms=float(args.base_latency_ms),
                extra_latency_ms=float(args.extra_latency_ms),
            )
        )
        client = fake
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
        print(json.dumps(result.to_dict(), indent=2))
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

    print(json.dumps(summary, indent=2))
    return 0

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
    p_val.add_argument(
        "--scenario",
        default="ok",
        help="Fake scenario: ok, f841_timeout, aff0_timeout, f841_short, random_latency",
    )
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


    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))