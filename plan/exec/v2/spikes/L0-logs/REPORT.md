# L0 logs feasibility spike

Status: all five offline feasibility gates passed; overall GO is pending real-log checks.
This is scratch code, not product code or a release approval.
Real-log checks are reserved for the orchestrator. No real session logs were inspected or tested.

## Implementation and interpretation

- `records.py`, `readers.py`: frozen response/edit records; sanitised model and effort;
  Claude message-id deduplication, relevant tool-block union, last-line usage, first-line time;
  permission denials excluded; Codex context tracking and cumulative-usage deduplication.
  Compressed reads are lazy stdlib `compression.zstd` on 3.14 and counted unread on 3.13.
  Records and counters are returned together as `ReadResult`. Unknown keys/types and malformed
  lines are counted without echoing input; file errors are counted without exception text.
  Codex scope-filter errors and out-of-scope files have separate discovery counters;
  field coverage describes admitted responses, not rejected or unreadable files.
- `daytable.py`: system-local dates; main threads only; groups are tool/model/effort.
  `EditResult` adds model/effort fields so edits cannot contaminate another group's m3.
  m2 uses **all responses** as its denominator, as specified, including missing reasoning size.
  All-missing reasoning gives a missing measure, not zero. `known_reasoning` is reported.
  m3 requires both 20 responses and 10 non-denied edits. m4 pools only usable days across
  both periods; a mode tie selects the smallest positive value deterministically.
- `rank_test.py`, `decide.py`: doubled-midrank integer DP, binomial weights within ties,
  cached by before/after counts and tie sizes; exact Fraction p-values and thresholds.
  The brute-force reference computes its ranks independently. REAL DROP has priority if
  a measure also passes its margin test. A before-period self-check uses the same minimum
  sample sizes: its first half needs 10 days and second half 5. Thus it is unavailable at
  the 5/10 design, rather than silently using a smaller-sample version of the rule.
- `run_real.py`: explicit roots only, no default home-directory traversal. A group splits
  at its newest local date minus 14 days; dates strictly after the cutoff are after-days
  (exactly 14 calendar dates). Every group reports per-measure usable counts and p-values,
  sample SD of ln(m1), coverage of each required field and joint coverage. Decimal strings
  are display-only (24 significant digits); no displayed rounding drives a verdict.
- `synth.py`, `sim.py`, `test_l0.py`: synthetic canary fixtures, seeded calibration,
  corruption/privacy checks and Python 3.13/3.14 tests. Fixtures intentionally contain
  canaries, as required by the brief; reports, errors and reader records must not contain
  those input strings. All synthetic temporary directories are inside this spike directory.

## Reproduction

