"""Tests for dr5_backup.protocol -- pure functions, no hardware needed."""

import pytest

from dr5_backup.protocol import (
    CMD_DT1,
    CMD_RQ1,
    DEVICE_ID,
    EOX,
    MANUFACTURER_ID,
    MODEL_ID,
    SOX,
    build_dt1,
    build_rq1,
    checksum,
    parse_blocks,
)


class TestChecksum:
    def test_all_zero_payload_is_zero(self) -> None:
        assert checksum(bytes([0x00, 0x00, 0x00])) == 0x00

    def test_matches_known_real_capture(self) -> None:
        # From a real captured RQ1 for the MIDI Thru switch:
        # f0 41 09 65 11 10 00 0f 00 00 01 60 f7
        body = bytes([0x10, 0x00, 0x0F, 0x00, 0x00, 0x01])
        assert checksum(body) == 0x60

    def test_result_is_always_7bit(self) -> None:
        for n in range(0, 256, 17):
            assert 0 <= checksum(bytes([n])) <= 0x7F


class TestBuildRq1:
    def test_matches_known_real_capture(self) -> None:
        address = bytes([0x10, 0x00, 0x0F])
        size = bytes([0x00, 0x00, 0x01])
        payload = build_rq1(address, size)
        assert payload == bytes(
            [MANUFACTURER_ID, DEVICE_ID, MODEL_ID, CMD_RQ1, 0x10, 0x00, 0x0F, 0x00, 0x00, 0x01, 0x60]
        )

    def test_length_is_header_plus_address_plus_size_plus_checksum(self) -> None:
        payload = build_rq1(bytes(3), bytes(3))
        assert len(payload) == 4 + 3 + 3 + 1


class TestBuildDt1:
    def test_matches_known_real_capture(self) -> None:
        # f0 41 09 65 12 10 00 0f 00 61 f7 -- MIDI Thru OFF write
        address = bytes([0x10, 0x00, 0x0F])
        data = bytes([0x00])
        payload = build_dt1(address, data)
        assert payload == bytes([MANUFACTURER_ID, DEVICE_ID, MODEL_ID, CMD_DT1, 0x10, 0x00, 0x0F, 0x00, 0x61])

    def test_length_is_header_plus_address_plus_data_plus_checksum(self) -> None:
        payload = build_dt1(bytes(3), bytes(10))
        assert len(payload) == 4 + 3 + 10 + 1


class TestParseBlocks:
    def test_single_block(self) -> None:
        data = bytes([SOX, 0x01, 0x02, EOX])
        assert parse_blocks(data) == [data]

    def test_multiple_blocks(self) -> None:
        block1 = bytes([SOX, 0x01, EOX])
        block2 = bytes([SOX, 0x02, 0x03, EOX])
        assert parse_blocks(block1 + block2) == [block1, block2]

    def test_empty_input_returns_empty_list(self) -> None:
        assert parse_blocks(b"") == []

    def test_missing_leading_sox_raises(self) -> None:
        with pytest.raises(ValueError, match="expected"):
            parse_blocks(bytes([0x01, 0x02, EOX]))

    def test_unterminated_block_raises(self) -> None:
        with pytest.raises(ValueError, match="unterminated"):
            parse_blocks(bytes([SOX, 0x01, 0x02]))

    def test_round_trips_output_of_build_rq1_and_build_dt1(self) -> None:
        rq1 = bytes([SOX]) + build_rq1(bytes([0x10, 0x00, 0x0F]), bytes([0x00, 0x00, 0x01])) + bytes([EOX])
        dt1 = bytes([SOX]) + build_dt1(bytes([0x10, 0x00, 0x0F]), bytes([0x00])) + bytes([EOX])
        blocks = parse_blocks(rq1 + dt1)
        assert blocks == [rq1, dt1]
