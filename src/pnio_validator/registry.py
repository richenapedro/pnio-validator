from __future__ import annotations

import json
import re
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


def _parse_int_loose(s: str) -> int:
    try:
        return int(str(s).strip())
    except Exception:
        return 0


def _extract_version_tuple(file_name: str, profile_header: dict) -> Tuple[int, int, int, int]:
    """
    Build a sortable version tuple for a GSDML:
      (gsdml_major, gsdml_minor, profile_revision, date_code)

    Priority:
    1) filename pattern like GSDML-V2.46-...
    2) ProfileHeader.ProfileRevision
    3) trailing date in filename, e.g. -20240115.xml
    """
    name = Path(file_name).name

    gsdml_major = 0
    gsdml_minor = 0
    profile_revision = _parse_int_loose(profile_header.get("ProfileRevision", "0"))
    date_code = 0

    m = re.search(r"GSDML-V(\d+)\.(\d+)", name, re.IGNORECASE)
    if m:
        gsdml_major = int(m.group(1))
        gsdml_minor = int(m.group(2))

    d = re.search(r"-(\d{8})(?:\.[^.]+)?$", name)
    if d:
        date_code = int(d.group(1))

    return (gsdml_major, gsdml_minor, profile_revision, date_code)


@dataclass(frozen=True)
class GsdEntry:
    """One imported GSDML entry in the local registry."""
    file: str
    vendor_id: str
    device_id: str
    product_name: str
    version_key: Tuple[int, int, int, int] = (0, 0, 0, 0)

    def key(self) -> str:
        return f"{self.vendor_id}:{self.device_id}".lower()

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "vendor_id": self.vendor_id,
            "device_id": self.device_id,
            "product_name": self.product_name,
            "version_key": list(self.version_key),
        }

    @staticmethod
    def from_dict(d: dict) -> "GsdEntry":
        raw_vk = d.get("version_key", [0, 0, 0, 0])
        if not isinstance(raw_vk, (list, tuple)):
            raw_vk = [0, 0, 0, 0]
        vk = tuple(int(x) for x in list(raw_vk)[:4])
        if len(vk) < 4:
            vk = tuple(list(vk) + [0] * (4 - len(vk)))

        return GsdEntry(
            file=str(d.get("file", "")),
            vendor_id=str(d.get("vendor_id", "")),
            device_id=str(d.get("device_id", "")),
            product_name=str(d.get("product_name", "")),
            version_key=vk,
        )


Registry = Dict[str, List[GsdEntry]]


def load_registry(path: Path = DEFAULT_REGISTRY_PATH) -> Registry:
    """Load registry file into dict keyed by 'vendor:device'."""
    if not path.exists():
        return {}

    raw = json.loads(path.read_text(encoding="utf-8"))
    out: Registry = {}

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

    version_key = _extract_version_tuple(src.name, model.profile_header)

    entry = GsdEntry(
        file=str(dst.as_posix()),
        vendor_id=vendor_id,
        device_id=device_id,
        product_name=product_name,
        version_key=version_key,
    )

    reg = load_registry(registry_path)
    key = entry.key()
    reg.setdefault(key, [])

    # Avoid duplicates by file path
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


def _pick_best(entries: List[GsdEntry]) -> Optional[GsdEntry]:
    if not entries:
        return None
    return sorted(
        entries,
        key=lambda e: (
            e.version_key[0],
            e.version_key[1],
            e.version_key[2],
            e.version_key[3],
            e.file.lower(),
        ),
        reverse=True,
    )[0]


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
    score: 1.0 = exact vendor+device match, 0.6 = product/name heuristic match, 0.0 = no match
    """
    reg = load_registry(registry_path)

    if vendor_id is not None and device_id is not None:
        key = f"0x{vendor_id:x}:0x{device_id:x}".lower()
        if key in reg and reg[key]:
            best = _pick_best(reg[key])
            return best, "vendor_id+device_id+latest_version", 1.0

    n = (name or "").strip().lower()
    if n:
        best: Tuple[Optional[GsdEntry], str, float] = (None, "no_match", 0.0)
        weak_candidates: List[GsdEntry] = []

        for entries in reg.values():
            for e in entries:
                pn = (e.product_name or "").strip().lower()
                if not pn:
                    continue
                if n in pn or pn in n:
                    return e, "name≈product_name", 0.6
                if len(n) >= 4 and (n[:4] in pn or pn[:4] in n):
                    weak_candidates.append(e)

        if weak_candidates:
            return _pick_best(weak_candidates), "name~product_name_weak", 0.3

        return best

    return None, "no_match", 0.0