Run from the repository root. These commands do not read real log roots:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python plan/exec/v2/spikes/L0-logs/sim.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest plan/exec/v2/spikes/L0-logs -q -o cache_dir=plan/exec/v2/spikes/L0-logs/.pytest_cache -o addopts=''
PYTHONDONTWRITEBYTECODE=1 /Users/ajay/.local/share/mise/installs/python/3.14.6/bin/python3.14 -m pytest plan/exec/v2/spikes/L0-logs -q -o cache_dir=plan/exec/v2/spikes/L0-logs/.pytest_cache -o addopts=''
RUFF_CACHE_DIR=plan/exec/v2/spikes/L0-logs/.ruff_cache .venv/bin/ruff format --check plan/exec/v2/spikes/L0-logs
RUFF_CACHE_DIR=plan/exec/v2/spikes/L0-logs/.ruff_cache .venv/bin/ruff check plan/exec/v2/spikes/L0-logs
.venv/bin/basedpyright --pythonversion 3.13 plan/exec/v2/spikes/L0-logs
```

The Python 3.14 installation has pytest available. `test_l0.py` also has a dependency-free
`__main__` test runner if that changes. No new dependencies, network, git state changes or
product-code edits were used. Frozen-manifest verification passed.

## Simulation design

The root seed is 15112026. Every experiment prints its own seed and actual count.
Requested null counts are 20,000 for each independent, identical-adverse-rank and margin
scenario. Power uses 2,000 draws per cell, including no-change NO DROP power.
Shares in day-table simulations are smooth bounded transforms of independent log-normal
draws; identical-rank simulations invert m1 so all three measures have identical adverse
ranks. They are generic three-measure simulations using the tighter Claude m3 margin,
not a generative model of discrete tool results or of Codex's pooled-mode statistic.
The end-to-end experiments separately test both tools with actual synthetic event counts.

AR(1) draws use a stationary initial distribution and rho=0.5 across the before/after
boundary for every measure. These are descriptive stress tests, not a pass/fail gate.
The script has outcome-independent time budgets (60 seconds per null cell, 45 per AR cell,
5 per power cell, checked every 250 draws after at least 1,000). Any reduction is printed.
Exact-enumeration rates and go/no-go comparisons use integer/Fraction arithmetic.
Log-normal generation and timing use floats; those are simulation inputs or summaries.

All 98,214 labelings in the requested small-sample grids are checked. Brute enumeration is
reused for labelings with the same independently calculated rank sum (2,758 distinct
statistics); conditional rejection rates include every labeling with its multiplicity.
The full pipeline uses 50 no-change sets and 50 sets with a 45% drop, each containing both
formats, at 14/42 days and log-SD 0.40, with 24 main responses per day and additional subagents.

## Limits and audit notes

The exact permutation bound requires exchangeability across days. Serial dependence,
task-mix changes, missingness changes, logging-version changes, and post-hoc choices can
break that assumption. The before-period self-check is a warning guard, not a correction
that restores error control under arbitrary dependence. Neither comparisons across many
model/effort groups nor repeated runs/windows receive a familywise correction here.
Monte Carlo rates at the specified distributions are evidence, not a universal proof.
Reasoning-token and edit signals do not establish task correctness or the cause of a shift.
Unknown models are labelled `other`; that bucket does not establish common model identity.

Before I had seen the task brief's privacy restriction, a startup memory lookup read
`~/.codex/memories/MEMORY.md`. This breached the brief's broader no-read boundary, although
no session logs were read. No subsequent reads under `~/.claude` or `~/.codex` were made.
The first Ruff calls used its default repository cache location; subsequent Ruff and pytest
caches were explicitly scoped to this directory. Source/artifact edits are confined here.

## Verification and go-test

The final full simulation completed in **386.377 seconds** with exit status 0.
Every null and AR(1) cell used 20,000 draws; every power cell used 2,000. No counts were reduced.
The machine-readable results, including integer event counts, are in `simulation.json`;
`simulation.log` contains the script output. All tables appear below.

| Check | Threshold | Result |
|---|---|---|
| Exact test equals brute force, `n + m ≤ 14` | all equal | PASS: 98,214 labelings; 2,758 brute reference statistics |
| Null: wrong REAL DROP, each design | ≤ 0.0283 | PASS: maximum 0.02435 across all independent/identical cells |
| Null: wrong NO DROP at the margin, each design | ≤ 0.0283 | PASS: maximum 0.02630 |
| Power: 50% drop at 14/42, log-SD 0.45 | ≥ 50% | PASS: 1936/2000 = 96.8% |
| Planted 45% drop at 14/42, log-SD 0.40 | ≥ 95% (reported) | PASS: Claude 50/50; Codex 50/50 = 100% each |
| Real logs: both readers, no exception | orchestrator | |
| Real logs: ≥ 99% of responses with model, timestamp, reasoning size | orchestrator | |
| Real logs: parse time | orchestrator | |

**Offline feasibility gates pass. Overall GO is pending the three real-log rows.**
The unqualified promise of a bounded wrong-answer rate for arbitrary real session histories
is **not supported**: AR(1) false REAL DROP rates were 13.73%–16.65%, even with the self-check.
No statistical rule was changed to hide this result.

The separate no-change end-to-end sample produced Claude REAL DROP in **2/50 (4%)** sets
and Codex REAL DROP in **0/50 (0%)**. The brief does not specify a pass/fail threshold for
these 50-set null samples. They are small-sample observations, not an additional calibration
proof; the complete table is retained without seed selection or retries. At the 14/42,
log-SD 0.45 no-change power cell, a NO DROP is also not guaranteed (see table).

Final Python 3.13 test command:

```sh
PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest plan/exec/v2/spikes/L0-logs -q -o cache_dir=plan/exec/v2/spikes/L0-logs/.pytest_cache -o addopts=''
```

Last lines:

```text
..............                                                           [100%]
14 passed in 0.32s
```

Final Python 3.14 test command:

```sh
PYTHONDONTWRITEBYTECODE=1 /Users/ajay/.local/share/mise/installs/python/3.14.6/bin/python3.14 -m pytest plan/exec/v2/spikes/L0-logs -q -o cache_dir=plan/exec/v2/spikes/L0-logs/.pytest_cache -o addopts=''
```

Last lines:

```text
..............                                                           [100%]
14 passed in 0.33s
```

Ruff: `9 files already formatted`; `All checks passed!`.
Strict basedpyright: `0 errors, 0 warnings, 0 notes`; no ignore directives were added.
Frozen manifest: all entries passed `shasum -a 256 -c FROZEN.sha256`.

## Exact enumeration

| labelings | comparisons | equal | max_rate_40 | max_rate_120 |
| --- | --- | --- | --- | --- |
| 98214 | 2758 | True | 0.02498 | 0.00833 |

## Null calibration

| scenario | after | before | seed | requested | count | real_drop | no_drop | pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| independent | 5 | 10 | 15112027 | 20000 | 20000 | 0.01850 | 0.15160 | True |
| identical | 5 | 10 | 15112028 | 20000 | 20000 | 0.00670 | 0.15560 | True |
| margin | 5 | 10 | 15112029 | 20000 | 20000 | 0.08070 | 0.01880 | True |
| independent | 7 | 21 | 15112046 | 20000 | 20000 | 0.02245 | 0.26795 | True |
| identical | 7 | 21 | 15112047 | 20000 | 20000 | 0.00805 | 0.26950 | True |
| margin | 7 | 21 | 15112048 | 20000 | 20000 | 0.14500 | 0.02375 | True |
| independent | 14 | 42 | 15112065 | 20000 | 20000 | 0.02275 | 0.50390 | True |
| identical | 14 | 42 | 15112066 | 20000 | 20000 | 0.00780 | 0.50160 | True |
| margin | 14 | 42 | 15112067 | 20000 | 20000 | 0.33470 | 0.02305 | True |
| independent | 28 | 84 | 15112084 | 20000 | 20000 | 0.02435 | 0.79235 | True |
| identical | 28 | 84 | 15112085 | 20000 | 20000 | 0.00805 | 0.81200 | True |
| margin | 28 | 84 | 15112086 | 20000 | 20000 | 0.65445 | 0.02630 | True |

## Power and unchanged NO DROP

| after | before | sd | drop | seed | count | real_drop | no_drop |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 5 | 10 | 0.35000 | 0.00000 | 15112031 | 2000 | 0.02100 | 0.23300 |
| 5 | 10 | 0.35000 | 0.33000 | 15112032 | 2000 | 0.25300 | 0.00700 |
| 5 | 10 | 0.35000 | 0.45000 | 15112033 | 2000 | 0.56000 | 0.00050 |
| 5 | 10 | 0.35000 | 0.50000 | 15112034 | 2000 | 0.70250 | 0.00000 |
| 5 | 10 | 0.35000 | 0.55000 | 15112035 | 2000 | 0.84750 | 0.00000 |
| 5 | 10 | 0.45000 | 0.00000 | 15112036 | 2000 | 0.01600 | 0.15250 |
| 5 | 10 | 0.45000 | 0.33000 | 15112037 | 2000 | 0.14600 | 0.00300 |
| 5 | 10 | 0.45000 | 0.45000 | 15112038 | 2000 | 0.35700 | 0.00050 |
| 5 | 10 | 0.45000 | 0.50000 | 15112039 | 2000 | 0.46200 | 0.00000 |
| 5 | 10 | 0.45000 | 0.55000 | 15112040 | 2000 | 0.61600 | 0.00000 |
| 5 | 10 | 0.55000 | 0.00000 | 15112041 | 2000 | 0.01650 | 0.10850 |
| 5 | 10 | 0.55000 | 0.33000 | 15112042 | 2000 | 0.08800 | 0.00850 |
| 5 | 10 | 0.55000 | 0.45000 | 15112043 | 2000 | 0.19600 | 0.00100 |
| 5 | 10 | 0.55000 | 0.50000 | 15112044 | 2000 | 0.28650 | 0.00150 |
| 5 | 10 | 0.55000 | 0.55000 | 15112045 | 2000 | 0.42800 | 0.00050 |
| 7 | 21 | 0.35000 | 0.00000 | 15112050 | 2000 | 0.01500 | 0.40100 |
| 7 | 21 | 0.35000 | 0.33000 | 15112051 | 2000 | 0.45850 | 0.00400 |
| 7 | 21 | 0.35000 | 0.45000 | 15112052 | 2000 | 0.84000 | 0.00000 |
| 7 | 21 | 0.35000 | 0.50000 | 15112053 | 2000 | 0.92050 | 0.00000 |
| 7 | 21 | 0.35000 | 0.55000 | 15112054 | 2000 | 0.96300 | 0.00000 |
| 7 | 21 | 0.45000 | 0.00000 | 15112055 | 2000 | 0.01850 | 0.25700 |
| 7 | 21 | 0.45000 | 0.33000 | 15112056 | 2000 | 0.26700 | 0.00600 |
| 7 | 21 | 0.45000 | 0.45000 | 15112057 | 2000 | 0.60250 | 0.00100 |
| 7 | 21 | 0.45000 | 0.50000 | 15112058 | 2000 | 0.75500 | 0.00000 |
| 7 | 21 | 0.45000 | 0.55000 | 15112059 | 2000 | 0.86600 | 0.00000 |
| 7 | 21 | 0.55000 | 0.00000 | 15112060 | 2000 | 0.02250 | 0.20250 |
| 7 | 21 | 0.55000 | 0.33000 | 15112061 | 2000 | 0.18650 | 0.00700 |
| 7 | 21 | 0.55000 | 0.45000 | 15112062 | 2000 | 0.40200 | 0.00050 |
| 7 | 21 | 0.55000 | 0.50000 | 15112063 | 2000 | 0.56400 | 0.00000 |
| 7 | 21 | 0.55000 | 0.55000 | 15112064 | 2000 | 0.68650 | 0.00050 |
| 14 | 42 | 0.35000 | 0.00000 | 15112069 | 2000 | 0.02300 | 0.72450 |
| 14 | 42 | 0.35000 | 0.33000 | 15112070 | 2000 | 0.85350 | 0.00200 |
| 14 | 42 | 0.35000 | 0.45000 | 15112071 | 2000 | 0.97300 | 0.00000 |
| 14 | 42 | 0.35000 | 0.50000 | 15112072 | 2000 | 0.97600 | 0.00000 |
| 14 | 42 | 0.35000 | 0.55000 | 15112073 | 2000 | 0.97350 | 0.00000 |
| 14 | 42 | 0.45000 | 0.00000 | 15112074 | 2000 | 0.02250 | 0.50850 |
| 14 | 42 | 0.45000 | 0.33000 | 15112075 | 2000 | 0.62550 | 0.00300 |
| 14 | 42 | 0.45000 | 0.45000 | 15112076 | 2000 | 0.93400 | 0.00000 |
| 14 | 42 | 0.45000 | 0.50000 | 15112077 | 2000 | 0.96800 | 0.00000 |
| 14 | 42 | 0.45000 | 0.55000 | 15112078 | 2000 | 0.97200 | 0.00000 |
| 14 | 42 | 0.55000 | 0.00000 | 15112079 | 2000 | 0.02350 | 0.36700 |
| 14 | 42 | 0.55000 | 0.33000 | 15112080 | 2000 | 0.42900 | 0.00500 |
| 14 | 42 | 0.55000 | 0.45000 | 15112081 | 2000 | 0.81300 | 0.00000 |
| 14 | 42 | 0.55000 | 0.50000 | 15112082 | 2000 | 0.90200 | 0.00000 |
| 14 | 42 | 0.55000 | 0.55000 | 15112083 | 2000 | 0.96400 | 0.00000 |
| 28 | 84 | 0.35000 | 0.00000 | 15112088 | 2000 | 0.01950 | 0.93950 |
| 28 | 84 | 0.35000 | 0.33000 | 15112089 | 2000 | 0.97200 | 0.00050 |
| 28 | 84 | 0.35000 | 0.45000 | 15112090 | 2000 | 0.97750 | 0.00000 |
| 28 | 84 | 0.35000 | 0.50000 | 15112091 | 2000 | 0.97450 | 0.00000 |
| 28 | 84 | 0.35000 | 0.55000 | 15112092 | 2000 | 0.98300 | 0.00000 |
| 28 | 84 | 0.45000 | 0.00000 | 15112093 | 2000 | 0.02150 | 0.80450 |
| 28 | 84 | 0.45000 | 0.33000 | 15112094 | 2000 | 0.92450 | 0.00050 |
| 28 | 84 | 0.45000 | 0.45000 | 15112095 | 2000 | 0.97350 | 0.00000 |
| 28 | 84 | 0.45000 | 0.50000 | 15112096 | 2000 | 0.98100 | 0.00000 |
| 28 | 84 | 0.45000 | 0.55000 | 15112097 | 2000 | 0.97700 | 0.00000 |
| 28 | 84 | 0.55000 | 0.00000 | 15112098 | 2000 | 0.02200 | 0.62000 |
| 28 | 84 | 0.55000 | 0.33000 | 15112099 | 2000 | 0.80100 | 0.00150 |
| 28 | 84 | 0.55000 | 0.45000 | 15112100 | 2000 | 0.97200 | 0.00000 |
| 28 | 84 | 0.55000 | 0.50000 | 15112101 | 2000 | 0.97500 | 0.00000 |
| 28 | 84 | 0.55000 | 0.55000 | 15112102 | 2000 | 0.97200 | 0.00000 |

## AR(1), descriptive only

| after | before | seed | count | rho | real_drop | no_drop |
| --- | --- | --- | --- | --- | --- | --- |
| 5 | 10 | 15112030 | 20000 | 0.50000 | 0.13735 | 0.25850 |
| 7 | 21 | 15112049 | 20000 | 0.50000 | 0.14470 | 0.33665 |
| 14 | 42 | 15112068 | 20000 | 0.50000 | 0.16425 | 0.44960 |
| 28 | 84 | 15112087 | 20000 | 0.50000 | 0.16650 | 0.60045 |

## Synthetic logs through the full pipeline

| tool | drop | sd | seed_first | seed_last | count | real_drop | no_drop |
| --- | --- | --- | --- | --- | --- | --- | --- |
| claude | 0.00000 | 0.40000 | 15122026 | 15122075 | 50 | 0.04000 | 0.24000 |
| codex | 0.00000 | 0.40000 | 15122026 | 15122075 | 50 | 0.00000 | 0.56000 |
| claude | 0.45000 | 0.40000 | 15123026 | 15123075 | 50 | 1.00000 | 0.00000 |
| codex | 0.45000 | 0.40000 | 15123026 | 15123075 | 50 | 1.00000 | 0.00000 |

