from __future__ import annotations

import json
from pathlib import Path

from .validator import ValidationResult


def write_report_json(path: str | Path, result: ValidationResult) -> None:
    p = Path(path)
    payload = result.to_dict()
    p.write_text(json.dumps(payload, indent=2), encoding="utf-8")