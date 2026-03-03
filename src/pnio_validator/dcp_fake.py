from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from .dcp import DcpResult


@dataclass
class FakeDcpState:
    """In-memory state used to simulate DCP configuration."""
    ip: str = "0.0.0.0"
    mask: str = "0.0.0.0"
    gw: str = "0.0.0.0"
    name: str = "unnamed"


class FakeDcpClient:
    """Fake DCP client for tests and offline development."""

    def __init__(self) -> None:
        self.devices: Dict[str, FakeDcpState] = {}

    def _get(self, mac: str) -> FakeDcpState:
        mac_l = mac.strip().lower()
        if mac_l not in self.devices:
            self.devices[mac_l] = FakeDcpState()
        return self.devices[mac_l]

    def set_name(self, *, target_mac: str, name: str, wait_response: bool = True) -> DcpResult:
        st = self._get(target_mac)
        st.name = name
        return DcpResult(ok=True, action="dcp_set_name", target_mac=target_mac, error=None, latency_ms=1.0)

    def set_ip(self, *, target_mac: str, ip: str, mask: str, gw: str, wait_response: bool = True) -> DcpResult:
        st = self._get(target_mac)
        st.ip = ip
        st.mask = mask
        st.gw = gw
        return DcpResult(ok=True, action="dcp_set_ip", target_mac=target_mac, error=None, latency_ms=1.0)

    def factory_reset(self, *, target_mac: str) -> DcpResult:
        st = self._get(target_mac)
        st.ip = "0.0.0.0"
        st.mask = "0.0.0.0"
        st.gw = "0.0.0.0"
        st.name = "unnamed"
        return DcpResult(ok=True, action="dcp_factory_reset", target_mac=target_mac, error=None, latency_ms=1.0)