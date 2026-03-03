from __future__ import annotations

from pnio_validator.pnio_client_fake import FakePnioClient, FakeScenario
from pnio_validator.validator import HeidenhainStrictValidator, ValidationConfig


def test_validator_pass_ok_scenario() -> None:
    client = FakePnioClient(FakeScenario(name="ok"))
    cfg = ValidationConfig(device_name="em31-new", retries=0, timeout_ms=100)
    v = HeidenhainStrictValidator(client=client, config=cfg)
    result = v.run()
    assert result.ok is True
    assert result.aff0.ok is True
    assert result.f841.ok is True
    assert result.aff0.bytes_len > 0
    assert result.f841.bytes_len > 0


def test_validator_fail_on_f841_timeout() -> None:
    client = FakePnioClient(FakeScenario(name="f841_timeout"))
    cfg = ValidationConfig(device_name="em31-new", retries=0, timeout_ms=10)
    v = HeidenhainStrictValidator(client=client, config=cfg)
    result = v.run()
    assert result.ok is False
    assert result.aff0.ok is True
    assert result.f841.ok is False
    assert result.f841.error is not None


def test_validator_retries_then_fail() -> None:
    client = FakePnioClient(FakeScenario(name="f841_timeout"))
    cfg = ValidationConfig(device_name="em31-new", retries=1, timeout_ms=10)  # 2 attempts
    v = HeidenhainStrictValidator(client=client, config=cfg)
    result = v.run()
    assert result.ok is False
    assert result.f841.attempts == 2

def test_validator_fail_on_f841_short_read() -> None:
    client = FakePnioClient(FakeScenario(name="f841_short"))
    cfg = ValidationConfig(device_name="em31-new", retries=0, timeout_ms=100, min_f841_ratio=0.90)
    v = HeidenhainStrictValidator(client=client, config=cfg)
    result = v.run()
    assert result.ok is False
    assert result.f841.ok is False
    assert result.f841.error is not None
    assert "short_read" in result.f841.error