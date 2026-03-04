from __future__ import annotations

from pnio_validator.util.mac import deterministic_fake_mac


def test_deterministic_fake_mac_is_stable() -> None:
    m1 = deterministic_fake_mac("em31-new")
    m2 = deterministic_fake_mac("em31-new")
    assert m1 == m2
    assert m1.startswith("02:")
    assert len(m1.split(":")) == 6
