import hashlib

import pytest

from ecu_recovery.intake import IntakeError, profile_binary


def test_profiles_binary_without_execution(tmp_path):
    firmware = tmp_path / "fixture.bin"
    data = bytes(range(256)) * 2 + b"\xff" * 256
    firmware.write_bytes(data)

    profile = profile_binary(firmware, processor="test-cpu", byte_order="big")

    assert profile.size == len(data)
    assert profile.sha256 == hashlib.sha256(data).hexdigest()
    assert profile.processor == "test-cpu"
    assert profile.byte_order == "big"
    assert profile.fill_bytes[0xFF] == 258
    assert profile.repeated_regions[0].first_offset == 0
    assert profile.repeated_regions[0].second_offset == 256


def test_rejects_unknown_format(tmp_path):
    firmware = tmp_path / "fixture.exe"
    firmware.write_bytes(b"not executable by this project")

    with pytest.raises(IntakeError, match="unsupported firmware format"):
        profile_binary(firmware)


def test_rejects_empty_image(tmp_path):
    firmware = tmp_path / "fixture.bin"
    firmware.write_bytes(b"")

    with pytest.raises(IntakeError, match="empty"):
        profile_binary(firmware)

