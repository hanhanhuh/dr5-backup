"""MIDI I/O boundary for talking to the DR-5.

Isolates all `mido`-specific mechanics (port handles, message framing,
polling for incoming SysEx) behind a small transport class, so the
protocol-orchestration layer (`backup.py`/`restore.py`) never touches
`mido` directly.
"""

from __future__ import annotations

import time
from collections.abc import Iterator
from types import TracebackType
from typing import Protocol

import mido

from dr5_backup.protocol import EOX, SOX

_POLL_INTERVAL_SECONDS = 0.002


class TransportNotOpenError(RuntimeError):
    """Raised when a `MidiTransport` method is called outside its `with` block."""


class SysexTransport(Protocol):
    """Structural interface required by the protocol-orchestration layer.

    `backup.perform_backup`/`restore.perform_restore` depend on this,
    not on `MidiTransport` directly, so tests can substitute a fake
    implementation without touching real MIDI ports.
    """

    def send_sysex(self, payload: bytes) -> None:
        """Send one SysEx message payload (without F0/F7 framing)."""
        ...

    def receive_sysex_stream(self, quiet_timeout: float, max_duration: float) -> Iterator[bytes]:
        """Yield complete SysEx blocks (with F0/F7 framing) as they arrive."""
        ...


class MidiTransport:
    """A bidirectional MIDI connection to the DR-5.

    Opens the same port name for both input and output, matching the
    DR-5's single bidirectional MIDI interface. Use as a context
    manager.
    """

    def __init__(self, port: str) -> None:
        """Initialize the transport.

        Args:
            port: MIDI port name, used for both input and output.
        """
        self._port_name = port
        self._inport: mido.ports.BaseInput | None = None
        self._outport: mido.ports.BaseOutput | None = None

    def __enter__(self) -> MidiTransport:
        self._inport = mido.open_input(self._port_name)
        self._outport = mido.open_output(self._port_name)
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        if self._inport is not None:
            self._inport.close()
        if self._outport is not None:
            self._outport.close()

    def send_sysex(self, payload: bytes) -> None:
        """Send one SysEx message.

        Args:
            payload: Message body (manufacturer/device/model/command/
                address/data/checksum), without F0/F7 framing.
        """
        if self._outport is None:
            raise TransportNotOpenError("MidiTransport must be used as a context manager")
        self._outport.send(mido.Message("sysex", data=payload))

    def receive_sysex_stream(self, quiet_timeout: float, max_duration: float) -> Iterator[bytes]:
        """Yield complete SysEx blocks as they arrive.

        Polls the input port until either no new SysEx message has
        arrived for ``quiet_timeout`` seconds (and at least one has
        been received), or ``max_duration`` seconds have elapsed in
        total.

        Args:
            quiet_timeout: Seconds of silence after which the stream
                is considered finished.
            max_duration: Hard cap on total listening time, regardless
                of activity.

        Yields:
            Each received SysEx message as a complete block including
            its leading F0 and trailing F7 byte.
        """
        if self._inport is None:
            raise TransportNotOpenError("MidiTransport must be used as a context manager")
        start = time.monotonic()
        last_received = start
        received_any = False

        while True:
            now = time.monotonic()
            if now - start > max_duration:
                return
            if received_any and now - last_received > quiet_timeout:
                return

            for msg in self._inport.iter_pending():
                if msg.type == "sysex":
                    yield bytes([SOX]) + bytes(msg.data) + bytes([EOX])
                    received_any = True
                    last_received = time.monotonic()

            time.sleep(_POLL_INTERVAL_SECONDS)
