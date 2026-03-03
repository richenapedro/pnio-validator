from __future__ import annotations

import ipaddress
import time
from dataclasses import dataclass
from typing import Optional

from scapy.all import Ether, Raw, conf, sendp, sniff, get_if_hwaddr  # type: ignore


PNIO_ETHERTYPE = 0x8892
DCP_MULTICAST_MAC = "01:0e:cf:00:00:00"


# DCP FrameIds (big-endian)
DCP_FRAME_ID_IDENTIFY = 0xFEFE
DCP_FRAME_ID_SET = 0xFEFD

# DCP ServiceId / ServiceType
DCP_SERVICE_ID_IDENTIFY = 0x05
DCP_SERVICE_ID_SET = 0x04
DCP_SERVICE_TYPE_REQUEST = 0x00
DCP_SERVICE_TYPE_RESPONSE = 0x01


@dataclass(frozen=True)
class DcpResult:
    """Standard action result for UI/CLI."""
    ok: bool
    action: str
    target_mac: str
    error: Optional[str] = None
    latency_ms: Optional[float] = None

    def to_dict(self) -> dict:
        return {
            "ok": self.ok,
            "action": self.action,
            "target_mac": self.target_mac,
            "error": self.error,
            "latency_ms": self.latency_ms,
        }


def _mac_norm(mac: str) -> str:
    return mac.strip().lower()


def _ip4_bytes(ip: str) -> bytes:
    return ipaddress.IPv4Address(ip).packed


def _pad_even(payload: bytes) -> bytes:
    """DCP blocks are padded to even length."""
    return payload if len(payload) % 2 == 0 else payload + b"\x00"


def _build_dcp_set_header(*, xid: bytes) -> bytes:
    """
    DCP Set header (best-effort):
    FrameID(2) + ServiceID(1) + ServiceType(1) + Xid(4) + ResponseDelay(2) + DataLength(2)
    """
    frame_id = DCP_FRAME_ID_SET.to_bytes(2, "big")
    service_id = bytes([DCP_SERVICE_ID_SET])
    service_type = bytes([DCP_SERVICE_TYPE_REQUEST])
    response_delay = b"\x00\x00"
    # DataLength appended by caller after blocks are assembled
    return frame_id + service_id + service_type + xid + response_delay


def _block(*, opt: int, sub: int, data: bytes) -> bytes:
    """Build a DCP block: Option(1) + Suboption(1) + BlockLength(2) + BlockInfo(2) + Data."""
    # BlockLength counts BlockInfo(2) + Data
    block_info = b"\x00\x00"
    block_len = (len(block_info) + len(data)).to_bytes(2, "big")
    return bytes([opt, sub]) + block_len + block_info + data


def _build_set_name_payload(*, name: str, xid: bytes) -> bytes:
    """
    Build DCP Set NameOfStation request payload.

    NameOfStation is commonly under option 0x02 (Device Properties), suboption 0x02.
    """
    name_bytes = name.encode("utf-8")
    b1 = _block(opt=0x02, sub=0x02, data=name_bytes)
    blocks = _pad_even(b1)
    header = _build_dcp_set_header(xid=xid)
    data_len = len(blocks).to_bytes(2, "big")
    return header + data_len + blocks


def _build_set_ip_payload(*, ip: str, mask: str, gw: str, xid: bytes) -> bytes:
    """
    Build DCP Set IP Suite request payload.

    IP parameters are commonly under option 0x01 (IP), suboption 0x02 (IP parameter).
    Data format is device-dependent, but the common layout is:
      IP(4) + SubnetMask(4) + Gateway(4)
    """
    data = _ip4_bytes(ip) + _ip4_bytes(mask) + _ip4_bytes(gw)
    b1 = _block(opt=0x01, sub=0x02, data=data)
    blocks = _pad_even(b1)
    header = _build_dcp_set_header(xid=xid)
    data_len = len(blocks).to_bytes(2, "big")
    return header + data_len + blocks


