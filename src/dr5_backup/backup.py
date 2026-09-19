"""Backup transfer logic: request and receive the DR-5's Sequence-data.

The exact message sequence (priming + request) was captured from a
real Dr5Edit Download over an ALSA sequencer tap. No front-panel
arming is needed, despite the Owner's Manual stating bulk dumps
require panel operation.
"""

from __future__ import annotations

import logging

from dr5_backup.protocol import (
    ADDR_MIDI_THRU_SWITCH,
    ADDR_SEQUENCE_DATA,
    SIZE_SEQUENCE_DATA,
    build_dt1,
    build_rq1,
)
from dr5_backup.transport import SysexTransport

logger = logging.getLogger(__name__)

# Observed real dumps: ~44981-45020 bytes across ~180-183 messages.
# Anything much smaller almost certainly means the transfer was cut off.
MIN_EXPECTED_BYTES = 40000


class IncompleteTransferError(RuntimeError):
    """Raised when a backup transfer yields no data or looks truncated.

    Attributes:
        partial_data: Whatever bytes were received before the transfer
            was judged incomplete, so a caller can still save them for
            inspection rather than discarding them.
    """

    def __init__(self, message: str, partial_data: bytes) -> None:
        super().__init__(message)
        self.partial_data = partial_data


def _prime_midi_thru_off(transport: SysexTransport) -> None:
    """Request and clear the DR-5's MIDI Thru switch before a transfer.

    Turns MIDI Thru off so the DR-5 doesn't echo/loop the transfer's
    own SysEx back out while it's busy. The captured Dr5Edit trace
    sent the RQ1 request twice before the DT1 write; a single request
    appeared sufficient in testing, but the duplicate is kept here to
    match the known-working sequence exactly.

    Args:
        transport: An open connection to the DR-5.
    """
    rq1_thru = build_rq1(ADDR_MIDI_THRU_SWITCH, bytes([0x00, 0x00, 0x01]))
    transport.send_sysex(rq1_thru)
    transport.send_sysex(rq1_thru)
    dt1_thru = build_dt1(ADDR_MIDI_THRU_SWITCH, bytes([0x00]))
    transport.send_sysex(dt1_thru)


def perform_backup(transport: SysexTransport, quiet_timeout: float, max_duration: float) -> bytes:
    """Request and collect the DR-5's Sequence-data over MIDI.

    Args:
        transport: An open connection to the DR-5.
        quiet_timeout: Seconds of silence after which the transfer is
            considered complete.
        max_duration: Hard cap on total listening time.

    Returns:
        The raw concatenated SysEx bytes received from the device.

    Raises:
        IncompleteTransferError: If no data was received, or the total
            received size is implausibly small for a full dump.
    """
    _prime_midi_thru_off(transport)

    logger.info("Requesting Sequence-data (RQ1 20 00 00, size 01 00 00)...")
    rq1_seq = build_rq1(ADDR_SEQUENCE_DATA, SIZE_SEQUENCE_DATA)
    transport.send_sysex(rq1_seq)

    logger.info("Listening (quiet timeout %ss, max %ss)...", quiet_timeout, max_duration)
    buf = bytearray()
    for i, block in enumerate(transport.receive_sysex_stream(quiet_timeout, max_duration), start=1):
        buf += block
        if i % 50 == 0:
            logger.info("  received msg #%d, %d bytes so far", i, len(buf))

    if not buf:
        raise IncompleteTransferError(
            "no data received -- check MIDI connections and port", partial_data=bytes(buf)
        )
    if len(buf) < MIN_EXPECTED_BYTES:
        raise IncompleteTransferError(
            f"only {len(buf)} bytes received, expected at least {MIN_EXPECTED_BYTES} "
            "for a full Sequence-data dump -- the transfer may have been interrupted",
            partial_data=bytes(buf),
        )
    return bytes(buf)
