"""Local network client for Orisec alarm panels.

Orisec ControlPlus panels expose a simple UDP based control protocol on the
local network (default port 20202). The panel expects a small binary frame
containing a command byte, the installer/user PIN and an optional payload,
and it replies with a frame of the same shape containing the current panel
and zone status.

This module intentionally keeps the wire format isolated behind a small,
well tested class (:class:`OrisecClient`) so that the rest of the
integration never has to deal with sockets or byte layout directly.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field

_LOGGER = logging.getLogger(__name__)

# Frame layout: <STX><CMD><PIN padded to 6 bytes><LEN><PAYLOAD><CHECKSUM><ETX>
STX = 0x02
ETX = 0x03

CMD_STATUS = 0x01
CMD_ARM_AWAY = 0x02
CMD_ARM_HOME = 0x03
CMD_DISARM = 0x04

MAX_ZONES = 32
PIN_MAX_LENGTH = 6

# Bit flags within the first byte of a status frame's body.
FLAG_ARMED_AWAY = 0x01
FLAG_ARMED_HOME = 0x02
FLAG_TRIGGERED = 0x04
FLAG_NOT_READY = 0x08

# Sentinel value returned as the flags byte when the supplied PIN is rejected.
# Only bits 0-3 above are currently defined, so 0xFF can never be produced by a
# legitimate combination of flags; keep it that way if new flags are added.
AUTH_REJECTED = 0xFF

# Default number of seconds to wait for a response before giving up. Defined
# here (rather than in const.py) so this module has no dependency on the
# rest of the Home Assistant integration and can be tested in isolation.
DEFAULT_TIMEOUT = 5


class OrisecError(Exception):
    """Base error for the Orisec client."""


class OrisecConnectionError(OrisecError):
    """Raised when the panel could not be reached."""


class OrisecAuthError(OrisecError):
    """Raised when the panel rejected the supplied PIN."""


@dataclass
class OrisecStatus:
    """Represents the last known state reported by the panel."""

    armed_away: bool = False
    armed_home: bool = False
    triggered: bool = False
    ready: bool = True
    zones: dict[int, bool] = field(default_factory=dict)


class _OrisecProtocol(asyncio.DatagramProtocol):
    """Minimal datagram protocol that resolves a future with the response."""

    def __init__(self, response: asyncio.Future[bytes]) -> None:
        self.transport: asyncio.DatagramTransport | None = None
        self.response = response

    def connection_made(self, transport: asyncio.BaseTransport) -> None:
        self.transport = transport  # type: ignore[assignment]

    def datagram_received(self, data: bytes, addr) -> None:  # noqa: ANN001
        if not self.response.done():
            self.response.set_result(data)

    def error_received(self, exc: Exception) -> None:
        if not self.response.done():
            self.response.set_exception(exc)


def _checksum(data: bytes) -> int:
    """Simple XOR checksum used to detect corrupted frames."""
    checksum = 0
    for byte in data:
        checksum ^= byte
    return checksum & 0xFF


def _build_frame(command: int, pin: str, payload: bytes = b"") -> bytes:
    if not 1 <= len(pin) <= PIN_MAX_LENGTH:
        raise OrisecError(
            f"PIN must be between 1 and {PIN_MAX_LENGTH} characters long"
        )
    pin_bytes = pin.encode("ascii").ljust(PIN_MAX_LENGTH, b"\x00")
    body = bytes([command]) + pin_bytes + bytes([len(payload)]) + payload
    return bytes([STX]) + body + bytes([_checksum(body), ETX])


def _parse_frame(data: bytes) -> OrisecStatus:
    if len(data) < 4 or data[0] != STX or data[-1] != ETX:
        raise OrisecError("Malformed response frame from panel")

    body = data[1:-2]
    checksum = data[-2]
    if _checksum(body) != checksum:
        raise OrisecError("Checksum mismatch in response frame from panel")

    if body[0] == AUTH_REJECTED:
        raise OrisecAuthError("Panel rejected the configured PIN")

    flags = body[0]
    zone_bitmap = body[1 : 1 + (MAX_ZONES // 8)]

    zones: dict[int, bool] = {}
    for zone_index in range(MAX_ZONES):
        byte_index, bit_index = divmod(zone_index, 8)
        if byte_index < len(zone_bitmap):
            zones[zone_index + 1] = bool(zone_bitmap[byte_index] & (1 << bit_index))

    return OrisecStatus(
        armed_away=bool(flags & FLAG_ARMED_AWAY),
        armed_home=bool(flags & FLAG_ARMED_HOME),
        triggered=bool(flags & FLAG_TRIGGERED),
        ready=not bool(flags & FLAG_NOT_READY),
        zones=zones,
    )


class OrisecClient:
    """Async client used to talk to an Orisec alarm panel over UDP."""

    def __init__(
        self, host: str, port: int, pin: str, timeout: float = DEFAULT_TIMEOUT
    ) -> None:
        self._host = host
        self._port = port
        self._pin = pin
        self._timeout = timeout

    async def _send(self, command: int, payload: bytes = b"") -> OrisecStatus:
        loop = asyncio.get_running_loop()
        frame = _build_frame(command, self._pin, payload)
        response: asyncio.Future[bytes] = loop.create_future()

        try:
            transport, protocol = await loop.create_datagram_endpoint(
                lambda: _OrisecProtocol(response),
                remote_addr=(self._host, self._port),
            )
        except OSError as err:
            raise OrisecConnectionError(str(err)) from err

        try:
            transport.sendto(frame)
            try:
                data = await asyncio.wait_for(protocol.response, timeout=self._timeout)
            except asyncio.TimeoutError as err:
                raise OrisecConnectionError(
                    f"Timed out waiting for a response from {self._host}:{self._port}"
                ) from err
            except OSError as err:
                raise OrisecConnectionError(str(err)) from err
        finally:
            transport.close()

        return _parse_frame(data)

    async def async_get_status(self) -> OrisecStatus:
        """Request the current status of the panel and its zones."""
        return await self._send(CMD_STATUS)

    async def async_arm_away(self) -> OrisecStatus:
        """Arm the panel in away mode."""
        return await self._send(CMD_ARM_AWAY)

    async def async_arm_home(self) -> OrisecStatus:
        """Arm the panel in home/stay mode."""
        return await self._send(CMD_ARM_HOME)

    async def async_disarm(self) -> OrisecStatus:
        """Disarm the panel."""
        return await self._send(CMD_DISARM)
