"""Non-executing firmware intake and deterministic binary profiling."""

from __future__ import annotations

import hashlib
import math
from collections import Counter
from pathlib import Path

from .models import BinaryProfile, RepeatedRegion

MAX_FIRMWARE_BYTES = 64 * 1024 * 1024
SUPPORTED_SUFFIXES = {".bin", ".rom", ".img"}


class IntakeError(ValueError):
    pass


def _entropy(counts: Counter[int], size: int) -> float:
    if size == 0:
        return 0.0
    return -sum((count / size) * math.log2(count / size) for count in counts.values())


def _repeated_regions(
    data: bytes, block_size: int = 256, limit: int = 32
) -> tuple[RepeatedRegion, ...]:
    """Find exact repeated blocks without quadratic pairwise comparison."""
    first_seen: dict[bytes, int] = {}
    repeats: list[RepeatedRegion] = []
    for offset in range(0, len(data) - block_size + 1, block_size):
        block = data[offset : offset + block_size]
        if block in first_seen:
            repeats.append(RepeatedRegion(first_seen[block], offset, block_size))
            if len(repeats) == limit:
                break
        else:
            first_seen[block] = offset
    return tuple(repeats)


def profile_binary(
    firmware_path: str | Path,
    *,
    processor: str | None = None,
    byte_order: str | None = None,
) -> BinaryProfile:
    path = Path(firmware_path).expanduser().resolve()
    if not path.is_file():
        raise IntakeError(f"firmware is not a regular file: {path}")
    if path.suffix.lower() not in SUPPORTED_SUFFIXES:
        raise IntakeError(
            f"unsupported firmware format {path.suffix or '(none)'}; "
            f"supported: {', '.join(sorted(SUPPORTED_SUFFIXES))}"
        )
    size = path.stat().st_size
    if size == 0:
        raise IntakeError("firmware image is empty")
    if size > MAX_FIRMWARE_BYTES:
        raise IntakeError(f"firmware exceeds the {MAX_FIRMWARE_BYTES} byte intake limit")
    if byte_order not in {None, "big", "little"}:
        raise IntakeError("byte order must be 'big' or 'little'")

    # Reading bytes is the only interaction with the firmware. Nothing is loaded
    # as executable code or passed to a shell.
    data = path.read_bytes()
    counts = Counter(data)
    fill_bytes = {value: counts[value] for value in (0x00, 0xFF) if counts[value]}
    return BinaryProfile(
        path=str(path),
        filename=path.name,
        size=size,
        sha256=hashlib.sha256(data).hexdigest(),
        sha1=hashlib.sha1(data).hexdigest(),
        md5=hashlib.md5(data, usedforsecurity=False).hexdigest(),
        entropy=_entropy(counts, size),
        byte_order=byte_order,
        processor=processor,
        fill_bytes=fill_bytes,
        repeated_regions=_repeated_regions(data),
    )
