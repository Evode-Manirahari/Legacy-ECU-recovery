# Synthetic firmware laboratory

This directory contains six reproducible known-source firmware fixtures. Rebuild
them with:

```bash
uv run python scripts/build_synthetic.py
```

During blinded analysis, expose only `binaries/<sample_id>/firmware.stripped`.
Keep `source/`, `ground_truth/`, `firmware.symbols`, `behavior.dylib`, and
`build.json` on the evaluator side. See `docs/synthetic-lab.md` for the contract.
