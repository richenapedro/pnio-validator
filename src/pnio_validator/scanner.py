from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional


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


def scan_dcp(iface: str, timeout_s: float = 5.0) -> List[DiscoveredDevice]:
    """
    DCP Discovery scan (placeholder).

    Implementação real:
    - Enviar Identify/Hello (DCP)
    - Coletar NameOfStation, IP, MAC, VendorID/DeviceID
    """
    _ = (iface, timeout_s)

    # TODO: implementar DCP de verdade.
    # Retorna vazio por enquanto para evitar "dados fake".
    return []