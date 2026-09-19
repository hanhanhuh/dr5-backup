"""A fake MidiTransport for testing protocol orchestration without hardware."""

from __future__ import annotations

from collections.abc import Iterator


class FakeTransport:
    """Records sent SysEx payloads and replays a canned response stream.

    Stands in for `dr5_backup.transport.MidiTransport` in tests of
    `backup.perform_backup`/`restore.perform_restore`, which only need
    an object with matching `send_sysex`/`receive_sysex_stream` methods.
    """

    def __init__(self, response_blocks: list[bytes] | None = None) -> None:
        self.sent: list[bytes] = []
        self._response_blocks = response_blocks or []

    def send_sysex(self, payload: bytes) -> None:
        self.sent.append(payload)

    def receive_sysex_stream(self, quiet_timeout: float, max_duration: float) -> Iterator[bytes]:
        yield from self._response_blocks
