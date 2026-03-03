from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from scapy.all import (
    Ether,
    Dot1Q,
    Raw,
    conf,
    get_if_list,
    sniff,
    sendp,
    get_if_hwaddr,
)

PNIO_ETHERTYPE = 0x8892
DCP_MULTICAST_MAC = "01:0e:cf:00:00:00"


@dataclass(frozen=True)
class DiscoveredDevice:
    name: Optional[str]
    ip: Optional[str]
    mac: str
    vendor_id: Optional[int] = None
    device_id: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "ip": self.ip,
            "mac": self.mac,
            "vendor_id": self.vendor_id,
            "device_id": self.device_id,
        }


def _pick_iface(user_iface: str) -> str:
    """
    Scapy on Windows often uses NPF device names (\\Device\\NPF_{GUID}).
    We try exact match, then case-insensitive, then substring match.
    """
    ifaces = get_if_list()
    if user_iface in ifaces:
        return user_iface

    low = user_iface.lower()
    for i in ifaces:
        if low == i.lower():
            return i
    for i in ifaces:
        if low in i.lower():
            return i

    return user_iface


def _ethertype(pkt) -> int | None:
    """
    Returns payload ethertype, handling VLAN-tagged frames (802.1Q).
    """
    if not pkt.haslayer(Ether):
        return None
    et = pkt.getlayer(Ether).type

    # VLAN tagged frame: Ether.type == 0x8100, actual ethertype in Dot1Q.type
    if et == 0x8100 and pkt.haslayer(Dot1Q):
        return pkt.getlayer(Dot1Q).type

    return et


def _build_dcp_identify_request(src_mac: str) -> Ether:
    """
    Minimal PROFINET DCP Identify request frame (Layer 2).

    NOTE:
    This is a pragmatic "works in many networks" frame.
    Later we can implement full DCP properly (including parsing header fields).
    """
    # DCP header (12 bytes):
    # FrameID (2) + ServiceID (1) + ServiceType (1) + XID (4) + ResponseDelay (2) + DataLength (2)
    frame_id = b"\xfe\xfe"          # DCP Identify
    service_id = b"\x05"            # Identify
    service_type = b"\x00"          # Request
    xid = b"\x12\x34\x56\x78"       # Transaction id (any)
    response_delay = b"\x00\x00"

    # DCP "All" block (Option=0xFF, Suboption=0xFF, BlockLength=0)
    block = b"\xff\xff\x00\x00"
    data_length = (len(block)).to_bytes(2, "big")

    payload = frame_id + service_id + service_type + xid + response_delay + data_length + block

    return Ether(dst=DCP_MULTICAST_MAC, src=src_mac, type=PNIO_ETHERTYPE) / Raw(load=payload)


def _parse_dcp_blocks(raw_bytes: bytes):
    """
    Best-effort DCP response parsing.

    Tries to extract:
    - NameOfStation (common: opt=0x02, sub=0x02)
    - IP (common: opt=0x01, sub=0x02 or 0x03)
    - Vendor/Device IDs (heuristic; not guaranteed)
    """
    name = None
    ip = None
    vendor_id = None
    device_id = None

    try:
        # Many DCP responses have 12 bytes header before the first block
        i = 12
        while i + 4 <= len(raw_bytes):
            opt = raw_bytes[i]
            sub = raw_bytes[i + 1]
            blen = int.from_bytes(raw_bytes[i + 2:i + 4], "big")

            data_start = i + 4
            data = raw_bytes[data_start:data_start + blen]

            # Device Properties / NameOfStation
            if opt == 0x02 and sub == 0x02 and blen >= 2:
                cand = data[2:]
                cand = cand.split(b"\x00")[0].strip()
                if cand:
                    name = cand.decode("utf-8", errors="ignore")

            # IP parameters block: 2 bytes BlockInfo + 4 bytes IP
            if opt == 0x01 and sub in (0x02, 0x03) and blen >= 6:
                ip_bytes = data[2:6]
                ip = ".".join(str(b) for b in ip_bytes)

            # Vendor/Device heuristics (not guaranteed; keep best-effort)
            if opt == 0x02 and sub in (0x03, 0x01) and blen >= 6:
                vendor_id = int.from_bytes(data[2:4], "big")
                device_id = int.from_bytes(data[4:6], "big")

            # Blocks are aligned to even length
            step = 4 + blen
            if step % 2 == 1:
                step += 1
            i += step
    except Exception:
        pass

    return name, ip, vendor_id, device_id


def scan_dcp(iface: str, timeout_s: float = 5.0) -> List[DiscoveredDevice]:
    """
    Sends a DCP Identify request and listens for responses.

    Windows notes:
    - Usually requires PowerShell as Administrator
    - Requires Npcap installed
    - Use \\Device\\NPF_{GUID} for iface when needed (Scapy style)
    """
    real_iface = _pick_iface(iface)
    conf.iface = real_iface

    # Get MAC of the selected adapter (portable across PCs)
    try:
        src_mac = get_if_hwaddr(real_iface)
        if not src_mac:
            raise RuntimeError("Empty MAC returned.")
    except Exception as e:
        raise RuntimeError(
            f"Could not get MAC for interface '{real_iface}'. "
            "Run PowerShell as Administrator and ensure Npcap is installed."
        ) from e

    req = _build_dcp_identify_request(src_mac=src_mac)

    devices: dict[str, DiscoveredDevice] = {}

    def _handle(pkt) -> None:
        if _ethertype(pkt) != PNIO_ETHERTYPE:
            return

        eth = pkt.getlayer(Ether)
        raw = bytes(pkt[Raw].load) if Raw in pkt else b""
        name, ip, vid, did = _parse_dcp_blocks(raw)

        devices[eth.src.lower()] = DiscoveredDevice(
            name=name,
            ip=ip,
            mac=eth.src,
            vendor_id=vid,
            device_id=did,
        )

    # Send Identify first, then sniff for responses (simple + reliable)
    sendp(req, iface=real_iface, verbose=False)

    sniff(
        iface=real_iface,
        timeout=timeout_s,
        store=False,
        prn=_handle,
        lfilter=lambda p: _ethertype(p) == PNIO_ETHERTYPE,
    )

    return list(devices.values())