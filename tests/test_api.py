"""Tests for the Orisec local network protocol client."""
from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "custom_components" / "orisec"))

from api import (  # noqa: E402  pylint: disable=wrong-import-position
    CMD_ARM_AWAY,
    CMD_ARM_HOME,
    CMD_DISARM,
    CMD_STATUS,
    ETX,
    PIN_MAX_LENGTH,
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
        self.last_command: int | None = None

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr) -> None:  # noqa: ANN001
        self.last_command = data[1]
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
    return transport, protocol, host, port


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


def test_parse_frame_rejects_frame_shorter_than_minimum_length() -> None:
    # STX + checksum(of empty body) + ETX is 3 bytes, one short of the
    # 4-byte minimum (STX + 1-byte body + checksum + ETX).
    too_short_frame = bytes([STX, _checksum(b""), ETX])
    with pytest.raises(OrisecError):
        _parse_frame(too_short_frame)


def test_parse_frame_accepts_minimum_length_frame() -> None:
    body = bytes([0x00])
    minimal_frame = bytes([STX]) + body + bytes([_checksum(body), ETX])
    status = _parse_frame(minimal_frame)
    assert status.zones == {}


def test_parse_frame_raises_auth_error() -> None:
    body = bytes([0xFF])
    frame = bytes([STX]) + body + bytes([_checksum(body), ETX])
    with pytest.raises(OrisecAuthError):
        _parse_frame(frame)


@pytest.mark.asyncio
async def test_client_get_status_against_fake_panel() -> None:
    transport, protocol, host, port = await _start_fake_panel(bytes([0b00000001]))
    try:
        client = OrisecClient(host, port, "1234", timeout=2)
        status = await client.async_get_status()
        assert status.armed_away is True
        assert protocol.last_command == CMD_STATUS
    finally:
        transport.close()


@pytest.mark.asyncio
async def test_client_raises_auth_error_for_rejected_pin() -> None:
    transport, protocol, host, port = await _start_fake_panel(reject_auth=True)
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


@pytest.mark.asyncio
async def test_client_raises_connection_error_when_socket_setup_fails() -> None:
    client = OrisecClient("127.0.0.1", 20202, "1234", timeout=2)
    loop = asyncio.get_running_loop()

    with patch.object(
        loop, "create_datagram_endpoint", side_effect=OSError("network unreachable")
    ):
        with pytest.raises(OrisecConnectionError):
            await client.async_get_status()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "expected_command"),
    [
        ("async_arm_away", CMD_ARM_AWAY),
        ("async_arm_home", CMD_ARM_HOME),
        ("async_disarm", CMD_DISARM),
    ],
)
async def test_client_command_methods_send_expected_command(
    method_name: str, expected_command: int
) -> None:
    transport, protocol, host, port = await _start_fake_panel()
    try:
        client = OrisecClient(host, port, "1234", timeout=2)
        await getattr(client, method_name)()
        assert protocol.last_command == expected_command
    finally:
        transport.close()


def test_build_frame_rejects_pin_that_is_too_long() -> None:
    with pytest.raises(OrisecError):
        _build_frame(CMD_STATUS, "1" * (PIN_MAX_LENGTH + 1))


def test_build_frame_rejects_empty_pin() -> None:
    with pytest.raises(OrisecError):
        _build_frame(CMD_STATUS, "")
