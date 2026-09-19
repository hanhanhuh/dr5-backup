"""Tests for dr5_backup.restore -- orchestration logic, no hardware needed."""

from dr5_backup.protocol import EOX, SOX, build_dt1, build_rq1
from dr5_backup.restore import perform_restore
from tests.fake_transport import FakeTransport


def test_sends_priming_before_blocks() -> None:
    transport = FakeTransport()
    blocks = [bytes([SOX, 0xAA, EOX]), bytes([SOX, 0xBB, EOX])]

    perform_restore(transport, blocks)

    # Priming: RQ1 (MIDI Thru), DT1 (MIDI Thru OFF), then the two blocks' stripped payloads.
    assert len(transport.sent) == 4
    assert transport.sent[2] == bytes([0xAA])
    assert transport.sent[3] == bytes([0xBB])


def test_priming_matches_captured_dr5edit_sequence() -> None:
    transport = FakeTransport()

    perform_restore(transport, blocks=[])

    expected_rq1 = build_rq1(bytes([0x10, 0x00, 0x0F]), bytes([0x00, 0x00, 0x01]))
    expected_dt1 = build_dt1(bytes([0x10, 0x00, 0x0F]), bytes([0x00]))
    assert transport.sent == [expected_rq1, expected_dt1]


def test_strips_f0_f7_framing_before_sending() -> None:
    transport = FakeTransport()
    block = bytes([SOX, 0x01, 0x02, 0x03, EOX])

    perform_restore(transport, blocks=[block])

    sent_block = transport.sent[-1]
    assert sent_block == bytes([0x01, 0x02, 0x03])
    assert SOX not in sent_block
    assert EOX not in sent_block


def test_sends_all_blocks_in_order() -> None:
    transport = FakeTransport()
    blocks = [bytes([SOX, i, EOX]) for i in range(10)]

    perform_restore(transport, blocks)

    sent_payloads = transport.sent[2:]  # skip the two priming messages
    assert sent_payloads == [bytes([i]) for i in range(10)]
