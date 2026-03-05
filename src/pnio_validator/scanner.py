from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional

from scapy.all import (
    Ether,
    Dot1Q,
    Raw,
    conf,
    get_if_list,
    sendp,
    get_if_hwaddr,
    AsyncSniffer,
)

PNIO_ETHERTYPE = 0x8892
DCP_MULTICAST_MAC = "01:0e:cf:00:00:00"


@dataclass(frozen=True)
class DiscoveredDevice:
    name: Optional[str]
    ip: Optional[str]
    mask: Optional[str]
    gateway: Optional[str]
    mac: str
    vendor_id: Optional[int] = None
    device_id: Optional[int] = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "ip": self.ip,
            "mask": self.mask,
            "gateway": self.gateway,
            "mac": self.mac,
            "vendor_id": self.vendor_id,
            "device_id": self.device_id,
        }

def _pick_iface(user_iface: str) -> str:
    """
    Scapy on Windows often uses NPF device names (\\Device\\NPF_{GUID}).
    Try exact match, then case-insensitive, then substring match.
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
    """Returns payload ethertype, handling VLAN-tagged frames (802.1Q)."""
    if not pkt.haslayer(Ether):
        return None

    et = pkt[Ether].type
    if et == 0x8100 and pkt.haslayer(Dot1Q):
        return pkt[Dot1Q].type
    return et


def _build_dcp_identify_request_like_proneta(src_mac: str) -> Ether:
    """
    FEFE Identify Request (copiado do request capturado do PRONETA).

    Hex capturado (após o EtherType 0x8892):
      fefe05000000031700c00004ffff0000
    """
    payload = bytes.fromhex("fefe05000000031700c00004ffff0000")

    pkt = Ether(dst=DCP_MULTICAST_MAC, src=src_mac, type=PNIO_ETHERTYPE) / Raw(payload)

    # Ethernet mínimo ~60 bytes (sem FCS). Alguns devices ignoram frame menor.
    b = bytes(pkt)
    if len(b) < 60:
        pkt = pkt / Raw(b"\x00" * (60 - len(b)))

    return pkt


def _parse_dcp_blocks(raw_bytes: bytes):
    name = None
    ip = None
    mask = None
    gateway = None
    vendor_id = None
    device_id = None

    def _ip4(b: bytes) -> str:
        return ".".join(str(x) for x in b)

    try:
        i = 12
        while i + 4 <= len(raw_bytes):
            opt = raw_bytes[i]
            sub = raw_bytes[i + 1]
            blen = int.from_bytes(raw_bytes[i + 2:i + 4], "big")

            data_start = i + 4
            data = raw_bytes[data_start:data_start + blen]

            # NameOfStation (opt=0x02 sub=0x02)
            if opt == 0x02 and sub == 0x02 and blen >= 2:
                cand = data[2:].split(b"\x00")[0].strip()
                if cand:
                    name = cand.decode("utf-8", errors="ignore")

            # IP Suite (opt=0x01 sub=0x02) -> IP(4) + Mask(4) + GW(4)
            # Normalmente vem com 2 bytes "BlockInfo" antes
            if opt == 0x01 and sub == 0x02 and blen >= 2 + 12:
                ip_bytes = data[2:6]
                mask_bytes = data[6:10]
                gw_bytes = data[10:14]
                ip = _ip4(ip_bytes)
                mask = _ip4(mask_bytes)
                gateway = _ip4(gw_bytes)

            # Alguns devices podem mandar em sub=0x03 (se você quiser manter):
            if opt == 0x01 and sub == 0x03 and blen >= 2 + 12 and ip is None:
                ip_bytes = data[2:6]
                mask_bytes = data[6:10]
                gw_bytes = data[10:14]
                ip = _ip4(ip_bytes)
                mask = _ip4(mask_bytes)
                gateway = _ip4(gw_bytes)

            # Vendor/Device heuristics
            if opt == 0x02 and sub in (0x03, 0x01) and blen >= 6:
                vendor_id = int.from_bytes(data[2:4], "big")
                device_id = int.from_bytes(data[4:6], "big")

            step = 4 + blen
            if step % 2 == 1:
                step += 1
            i += step
    except Exception:
        pass

    return name, ip, mask, gateway, vendor_id, device_id
def scan_dcp(iface: str, timeout_s: float = 5.0) -> List[DiscoveredDevice]:
    real_iface = _pick_iface(iface)

    conf.use_pcap = True
    conf.iface = real_iface
    conf.sniff_promisc = True  # ajuda no Windows/Npcap

    try:
        src_mac = get_if_hwaddr(real_iface)
        if not src_mac:
            raise RuntimeError("Empty MAC returned.")
    except Exception as e:
        raise RuntimeError(
            f"Could not get MAC for interface '{real_iface}'. "
            "Run PowerShell as Administrator and ensure Npcap is installed."
        ) from e

    req = _build_dcp_identify_request_like_proneta(src_mac=src_mac)

    devices: dict[str, DiscoveredDevice] = {}

    def _handle(pkt) -> None:
        # BPF já filtra 0x8892, mas mantém seguro
        if _ethertype(pkt) != PNIO_ETHERTYPE:
            return
        if not pkt.haslayer(Ether) or not pkt.haslayer(Raw):
            return

        eth = pkt[Ether]
        raw_bytes = bytes(pkt[Raw].load)

        # FEFF = Identify Response
        if len(raw_bytes) < 2:
            return
        frame_id = int.from_bytes(raw_bytes[0:2], "big")
        if frame_id != 0xFEFF:
            return

        name, ip, mask, gw, vid, did = _parse_dcp_blocks(raw_bytes)

        devices[eth.src.lower()] = DiscoveredDevice(
            name=name,
            ip=ip,
            mask=mask,
            gateway=gw,
            mac=eth.src,
            vendor_id=vid,
            device_id=did,
        )

    sniffer = AsyncSniffer(
        iface=real_iface,
        store=False,
        prn=_handle,
        filter="ether proto 0x8892",
        promisc=True,
    )

    # 1) começa sniff antes do send
    sniffer.start()

    # 2) manda vários requests (melhora muito em rede industrial)
    sendp(req, iface=real_iface, count=5, inter=0.2, verbose=False)

    # 3) espera até timeout, para e coleta
    sniffer.join(timeout=timeout_s)
    try:
        sniffer.stop()
    except Exception:
        pass

    return list(devices.values())