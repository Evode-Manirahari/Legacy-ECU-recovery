"""Collect facts through the bounded tool layer, and only through it.

Every call in this module goes via `ToolRegistry.call`. There is no analysis
session here, no Ghidra, no filesystem, no shell, no network. That is the whole
point: if the agent could reach around the tool surface, the bounds measured by
TOOLS-001 would describe something the agent does not actually use.

A refused tool call becomes a recorded refusal, never a fact. That distinction
is the one most likely to be got wrong under pressure to produce an answer: an
error object read as a finding is how a system starts asserting things no tool
ever said.
"""

from __future__ import annotations

from typing import Any

from ..tools import REGISTRY, ToolContext, ToolRegistry
from .models import Fact, FactSheet, InvestigationBudget, canonical_digest


def _fact_id(index: int) -> str:
    return f"F{index:03d}"


def _summarize_function(record: dict[str, Any]) -> str:
    return (
        f"function {record['id']} named {record['name']}, "
        f"{record['size']} bytes, spanning {record['start_address']}-{record['end_address']}, "
        f"{len(record['callers'])} caller(s) and {len(record['callees'])} callee(s)"
    )


def gather_facts(
    context: ToolContext,
    subject: str,
    budget: InvestigationBudget | None = None,
    registry: ToolRegistry = REGISTRY,
) -> FactSheet:
    """Build the fact sheet for one function.

    Deterministic: the same session and subject produce the same sheet, in the
    same order, with the same fact ids. That matters because a citation names a
    fact id, and an id that moved between runs would make transcripts
    uncomparable.
    """
    budget = budget or InvestigationBudget()
    facts: list[Fact] = []
    refusals: list[tuple[str, str]] = []

    def record(tool: str, arguments: dict[str, Any], summary: str, payload: dict[str, Any]) -> None:
        facts.append(
            Fact(
                id=_fact_id(len(facts)),
                tool=tool,
                arguments=dict(arguments),
                subject=subject,
                summary=summary,
                # The digest is what makes a citation checkable later. Without
                # it, replay can only prove the call still succeeds, which is
                # not the same as proving it still says the same thing.
                result_digest=canonical_digest(payload),
            )
        )

    def call(tool: str, arguments: dict[str, Any]) -> dict[str, Any] | None:
        result = registry.call(tool, context, arguments)
        if not result.ok or result.data is None:
            error = result.error
            refusals.append((tool, "unknown error" if error is None else error.code))
            return None
        return result.data

    summary_args: dict[str, Any] = {}
    summary = call("binary_summary", summary_args)
    if summary is not None:
        program = summary["program"]
        record(
            "binary_summary",
            summary_args,
            f"program {program['program_name']} is {program['language_id']} "
            f"({program['processor']}, {program['endian']}-endian, "
            f"{program['address_size_bits']}-bit) with {summary['function_count']} functions "
            f"and {summary['analysis_warning_count']} analysis warning(s)",
            summary,
        )

    inspect_args = {"function_id": subject, "instruction_limit": budget.max_instructions}
    inspected = call("inspect_function", inspect_args)
    if inspected is not None:
        record(
            "inspect_function",
            inspect_args,
            _summarize_function(inspected["function"]),
            inspected,
        )
        listing = ", ".join(
            f"{item['address']} {item['mnemonic']} {item['operands']}".strip()
            for item in inspected["instructions"]
        )
        record(
            "inspect_function",
            inspect_args,
            f"disassembly of {subject}"
            + (" (truncated)" if inspected["instructions_truncated"] else "")
            + f": {listing}",
            inspected,
        )

    callers_args = {"function_id": subject, "limit": budget.max_callers}
    callers = call("get_callers", callers_args)
    if callers is not None:
        names = ", ".join(item["id"] for item in callers["callers"]) or "none"
        record("get_callers", callers_args, f"{subject} is called by: {names}", callers)

    callees_args = {"function_id": subject, "limit": budget.max_callees}
    callees = call("get_callees", callees_args)
    if callees is not None:
        names = ", ".join(item["id"] for item in callees["callees"]) or "none"
        record("get_callees", callees_args, f"{subject} calls: {names}", callees)

    if budget.decompile:
        decompile_args = {"function_id": subject}
        decompiled = call("decompile_function", decompile_args)
        if decompiled is not None:
            if decompiled["success"]:
                record(
                    "decompile_function",
                    decompile_args,
                    f"decompilation of {subject}"
                    + (" (truncated)" if decompiled["text_truncated"] else "")
                    + f": {decompiled['text']}",
                    decompiled,
                )
            else:
                # A decompiler that gave up is information, but it is not a fact
                # about the program. Record it where refusals live.
                refusals.append(("decompile_function", "decompilation_failed"))

    return FactSheet(subject=subject, facts=tuple(facts), refusals=tuple(refusals))
