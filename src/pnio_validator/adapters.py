from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional
import json
import platform
import subprocess

from scapy.all import get_if_list


@dataclass(frozen=True)
class AdapterInfo:
    """
    Represents a capture-capable network adapter entry similar to what Wireshark exposes.

    On Windows, we map Get-NetAdapter InterfaceGuid -> Scapy/Npcap device name:
        \\Device\\NPF_{GUID}
    """
    index: int
    friendly_name: str
    mac: Optional[str]
    guid: Optional[str]
    scapy_iface: str
    status: Optional[str] = None

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "friendly_name": self.friendly_name,
            "mac": self.mac,
            "guid": self.guid,
            "scapy_iface": self.scapy_iface,
            "status": self.status,
        }


def _normalize_guid(guid: str) -> str:
    g = guid.strip()
    if g.startswith("{") and g.endswith("}"):
        g = g[1:-1]
    return g.upper()


def _windows_get_netadapters() -> list[dict]:
    """
    Returns Windows adapter list using PowerShell Get-NetAdapter in JSON form.
    """
    ps = (
        "Get-NetAdapter | "
        "Select-Object Name, MacAddress, InterfaceGuid, Status | "
        "ConvertTo-Json -Depth 2"
    )
    proc = subprocess.run(
        ["powershell", "-NoProfile", "-Command", ps],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"Get-NetAdapter failed: {proc.stderr.strip() or proc.stdout.strip()}")

    data = json.loads(proc.stdout)

    # ConvertTo-Json returns either an object or a list depending on count
    if isinstance(data, dict):
        return [data]
    if isinstance(data, list):
        return data
    return []


def list_adapters() -> List[AdapterInfo]:
    """
    Lists adapters in a user-friendly way:
    - Windows: uses Get-NetAdapter to show friendly name + MAC + GUID, mapped to \\Device\\NPF_{GUID}
    - Non-Windows: falls back to Scapy get_if_list() only
    """
    scapy_ifaces = set(get_if_list())
    items: List[AdapterInfo] = []

    if platform.system().lower() == "windows":
        netadapters = _windows_get_netadapters()
        idx = 0
        for a in netadapters:
            name = (a.get("Name") or "").strip() or "<unknown>"
            mac = (a.get("MacAddress") or None)
            guid_raw = (a.get("InterfaceGuid") or None)
            status = (a.get("Status") or None)

            if guid_raw:
                guid = _normalize_guid(str(guid_raw))
                scapy_iface = f"\\Device\\NPF_{{{guid}}}"
            else:
                guid = None
                scapy_iface = name  # fallback

            # Prefer only those that Scapy/Npcap can actually see
            if scapy_iface in scapy_ifaces:
                items.append(
                    AdapterInfo(
                        index=idx,
                        friendly_name=name,
                        mac=mac,
                        guid=guid,
                        scapy_iface=scapy_iface,
                        status=status,
                    )
                )
                idx += 1

        # If mapping yields nothing (rare), fall back to showing Scapy list
        if not items:
            for i, iface in enumerate(sorted(scapy_ifaces)):
                items.append(
                    AdapterInfo(
                        index=i,
                        friendly_name=iface,
                        mac=None,
                        guid=None,
                        scapy_iface=iface,
                        status=None,
                    )
                )
        return items

    # Non-Windows fallback
    for i, iface in enumerate(sorted(scapy_ifaces)):
        items.append(
            AdapterInfo(
                index=i,
                friendly_name=iface,
                mac=None,
                guid=None,
                scapy_iface=iface,
                status=None,
            )
        )
    return items


def resolve_iface(iface: Optional[str], adapter_index: Optional[int]) -> str:
    """
    Resolves which Scapy interface to use.

    Priority:
    1) Explicit --iface
    2) --adapter <index> mapped via list_adapters()
    """
    if iface:
        return iface

    if adapter_index is None:
        raise ValueError("Either --iface or --adapter must be provided.")

    adapters = list_adapters()
    for a in adapters:
        if a.index == adapter_index:
            return a.scapy_iface

    raise ValueError(f"Adapter index {adapter_index} not found. Run: pnio-validator adapters")