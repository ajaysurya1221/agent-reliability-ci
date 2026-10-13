# Measurements log (orchestrator-recorded; receipts proper go to docs/measurement/receipts once T10 lands)

| when (UTC) | what | machine | result |
|---|---|---|---|
| 2026-10-13 03:36 | `examples/retry_agent/hero_demo.py --n 200` from the checkout, 8 workers | 15-core Apple Silicon Mac, Python 3.13.12 | 38.2 s wall, exit 0 |
| 2026-10-13 04:05 | T02 wheel smoke: `uv build --no-sources` from `sprint/demo` (2ae4bfd), then from an EMPTY directory `uvx --from <wheel> arci demo` (uvx env creation included) | same | 1:12.25 wall, exit 0, "All six steps held", A 192/200 B 132/200, 0 files left in cwd; wheel 115 KB (38 files, incl. arci/demo/* and arci/__main__.py); sdist 5.9 MB (unrestricted until T12) |
