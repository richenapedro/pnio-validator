from __future__ import annotations

import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from .gsdml_parser import parse_gsdml


DEFAULT_DATA_DIR = Path("data")
DEFAULT_GSD_DIR = DEFAULT_DATA_DIR / "gsdml"
DEFAULT_REGISTRY_PATH = DEFAULT_DATA_DIR / "gsd_registry.json"


def _norm_hex(s: str) -> str:
    """Normalize vendor/device id strings like '0x1234' / '1234' to lowercase '0x1234'."""
    st = (s or "").strip().lower()
    if not st:
        return ""
    if st.startswith("0x"):
        try:
            return f"0x{int(st, 16):x}"
        except Exception:
            return st
    try:
        return f"0x{int(st, 10):x}"
    except Exception:
        return st


def _as_list(v):
    if v is None:
        return []
    if isinstance(v, list):
        return v
    return [v]


@dataclass(frozen=True)
class GsdEntry:
    """One imported GSDML entry in the local registry."""
    file: str
    vendor_id: str
    device_id: str
    product_name: str

    def key(self) -> str:
        return f"{self.vendor_id}:{self.device_id}".lower()

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "vendor_id": self.vendor_id,
            "device_id": self.device_id,
            "product_name": self.product_name,
        }

    @staticmethod
    def from_dict(d: dict) -> "GsdEntry":
        return GsdEntry(
            file=str(d.get("file", "")),
            vendor_id=str(d.get("vendor_id", "")),
            device_id=str(d.get("device_id", "")),
            product_name=str(d.get("product_name", "")),
        )


# Registry format v2: Dict[key -> List[GsdEntry]]
Registry = Dict[str, List[GsdEntry]]


def load_registry(path: Path = DEFAULT_REGISTRY_PATH) -> Registry:
    """Load registry file into dict keyed by 'vendor:device'."""
    if not path.exists():
        return {}

    raw = json.loads(path.read_text(encoding="utf-8"))
    out: Registry = {}

    # Backward compat:
    # - v1 stored Dict[key -> entry dict]
    # - v2 stores Dict[key -> [entry dict, ...]]
    for k, v in raw.items():
        key = str(k).lower()
        items = []
        for it in _as_list(v):
            if isinstance(it, dict):
                items.append(GsdEntry.from_dict(it))
        if items:
            out[key] = items

    return out


def save_registry(reg: Registry, path: Path = DEFAULT_REGISTRY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        k: [e.to_dict() for e in v]
        for k, v in sorted(reg.items(), key=lambda kv: kv[0])
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def import_gsdml(
    file_path: str | Path,
    gsd_dir: Path = DEFAULT_GSD_DIR,
    registry_path: Path = DEFAULT_REGISTRY_PATH,
) -> GsdEntry:
    """
    Import a GSDML file into data/gsdml and register it by VendorId+DeviceId.

    Matching is based on GSDML DeviceIdentity VendorId/DeviceId.
    Supports multiple entries per (vendor_id, device_id).
    """
    src = Path(file_path)
    if not src.exists():
        raise FileNotFoundError(str(src))

    model = parse_gsdml(src)

    vendor_id = _norm_hex(model.device_identity.get("VendorId", ""))
    device_id = _norm_hex(model.device_identity.get("DeviceId", ""))

    product_name = (
        model.device_identity.get("ProductName")
        or model.device_identity.get("VendorName")
        or ""
    )

    if not vendor_id or not device_id:
        raise ValueError("GSDML DeviceIdentity VendorId/DeviceId not found; cannot register.")

    gsd_dir.mkdir(parents=True, exist_ok=True)
    dst = gsd_dir / src.name
    shutil.copy2(src, dst)

    entry = GsdEntry(
        file=str(dst.as_posix()),
        vendor_id=vendor_id,
        device_id=device_id,
        product_name=product_name,
    )

    reg = load_registry(registry_path)
    key = entry.key()
    reg.setdefault(key, [])

    # Avoid duplicates by file path (same copied name)
    if not any(e.file == entry.file for e in reg[key]):
        reg[key].append(entry)

    save_registry(reg, registry_path)
    return entry


def list_registry(registry_path: Path = DEFAULT_REGISTRY_PATH) -> List[GsdEntry]:
    reg = load_registry(registry_path)
    out: List[GsdEntry] = []
    for lst in reg.values():
        out.extend(lst)
    return out


def match_device_to_gsd(
    *,
    vendor_id: Optional[int],
    device_id: Optional[int],
    name: Optional[str],
    registry_path: Path = DEFAULT_REGISTRY_PATH,
) -> Tuple[Optional[GsdEntry], str, float]:
    """
    Try to match a scanned device to an imported GSD.

    Returns (entry, reason, score)
    score: 1.0 = exact vendor+device match (best candidate), 0.6 = product/name heuristic match, 0.0 = no match

    NOTE:
    - If multiple candidates exist for the same vendor+device, we return the first deterministically (sorted by file name).
    - Later we will upgrade this to choose by GSD version.
    """
    reg = load_registry(registry_path)

    if vendor_id is not None and device_id is not None:
        key = f"0x{vendor_id:x}:0x{device_id:x}".lower()
        if key in reg and reg[key]:
            # deterministic pick for now
            best = sorted(reg[key], key=lambda e: e.file.lower())[0]
            return best, "vendor_id+device_id", 1.0

    # Weak heuristic: match by product_name containing device name (or vice-versa)
    n = (name or "").strip().lower()
    if n:
        best: Tuple[Optional[GsdEntry], str, float] = (None, "no_match", 0.0)
        for entries in reg.values():
            for e in entries:
                pn = (e.product_name or "").strip().lower()
                if not pn:
                    continue
                if n in pn or pn in n:
                    return e, "name≈product_name", 0.6
                if len(n) >= 4 and (n[:4] in pn or pn[:4] in n):
                    best = (e, "name~product_name_weak", 0.3)
        return best

    return None, "no_match", 0.0