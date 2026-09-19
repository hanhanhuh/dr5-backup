"""Tests for dr5_backup.backup -- orchestration logic, no hardware needed."""

import pytest

from dr5_backup.backup import IncompleteTransferError, perform_backup
from tests.fake_transport import FakeTransport


def test_sends_priming_then_request_before_listening() -> None:
    response = [b"\xf0" + bytes(250) + b"\xf7"] * 180  # comfortably over MIN_EXPECTED_BYTES
    transport = FakeTransport(response_blocks=response)

    perform_backup(transport, quiet_timeout=1.0, max_duration=5.0)

    # Priming: RQ1 (MIDI Thru) x2, then DT1 (MIDI Thru OFF), then RQ1 (Sequence-data request).
    assert len(transport.sent) == 4
    assert transport.sent[0] == transport.sent[1]  # the documented duplicate RQ1


def test_returns_concatenated_response_bytes() -> None:
    response = [b"\xf0" + bytes([i]) * 300 + b"\xf7" for i in range(150)]
    transport = FakeTransport(response_blocks=response)

    data = perform_backup(transport, quiet_timeout=1.0, max_duration=5.0)

    assert data == b"".join(response)


def test_raises_on_no_data() -> None:
    transport = FakeTransport(response_blocks=[])

    with pytest.raises(IncompleteTransferError) as exc_info:
        perform_backup(transport, quiet_timeout=1.0, max_duration=5.0)

    assert exc_info.value.partial_data == b""


def test_raises_on_truncated_transfer_but_preserves_partial_data() -> None:
    response = [b"\xf0short\xf7"]
    transport = FakeTransport(response_blocks=response)

    with pytest.raises(IncompleteTransferError) as exc_info:
        perform_backup(transport, quiet_timeout=1.0, max_duration=5.0)

    assert exc_info.value.partial_data == b"".join(response)
