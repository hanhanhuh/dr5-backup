# dr5-backup

Backup and restore for the Boss DR-5 drum machine's pattern data, over
MIDI, without needing Dr5Edit or any Windows software.

The DR-5 Owner's Manual states that MIDI bulk dumps require front-panel
operation to arm. In practice, requesting the data over MIDI (a plain
Roland RQ1 message) is enough — no front-panel arming needed. Details
and the exact byte sequence are documented in the package's own
docstrings (`src/dr5_backup/`).

## What it does

- `dr5-backup` — requests the DR-5's Sequence-data (all 400 preset +
  programmable patterns) and saves it to a `.syx` file.
- `dr5-restore` — sends a previously-saved `.syx` file back to the
  DR-5.

**Both MIDI In and MIDI Out must be connected between your computer and
the DR-5** — In to receive the backup data, Out to send the priming and
request messages. A single one-directional MIDI cable is not enough
for either command.

**Scope**: this backs up pattern/sequence data only (address region
`20 00 00`), not kit names, system settings, or songs outside that
region.

## Install

```bash
uv sync
```

## Usage

```bash
# find your MIDI port name
uv run python -c "import mido; print(mido.get_input_names())"

# back up (writes dr5_backup_<timestamp>.syx by default)
uv run dr5-backup --port "your port name here"

# restore
uv run dr5-restore dr5_backup_20250101_120000.syx --port "your port name here"
```

`--port` is required for both commands.

## Development

```bash
uv sync --group dev
uv run pre-commit install
```

Runs `ruff` (lint + format) and `mypy` (strict) on every commit.

```bash
uv run pytest
```

Tests cover the pure protocol-framing logic (`tests/test_protocol.py`)
and the backup/restore orchestration logic against a fake MIDI
transport (`tests/test_backup.py`, `tests/test_restore.py`) — no real
DR-5 hardware needed to run them.

## License

MIT — see [LICENSE](LICENSE).
