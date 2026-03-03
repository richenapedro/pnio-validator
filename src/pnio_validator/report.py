from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet

from .validator import ValidationResult


@dataclass(frozen=True)
class ReportMeta:
    """Extra metadata to make reports self-contained and vendor-friendly."""
    generated_at: str
    mode: str  # "fake" or "real"
    scenario: Optional[str]
    iface: Optional[str]
    adapter: Optional[int]
    device_name: str
    timeout_ms: int
    retries: int
    len_aff0: int
    len_f841: int
    min_aff0_bytes: int
    min_f841_ratio: float


def build_report_payload(result: ValidationResult, meta: ReportMeta) -> Dict[str, Any]:
    return {
        "meta": asdict(meta),
        "result": result.to_dict(),
    }


def write_report_json(path: str | Path, result: ValidationResult, meta: ReportMeta) -> None:
    p = Path(path)
    payload = build_report_payload(result, meta)
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def write_report_pdf(path: str | Path, result: ValidationResult, meta: ReportMeta) -> None:
    p = Path(path)

    styles = getSampleStyleSheet()
    title = styles["Heading1"]
    h2 = styles["Heading2"]
    normal = styles["Normal"]

    doc = SimpleDocTemplate(
        str(p),
        pagesize=A4,
        rightMargin=30,
        leftMargin=30,
        topMargin=30,
        bottomMargin=30,
    )

    elements = []
    elements.append(Paragraph("PNIO Validator Report", title))
    elements.append(Spacer(1, 8))

    # Metadata block
    elements.append(Paragraph(f"Generated: {meta.generated_at}", normal))
    elements.append(Paragraph(f"Mode: {meta.mode}" + (f" (scenario: {meta.scenario})" if meta.scenario else ""), normal))
    elements.append(Paragraph(f"Device Name: {meta.device_name}", normal))
    if meta.iface:
        elements.append(Paragraph(f"Interface: {meta.iface}", normal))
    if meta.adapter is not None:
        elements.append(Paragraph(f"Adapter Index: {meta.adapter}", normal))
    elements.append(Paragraph(f"Timeout: {meta.timeout_ms} ms | Retries: {meta.retries}", normal))
    elements.append(Paragraph(f"Thresholds: AFF0 >= {meta.min_aff0_bytes} bytes | F841 >= {meta.min_f841_ratio:.2f}x requested", normal))
    elements.append(Spacer(1, 10))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.grey))
    elements.append(Spacer(1, 12))

    # Table rows
    def row(label: str, rr: dict, requested: int, min_expected: str) -> list:
        status = "PASS" if rr.get("ok") else "FAIL"
        return [
            label,
            str(requested),
            min_expected,
            str(rr.get("bytes_len", 0)),
            f'{rr.get("latency_ms", 0.0):.1f}',
            status,
            rr.get("error") or "",
        ]

    r = result.to_dict()
    aff0 = r["records"]["0xAFF0"]
    f841 = r["records"]["0xF841"]

    data = [
        ["Record", "Requested", "Min Expected", "Received", "Latency (ms)", "Status", "Error"],
        row(
            "0xAFF0",
            aff0,
            meta.len_aff0,
            f">= {meta.min_aff0_bytes}",
        ),
        row(
            "0xF841",
            f841,
            meta.len_f841,
            f">= {int(meta.len_f841 * meta.min_f841_ratio)} ({meta.min_f841_ratio:.2f}x)",
        ),
    ]

    table = Table(data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ALIGN", (1, 1), (4, -1), "CENTER"),
                ("ALIGN", (5, 1), (5, -1), "CENTER"),
            ]
        )
    )

    elements.append(table)
    elements.append(Spacer(1, 16))
    elements.append(Paragraph(f"Overall Result: {'PASS' if result.ok else 'FAIL'}", h2))

    doc.build(elements)