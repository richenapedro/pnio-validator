from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import xml.etree.ElementTree as ET


@dataclass(frozen=True)
class GsdmlInfo:
    file: str
    profile_version: Optional[str]
    vendor_name: Optional[str]
    device_name: Optional[str]

    def to_dict(self) -> dict:
        return {
            "file": self.file,
            "profile_version": self.profile_version,
            "vendor_name": self.vendor_name,
            "device_name": self.device_name,
        }


def parse_gsdml(path: str | Path) -> GsdmlInfo:
    """
    Parser mínimo (WIP).
    Futuro: extrair DAP, módulos/submódulos, APIs, IOData, RecordDataList etc.
    """
    p = Path(path)
    tree = ET.parse(p)
    root = tree.getroot()

    # Heurísticas simples (namespaces variam)
    profile_version = root.attrib.get("ProfileRevision") or root.attrib.get("ProfileVersion")

    vendor_name = None
    device_name = None

    # Busca bruta por tags comuns
    for el in root.iter():
        tag = el.tag.split("}")[-1]  # remove namespace
        if tag == "VendorName" and (el.text or "").strip():
            vendor_name = (el.text or "").strip()
        if tag in ("DeviceName", "InfoText") and (el.text or "").strip() and device_name is None:
            device_name = (el.text or "").strip()

    return GsdmlInfo(
        file=str(p.name),
        profile_version=profile_version,
        vendor_name=vendor_name,
        device_name=device_name,
    )