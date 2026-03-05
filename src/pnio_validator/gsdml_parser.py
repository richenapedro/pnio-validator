from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET


def _strip_ns(tag: str) -> str:
    """Strip XML namespace from tag name."""
    if "}" in tag:
        return tag.split("}", 1)[1]
    return tag


def _find_first(root: ET.Element, tag: str) -> Optional[ET.Element]:
    """Find first element with matching local tag name (namespace-agnostic)."""
    for el in root.iter():
        if _strip_ns(el.tag) == tag:
            return el
    return None


def _find_all(root: ET.Element, tag: str) -> List[ET.Element]:
    """Find all elements with matching local tag name (namespace-agnostic)."""
    out: List[ET.Element] = []
    for el in root.iter():
        if _strip_ns(el.tag) == tag:
            out.append(el)
    return out


@dataclass(frozen=True)
class GsdmlSubmodule:
    """Submodule definition extracted from GSDML."""
    id: Optional[str]
    submodule_ident_number: Optional[int]
    name: Optional[str]


@dataclass(frozen=True)
class GsdmlModule:
    """Module definition extracted from GSDML."""
    id: Optional[str]
    module_ident_number: Optional[int]
    name: Optional[str]
    submodules: List[GsdmlSubmodule]


@dataclass(frozen=True)
class GsdmlDap:
    """Device Access Point (DAP) info."""
    id: Optional[str]
    module_ident_number: Optional[int]
    name: Optional[str]


@dataclass(frozen=True)
class GsdmlModel:
    """High-level parsed representation of a GSDML file."""
    file_path: str
    profile_header: Dict[str, str]
    device_identity: Dict[str, str]
    dap: Optional[GsdmlDap]
    modules: List[GsdmlModule]
    texts: Dict[str, str]

    def to_dict(self) -> dict:
        return {
            "file_path": self.file_path,
            "profile_header": dict(self.profile_header),
            "device_identity": dict(self.device_identity),
            "dap": None
            if self.dap is None
            else {
                "id": self.dap.id,
                "module_ident_number": self.dap.module_ident_number,
                "name": self.dap.name,
            },
            "modules": [
                {
                    "id": m.id,
                    "module_ident_number": m.module_ident_number,
                    "name": m.name,
                    "submodules": [
                        {
                            "id": s.id,
                            "submodule_ident_number": s.submodule_ident_number,
                            "name": s.name,
                        }
                        for s in m.submodules
                    ],
                }
                for m in self.modules
            ],
            "texts": dict(self.texts),
        }

    def to_json(self, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, ensure_ascii=False)

    def save_json(self, path: str | Path) -> None:
        Path(path).write_text(self.to_json(), encoding="utf-8")


def _parse_int_maybe(s: Optional[str]) -> Optional[int]:
    """Parse decimal or hex int strings like '0x1234' or '4660'."""
    if not s:
        return None
    st = s.strip()
    try:
        if st.lower().startswith("0x"):
            return int(st, 16)
        return int(st, 10)
    except Exception:
        return None


def _parse_external_texts(root: ET.Element) -> Dict[str, str]:
    """
    Parse ExternalTextList into a dict: TextId -> Value.

    GSDML commonly uses:
      <ExternalText TextId="..."><Text Value="..."/></ExternalText>
    """
    texts: Dict[str, str] = {}
    for ext in _find_all(root, "ExternalText"):
        text_id = ext.attrib.get("TextId") or ext.attrib.get("ID")
        if not text_id:
            continue

        value = None
        for ch in list(ext):
            if _strip_ns(ch.tag) == "Text":
                value = ch.attrib.get("Value") or (ch.text or "").strip()
                break
        if value is None:
            value = (ext.text or "").strip() or ""

        texts[text_id] = value
    return texts


def _resolve_name(texts: Dict[str, str], text_id: Optional[str]) -> Optional[str]:
    if not text_id:
        return None
    return texts.get(text_id, text_id)


