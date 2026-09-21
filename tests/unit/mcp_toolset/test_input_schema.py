"""The bridge must tell a model what arguments a tool takes."""

from __future__ import annotations

from arci.mcp_toolset_server import _describe, _input_schema  # pyright: ignore[reportPrivateUsage]


def reserve(order_id: str, sku: str, quantity: int = 1, note=None) -> None:  # type: ignore[no-untyped-def]
    """Reserve stock for an order.

    Longer text that a model does not need.
    """


def test_schema_comes_from_the_python_signature() -> None:
    assert _input_schema(reserve) == {
        "type": "object",
        "properties": {
            "order_id": {"type": "string"},
            "sku": {"type": "string"},
            "quantity": {"type": "integer"},
            "note": {},
        },
        "required": ["order_id", "sku"],
    }
    assert _describe("reserve", reserve) == "Reserve stock for an order."
    assert _describe("noop", lambda: None) == "noop"
