# Experiments

Use a numbered record for every technical claim. Keep fixtures, expected results,
tool versions, and failures reproducible.

## EXP-001 — Known-source static analysis

Goal: prove the analysis loop before using unknown ECU firmware.

1. Rebuild the six Prompt 2 fixtures and confirm artifact hashes.
2. Import one stripped image into Ghidra without exposing source or ground truth.
3. Export function addresses, call relationships, and decompiler output as JSON.
4. Freeze the deterministic result before revealing the symbols-on address map.
5. Score function discovery and calls using `synthetic-lab.md`.
6. After deterministic analysis passes, ask the future agent to label five
   functions while citing tool evidence for every label.
7. Compare labels against function roles and record accuracy plus investigator
   time.

Success means all five functions are correctly explained, uncertainty is honest,
every conclusion is traceable to evidence, and median investigator time is at
least 50% lower than the manual baseline.

## EXP-002 — Real firmware intake

With authorization from the owner, profile one historical ECU image and have a
specialist validate only the deterministic inventory and Ghidra import. Do not
attempt emulation or flashing in this experiment.
