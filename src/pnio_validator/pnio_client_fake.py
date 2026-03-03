from __future__ import annotations

import time
from dataclasses import dataclass

from .models import ReadRequest, ReadResult
from .pnio_client import PnioTimeout, PnioError


IDX_AFF0 = 0xAFF0
IDX_F841 = 0xF841


@dataclass(frozen=True)
class FakeScenario:
    """
    Defines fake behaviors to simulate real PNIO issues.

    Supported scenarios:
    - "ok": AFF0 ok + F841 ok
    - "f841_timeout": AFF0 ok + F841 timeout
    - "aff0_timeout": AFF0 timeout + F841 ok (usually fails early)
    - "f841_short": AFF0 ok + F841 returns less bytes than requested
    - "random_latency": same as ok but with extra latency
    """
    name: str = "ok"
    base_latency_ms: float = 15.0
    extra_latency_ms: float = 0.0


class FakePnioClient:
    """
    Fake PNIO client used for local development and unit tests.

    It does not access the network. It returns deterministic results
    depending on the selected scenario.
    """

    def __init__(self, scenario: FakeScenario | None = None) -> None:
        self.scenario = scenario or FakeScenario()

    def read_implicit(self, req: ReadRequest, timeout_ms: int) -> ReadResult:
        """
        Simulates a read operation and returns a normalized ReadResult.

        The validator can also call the real client, so we keep the interface compatible.
        """
        t0 = time.perf_counter()

        # Simulate latency
        latency = self.scenario.base_latency_ms + self.scenario.extra_latency_ms
        time.sleep(max(0.0, latency / 1000.0))

        # Scenario-based behaviors
        if self.scenario.name == "aff0_timeout" and req.index == IDX_AFF0:
            raise PnioTimeout("Simulated timeout on 0xAFF0")

        if self.scenario.name == "f841_timeout" and req.index == IDX_F841:
            raise PnioTimeout("Simulated timeout on 0xF841")

        if self.scenario.name == "random_latency":
            # Add a bit more delay deterministically
            time.sleep(0.050)

        if req.index == IDX_AFF0:
            # Return a small payload representing I&M0/RealIdentificationData
            data = b"IM0" + b"\x00" * max(0, min(req.length, 64) - 3)
        elif req.index == IDX_F841:
            # Return large payload representing PDRRealData (~24kB)
            if self.scenario.name == "f841_short":
                data = b"PDR" + b"\x11" * max(0, (req.length // 2) - 3)
            else:
                data = b"PDR" + b"\x11" * max(0, req.length - 3)
        else:
            raise PnioError(f"Unsupported index in fake client: 0x{req.index:04X}")

        dt_ms = (time.perf_counter() - t0) * 1000.0
        return ReadResult(ok=True, data=data, latency_ms=dt_ms, error=None)