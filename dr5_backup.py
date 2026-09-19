#!/usr/bin/env python3
"""Automated Complete Sequence-data backup from the Boss DR-5 -- no
front-panel interaction needed.

Usage:
    dr5-backup [outfile.syx] [--port PORT] [--quiet-timeout SECS] [--max-duration SECS]

The exact message sequence (priming + request) was captured from a real
Dr5Edit Download over an ALSA sequencer tap; see dr5_sysex.py for the
byte-level details. No front-panel arming is needed, despite the Owner's
Manual stating bulk dumps require panel operation.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import mido

from dr5_sysex import (
    ADDR_MIDI_THRU_SWITCH,
    ADDR_SEQUENCE_DATA,
    SIZE_SEQUENCE_DATA,
    build_dt1,
    build_rq1,
)

# Observed real dumps: ~44981-45020 bytes across ~180-183 messages.
# Anything much smaller almost certainly means the transfer was cut off.
MIN_EXPECTED_BYTES = 40000


def backup(port: str, outfile: str, quiet_timeout: float, max_duration: float) -> int:
    buf = bytearray()

    with mido.open_input(port) as inport, mido.open_output(port) as outport:
        print("Priming: MIDI Thru OFF...", file=sys.stderr)
        # The captured Dr5Edit trace sent this RQ1 twice before the DT1 write;
        # a single request appeared sufficient in testing, but the duplicate
        # is kept here to match the known-working sequence exactly.
        rq1_thru = build_rq1(ADDR_MIDI_THRU_SWITCH, bytes([0x00, 0x00, 0x01]))
        outport.send(mido.Message("sysex", data=rq1_thru))
        time.sleep(0.01)
        outport.send(mido.Message("sysex", data=rq1_thru))
        time.sleep(0.01)
        dt1_thru = build_dt1(ADDR_MIDI_THRU_SWITCH, bytes([0x00]))
        outport.send(mido.Message("sysex", data=dt1_thru))
        time.sleep(0.01)

        print("Requesting Sequence-data (RQ1 20 00 00, size 01 00 00)...", file=sys.stderr)
        rq1_seq = build_rq1(ADDR_SEQUENCE_DATA, SIZE_SEQUENCE_DATA)
        outport.send(mido.Message("sysex", data=rq1_seq))

        print(f"Listening (quiet timeout {quiet_timeout}s, max {max_duration}s)...", file=sys.stderr)
        start = time.monotonic()
        last_data = time.monotonic()
        msg_count = 0

        while True:
            now = time.monotonic()
            if now - start > max_duration:
                print("Max duration reached, stopping.", file=sys.stderr)
                break
            if now - last_data > quiet_timeout and msg_count > 0:
                print("Quiet timeout reached, transfer complete.", file=sys.stderr)
                break
            got_any = False
            for msg in inport.iter_pending():
                if msg.type == "sysex":
                    block = bytes([0xF0]) + bytes(msg.data) + bytes([0xF7])
                    buf += block
                    msg_count += 1
                    got_any = True
                    if msg_count % 50 == 0:
                        print(f"  received msg #{msg_count}, {len(buf)} bytes so far", file=sys.stderr)
            if got_any:
                last_data = time.monotonic()
            time.sleep(0.002)

    Path(outfile).write_bytes(bytes(buf))
    print(f"Done. {len(buf)} bytes / {msg_count} messages -> {outfile}", file=sys.stderr)

    if msg_count == 0:
        print("ERROR: no data received -- check MIDI connections and --port.", file=sys.stderr)
        return 1
    if len(buf) < MIN_EXPECTED_BYTES:
        print(
            f"WARNING: only {len(buf)} bytes received, expected at least "
            f"{MIN_EXPECTED_BYTES} for a full Sequence-data dump -- the "
            "transfer may have been interrupted. Saved anyway; inspect "
            "before trusting this backup.",
            file=sys.stderr,
        )
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "outfile", nargs="?", default=None, help="output .syx path (default: dr5_backup_<timestamp>.syx)"
    )
    parser.add_argument(
        "--port",
        required=True,
        help="MIDI port name (both directions); list available ports with "
        '`python -c "import mido; print(mido.get_input_names())"`',
    )
    parser.add_argument(
        "--quiet-timeout",
        type=float,
        default=3.0,
        help="seconds of silence after which the transfer is considered done",
    )
    parser.add_argument("--max-duration", type=float, default=60.0, help="hard timeout in seconds")
    args = parser.parse_args()

    outfile = args.outfile or time.strftime("dr5_backup_%Y%m%d_%H%M%S.syx")
    return backup(args.port, outfile, args.quiet_timeout, args.max_duration)


if __name__ == "__main__":
    raise SystemExit(main())
