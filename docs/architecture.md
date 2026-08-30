# Architecture

This file has been folded into **[architecture/](architecture/)**, which is the
system design of record: the diagram, and one contract per component covering
position, responsibility, inputs, outputs, permitted dependencies, and testing.

- **Target system design** — [architecture/README.md](architecture/README.md)
- **Component contracts** — [architecture/components/](architecture/components/)
- **What is actually built** — [../ARCHITECTURE.md](../ARCHITECTURE.md)

The design constraint this file used to record still holds and now lives in the
component contracts: the analysis path supports one investigator-selected
processor family and static analysis. Architecture auto-detection, emulation,
peripheral simulation, and vehicle interaction are not on the critical path —
see [architecture/components/intake.md](architecture/components/intake.md) and
[architecture/components/verification.md](architecture/components/verification.md).
