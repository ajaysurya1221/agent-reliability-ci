Review [RESULTS.md](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/spikes/s1c/RESULTS.md). Two full generations were **byte-identical**, finishing in **282 seconds total**.

1. **Error control:** balanced rounds prove ≤2.5% per direction under the stated independence assumptions. Search maximum: **1.596%**. Mid-round looks can false-PASS with **100%** probability.
2. **Power/cost:** N=10 matches sampled. N=20/50 lose **0.444/1.222 percentage points** of mean power and require **7.52/24.91** additional pairs.
3. **Grid sizes:** all requested sizes through N=300 can decide within 400 pairs. N>400 cannot complete one round.
4. **Recommendation:** **balanced only** for the conditional-per-manifest guarantee.

Created only inside `plan/exec/v2/spikes/s1c/`:

- Code: `balanced.py`, `run_all.py`, `s1c_study.py`, `test_s1c.py`.
- Evidence: `PROOF.md`, `RESULTS.md`, `results.json`.
- Records: `progress.md`, `elapsed.txt`, `run.log`, `final-run.log`.

Commands and last lines, using:
```sh
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=plan/exec/v2/spikes/s1:plan/exec/v2/spikes/s1b:plan/exec/v2/spikes/s1c

.venv/bin/python plan/exec/v2/spikes/s1c/run_all.py --verify-repeat
# PASS: S1c; elapsed=282.187s

.venv/bin/pytest plan/exec/v2/spikes/s1c -q -p no:cacheprovider -o addopts=
# 12 passed

.venv/bin/ruff format --check --no-cache plan/exec/v2/spikes/s1c
# 7 files already formatted

.venv/bin/ruff check --no-cache plan/exec/v2/spikes/s1c
# All checks passed!

.venv/bin/basedpyright plan/exec/v2/spikes/s1c
# 0 errors, 0 warnings, 0 notes

shasum -a 256 -c FROZEN.sha256
# uv.lock: OK — all 54 passed
```

**Limits:** Table C specifies eight combinations, not twelve; its 1.0-drop case is impossible from the supplied baselines. Six feasible combinations were evaluated. The adversarial search covers two disclosed law families.

The earlier slow exploratory run remains active because the sandbox denied termination. Its source-hash guard prevents it from overwriting the verified outputs.