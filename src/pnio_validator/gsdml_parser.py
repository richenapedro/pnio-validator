from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
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
class GsdmlText:
    """Text resolved from ExternalTextList."""
    text_id: str
    value: str


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
    GSDML commonly uses <ExternalText TextId="..."><Text Value="..."/></ExternalText>
    """
    texts: Dict[str, str] = {}
    for ext in _find_all(root, "ExternalText"):
        text_id = ext.attrib.get("TextId") or ext.attrib.get("ID")
        if not text_id:
            continue

        # Typically: <ExternalText ...><Text Value="..."/></ExternalText>
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
    Namespace handling is done in a tolerant way (by stripping namespaces).
    """
    p = Path(path)
    tree = ET.parse(p)
    root = tree.getroot()

    texts = _parse_external_texts(root)

    # ProfileHeader (best-effort)
    profile_header: Dict[str, str] = {}
    ph = _find_first(root, "ProfileHeader")
    if ph is not None:
        for k in ["ProfileIdentification", "ProfileRevision", "ProfileName", "ProfileSource", "ProfileClassID"]:
            v = ph.attrib.get(k)
            if v:
                profile_header[k] = v

    # DeviceIdentity / DeviceFunction / DeviceInfo vary by vendor; best-effort fields
    device_identity: Dict[str, str] = {}
    dev = _find_first(root, "DeviceIdentity")
    if dev is not None:
        for k in ["VendorId", "DeviceId", "InfoText", "VendorName", "DeviceFamily", "ProductName"]:
            v = dev.attrib.get(k)
            if v:
                device_identity[k] = v

    # DAP: DeviceAccessPointItem
    dap_item = _find_first(root, "DeviceAccessPointItem")
    dap: Optional[GsdmlDap] = None
    if dap_item is not None:
        dap_id = dap_item.attrib.get("ID")
        dap_ident = _parse_int_maybe(dap_item.attrib.get("ModuleIdentNumber"))
        dap_name = _resolve_name(texts, dap_item.attrib.get("TextId"))
        dap = GsdmlDap(id=dap_id, module_ident_number=dap_ident, name=dap_name)

    # Modules/Submodules: ModuleItem / SubmoduleItem
    modules: List[GsdmlModule] = []
    for mi in _find_all(root, "ModuleItem"):
        mid = mi.attrib.get("ID")
        mident = _parse_int_maybe(mi.attrib.get("ModuleIdentNumber"))
        mname = _resolve_name(texts, mi.attrib.get("TextId"))

        submods: List[GsdmlSubmodule] = []
        # Many GSDMLs reference submodules via <UseableSubmodules> or <VirtualSubmoduleList>,
        # but for MVP we parse submodule definitions globally.
        # We'll also parse nested SubmoduleItem definitions if present under ModuleItem (some vendors do).
        for si in mi.iter():
            if _strip_ns(si.tag) != "SubmoduleItem":
                continue
            sid = si.attrib.get("ID")
            sident = _parse_int_maybe(si.attrib.get("SubmoduleIdentNumber"))
            sname = _resolve_name(texts, si.attrib.get("TextId"))
            submods.append(GsdmlSubmodule(id=sid, submodule_ident_number=sident, name=sname))

        modules.append(GsdmlModule(id=mid, module_ident_number=mident, name=mname, submodules=submods))

    # If ModuleItems list is empty, fallback to global SubmoduleItem list (still useful)
    if not modules:
        # Create a synthetic module to hold submodules
        submods: List[GsdmlSubmodule] = []
        for si in _find_all(root, "SubmoduleItem"):
            sid = si.attrib.get("ID")
            sident = _parse_int_maybe(si.attrib.get("SubmoduleIdentNumber"))
            sname = _resolve_name(texts, si.attrib.get("TextId"))
            submods.append(GsdmlSubmodule(id=sid, submodule_ident_number=sident, name=sname))
        if submods:
            modules.append(GsdmlModule(id="__GLOBAL__", module_ident_number=None, name="GlobalSubmodules", submodules=submods))

    return GsdmlModel(
        file_path=str(p),
        profile_header=profile_header,
        device_identity=device_identity,
        dap=dap,
        modules=modules,
        texts=texts,
    )