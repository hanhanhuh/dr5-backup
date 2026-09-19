"""Restore transfer logic: prime and send Sequence-data blocks to the DR-5.

The message sequence was captured from a real Dr5Edit Upload over an
ALSA sequencer tap. The MIDI-Thru-off priming step and the ~3ms
inter-message pacing are both required -- without them the DR-5 gets
stuck on its "RxSys" screen.
"""

from __future__ import annotations

import logging
import time

from dr5_backup.protocol import ADDR_MIDI_THRU_SWITCH, build_dt1, build_rq1
from dr5_backup.transport import SysexTransport

logger = logging.getLogger(__name__)

_SEND_PACING_SECONDS = 0.003


def _prime_midi_thru_off(transport: SysexTransport) -> None:
    """Request and clear the DR-5's MIDI Thru switch before a transfer.

    Args:
        transport: An open connection to the DR-5.
    """
    rq1_thru = build_rq1(ADDR_MIDI_THRU_SWITCH, bytes([0x00, 0x00, 0x01]))
    transport.send_sysex(rq1_thru)
    time.sleep(0.019)
    dt1_thru = build_dt1(ADDR_MIDI_THRU_SWITCH, bytes([0x00]))
    transport.send_sysex(dt1_thru)
    time.sleep(0.009)


def perform_restore(transport: SysexTransport, blocks: list[bytes]) -> None:
    """Send previously-captured SysEx blocks back to the DR-5.

    Args:
        transport: An open connection to the DR-5.
        blocks: Complete SysEx blocks (each including its own F0/F7
            framing), typically from `protocol.parse_blocks`.
    """
    _prime_midi_thru_off(transport)

    logger.info("Streaming captured blocks at ~%dms pacing...", _SEND_PACING_SECONDS * 1000)
    for i, block in enumerate(blocks, start=1):
        transport.send_sysex(block[1:-1])  # strip F0/F7; mido adds its own when sending
        if i % 50 == 1:
            logger.info("  sent block %d/%d (%d bytes)", i, len(blocks), len(block))
        time.sleep(_SEND_PACING_SECONDS)

    logger.info("Done. Sent %d blocks.", len(blocks))
    logger.info("NOTE: MIDI Thru left OFF -- reset manually if needed (Utility mode > System Setup).")
