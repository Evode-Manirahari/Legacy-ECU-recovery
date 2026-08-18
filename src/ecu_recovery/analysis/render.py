"""Human-readable rendering of a `BinaryAnalysis`.

The node contract names six output categories for `ecu-recovery analyze`:
binary metadata, memory map, function count, function records, call
relationships, and analysis warnings. All six are produced here, in the
analysis package, so the command-line layer only has to print the result.

Rendering lives beside the records rather than in the CLI because the same
summary belongs in a report, a log, and a terminal, and three copies of it would
drift apart.
"""

from __future__ import annotations

from .models import BinaryAnalysis, render_address

#: Terminal output is read, not parsed. Long lists are capped and the omission
#: is stated, because a truncated list that does not say so is a lie.
DEFAULT_FUNCTION_LIMIT = 25
DEFAULT_WARNING_LIMIT = 25


def _tail(shown: int, total: int, noun: str) -> list[str]:
    if total <= shown:
        return []
    return [f"  ... {total - shown} further {noun} in the serialized export"]


def render_analysis_summary(
    analysis: BinaryAnalysis,
    function_limit: int = DEFAULT_FUNCTION_LIMIT,
    warning_limit: int = DEFAULT_WARNING_LIMIT,
) -> str:
    """Render every output category the node contract requires."""
    program = analysis.program
    lines: list[str] = ["binary metadata:"]
    lines.extend(
        [
            f"  source            {program.source_path}",
            f"  sha256            {program.executable_sha256}",
            f"  format            {program.executable_format}",
            f"  language          {program.language_id}",
            f"  compiler spec     {program.compiler_spec_id}",
            f"  processor         {program.processor} {program.endian}-endian "
            f"{program.address_size_bits}-bit",
            f"  image base        {render_address(program.image_base)}",
            "  entry points      "
            + (", ".join(render_address(item) for item in program.entry_points) or "none"),
            f"  engine            {program.engine} {program.engine_version}",
            f"  auto-analysis     {'ran' if program.auto_analysis_ran else 'skipped'}",
        ]
    )

    lines.append("")
    lines.append(f"memory map: {len(analysis.memory_regions)} region(s)")
    for region in analysis.memory_regions:
        flags = "".join(
            (
                "r" if region.readable else "-",
                "w" if region.writable else "-",
                "x" if region.executable else "-",
                "i" if region.initialized else "-",
            )
        )
        lines.append(
            f"  {render_address(region.start_address)}-{render_address(region.end_address)}"
            f"  {flags}  {region.size:>8} bytes  {region.name}"
        )

    lines.append("")
    lines.append(f"function count: {len(analysis.functions)}")
    lines.append("function records:")
    for function in analysis.functions[:function_limit]:
        lines.append(
            f"  {render_address(function.start_address)}  {function.size:>6} bytes  "
            f"{len(function.callers)} caller(s)  {len(function.callees)} callee(s)  "
            f"{function.name}"
        )
    lines.extend(_tail(function_limit, len(analysis.functions), "function records"))

    edges = analysis.call_relationships
    lines.append("")
    lines.append(f"call relationships: {len(edges)} edge(s)")
    for edge in edges:
        lines.append(f"  {edge.caller_id} -> {edge.callee_id}")

    warnings = analysis.analysis_warnings
    lines.append("")
    lines.append(f"analysis warnings: {len(warnings)}")
    for warning in warnings[:warning_limit]:
        location = "" if warning.address is None else f" at {render_address(warning.address)}"
        lines.append(f"  [{warning.severity}] {warning.code}{location}: {warning.message}")
    lines.extend(_tail(warning_limit, len(warnings), "warnings"))
    return "\n".join(lines)
