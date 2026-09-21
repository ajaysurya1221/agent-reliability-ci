from __future__ import annotations

import io
import threading
from collections.abc import Callable
from typing import cast

import arci.mcp_shim as shim_module


def test_shim_pump_relays_bytes_unchanged() -> None:
    pump = cast(
        Callable[[Callable[[int], bytes], Callable[[bytes], object], threading.Event], None],
        vars(shim_module)["_pump"],
    )
    source = io.BytesIO(b"one\x00two\n")
    destination = io.BytesIO()
    pump(source.read, destination.write, threading.Event())
    assert destination.getvalue() == b"one\x00two\n"
