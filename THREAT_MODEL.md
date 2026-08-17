# Threat Model

## Assets

- legally obtained firmware and its provenance;
- ground-truth source that must remain hidden from the investigator;
- reverse-engineering results and engineer annotations;
- local workstation, credentials, network, and connected devices;
- integrity of evidence, confidence scores, and reports.

## Trust boundaries

Firmware files are untrusted input. Ghidra and future emulators parse or execute
adversarial bytes and therefore require process isolation and resource limits.
AI model output is untrusted interpretation. MCP, if later introduced, is a
capability boundary and must expose only enumerated analysis operations. Reports
are research artifacts, not deployment approval.

## Allowed inputs

Only analyze:

- synthetic firmware created for this project;
- open-source firmware whose license permits the work;
- firmware the user is explicitly authorized to analyze.

Record provenance and authorization alongside every non-synthetic sample.

## Prohibited capabilities

Do not implement:

- firmware flashing;
- immobilizer or security-access bypass;
- secret or key extraction;
- remote exploitation;
- live vehicle control;
- vehicle-network attacks or CAN injection;
- modification or deployment of a real safety-critical ECU.

No current or future “analysis” command may silently expand into one of these
capabilities.

## Principal threats and controls

| Threat | Initial control |
|---|---|
| Malicious firmware exploits a parser | Byte-only bounded intake; later run Ghidra/emulators in isolated local processes with time and memory limits |
| Model gains host access | Narrow structured tools; no shell, arbitrary Python, network, or filesystem-wide APIs |
| Firmware or source leaks externally | Local processing by default; explicit disclosure controls before any model call |
| Ground truth contaminates evaluation | Separate source/ground-truth directories and investigator-visible artifacts |
| AI invents semantics or evidence | Typed hypotheses, resolvable citations, confidence calibration, alternatives, and human review |
| Resource exhaustion | File-size limits, pagination, bounded memory reads, process timeouts, and output caps |
| Analysis is mistaken for safe deployable code | Prominent report warnings and separation of research, reconstruction, certification, and deployment |
| Unauthorized firmware enters dataset | Required provenance record and manual authorization gate |

## Current posture

Intake reads an allowlisted extension up to 64 MiB and never executes the file.
The allowlist is `.bin`, `.rom`, `.img`, `.hex`, `.s19`, `.srec`, `.stripped`,
and `.symbols`. Treat it as a guard against selecting the wrong file, not as a
security control: an extension says nothing about content. The controls that
carry weight are the regular-file check, the size cap, and the fact that intake
only reads bytes.

There is no model, MCP server, emulator, network access, vehicle interface, or
firmware-writing capability.

### Open risk: Ghidra parses untrusted input in our process

As of Prompt 3, `--ghidra` starts a JVM inside the `ecu-recovery` process and
hands the binary to Ghidra's loaders, analyzers, and decompiler. A malicious
firmware image that exploits a Ghidra parser would be executing in our process,
with our filesystem access and no memory, CPU, or time limit.

This is currently accepted because every analyzed input is a fixture this
repository compiled from source it owns. It stops being acceptable the moment a
third-party image is analyzed.

Partial mitigations in place today:

- each session opens in a throwaway project directory that is deleted on close,
  so Ghidra's writable state never lands in the repository;
- responses are bounded by `MAX_READ_BYTES`, `MAX_INSTRUCTIONS`, and
  `MAX_RESULTS`, so no caller can pull an unbounded result;
- Ghidra's Java objects cannot escape `analysis/ghidra.py`.

Not in place: process isolation, memory limits, CPU limits, wall-clock limits,
and a network-disabled sandbox. Prompt 16 owns closing this, and Prompt 19's
readiness review must treat it as a blocker for real firmware.

Passing tests does not establish that the system is secure. Isolation controls
must be actively tested before untrusted third-party firmware enters the
workflow.

