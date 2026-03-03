from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .scanner import scan_dcp
from .pnio_client import PnioClient, PnioClientConfig
from .validator import HeidenhainStrictValidator, ValidationConfig
from .report import write_report_json


def _cmd_scan(args: argparse.Namespace) -> int:
    devices = scan_dcp(iface=args.iface, timeout_s=args.timeout)
    if args.json:
        print(json.dumps([d.to_dict() for d in devices], indent=2))
    else:
        if not devices:
            print("No devices found.")
            return 0
        for d in devices:
            print(f"- {d.name or '<no-name>'}  ip={d.ip or '-'}  mac={d.mac}  vendor={d.vendor_id}  device={d.device_id}")
    return 0


def _cmd_validate(args: argparse.Namespace) -> int:
    client = PnioClient(PnioClientConfig(iface=args.iface, timeout_ms=args.timeout_ms))

    vcfg = ValidationConfig(
        device_name=args.device_name,
        slot=args.slot,
        subslot=args.subslot,
        read_len_aff0=args.len_aff0,
        read_len_f841=args.len_f841,
        retries=args.retries,
    )
    validator = HeidenhainStrictValidator(client=client, config=vcfg)
    result = validator.run()

    if args.json:
        print(json.dumps(result.to_dict(), indent=2))
    else:
        print(result.to_text())

    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        write_report_json(out, result)
        print(f"\nReport written: {out}")

    return 0 if result.ok else 2


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="pnio-validator", description="PROFINET IO strict validation tool (WIP).")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_scan = sub.add_parser("scan", help="DCP discovery scan (stub).")
    p_scan.add_argument("--iface", required=True, help="Network interface name (e.g. 'Ethernet', 'eth0').")
    p_scan.add_argument("--timeout", type=float, default=5.0, help="Scan timeout in seconds.")
    p_scan.add_argument("--json", action="store_true", help="Print as JSON.")
    p_scan.set_defaults(fn=_cmd_scan)

    p_val = sub.add_parser("validate", help="Run strict validation (stub).")
    p_val.add_argument("--iface", required=True, help="Network interface name.")
    p_val.add_argument("--device-name", required=True, help="PROFINET station name (NameOfStation).")
    p_val.add_argument("--slot", type=int, default=0, help="Slot (default: 0).")
    p_val.add_argument("--subslot", type=int, default=1, help="Subslot (default: 1).")
    p_val.add_argument("--timeout-ms", type=int, default=3000, help="Read timeout in ms.")
    p_val.add_argument("--retries", type=int, default=1, help="Retries per request.")
    p_val.add_argument("--len-aff0", type=int, default=2048, help="Requested length for 0xAFF0.")
    p_val.add_argument("--len-f841", type=int, default=24576, help="Requested length for 0xF841 (~24kB).")
    p_val.add_argument("--out", default="", help="Write report JSON to path.")
    p_val.add_argument("--json", action="store_true", help="Print as JSON.")
    p_val.set_defaults(fn=_cmd_validate)

    return p


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.fn(args))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))