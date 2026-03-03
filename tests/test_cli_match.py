from __future__ import annotations

from pathlib import Path

from pnio_validator.registry import import_gsdml
from pnio_validator import cli


def test_cli_match_returns_0_for_exact_match(tmp_path: Path, capsys) -> None:
    # Build a temporary registry
    data_dir = tmp_path / "data"
    gsd_dir = data_dir / "gsdml"
    reg_path = data_dir / "gsd_registry.json"

    sample = Path(__file__).parent / "fixtures" / "sample_gsdml.xml"
    import_gsdml(sample, gsd_dir=gsd_dir, registry_path=reg_path)

    # Monkeypatch registry defaults by pointing CWD to tmp_path
    # (registry uses relative 'data/...', so this isolates test)
    old_cwd = Path.cwd()
    try:
        import os
        os.chdir(tmp_path)

        rc = cli.main(["match", "--vendor-id", "0x1234", "--device-id", "0x5678"])
        out = capsys.readouterr().out
        assert rc == 0
        assert "Match:" in out
    finally:
        import os
        os.chdir(old_cwd)