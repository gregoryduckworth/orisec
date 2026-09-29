"""Tests for the Orisec local network protocol client."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "orisec"))

from api import (  # noqa: E402  pylint: disable=wrong-import-position
    ETX,
    STX,
    OrisecAuthError,
    OrisecClient,
    OrisecConnectionError,
    OrisecError,
    _build_frame,
    _checksum,
    _parse_frame,
)


class _FakePanelProtocol(asyncio.DatagramProtocol):
    """A tiny fake panel used to exercise OrisecClient end-to-end."""

    def __init__(self, response_body: bytes | None, reject_auth: bool = False) -> None:
        self._response_body = response_body
        self._reject_auth = reject_auth
        self.transport: asyncio.DatagramTransport | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr) -> None:  # noqa: ANN001
        if self._reject_auth:
            body = bytes([0xFF])
        elif self._response_body is not None:
            body = self._response_body
        else:
            # Echo back a simple "all clear" status frame.
            body = bytes([0x00])
        frame = bytes([STX]) + body + bytes([_checksum(body), ETX])
        self.transport.sendto(frame, addr)  # type: ignore[union-attr]


async def _start_fake_panel(response_body: bytes | None = None, reject_auth: bool = False):
    loop = asyncio.get_running_loop()
    transport, protocol = await loop.create_datagram_endpoint(
        lambda: _FakePanelProtocol(response_body, reject_auth),
        local_addr=("127.0.0.1", 0),
    )
    host, port = transport.get_extra_info("sockname")
    return transport, host, port


def test_build_and_parse_frame_roundtrip() -> None:
    frame = _build_frame(0x01, "1234")
    assert frame[0] == STX
    assert frame[-1] == ETX

    # Simulate an "all clear, zones 1 and 3 open" status response.
    body = bytes([0x00, 0b00000101])
    response = bytes([STX]) + body + bytes([_checksum(body), ETX])
    status = _parse_frame(response)

    assert status.armed_away is False
    assert status.armed_home is False
    assert status.triggered is False
    assert status.ready is True
    assert status.zones[1] is True
    assert status.zones[2] is False
    assert status.zones[3] is True


def test_parse_frame_rejects_bad_checksum() -> None:
    body = bytes([0x00])
    bad_frame = bytes([STX]) + body + bytes([_checksum(body) ^ 0xFF, ETX])
    with pytest.raises(OrisecError):
        _parse_frame(bad_frame)


def test_parse_frame_rejects_missing_markers() -> None:
    with pytest.raises(OrisecError):
        _parse_frame(b"\x00\x00\x00")


def test_parse_frame_raises_auth_error() -> None:
    body = bytes([0xFF])
    frame = bytes([STX]) + body + bytes([_checksum(body), ETX])
    with pytest.raises(OrisecAuthError):
        _parse_frame(frame)


@pytest.mark.asyncio
async def test_client_get_status_against_fake_panel() -> None:
    transport, host, port = await _start_fake_panel(bytes([0b00000001]))
    try:
        client = OrisecClient(host, port, "1234", timeout=2)
        status = await client.async_get_status()
        assert status.armed_away is True
    finally:
        transport.close()


@pytest.mark.asyncio
async def test_client_raises_auth_error_for_rejected_pin() -> None:
    transport, host, port = await _start_fake_panel(reject_auth=True)
    try:
        client = OrisecClient(host, port, "0000", timeout=2)
        with pytest.raises(OrisecAuthError):
            await client.async_get_status()
    finally:
        transport.close()


@pytest.mark.asyncio
async def test_client_raises_connection_error_on_timeout() -> None:
    # Nothing is listening on this port, so the client should time out.
    client = OrisecClient("127.0.0.1", 1, "1234", timeout=0.2)
    with pytest.raises(OrisecConnectionError):
        await client.async_get_status()
