Review the [P1c verification report](/Users/ajay/Developer/.arci-worktrees/wt-v2-suite/tests/unit/suite/VERIFICATION.md:142). **Implemented all requested fixes in 13 owned files.**

1. **§8.1–2:** bounded rational parts to seven digits and validated experiment-ID shape. Verified by schema and schedule tests.
2. **§8.3–5,7:** per-round digests, rejection of bytes seals, normalized decision replay, and warning-free rebuilds. Verified by gate tests.
3. **§8.6:** carried integer wealth products forward. Exact-product tests pass; **5,000 rounds: 0.652 s; 100,000 rounds: 52.925 s**.
4. **Bench/docs:** asymmetric paths, early BLOCK, error/hard-violation checks, manifest-derived defaults, expanded margin grid, and common-mode reporting. Documentation now states the estimand and order-effect assumption.

Changed: four `src/arci/suite_*.py` modules; `bench/selfcheck_suite.py`; `docs/STATISTICS_SUITE.md`; suite helpers, four suite test files, selfcheck tests, and `VERIFICATION.md`.

| Command | Result / tail |
|---|---|
| `.venv/bin/pytest tests/unit/suite tests/unit/selfcheck -q` | **286 passed**, `[100%]` |
| `.venv/bin/python -m bench.selfcheck_suite` | **289.244 s**, `All suite checks PASS` |
| `.venv/bin/pytest -q` | **1,575 passed, 65 failed, 2 skipped** |
| Ruff format/check + basedpyright | Clean; `0 errors, 0 warnings, 0 notes` |
| `shasum -a 256 -c FROZEN.sha256` | **54 OK**; `uv.lock: OK` |

Largest directional errors at **1/2/5/10/20 cells**: **2.156820% / 1.971013% / 1.667272% / 1.415388% / 1.146505%**—matching the ADR’s rounded figures.

**Limits:** all 65 remaining failures are existing socket/`ps` sandbox failures; none concern changed tests. Multi-round suite decisions need regeneration because round-digest semantics changed. No frozen files, dependencies, or git state were modified.

Next: open the [named failure list](/Users/ajay/Developer/.arci-worktrees/wt-v2-suite/tests/unit/suite/VERIFICATION.md:48) for the orchestrator’s unrestricted rerun.