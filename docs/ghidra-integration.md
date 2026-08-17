# Ghidra Integration

## Why PyGhidra

Ghidra is reached through PyGhidra's JVM bridge rather than by shelling out to
`analyzeHeadless` with an export script.

The later agent tool layer needs interactive, query-shaped access: decompile one
function, list who calls it, search a constant, read sixteen bytes. A headless
script forces each of those through a batch export round trip, and every new
capability means editing a Java-side script. In-process access gives the
decompiler, reference manager, and listing directly.

The cost is recorded honestly in `THREAT_MODEL.md`: Ghidra parses untrusted
binaries inside our process, unsandboxed.

`ecu_recovery.ghidra.bridge` still exists for importing an analysis someone else
produced out of process.

## Installing

```bash
brew install ghidra          # also installs openjdk@21
uv sync --extra ghidra       # installs pyghidra
uv run ecu-recovery doctor
```

`doctor` reports Ghidra and PyGhidra separately, because either one alone is not
enough to run an analysis.

Discovery order:

1. `GHIDRA_INSTALL_DIR`
2. `GHIDRA_HOME`
3. `/usr/local/opt/ghidra/libexec`, `/opt/homebrew/opt/ghidra/libexec`,
   `/opt/ghidra`
4. a directory reachable from `ghidraRun` or `pyghidraRun` on `PATH`

A candidate only counts when it contains `Ghidra/application.properties`. A
launcher script by itself is not something PyGhidra can start, so it is rejected.

Verified on Ghidra 12.1.2 with Zulu OpenJDK 21 on macOS x86-64. PyGhidra locates
JDK 21 on its own; `JAVA_HOME` does not need to be exported.

## Layers

```text
analysis/models.py   plain records; imports no engine
analysis/base.py     StaticAnalysisEngine / StaticAnalysisSession, bounds, errors
analysis/ghidra.py   the only module that touches Java
```

`models.py` and `base.py` are importable and fully testable on a host with no
Ghidra and no JVM. That constraint is what keeps the boundary real: if a Java
type leaked into the vocabulary, those modules would stop importing.

## Session lifetime

`analyze_binary` returns a context-managed session:

```python
from ecu_recovery.analysis import ArchitectureConfig
from ecu_recovery.analysis.ghidra import GhidraEngine

engine = GhidraEngine()
with engine.analyze_binary(
    "firmware.bin",
    ArchitectureConfig(
        language_id="x86:LE:64:default",
        base_address=0x8000,
    ),
) as session:
    for function in session.list_functions(limit=25):
        print(function.id, function.name, function.callees)
    print(session.decompile_function("0x00008000").text)
```

Each session opens its own temporary Ghidra project, deleted on close. Sessions
are not safe to share across threads.

## Declared versus detected

`ArchitectureConfig` carries what the investigator declared. `ProgramSummary`
carries what Ghidra actually loaded, and keeps the request under `.requested`.
Both appear in the export, so a reader can always tell a supplied fact from a
detected one — which matters because a wrong declared language produces confident
nonsense.

Leave a field `None` to let Ghidra detect it. `base_address` is for raw dumps
that carry no load address; it is applied before auto-analysis so discovered
addresses use the real base.

## Bounds

Defined once in `analysis/base.py` so a second engine cannot silently lose them:

| Limit | Value | Applies to |
|---|---|---|
| `MAX_READ_BYTES` | 4096 | `read_bytes` |
| `MAX_INSTRUCTIONS` | 4096 | `get_disassembly` |
| `MAX_RESULTS` | 1000 | paging, xrefs, constants |
| `DEFAULT_PAGE_SIZE` | 100 | `list_functions`, `list_strings` |

Over-limit requests raise `InvalidRequestError`. `get_disassembly` truncates and
sets `truncated=True` rather than silently returning a short result.

## Errors

`AnalysisError` is the root. `EngineUnavailableError` means Ghidra or PyGhidra is
missing, `UnknownFunctionError` means an address resolved to nothing, and
`InvalidRequestError` means the arguments were out of range.

Decompiler failure is deliberately *not* an error. It returns
`DecompilerResult(success=False, warnings=(...))`, because which functions the
decompiler cannot handle is a finding the agent needs to cite.

## Running the tests

Ghidra tests carry the `ghidra` marker and run by default, skipping with a stated
reason when Ghidra or PyGhidra is missing.

```bash
uv run pytest                    # everything
uv run pytest -m ghidra          # Ghidra only
uv run pytest -m "not ghidra"    # skip the slow JVM path
```

They analyze `firmware.stripped` only, then read ground truth from the symbols-on
build afterwards, matching the boundary in `docs/synthetic-lab.md`.

## Measured on the synthetic fixtures

Ghidra 12.1.2 recovers every expected function at its exact ground-truth entry
address, with no extras, in `temperature_controller_v1`, and reproduces the
`multi_function_pipeline_v1` call graph exactly (5 of 5 edges). The decompiler
renders `temperature_fan_on` as a single comparison return.

This is compiler-generated, unobfuscated, unoptimized-for-size x86-64 with intact
function prologues. It sets no expectation for real ECU firmware, where hand-
written assembly, overlays, and unusual calling conventions are normal.
