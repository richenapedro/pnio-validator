from __future__ import annotations

from pnio_validator.dcp_fake import FakeDcpClient


def test_fake_dcp_set_name_and_ip_and_reset() -> None:
    c = FakeDcpClient()
    mac = "aa:bb:cc:dd:ee:ff"

    r1 = c.set_name(target_mac=mac, name="em31-new")
    assert r1.ok is True

    r2 = c.set_ip(target_mac=mac, ip="192.168.0.10", mask="255.255.255.0", gw="192.168.0.1")
    assert r2.ok is True

    st = c.devices[mac]
    assert st.name == "em31-new"
    assert st.ip == "192.168.0.10"

    r_b = c.blink(target_mac=mac, on=True, duration_s=10)
    assert r_b.ok is True
    assert c.devices[mac].blink is True

    r3 = c.factory_reset(target_mac=mac)
    assert r3.ok is True
    st2 = c.devices[mac]
    assert st2.name == "unnamed"
    assert st2.ip == "0.0.0.0"
    assert st2.blink is False