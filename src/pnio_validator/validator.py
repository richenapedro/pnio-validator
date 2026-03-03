from __future__ import annotations

from operator import index
import time
from dataclasses import dataclass
from typing import Optional, Protocol

from .models import ReadRequest, ReadResult
from .pnio_client import PnioTimeout, PnioError, PnioClient


IDX_AFF0 = 0xAFF0  # RealIdentificationData / I&M0 (observed in controllers)
IDX_F841 = 0xF841  # PDRRealData (observed in your case)


class ReadImplicitClient(Protocol):
    """
    Small protocol to allow swapping the real network client with a fake client.
    """

    def read_implicit(self, req: ReadRequest, timeout_ms: int) -> ReadResult:
        ...


@dataclass(frozen=True)
class ValidationConfig:
    device_name: str
    slot: int = 0
    subslot: int = 1
    read_len_aff0: int = 2048
    read_len_f841: int = 24576
    retries: int = 1
    timeout_ms: int = 3000

    # Strictness thresholds
    min_aff0_bytes: int = 32
    min_f841_ratio: float = 0.90  # require at least 90% of requested length


@dataclass
class RecordResult:
    index: int
    ok: bool
    requested_len: int = 0
    min_expected_len: int = 0
    bytes_len: int = 0
    latency_ms: float = 0.0
    error: Optional[str] = None
    attempts: int = 0


@dataclass
class ValidationResult:
    device_name: str
    ok: bool
    aff0: RecordResult
    f841: RecordResult

    def to_dict(self) -> dict:
        return {
            "device_name": self.device_name,
            "ok": self.ok,
            "records": {
                "0xAFF0": self.aff0.__dict__,
                "0xF841": self.f841.__dict__,
            },
        }

    def to_text(self) -> str:
        def line(rr: RecordResult) -> str:
            idx = f"0x{rr.index:04X}"
            if rr.ok:
                return f"{idx}: OK ({rr.bytes_len} bytes, {rr.latency_ms:.1f} ms, attempts={rr.attempts})"
            return f"{idx}: FAIL ({rr.error}, attempts={rr.attempts})"

        return "\n".join(
            [
                f"Device: {self.device_name}",
                line(self.aff0),
                line(self.f841),
                f"Overall: {'PASS' if self.ok else 'FAIL'}",
            ]
        )


class RealPnioClientAdapter:
    """
    Adapter to wrap the real PnioClient (network) into the normalized interface.

    This allows the validator to depend on ReadImplicitClient instead of network details.
    """

    def __init__(self, client: PnioClient) -> None:
        self._client = client

    def read_implicit(self, req: ReadRequest, timeout_ms: int) -> ReadResult:
        t0 = time.perf_counter()
        data = self._client.read_implicit(
            device_name=req.device_name,
            slot=req.slot,
            subslot=req.subslot,
            index=req.index,
            length=req.length,
            block_version=req.block_version,
            timeout_ms=timeout_ms,
        )
        dt_ms = (time.perf_counter() - t0) * 1000.0
        return ReadResult(ok=True, data=data, latency_ms=dt_ms, error=None)


class HeidenhainStrictValidator:
    """
    MVP strict rules:
    - Must read 0xAFF0 successfully
    - Must read 0xF841 (~24kB) successfully
    - Any timeout/error => FAIL
    """

    def __init__(self, client: ReadImplicitClient, config: ValidationConfig) -> None:
        self.client = client
        self.config = config

    def _read_with_retries(self, index: int, length: int) -> RecordResult:
        rr = RecordResult(
            index=index,
            ok=False,
            attempts=0,
            requested_len=length,
            min_expected_len=0,
        )
        last_err: Optional[str] = None

        for attempt in range(1, self.config.retries + 2):  # retries=1 => 2 attempts
            rr.attempts = attempt
            req = ReadRequest(
                device_name=self.config.device_name,
                slot=self.config.slot,
                subslot=self.config.subslot,
                index=index,
                length=length,
                block_version=1,
            )
            try:
                res = self.client.read_implicit(req=req, timeout_ms=self.config.timeout_ms)
                rr.ok = True
                rr.bytes_len = len(res.data)
                rr.latency_ms = res.latency_ms
                if index == IDX_AFF0:
                    rr.min_expected_len = int(self.config.min_aff0_bytes)
                    if rr.bytes_len < rr.min_expected_len:
                        rr.ok = False
                        rr.error = f"short_read: expected >= {rr.min_expected_len}, got {rr.bytes_len}"
                        return rr

                if index == IDX_F841:
                    rr.min_expected_len = int(length * float(self.config.min_f841_ratio))
                    if rr.bytes_len < rr.min_expected_len:
                        rr.ok = False
                        rr.error = f"short_read: expected >= {rr.min_expected_len} ({self.config.min_f841_ratio:.2f}x), got {rr.bytes_len}"
                        return rr

                rr.ok = True
                rr.error = None
                return rr
            except PnioTimeout as e:
                last_err = f"timeout: {e}"
            except PnioError as e:
                last_err = f"pnio_error: {e}"
            except NotImplementedError as e:
                last_err = f"not_implemented: {e}"
            except Exception as e:
                last_err = f"unexpected: {e}"

        rr.ok = False
        rr.error = last_err or "unknown"
        return rr

    def run(self) -> ValidationResult:
        aff0 = self._read_with_retries(IDX_AFF0, self.config.read_len_aff0)
        f841 = self._read_with_retries(IDX_F841, self.config.read_len_f841)
        ok = bool(aff0.ok and f841.ok)
        return ValidationResult(device_name=self.config.device_name, ok=ok, aff0=aff0, f841=f841)