from __future__ import annotations

from pathlib import Path

from pnio_validator.gsdml_parser import parse_gsdml, summarize_gsdml, export_expected_model


def test_summarize_contains_key_fields() -> None:
    xml_path = Path(__file__).parent / "fixtures" / "sample_gsdml.xml"
    model = parse_gsdml(xml_path)
    text = summarize_gsdml(model)

    assert "DAP:" in text
    assert "Modules:" in text
    assert "Module 1" in text
    assert "Submodule 1" in text


def test_export_expected_model_shape() -> None:
    xml_path = Path(__file__).parent / "fixtures" / "sample_gsdml.xml"
    model = parse_gsdml(xml_path)
    expected = export_expected_model(model)

    assert "dap" in expected
    assert "modules" in expected
    assert isinstance(expected["modules"], list)
    assert expected["dap"]["module_ident_number"] == 1
    assert expected["modules"][0]["module_ident_number"] == 0x1001