def parse_gsdml(path: str | Path) -> GsdmlModel:
    """
    Parse a GSDML file into a structured model.

    This parser is tolerant by design:
    - It strips namespaces and searches by local tag names.
    - It extracts DAP, ModuleItem, SubmoduleItem and resolves ExternalTextList.
    """
    p = Path(path)
    tree = ET.parse(p)
    root = tree.getroot()

    texts = _parse_external_texts(root)

    profile_header: Dict[str, str] = {}
    ph = _find_first(root, "ProfileHeader")
    if ph is not None:
        for k in ["ProfileIdentification", "ProfileRevision", "ProfileName", "ProfileSource", "ProfileClassID"]:
            v = ph.attrib.get(k)
            if v:
                profile_header[k] = v

    # ---------------- DeviceIdentity (robust) ----------------
    device_identity: Dict[str, str] = {}
    dev = _find_first(root, "DeviceIdentity")
    if dev is not None:
        # Some GSDMLs use VendorID/DeviceID (ID uppercase) instead of VendorId/DeviceId.
        def _get_attr(*names: str) -> Optional[str]:
            for n in names:
                v = dev.attrib.get(n)
                if v:
                    return v
            return None

        vendor = _get_attr("VendorId", "VendorID", "vendorId", "vendorID")
        device = _get_attr("DeviceId", "DeviceID", "deviceId", "deviceID")

        if vendor:
            device_identity["VendorId"] = vendor  # normalize key
        if device:
            device_identity["DeviceId"] = device  # normalize key

        # Other optional attributes (keep as-is)
        for k in ["InfoText", "VendorName", "DeviceFamily", "ProductName"]:
            v = dev.attrib.get(k)
            if v:
                device_identity[k] = v

        # Some vendors put these as nested elements with Value="..."
        # e.g. <VendorName Value="INVEOR"/> inside <DeviceIdentity>
        if "VendorName" not in device_identity:
            vn_el = _find_first(dev, "VendorName")
            if vn_el is not None:
                v = vn_el.attrib.get("Value") or (vn_el.text or "").strip()
                if v:
                    device_identity["VendorName"] = v

        if "ProductName" not in device_identity:
            pn_el = _find_first(dev, "ProductName")
            if pn_el is not None:
                v = pn_el.attrib.get("Value") or (pn_el.text or "").strip()
                if v:
                    device_identity["ProductName"] = v

    # ---------------- DAP ----------------
    dap_item = _find_first(root, "DeviceAccessPointItem")
    dap: Optional[GsdmlDap] = None
    if dap_item is not None:
        dap_id = dap_item.attrib.get("ID")
        dap_ident = _parse_int_maybe(dap_item.attrib.get("ModuleIdentNumber"))
        dap_name = _resolve_name(texts, dap_item.attrib.get("TextId"))
        dap = GsdmlDap(id=dap_id, module_ident_number=dap_ident, name=dap_name)

    # ---------------- Modules/Submodules ----------------
    modules: List[GsdmlModule] = []
    for mi in _find_all(root, "ModuleItem"):
        mid = mi.attrib.get("ID")
        mident = _parse_int_maybe(mi.attrib.get("ModuleIdentNumber"))
        mname = _resolve_name(texts, mi.attrib.get("TextId"))

        submods: List[GsdmlSubmodule] = []
        for si in mi.iter():
            if _strip_ns(si.tag) != "SubmoduleItem":
                continue
            sid = si.attrib.get("ID")
            sident = _parse_int_maybe(si.attrib.get("SubmoduleIdentNumber"))
            sname = _resolve_name(texts, si.attrib.get("TextId"))
            submods.append(GsdmlSubmodule(id=sid, submodule_ident_number=sident, name=sname))

        modules.append(GsdmlModule(id=mid, module_ident_number=mident, name=mname, submodules=submods))

    # Fallback: if there are no ModuleItem entries, still expose SubmoduleItem entries.
    if not modules:
        submods: List[GsdmlSubmodule] = []
        for si in _find_all(root, "SubmoduleItem"):
            sid = si.attrib.get("ID")
            sident = _parse_int_maybe(si.attrib.get("SubmoduleIdentNumber"))
            sname = _resolve_name(texts, si.attrib.get("TextId"))
            submods.append(GsdmlSubmodule(id=sid, submodule_ident_number=sident, name=sname))
        if submods:
            modules.append(
                GsdmlModule(
                    id="__GLOBAL__",
                    module_ident_number=None,
                    name="GlobalSubmodules",
                    submodules=submods,
                )
            )

    return GsdmlModel(
        file_path=str(p),
        profile_header=profile_header,
        device_identity=device_identity,
        dap=dap,
        modules=modules,
        texts=texts,
    )

def summarize_gsdml(model: GsdmlModel, max_modules: int = 200) -> str:
    """
    Create a human-readable summary of the parsed GSDML.

    Output is plain text so it is friendly for terminals, logs and CI.
    """
    lines: List[str] = []

    # Header
    ph = model.profile_header
    di = model.device_identity

    lines.append(f"File: {model.file_path}")
    if ph:
        lines.append(
            "ProfileHeader: "
            + ", ".join(f"{k}={v}" for k, v in ph.items())
        )
    if di:
        lines.append(
            "DeviceIdentity: "
            + ", ".join(f"{k}={v}" for k, v in di.items())
        )

    # DAP
    if model.dap is None:
        lines.append("DAP: <not found>")
    else:
        dap_ident = (
            f"0x{model.dap.module_ident_number:08X}"
            if model.dap.module_ident_number is not None
            else "-"
        )
        lines.append(f"DAP: {model.dap.name or '-'}  id={model.dap.id or '-'}  ident={dap_ident}")

    # Modules
    lines.append("")
    lines.append("Modules:")
    if not model.modules:
        lines.append("  <none>")
        return "\n".join(lines)

    count = 0
    for m in model.modules:
        count += 1
        if count > max_modules:
            lines.append(f"  ... truncated (max_modules={max_modules})")
            break

        m_ident = f"0x{m.module_ident_number:08X}" if m.module_ident_number is not None else "-"
        lines.append(f"  - {m.name or '-'}  id={m.id or '-'}  ident={m_ident}")

        if not m.submodules:
            lines.append("      (no submodules parsed)")
            continue

        for s in m.submodules[:200]:
            s_ident = f"0x{s.submodule_ident_number:08X}" if s.submodule_ident_number is not None else "-"
            lines.append(f"      * {s.name or '-'}  id={s.id or '-'}  ident={s_ident}")

        if len(m.submodules) > 200:
            lines.append(f"      ... truncated submodules ({len(m.submodules)} total)")

    return "\n".join(lines)


def export_expected_model(model: GsdmlModel) -> dict:
    """
    Export an 'expected model' in a compact format suitable for later comparisons
    against real device reads (RealIdentificationData / ModuleDiff-like checks).
    """
    expected = {
        "profile_header": dict(model.profile_header),
        "device_identity": dict(model.device_identity),
        "dap": None
        if model.dap is None
        else {
            "id": model.dap.id,
            "module_ident_number": model.dap.module_ident_number,
            "name": model.dap.name,
        },
        "modules": [],
    }

    for m in model.modules:
        expected["modules"].append(
            {
                "id": m.id,
                "module_ident_number": m.module_ident_number,
                "name": m.name,
                "submodules": [
                    {
                        "id": s.id,
                        "submodule_ident_number": s.submodule_ident_number,
                        "name": s.name,
                    }
                    for s in m.submodules
                ],
            }
        )

    return expected