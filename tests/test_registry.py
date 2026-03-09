from __future__ import annotations

from pathlib import Path

from pnio_validator.registry import import_gsdml, load_registry, match_device_to_gsd


def test_import_and_match(tmp_path: Path) -> None:
    data_dir = tmp_path / "data"
    gsd_dir = data_dir / "gsdml"
    reg_path = data_dir / "gsd_registry.json"

    sample = Path(__file__).parent / "fixtures" / "sample_gsdml.xml"
    entry = import_gsdml(sample, gsd_dir=gsd_dir, registry_path=reg_path)

    assert entry.vendor_id == "0x1234"
    assert entry.device_id == "0x5678"
    assert (gsd_dir / sample.name).exists()

    reg = load_registry(reg_path)
    assert entry.key() in reg

    m, reason, score = match_device_to_gsd(
        vendor_id=0x1234,
        device_id=0x5678,
        name="anything",
        registry_path=reg_path,
    )

    assert m is not None
    assert m.vendor_id == "0x1234"
    assert m.device_id == "0x5678"
    assert reason == "vendor_id+device_id+latest_version"
    assert score == 1.0