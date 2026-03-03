from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PnioClientConfig:
    iface: str
    timeout_ms: int = 3000


class PnioError(RuntimeError):
    pass


class PnioTimeout(PnioError):
    pass


class PnioClient:
    """
    PNIO CM acyclic client (Read Implicit) — placeholder.

    Alvo:
    - Read Implicit (sem AR cíclico) por slot/subslot/index
    - Suporte a records grandes (fragmentação RPC)
    """

    def __init__(self, config: PnioClientConfig) -> None:
        self.config = config

    def read_implicit(
        self,
        device_name: str,
        slot: int,
        subslot: int,
        index: int,
        length: int,
        block_version: int = 1,
        timeout_ms: int | None = None,
    ) -> bytes:
        _ = (device_name, slot, subslot, index, length, block_version, timeout_ms)

        # TODO: Implementar PNIO CM Read Implicit.
        # Aqui deve retornar bytes (RecordData) ou levantar PnioTimeout/PnioError.
        raise NotImplementedError("PNIO CM Read Implicit not implemented yet.")