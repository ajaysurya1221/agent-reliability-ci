"""`ARCI_HTTPS_PROXY`: an explicit CONNECT tunnel for the upstream client.

The ambient `HTTPS_PROXY` is never read, because the real key travels on this connection.
"""

from __future__ import annotations

import http.client
from typing import Any, ClassVar

import pytest

from arci import mcp_boundary

UPSTREAM_PROXY_ENV = mcp_boundary.UPSTREAM_PROXY_ENV
_open = mcp_boundary._open_upstream_connection  # pyright: ignore[reportPrivateUsage]


class _FakeHttps:
    """Records what the factory asked for; never opens a socket."""

    instances: ClassVar[list[_FakeHttps]] = []

    def __init__(self, host: str, port: int | None = None, timeout: float | None = None) -> None:
        self.host, self.port, self.timeout = host, port, timeout
        self.tunnel: tuple[str, int | None] | None = None
        type(self).instances.append(self)

    def set_tunnel(self, host: str, port: int | None = None, headers: Any = None) -> None:
        self.tunnel = (host, port)


@pytest.fixture(autouse=True)
def _fresh(monkeypatch: pytest.MonkeyPatch) -> None:
    _FakeHttps.instances = []
    monkeypatch.setattr(mcp_boundary.http.client, "HTTPSConnection", _FakeHttps)
    monkeypatch.delenv(UPSTREAM_PROXY_ENV, raising=False)
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:9")  # ambient; must be ignored


def test_default_is_a_direct_connection_even_with_an_ambient_https_proxy() -> None:
    connection = _open("https", "api.typesafe.ai", None, timeout=1.0)
    assert isinstance(connection, _FakeHttps)
    assert (connection.host, connection.port, connection.tunnel) == ("api.typesafe.ai", None, None)


def test_explicit_proxy_tunnels_to_the_upstream(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(UPSTREAM_PROXY_ENV, "http://127.0.0.1:3128")
    connection = _open("https", "api.typesafe.ai", None, timeout=2.5)
    assert isinstance(connection, _FakeHttps)
    assert (connection.host, connection.port, connection.timeout) == ("127.0.0.1", 3128, 2.5)
    assert connection.tunnel == ("api.typesafe.ai", 443)


def test_an_explicit_upstream_port_is_kept_in_the_tunnel(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(UPSTREAM_PROXY_ENV, "http://proxy.internal:8080")
    connection = _open("https", "gateway.example", 8443, timeout=1.0)
    assert isinstance(connection, _FakeHttps)
    assert connection.tunnel == ("gateway.example", 8443)


def test_loopback_http_upstreams_never_use_the_proxy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(UPSTREAM_PROXY_ENV, "http://127.0.0.1:3128")
    connection = _open("http", "127.0.0.1", 8123, timeout=1.0)
    assert type(connection) is http.client.HTTPConnection
    assert (connection.host, connection.port) == ("127.0.0.1", 8123)
    assert _FakeHttps.instances == []


@pytest.mark.parametrize("value", ["https://proxy:3128", "127.0.0.1:3128", "http://proxy"])
def test_a_malformed_proxy_setting_is_a_transport_error(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    monkeypatch.setenv(UPSTREAM_PROXY_ENV, value)
    with pytest.raises(mcp_boundary._DecisionTransportError, match=UPSTREAM_PROXY_ENV):  # pyright: ignore[reportPrivateUsage]
        _open("https", "api.typesafe.ai", None, timeout=1.0)
