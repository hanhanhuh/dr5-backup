"""Shared Roland/Boss DR-5 SysEx helpers.

Roland's F0 41 DT1/RQ1 one-way-transfer framing, per the DR-5 Owner's
Manual's MIDI Implementation section (Roland Exclusive Messages,
Section 1-3).
"""

from __future__ import annotations

MANUFACTURER_ID = 0x41
DEVICE_ID = 0x09
MODEL_ID = 0x65
CMD_RQ1 = 0x11
CMD_DT1 = 0x12

SOX = 0xF0
EOX = 0xF7

# Address of the DR-5's MIDI Thru switch (System Setup parameter map,
# Owner's Manual p.11-19). Dr5Edit turns this OFF before every bulk
# transfer, in both directions, so the DR-5 doesn't echo/loop the
# transfer's own SysEx back out while it's busy.
ADDR_MIDI_THRU_SWITCH = bytes([0x10, 0x00, 0x0F])

# Address + request size for the Sequence-data region (Owner's Manual's
# own Table 4-3 documents this as one large, internally opaque block --
# no field-level layout is specified in the manual itself).
ADDR_SEQUENCE_DATA = bytes([0x20, 0x00, 0x00])
SIZE_SEQUENCE_DATA = bytes([0x01, 0x00, 0x00])


def checksum(payload: bytes) -> int:
    """Roland checksum: (-sum(payload)) & 0x7F."""
    return (-sum(payload)) & 0x7F


def build_rq1(address: bytes, size: bytes) -> bytes:
    """Build an RQ1 (request data) message payload (no F0/F7 -- mido adds those)."""
    body = address + size
    return bytes([MANUFACTURER_ID, DEVICE_ID, MODEL_ID, CMD_RQ1]) + body + bytes([checksum(body)])


def build_dt1(address: bytes, data: bytes) -> bytes:
    """Build a DT1 (data set) message payload (no F0/F7 -- mido adds those)."""
    body = address + data
    return bytes([MANUFACTURER_ID, DEVICE_ID, MODEL_ID, CMD_DT1]) + body + bytes([checksum(body)])


def parse_blocks(data: bytes) -> list[bytes]:
    """Split a raw .syx capture into individual F0...F7 blocks (each including F0/F7)."""
    blocks = []
    i, n = 0, len(data)
    while i < n:
        if data[i] != SOX:
            raise ValueError(f"expected {SOX:#x} at offset {i}, got {data[i]:#x}")
        j = i + 1
        while j < n and data[j] != EOX:
            j += 1
        if j >= n:
            raise ValueError(f"unterminated block starting at offset {i}")
        blocks.append(data[i : j + 1])
        i = j + 1
    return blocks
