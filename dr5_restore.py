#!/usr/bin/env python3
"""Restore a Sequence-data .syx backup to the Boss DR-5 -- no front-panel
interaction needed.

Usage:
    dr5-restore backup.syx [--port PORT]

The message sequence was captured from a real Dr5Edit Upload over an
ALSA sequencer tap; see dr5_sysex.py for the byte-level details. The
MIDI-Thru-off priming step and the ~3ms inter-message pacing are both
required -- without them the DR-5 gets stuck on its "RxSys" screen.
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

import mido

from dr5_sysex import ADDR_MIDI_THRU_SWITCH, build_dt1, build_rq1, parse_blocks


def restore(port: str, infile: str) -> int:
    data = Path(infile).read_bytes()
    blocks = parse_blocks(data)
    print(f"Parsed {len(blocks)} SysEx blocks, {sum(len(b) for b in blocks)} bytes", file=sys.stderr)

    with mido.open_output(port) as outport:
        print("Priming: MIDI Thru OFF (RQ1 + DT1 at 10 00 0F)...", file=sys.stderr)
        rq1_thru = build_rq1(ADDR_MIDI_THRU_SWITCH, bytes([0x00, 0x00, 0x01]))
        outport.send(mido.Message("sysex", data=rq1_thru))
        time.sleep(0.019)
        dt1_thru = build_dt1(ADDR_MIDI_THRU_SWITCH, bytes([0x00]))
        outport.send(mido.Message("sysex", data=dt1_thru))
        time.sleep(0.009)

        print("Streaming captured blocks at ~3ms pacing...", file=sys.stderr)
        for idx, block in enumerate(blocks):
            msg = mido.Message("sysex", data=block[1:-1])
            outport.send(msg)
            if idx % 50 == 0:
                print(f"  sent block {idx + 1}/{len(blocks)} ({len(block)} bytes)", file=sys.stderr)
            time.sleep(0.003)

    print(f"Done. Sent {len(blocks)} blocks.", file=sys.stderr)
    print("NOTE: MIDI Thru left OFF -- reset manually if needed "
          "(Utility mode > System Setup).", file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("infile", help="path to a .syx backup previously made by dr5-backup")
    parser.add_argument("--port", required=True,
                         help="MIDI port name (both directions); list available ports with "
                              "`python -c \"import mido; print(mido.get_input_names())\"`")
    args = parser.parse_args()
    return restore(args.port, args.infile)


if __name__ == "__main__":
    raise SystemExit(main())
