# Research Notes

## 2026-08-17 — Source material reviewed

The supplied project brief defines the product thesis as an autonomous embedded-
software investigation system following:

> observe → hypothesize → experiment → compare → document → repeat

The supplied step-by-step build prompts intentionally order delivery as static
analysis, agent investigation, evidence, evaluation, emulation, experimentation,
reconstruction, and only then productization. Prompts are to be executed one at
a time with a working repository after each.

## Open research question: first architecture

No architecture has been selected. Candidate evaluation must consider:

- availability of a reproducible C compiler and binutils;
- mature Ghidra processor support through PyGhidra;
- suitability for six small synthetic fixtures;
- emulator availability for the later controlled-execution milestone;
- accessible processor manuals and memory-map documentation;
- relevance to a narrow legacy ECU family;
- legally usable firmware and expert access after synthetic validation.

Do not select based on vehicle-brand recognition. Prompt 2 must state the chosen
architecture and the evidence supporting it.

## Current technical observations

- The repository began empty and now contains a dependency-free Python proof of
  safe byte intake, SQLite storage, a JSON import boundary, and Markdown output.
- That proof predates the step-by-step prompt contract. Prompt 1 should preserve
  working behavior while establishing the requested package boundaries and
  developer tooling.
- Ghidra and Java availability have not yet been diagnosed by a repository
  command. That is explicitly Prompt 1 work.
- The existing Ghidra bridge is not PyGhidra integration and must not be described
  as such.

## Research log format

Future entries should record date, question, sources or experiment identifiers,
observations, decision impact, unresolved uncertainty, and the next falsifiable
test. Never store questionable proprietary firmware in this repository.

