# Experiments

Use a numbered record for every technical claim. Keep fixtures, expected results,
tool versions, and failures reproducible.

## EXP-001 — Known-source static analysis

Goal: prove the analysis loop before using unknown ECU firmware.

1. Select the first processor family using `research.md` criteria.
2. Write a small embedded C fixture with at least five meaningful functions:
   initialization, sensor conversion, table lookup, checksum, and communication
   parsing.
3. Compile with symbols for ground truth, then strip symbols for analysis.
4. Import the stripped image into Ghidra with an explicit memory map.
5. Export function addresses, call relationships, and decompiler output as JSON.
6. Ask the agent to label five functions, citing tool evidence for every label.
7. Compare labels against source truth and record accuracy plus investigator time.

Success means all five functions are correctly explained, uncertainty is honest,
every conclusion is traceable to evidence, and median investigator time is at
least 50% lower than the manual baseline.

## EXP-002 — Real firmware intake

With authorization from the owner, profile one historical ECU image and have a
specialist validate only the deterministic inventory and Ghidra import. Do not
attempt emulation or flashing in this experiment.
