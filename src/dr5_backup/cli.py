"""Command-line entry points for dr5-backup and dr5-restore."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import mido

from dr5_backup.backup import IncompleteTransferError, perform_backup
from dr5_backup.protocol import parse_blocks
from dr5_backup.restore import perform_restore
from dr5_backup.transport import MidiTransport

logger = logging.getLogger(__name__)

_PORT_HELP = "MIDI port name (both directions); omit to be prompted if more than one is available"


class NoMidiPortError(RuntimeError):
    """Raised when no MIDI port is available for both input and output."""


def _configure_logging() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s", stream=sys.stderr)


def _resolve_port(requested: str | None) -> str:
    """Resolve the MIDI port to use, prompting the user if necessary.

    A usable port must appear in both mido's input and output port
    lists, since the DR-5's single bidirectional interface is opened
    both ways under the same name.

    Args:
        requested: The `--port` value the user passed, or None if they
            didn't pass one.

    Returns:
        The port name to open.

    Raises:
        NoMidiPortError: If no port is available for both directions.
    """
    if requested is not None:
        return requested

    input_names: set[str] = set(mido.get_input_names())
    output_names: set[str] = set(mido.get_output_names())
    candidates: list[str] = sorted(input_names & output_names)

    if not candidates:
        raise NoMidiPortError(
            "no MIDI port found that supports both input and output -- check your MIDI interface is connected"
        )
    if len(candidates) == 1:
        logger.info("Using the only available MIDI port: %s", candidates[0])
        return candidates[0]

    print("Multiple MIDI ports available:", file=sys.stderr)
    for i, name in enumerate(candidates, start=1):
        print(f"  [{i}] {name}", file=sys.stderr)
    while True:
        choice = input(f"Select a port [1-{len(candidates)}]: ").strip()
        if choice.isdigit() and 1 <= int(choice) <= len(candidates):
            return candidates[int(choice) - 1]
        print("Invalid choice, try again.", file=sys.stderr)


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
    parser.add_argument("--port", help=_PORT_HELP)
    parser.add_argument(
        "--quiet-timeout",
        type=float,
        default=3.0,
        help="seconds of silence after which the transfer is considered done",
    )
    parser.add_argument("--max-duration", type=float, default=60.0, help="hard timeout in seconds")
    args = parser.parse_args()

    try:
        port = _resolve_port(args.port)
    except NoMidiPortError as exc:
        logger.error("%s", exc)
        return 1

    outfile = args.outfile or time.strftime("dr5_backup_%Y%m%d_%H%M%S.syx")

    try:
        with MidiTransport(port) as transport:
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
    parser.add_argument("--port", help=_PORT_HELP)
    args = parser.parse_args()

    try:
        port = _resolve_port(args.port)
    except NoMidiPortError as exc:
        logger.error("%s", exc)
        return 1

    data = Path(args.infile).read_bytes()
    blocks = parse_blocks(data)
    logger.info("Parsed %d SysEx blocks, %d bytes", len(blocks), sum(len(b) for b in blocks))

    with MidiTransport(port) as transport:
        perform_restore(transport, blocks)

    return 0
