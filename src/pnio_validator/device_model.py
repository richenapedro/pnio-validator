from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


@dataclass(slots=True)
class DeviceModel:
    """Unified device representation for GUI/backend."""
    name: str
    ip: Optional[str] = None
    mac: Optional[str] = None
    vendor_id: Optional[int] = None
    device_id: Optional[int] = None

    gsd_match: Optional[Dict[str, Any]] = None
    gsd_match_reason: Optional[str] = ""
    gsd_match_score: Optional[float] = None

    # Optional: full parsed/selected GSD entry (future GUI usage)
    gsd: Optional[Dict[str, Any]] = None

    capabilities: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        # NOTE: Keep keys stable for CLI/GUI consumers.
        return {
            "name": self.name,
            "ip": self.ip,
            "mac": self.mac,
            "vendor_id": self.vendor_id,
            "device_id": self.device_id,

            # Match output (expected by CLI scan --match-gsd)
            "gsd_match": self.gsd_match,
            "gsd_match_reason": self.gsd_match_reason,
            "gsd_match_score": self.gsd_match_score,

            # Optional: full parsed/selected gsd entry (if you want later)
            #"gsd": self.gsd,

            "capabilities": self.capabilities,
        }

    @staticmethod
    def default_capabilities() -> Dict[str, Any]:
        return {
            "supports": {
                "dcp_set_name": True,
                "dcp_set_ip": True,
                "dcp_blink": "best_effort",
                "factory_reset": "placeholder",
            }
        }