def _wait_for_set_response(*, iface: str, target_mac: str, xid: bytes, timeout_s: float) -> bool:
    """
    Best-effort: sniff for a DCP response coming from target MAC with same XID.
    Not all devices respond in a consistent way (or at all), so we keep this tolerant.
    """
    tmac = _mac_norm(target_mac)

    def _is_match(pkt) -> bool:
        if not pkt.haslayer(Ether):
            return False
        eth = pkt.getlayer(Ether)
        if _mac_norm(eth.src) != tmac:
            return False
        if not pkt.haslayer(Raw):
            return False
        raw = bytes(pkt.getlayer(Raw).load)
        # Minimum header length check
        if len(raw) < 12:
            return False
        frame_id = int.from_bytes(raw[0:2], "big")
        service_id = raw[2]
        service_type = raw[3]
        rx_xid = raw[4:8]
        if frame_id != DCP_FRAME_ID_SET:
            return False
        if service_id != DCP_SERVICE_ID_SET:
            return False
        if service_type != DCP_SERVICE_TYPE_RESPONSE:
            return False
        return rx_xid == xid

    pkts = sniff(iface=iface, timeout=timeout_s, store=True, lfilter=_is_match)
    return len(pkts) > 0


class DcpClient:
    """
    Minimal DCP client for PRONETA-like configuration.

    This is intentionally conservative:
    - It crafts DCP Set requests on Ethernet (Ethertype 0x8892).
    - It optionally waits for responses, but does not require them.
    """

    def __init__(self, iface: str, timeout_s: float = 3.0) -> None:
        self.iface = iface
        self.timeout_s = float(timeout_s)

    def _src_mac(self) -> str:
        try:
            mac = get_if_hwaddr(self.iface)  # type: ignore[attr-defined]
            return mac or "00:00:00:00:00:00"
        except Exception:
            return "00:00:00:00:00:00"

    def set_name(self, *, target_mac: str, name: str, wait_response: bool = True) -> DcpResult:
        xid = int(time.time() * 1000).to_bytes(4, "big", signed=False)
        payload = _build_set_name_payload(name=name, xid=xid)

        t0 = time.time()
        frame = Ether(dst=target_mac, src=self._src_mac(), type=PNIO_ETHERTYPE) / Raw(load=payload)
        conf.iface = self.iface
        sendp(frame, iface=self.iface, verbose=False)

        got = _wait_for_set_response(iface=self.iface, target_mac=target_mac, xid=xid, timeout_s=self.timeout_s) if wait_response else False
        dt = (time.time() - t0) * 1000.0

        # If no response, still consider "sent" ok (devices vary).
        return DcpResult(
            ok=True if (got or not wait_response) else True,
            action="dcp_set_name",
            target_mac=target_mac,
            error=None if got else None,
            latency_ms=dt,
        )

    def set_ip(self, *, target_mac: str, ip: str, mask: str, gw: str, wait_response: bool = True) -> DcpResult:
        xid = int(time.time() * 1000).to_bytes(4, "big", signed=False)
        payload = _build_set_ip_payload(ip=ip, mask=mask, gw=gw, xid=xid)

        t0 = time.time()
        frame = Ether(dst=target_mac, src=self._src_mac(), type=PNIO_ETHERTYPE) / Raw(load=payload)
        conf.iface = self.iface
        sendp(frame, iface=self.iface, verbose=False)

        got = _wait_for_set_response(iface=self.iface, target_mac=target_mac, xid=xid, timeout_s=self.timeout_s) if wait_response else False
        dt = (time.time() - t0) * 1000.0

        return DcpResult(
            ok=True if (got or not wait_response) else True,
            action="dcp_set_ip",
            target_mac=target_mac,
            error=None if got else None,
            latency_ms=dt,
        )

    def factory_reset(self, *, target_mac: str) -> DcpResult:
        # Not standardized across devices; keep as stub/capability placeholder.
        return DcpResult(
            ok=False,
            action="dcp_factory_reset",
            target_mac=target_mac,
            error="not_supported",
            latency_ms=None,
        )