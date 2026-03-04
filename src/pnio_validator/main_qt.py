from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from .qt_backend import QtBackend


def main() -> int:
    app = QApplication(sys.argv)

    backend = QtBackend()

    print("Adapters:")
    print(backend.listAdapters())

    print("\nMatch sample:")
    print(backend.match("0x1234", "0x5678", ""))

    print("\nValidate fake:")
    print(backend.validateFake("em31-new", "ok"))

    print("\nDCP fake:")
    print(backend.dcpSetNameFake("em31-new", "foo"))
    print(backend.dcpSetIpFake("em31-new", "192.168.0.10", "255.255.255.0", "192.168.0.1"))
    print(backend.dcpBlinkFake("em31-new", True, 10.0))
    print(backend.dcpFactoryResetFake("em31-new"))

    return 0


if __name__ == "__main__":
    raise SystemExit(main())