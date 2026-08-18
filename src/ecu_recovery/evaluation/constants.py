"""Classify the evidence behind each declared fixture constant.

This is reported, never gated. `GHIDRA-001` recovers a constant only when an
instruction operand carries it or a defined data object that code refers to
holds it. Some declared constants satisfy neither, for reasons that belong to
the compiler rather than the analyzer: zero is materialised with `xor`, a range
check is folded into a comparison against a different number, and a table
indexed by a computed offset gets a reference to its base and to no element.

Turning that into a pass/fail threshold would score the corpus, not the tool,
and the only way to make such a gate green would be to loosen what counts as
evidence until matching bytes qualify. So the four classes below are published
side by side and the reader draws their own conclusion.

`reachable-table-data` is the interesting middle case, and it is deliberately
*not* counted as recovery: the value is in a region whose address an
instruction loads, so `read_bytes` reaches it deterministically, but no operand
and no referenced data object names it.
"""

from __future__ import annotations

import struct
from typing import Any

from ..analysis.base import MAX_READ_BYTES, StaticAnalysisSession
from ..analysis.models import CONSTANT_KIND_DATA, CONSTANT_KIND_OPERAND
from .groundtruth import GroundTruth
from .models import (
    EVIDENCE_OPERAND,
    EVIDENCE_REFERENCED_DATA,
    EVIDENCE_TABLE_DATA,
    EVIDENCE_UNSUPPORTED,
    ConstantEvidence,
    ConstantMetrics,
)
from .scoring import parse_address

#: docs/synthetic-lab.md records that dataset v1 tables are emitted as int32.
#: This is a documented property of the corpus, not a hint taken from the
#: answer key, and it is the only width scanned.
TABLE_ELEMENT_BYTES = 4


def candidate_data_regions(
    payload: dict[str, Any], session: StaticAnalysisSession
) -> tuple[tuple[str, int, int], ...]:
    """Regions a program takes the address of and stores no code in.

    The reference requirement is what keeps the Mach-O header out. The header is
    mapped executable and is full of small integers, and without this test every
    fixture would report a pile of "reachable" constants that no instruction
    ever loads.
    """
    function_starts = {parse_address(item["start_address"]) for item in payload["functions"]}
    regions: list[tuple[str, int, int]] = []
    for region in payload["memory_regions"]:
        start = parse_address(region["start_address"])
        end = parse_address(region["end_address"])
        if not region["initialized"] or not region["readable"]:
            continue
        if any(start <= address <= end for address in function_starts):
            continue
        references = session.get_cross_references(start)
        if not any(item.from_function_id is not None for item in references):
            continue
        regions.append((str(region["name"]), start, end))
    return tuple(regions)


def _read_region(session: StaticAnalysisSession, start: int, end: int) -> bytes:
    """Read a whole region through the bounded byte window."""
    collected = bytearray()
    address = start
    while address <= end:
        length = min(MAX_READ_BYTES, end - address + 1)
        window = session.read_bytes(address, length)
        if window.length == 0:
            break
        collected.extend(bytes.fromhex(window.data_hex))
        address += window.length
    return bytes(collected)


def scan_region_for_value(
    data: bytes, base: int, value: int, little_endian: bool
) -> tuple[int, ...]:
    """Aligned int32 slots in `data` holding `value`, as absolute addresses."""
    order = "<" if little_endian else ">"
    hits: list[int] = []
    for offset in range(0, len(data) - TABLE_ELEMENT_BYTES + 1, TABLE_ELEMENT_BYTES):
        chunk = data[offset : offset + TABLE_ELEMENT_BYTES]
        signed = struct.unpack(f"{order}i", chunk)[0]
        unsigned = struct.unpack(f"{order}I", chunk)[0]
        if value in (signed, unsigned):
            hits.append(base + offset)
    return tuple(hits)


def classify_constants(
    session: StaticAnalysisSession, payload: dict[str, Any], truth: GroundTruth
) -> ConstantMetrics:
    """Sort every declared constant into exactly one evidence class."""
    little_endian = str(payload["program"]["endian"]) != "big"
    regions = candidate_data_regions(payload, session)
    region_bytes = {
        name: (start, _read_region(session, start, end)) for name, start, end in regions
    }

    entries: list[ConstantEvidence] = []
    for value in truth.expected_constants:
        matches = session.search_constant(value)
        operands = tuple(
            sorted(item.address for item in matches if item.kind == CONSTANT_KIND_OPERAND)
        )
        data = tuple(sorted(item.address for item in matches if item.kind == CONSTANT_KIND_DATA))
        if operands:
            entries.append(
                ConstantEvidence(
                    value=value,
                    evidence=EVIDENCE_OPERAND,
                    addresses=operands,
                    detail=f"{len(operands)} instruction operand(s)",
                )
            )
            continue
        if data:
            entries.append(
                ConstantEvidence(
                    value=value,
                    evidence=EVIDENCE_REFERENCED_DATA,
                    addresses=data,
                    detail=f"{len(data)} code-referenced data object(s)",
                )
            )
            continue
        reachable: list[int] = []
        found_in: list[str] = []
        for name, (base, blob) in sorted(region_bytes.items()):
            hits = scan_region_for_value(blob, base, value, little_endian)
            if hits:
                reachable.extend(hits)
                found_in.append(name)
        if reachable:
            entries.append(
                ConstantEvidence(
                    value=value,
                    evidence=EVIDENCE_TABLE_DATA,
                    addresses=tuple(sorted(reachable)),
                    detail=(
                        f"int32 slot in code-referenced region {', '.join(found_in)}; "
                        "reachable through read_bytes but named by no operand or data object"
                    ),
                )
            )
            continue
        entries.append(
            ConstantEvidence(
                value=value,
                evidence=EVIDENCE_UNSUPPORTED,
                detail="no operand, no referenced data object, and no code-referenced region slot",
            )
        )
    return ConstantMetrics(entries=tuple(entries))
