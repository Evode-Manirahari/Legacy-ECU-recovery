# Research decisions

## Selected laboratory architecture

Synthetic dataset v1 uses little-endian x86-64 Mach-O on macOS. This choice is
limited to controlled ground-truth experiments. It was selected because the
current host can compile, strip, inspect, and execute it reproducibly, while both
Ghidra and Unicorn support x86-64.

See [`synthetic-lab.md`](synthetic-lab.md) for the complete rationale and scoring
protocol.

## Open selection: first ECU family

No real ECU processor family is selected yet. That is the project's highest-
leverage product research decision. Score candidates using:

1. legally available firmware samples;
2. processor and memory-map documentation;
3. mature Ghidra language support;
4. available compiler/toolchain for a known-source fixture;
5. emulator availability for the next milestone;
6. access to a specialist who can judge the output;
7. repeated commercial pain across multiple ECUs.

Record evidence for each candidate before committing. The CLI therefore requires
the investigator to supply processor information and does not guess silently.

## Product boundary

The first customer is an ECU repair, remanufacturing, restoration, reverse-
engineering, or embedded-maintenance specialist. The first value metric is time
saved while reaching defensible understanding—not percentage of source code
generated.

## Safety and legal boundary

Only use firmware that the investigator is authorized to analyze. Keep the
initial product read-only. Generated analysis may be wrong and must not be used
to flash an ECU or operate a vehicle. Any future execution belongs in an isolated
emulator with explicit resource limits, never on the host or connected hardware.
