from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from .pnio_client import PnioClient, PnioTimeout, PnioError


IDX_AFF0 = 0xAFF0  # RealIdentificationData / I&M0 (observado em controladores)
IDX_F841 = 0xF841  # PDRRealData (observado no teu caso)


@dataclass(frozen=True)
class ValidationConfig:
    device_name: str
    slot: int = 0
    subslot: int = 1
    read_len_aff0: int = 2048
    read_len_f841: int = 24576
    retries: int = 1


@dataclass
class RecordResult:
    index: int
    ok: bool
    bytes_len: int = 0
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
                return f"{idx}: OK ({rr.bytes_len} bytes, attempts={rr.attempts})"
            return f"{idx}: FAIL ({rr.error}, attempts={rr.attempts})"

        return "\n".join(
            [
                f"Device: {self.device_name}",
                line(self.aff0),
                line(self.f841),
                f"Overall: {'PASS' if self.ok else 'FAIL'}",
            ]
        )


class HeidenhainStrictValidator:
    """
    Regra inicial (MVP):
    - Deve responder 0xAFF0
    - Deve responder 0xF841 (~24kB)
    - Timeout/erro => FAIL
    """

    def __init__(self, client: PnioClient, config: ValidationConfig) -> None:
        self.client = client
        self.config = config

    def _read_with_retries(self, index: int, length: int) -> RecordResult:
        rr = RecordResult(index=index, ok=False, attempts=0)
        last_err: Optional[str] = None

        for attempt in range(1, self.config.retries + 2):  # retries=1 => 2 tentativas
            rr.attempts = attempt
            try:
                data = self.client.read_implicit(
                    device_name=self.config.device_name,
                    slot=self.config.slot,
                    subslot=self.config.subslot,
                    index=index,
                    length=length,
                    block_version=1,
                )
                rr.ok = True
                rr.bytes_len = len(data)
                rr.error = None
                return rr
            except PnioTimeout as e:
                last_err = f"timeout: {e}"
            except (PnioError, NotImplementedError) as e:
                last_err = f"pnio_error: {e}"
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