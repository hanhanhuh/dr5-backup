"""Command-line entry points for dr5-backup and dr5-restore."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

from dr5_backup.backup import IncompleteTransferError, perform_backup
from dr5_backup.protocol import parse_blocks
from dr5_backup.restore import perform_restore
from dr5_backup.transport import MidiTransport

logger = logging.getLogger(__name__)

_PORT_HELP = (
    "MIDI port name (both directions); list available ports with "
    '`python -c "import mido; print(mido.get_input_names())"`'
)


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)


def backup_main() -> int:
    """CLI entry point for `dr5-backup`."""
    _configure_logging()

    parser = argparse.ArgumentParser(
        description=(
            "Request and save the Boss DR-5's Sequence-data over MIDI -- no front-panel interaction needed."
        )
    )
    parser.add_argument(
        "outfile", nargs="?", default=None, help="output .syx path (default: dr5_backup_<timestamp>.syx)"
    )
    parser.add_argument("--port", required=True, help=_PORT_HELP)
    parser.add_argument(
        "--quiet-timeout",
        type=float,
        default=3.0,
        help="seconds of silence after which the transfer is considered done",
    )
    parser.add_argument("--max-duration", type=float, default=60.0, help="hard timeout in seconds")
    args = parser.parse_args()

    outfile = args.outfile or time.strftime("dr5_backup_%Y%m%d_%H%M%S.syx")

    try:
        with MidiTransport(args.port) as transport:
            data = perform_backup(transport, args.quiet_timeout, args.max_duration)
    except IncompleteTransferError as exc:
        if exc.partial_data:
            Path(outfile).write_bytes(exc.partial_data)
            logger.warning(
                "%s. Saved %d partial bytes to %s for inspection.", exc, len(exc.partial_data), outfile
            )
        else:
            logger.error("%s", exc)
        return 1

    Path(outfile).write_bytes(data)
    logger.info("Done. %d bytes -> %s", len(data), outfile)
    return 0


def restore_main() -> int:
    """CLI entry point for `dr5-restore`."""
    _configure_logging()

    parser = argparse.ArgumentParser(
        description=(
            "Send a previously-saved Sequence-data .syx backup to the Boss "
            "DR-5 over MIDI -- no front-panel interaction needed."
        )
    )
    parser.add_argument("infile", help="path to a .syx backup previously made by dr5-backup")
    parser.add_argument("--port", required=True, help=_PORT_HELP)
    args = parser.parse_args()

    data = Path(args.infile).read_bytes()
    blocks = parse_blocks(data)
    logger.info("Parsed %d SysEx blocks, %d bytes", len(blocks), sum(len(b) for b in blocks))

    with MidiTransport(args.port) as transport:
        perform_restore(transport, blocks)

    return 0
