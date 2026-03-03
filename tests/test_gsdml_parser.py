from __future__ import annotations

from pathlib import Path

from pnio_validator.gsdml_parser import parse_gsdml


def test_parse_sample_gsdml() -> None:
    xml_path = Path(__file__).parent / "fixtures" / "sample_gsdml.xml"
    model = parse_gsdml(xml_path)

    assert model.dap is not None
    assert model.dap.id == "DAP_1"
    assert model.dap.module_ident_number == 1
    assert model.dap.name == "Device Access Point"

    assert len(model.modules) == 1
    m = model.modules[0]
    assert m.id == "MOD_1"
    assert m.module_ident_number == 0x1001
    assert m.name == "Module 1"

    assert len(m.submodules) == 2
    assert m.submodules[0].submodule_ident_number == 0x2001
    assert m.submodules[1].submodule_ident_number == 0x2002