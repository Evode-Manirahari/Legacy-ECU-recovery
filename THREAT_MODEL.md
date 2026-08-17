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

The implemented intake reads `.bin`, `.img`, and `.rom` files up to 64 MiB and
does not execute them. The optional Ghidra path only imports an existing JSON
file; Ghidra itself is not yet launched. There is no model, MCP server, emulator,
network access, vehicle interface, or firmware-writing capability.

Passing tests does not establish that the system is secure. Isolation controls
must be actively tested before execution or third-party parsers become part of
the supported workflow.

