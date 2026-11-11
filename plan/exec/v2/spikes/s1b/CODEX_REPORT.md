Review [RESULTS.md](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/spikes/s1b/RESULTS.md). **S1b is complete; both regeneration runs produced byte-identical outputs.**

Created only inside `plan/exec/v2/spikes/s1b/`: the seven requested Python files, `RESULTS.md`, `results.json`, and `elapsed.txt`.

**Winner: `{1/4, 1/2}`.** Minimum correct-decision probability: **53.7656%**, just **0.1049 percentage points** below the maximum; it wins the declared tie by saving **10.0697 expected pairs**.

Default floors, in pairs:

| Measure | Result |
|---|---:|
| Earliest possible PASS / BLOCK | 10 / 20 |
| All-zero PASS | 80 |
| PASS with 1, 2, 3, 5 losses; otherwise zeros | 100, 110, 120, 150 |
| Maximum losses with remaining zeros at 200 / 400 pairs | 8 / 23 |

Conditional-on-schedule spread: concentrated false-PASS **≈0–52.85%**, false-BLOCK **0–38.38%**; means **1.2215% / 0.4781%**. **The 2.5% bound is not conditional on an individual manifest.**

| Comparator | Conclusion |
|---|---|
| Clopper–Pearson fixed | Mixed: higher power and lower expected cost in measured non-margin cases; higher boundary errors. |
| Newcombe fixed | Mixed: lower power/cost at cap 200; higher power at cap 400, with double the ceiling. |
| Newcombe sequential | Mixed: lower power/cost at cap 200; higher power and lower expected cost at cap 400, with double the ceiling. |

Verification commands, using these shared settings:

```sh
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH=plan/exec/v2/spikes/s1:plan/exec/v2/spikes/s1b
S1B=plan/exec/v2/spikes/s1b
```

| Command | Last result |
|---|---|
| `.venv/bin/python "$S1B/run_all.py" --verify-repeat` | Byte-identical; PASS; **171.337s** |
| `.venv/bin/pytest "$S1B" -q -p no:cacheprovider -o addopts=` | **37 passed** |
| `.venv/bin/ruff format --check --no-cache "$S1B"` | 8 files already formatted |
| `.venv/bin/ruff check --no-cache "$S1B"` | All checks passed! |
| `.venv/bin/basedpyright "$S1B"` | 0 errors, 0 warnings, 0 notes |

`shasum -a 256 -c FROZEN.sha256` passed; last line: `uv.lock: OK`.

No requested deliverable remains unfinished. Cross-version execution was not tested; 63-bit seeds cannot guarantee collision freedom. The orchestrator must independently rerun acceptance checks.