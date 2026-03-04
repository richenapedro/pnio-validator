from __future__ import annotations

import hashlib


def deterministic_fake_mac(seed: str) -> str:
    """Return a deterministic locally-administered unicast MAC derived from `seed`.

    We intentionally do NOT use Python's built-in `hash()` because it is randomized
    between processes (unless PYTHONHASHSEED is fixed).
    """
    if not seed:
        seed = "pnio-validator"

    # 5 bytes from a stable hash + fixed 0x02 prefix => 6 bytes MAC
    d = hashlib.blake2s(seed.encode("utf-8"), digest_size=5).digest()
    b0 = 0x02  # locally administered, unicast
    mac_bytes = bytes([b0]) + d
    return ":".join(f"{x:02x}" for x in mac_bytes)
