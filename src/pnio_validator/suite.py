from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .pnio_client_fake import FakePnioClient, FakeScenario
from .validator import HeidenhainStrictValidator, ValidationConfig
from .report import ReportMeta, write_report_json, write_report_pdf


@dataclass(frozen=True)
class SuiteRunConfig:
    """Configuration for running a predefined validation suite."""
    device_name: str
    out_dir: Path
    mode: str  # "fake" or "real" (suite currently supports fake only)
    iface: Optional[str]
    adapter: Optional[int]
    timeout_ms: int
    retries: int
    len_aff0: int
    len_f841: int
    min_aff0_bytes: int
    min_f841_ratio: float
    pdf: bool
    json: bool


DEFAULT_FAKE_SCENARIOS = [
    "ok",
    "f841_short",
    "f841_timeout",
    "random_latency",
]


def run_fake_suite(cfg: SuiteRunConfig, base_latency_ms: float, extra_latency_ms: float) -> dict:
    """
    Runs multiple fake scenarios and writes per-scenario JSON/PDF reports.

    Returns a summary dict that can be printed or saved.
    """
    cfg.out_dir.mkdir(parents=True, exist_ok=True)

    summary = {
        "device_name": cfg.device_name,
        "mode": cfg.mode,
        "out_dir": str(cfg.out_dir),
        "scenarios": [],
    }

    for scenario_name in DEFAULT_FAKE_SCENARIOS:
        client = FakePnioClient(
            FakeScenario(
                name=scenario_name,
                base_latency_ms=float(base_latency_ms),
                extra_latency_ms=float(extra_latency_ms),
            )
        )

        vcfg = ValidationConfig(
            device_name=cfg.device_name,
            slot=0,
            subslot=1,
            read_len_aff0=cfg.len_aff0,
            read_len_f841=cfg.len_f841,
            retries=cfg.retries,
            timeout_ms=cfg.timeout_ms,
            min_aff0_bytes=cfg.min_aff0_bytes,
            min_f841_ratio=cfg.min_f841_ratio,
        )

        result = HeidenhainStrictValidator(client=client, config=vcfg).run()

        meta = ReportMeta(
            generated_at=__import__("datetime").datetime.now().isoformat(timespec="seconds"),
            mode="fake",
            scenario=scenario_name,
            iface=cfg.iface,
            adapter=cfg.adapter,
            device_name=cfg.device_name,
            timeout_ms=cfg.timeout_ms,
            retries=cfg.retries,
            len_aff0=cfg.len_aff0,
            len_f841=cfg.len_f841,
            min_aff0_bytes=cfg.min_aff0_bytes,
            min_f841_ratio=cfg.min_f841_ratio,
        )

        base = cfg.out_dir / scenario_name

        json_path = base.with_suffix(".json")
        pdf_path = base.with_suffix(".pdf")

        if cfg.json:
            write_report_json(json_path, result, meta)

        if cfg.pdf:
            write_report_pdf(pdf_path, result, meta)

        summary["scenarios"].append(
            {
                "scenario": scenario_name,
                "ok": bool(result.ok),
                "json": str(json_path) if cfg.json else None,
                "pdf": str(pdf_path) if cfg.pdf else None,
            }
        )

    # Write summary file always (useful for CI artifacts and vendor sharing)
    summary_path = cfg.out_dir / "summary.json"
    import json as _json
    summary_path.write_text(_json.dumps(summary, indent=2), encoding="utf-8")
    summary["summary_json"] = str(summary_path)

    return summary