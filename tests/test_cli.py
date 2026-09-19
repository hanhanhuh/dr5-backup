"""Tests for dr5_backup.cli -- port resolution logic."""

from unittest.mock import patch

import pytest

from dr5_backup.cli import NoMidiPortError, _resolve_port


def test_explicit_port_is_returned_unchanged() -> None:
    assert _resolve_port("my port") == "my port"


def test_no_ports_raises() -> None:
    with (
        patch("dr5_backup.cli.mido.get_input_names", return_value=[]),
        patch("dr5_backup.cli.mido.get_output_names", return_value=[]),
        pytest.raises(NoMidiPortError),
    ):
        _resolve_port(None)


def test_single_bidirectional_port_is_used_automatically() -> None:
    with (
        patch("dr5_backup.cli.mido.get_input_names", return_value=["io|2:io|2 MIDI 1 20:0"]),
        patch("dr5_backup.cli.mido.get_output_names", return_value=["io|2:io|2 MIDI 1 20:0"]),
    ):
        assert _resolve_port(None) == "io|2:io|2 MIDI 1 20:0"


def test_input_only_port_is_not_a_candidate() -> None:
    with (
        patch("dr5_backup.cli.mido.get_input_names", return_value=["in-only", "both"]),
        patch("dr5_backup.cli.mido.get_output_names", return_value=["both", "out-only"]),
    ):
        assert _resolve_port(None) == "both"


def test_multiple_ports_prompts_and_returns_chosen_one() -> None:
    with (
        patch("dr5_backup.cli.mido.get_input_names", return_value=["port-a", "port-b"]),
        patch("dr5_backup.cli.mido.get_output_names", return_value=["port-a", "port-b"]),
        patch("builtins.input", return_value="2"),
    ):
        assert _resolve_port(None) == "port-b"


def test_multiple_ports_reprompts_on_invalid_input() -> None:
    with (
        patch("dr5_backup.cli.mido.get_input_names", return_value=["port-a", "port-b"]),
        patch("dr5_backup.cli.mido.get_output_names", return_value=["port-a", "port-b"]),
        patch("builtins.input", side_effect=["nonsense", "99", "1"]),
    ):
        assert _resolve_port(None) == "port-a"
