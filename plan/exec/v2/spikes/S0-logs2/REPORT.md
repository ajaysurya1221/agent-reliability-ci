GO: G1 and G4 pass for the specified seeded generators; the conditional exchangeability and retention limits still apply.

# S0 logs/2 spike

Scratch only. Seed base 17112026. Every table row names its seed. All brackets are Wilson 95% intervals from the existing self-check helper. Error rates are unconditional over generated histories; CANNOT TELL stays in that denominator. These finite simulations are implementation evidence, not a proof about user logs.

## Generator and production path

The window is 98 calendar days, 2026-01-01 through 2026-04-08 at UTC offset 0. The split is 2026-03-26 (day 84). Current-setting before-days are the last b days before that split; its a after-days are the last a days of the window. The remaining after-days have no current-setting response. The old setting occupies all earlier days and stops at the adoption date, strictly within the before period. Exactly half of each fixed-count cell has a third setting on six random after-days.

Settings use raw ids claude-opus-4 (old), claude-sonnet-4 (current), and claude-haiku-4 (minor), all effort high. Token medians center near 20000, 10000, and 5000. This scale preserves integer counts for every requested exact percentage move. Each day has a single positive count value. The existing history_days generator supplies independent Gaussian latent streams and quantized log-normal counts. Baseline log SD is 0.45, except the stated 0.40 power cells.

Current known responses per day are uniformly chosen from 20, 40, 60, 80, 100; 0 to 20 unknown responses are added independently. Known-count zero shares are the existing generator rounded to tenths before any shift (0.1 to 0.4). Old days have 60, 80, or 100 known responses plus 0 to 20 unknowns, zero shares 0.0 to 0.3. Minor days have four known responses (two zero) plus two unknowns. Edit counts and failures use the existing denominator-100 generator. No unknown reasoning count becomes zero. The minor setting is deliberately too small to win.

In G1, the selected day values are exchangeable conditional on the response structure: response totals do not change their distributions. All three gating measures have exactly the requested usable days. The token boundary multiplies after-day medians by exactly 3/4. The share boundary adds exactly 1/10 to no_reasoning_share, changing no other day value or usable-day count. No clipping or rounding follows either move.

Every simulated table calls production decide.decide_tool, including its whole-tool streak veto and unchanged exact rank tests. The first 500 histories in each G1 cell additionally expand to Response/EditResult records, select by after-period main-thread response counts, and call measures.build with model and effort overrides. Assertions compare the entire ToolTable and ToolDecision, not just the headline. Thus each design has 1500 record-path checks, 6000 total. Extra deterministic checks cover raw lexical model/effort ties, unknown reasoning, subagents, project filtering, future/out-of-window records, empty after-periods, and opaque setting aliases.

## G1: error rates with setting changes

Gate: wrong REAL DROP under null, and wrong NO DROP at each single-measure margin, must each be at most 566/20000. The old-choice column counts histories where the existing pooled-period selector would select the old setting. Record checks count exact selection, table, and decision matches.

| design a/b | scenario | seed | wrong result (95% CI) | passed streak check (95% CI) | old choice (95% CI) | record checks (95% CI) | gate | seconds |
|---|---|---:|---|---|---|---|---|---:|
| 5/10 | null | 17112026 | 287/20000 = 0.014350 [0.012793, 0.016094] | 18175/20000 = 0.908750 [0.904680, 0.912663] | 20000/20000 = 1.000000 [0.999808, 1.000000] | 500/500 = 1.000000 [0.992376, 1.000000] | PASS | 34.131 |
| 5/10 | token-margin | 17112027 | 3/20000 = 0.000150 [0.000051, 0.000441] | 18200/20000 = 0.910000 [0.905955, 0.913888] | 20000/20000 = 1.000000 [0.999808, 1.000000] | 500/500 = 1.000000 [0.992376, 1.000000] | PASS | 33.844 |
| 5/10 | share-margin | 17112028 | 1/20000 = 0.000050 [0.000009, 0.000283] | 18168/20000 = 0.908400 [0.904323, 0.912320] | 20000/20000 = 1.000000 [0.999808, 1.000000] | 500/500 = 1.000000 [0.992376, 1.000000] | PASS | 33.823 |
| 7/21 | null | 17112029 | 320/20000 = 0.016000 [0.014352, 0.017834] | 16959/20000 = 0.847950 [0.842907, 0.852860] | 20000/20000 = 1.000000 [0.999808, 1.000000] | 500/500 = 1.000000 [0.992376, 1.000000] | PASS | 56.448 |
| 7/21 | token-margin | 17112030 | 8/20000 = 0.000400 [0.000203, 0.000789] | 17019/20000 = 0.850950 [0.845947, 0.855818] | 20000/20000 = 1.000000 [0.999808, 1.000000] | 500/500 = 1.000000 [0.992376, 1.000000] | PASS | 57.318 |
| 7/21 | share-margin | 17112031 | 1/20000 = 0.000050 [0.000009, 0.000283] | 16991/20000 = 0.849550 [0.844528, 0.854438] | 20000/20000 = 1.000000 [0.999808, 1.000000] | 500/500 = 1.000000 [0.992376, 1.000000] | PASS | 55.691 |
| 14/16 | null | 17112032 | 358/20000 = 0.017900 [0.016153, 0.019832] | 17805/20000 = 0.890250 [0.885843, 0.894507] | 20000/20000 = 1.000000 [0.999808, 1.000000] | 500/500 = 1.000000 [0.992376, 1.000000] | PASS | 67.946 |
| 14/16 | token-margin | 17112033 | 15/20000 = 0.000750 [0.000455, 0.001237] | 17759/20000 = 0.887950 [0.883504, 0.892247] | 20000/20000 = 1.000000 [0.999808, 1.000000] | 500/500 = 1.000000 [0.992376, 1.000000] | PASS | 66.671 |
| 14/16 | share-margin | 17112034 | 1/20000 = 0.000050 [0.000009, 0.000283] | 17780/20000 = 0.889000 [0.884572, 0.893279] | 20000/20000 = 1.000000 [0.999808, 1.000000] | 500/500 = 1.000000 [0.992376, 1.000000] | PASS | 64.857 |
| 14/42 | null | 17112035 | 380/20000 = 0.019000 [0.017198, 0.020987] | 15818/20000 = 0.790900 [0.785208, 0.796480] | 5680/20000 = 0.284000 [0.277792, 0.290291] | 500/500 = 1.000000 [0.992376, 1.000000] | PASS | 151.730 |
| 14/42 | token-margin | 17112036 | 29/20000 = 0.001450 [0.001010, 0.002082] | 15718/20000 = 0.785900 [0.780160, 0.791530] | 5690/20000 = 0.284500 [0.278289, 0.290794] | 500/500 = 1.000000 [0.992376, 1.000000] | PASS | 148.614 |
| 14/42 | share-margin | 17112037 | 0/20000 = 0.000000 [0.000000, 0.000192] | 15776/20000 = 0.788800 [0.783088, 0.794401] | 5718/20000 = 0.285900 [0.279679, 0.292203] | 500/500 = 1.000000 [0.992376, 1.000000] | PASS | 143.801 |

## G2: assumption failures, report only

Busy-day histories multiply the current-setting token median by exp(-0.012 * (responses - 70)), quantized to 100 before testing. This is a strong inverse association, identical in both periods. It breaks the proposed conditional exchangeability assumption even though independent response counts and the fixed winner preserve unconditional exchangeability in this particular generator. A small error rate here would not establish the conditional assumption.

New-model histories multiply only the first five current-setting day medians by exactly 1.15. There is no split-date shift. This intentionally makes early before-days different from later days. Both cells use log SD 0.45 and the production whole-tool rule.

| design a/b | departure | seed | wrong REAL DROP / generated (95% CI) | passed streak check (95% CI) | wrong REAL DROP / tested (95% CI) | seconds |
|---|---|---:|---|---|---|---:|
| 14/16 | busy | 17112038 | 389/20000 = 0.019450 [0.017626, 0.021458] | 17850/20000 = 0.892500 [0.888132, 0.896718] | 389/17850 = 0.021793 [0.019751, 0.024040] | 61.919 |
| 7/21 | busy | 17112039 | 314/20000 = 0.015700 [0.014068, 0.017518] | 16935/20000 = 0.846750 [0.841691, 0.851676] | 314/16935 = 0.018541 [0.016616, 0.020685] | 52.469 |
| 14/16 | new-model | 17112040 | 535/20000 = 0.026750 [0.024603, 0.029079] | 17765/20000 = 0.888250 [0.883809, 0.892542] | 535/17765 = 0.030115 [0.027702, 0.032732] | 62.024 |
| 7/21 | new-model | 17112041 | 415/20000 = 0.020750 [0.018865, 0.022820] | 16783/20000 = 0.839150 [0.833993, 0.844177] | 415/16783 = 0.024727 [0.022484, 0.027188] | 52.385 |

## G3: power, report only

Tested means all measures have enough days and the whole-tool streak check passes. Each cell stops on exactly 2000 tested histories. Generated also counts streak-vetoed histories. Conditional detection among tested histories and detection among all generated histories are both shown; the latter includes the cost of the rule as built. Wilson intervals are descriptive here because the generated denominator uses a stopping rule, not a prespecified fixed count. The stopping rule never uses REAL DROP or NO DROP.

| design a/b | log SD | token drop | seed | tested | generated | REAL DROP / tested (95% CI) | REAL DROP / generated (95% CI) | NO DROP / generated (95% CI) | seconds |
|---|---:|---|---:|---:|---:|---|---|---|---:|
| 5/10 | 0.40 | 33/100 | 17112042 | 2000 | 2203 | 354/2000 = 0.177000 [0.160897, 0.194342] | 354/2203 = 0.160690 [0.145947, 0.176614] | 0/2203 = 0.000000 [0.000000, 0.001741] | 3.233 |
| 5/10 | 0.40 | 9/20 | 17112043 | 2000 | 2191 | 837/2000 = 0.418500 [0.397056, 0.440256] | 837/2191 = 0.382017 [0.361896, 0.402552] | 0/2191 = 0.000000 [0.000000, 0.001750] | 3.194 |
| 5/10 | 0.40 | 11/20 | 17112044 | 2000 | 2205 | 1469/2000 = 0.734500 [0.714710, 0.753391] | 1469/2205 = 0.666213 [0.646256, 0.685592] | 0/2205 = 0.000000 [0.000000, 0.001739] | 3.160 |
| 5/10 | 0.45 | 33/100 | 17112045 | 2000 | 2191 | 280/2000 = 0.140000 [0.125482, 0.155898] | 280/2191 = 0.127796 [0.114464, 0.142429] | 0/2191 = 0.000000 [0.000000, 0.001750] | 3.239 |
| 5/10 | 0.45 | 9/20 | 17112046 | 2000 | 2199 | 705/2000 = 0.352500 [0.331863, 0.373702] | 705/2199 = 0.320600 [0.301421, 0.340405] | 0/2199 = 0.000000 [0.000000, 0.001744] | 3.236 |
| 5/10 | 0.45 | 11/20 | 17112047 | 2000 | 2217 | 1211/2000 = 0.605500 [0.583898, 0.626698] | 1211/2217 = 0.546234 [0.525448, 0.566860] | 0/2217 = 0.000000 [0.000000, 0.001730] | 3.185 |
| 14/16 | 0.40 | 33/100 | 17112048 | 2000 | 2269 | 1138/2000 = 0.569000 [0.547185, 0.590551] | 1138/2269 = 0.501543 [0.480984, 0.522096] | 0/2269 = 0.000000 [0.000000, 0.001690] | 6.590 |
| 14/16 | 0.40 | 9/20 | 17112049 | 2000 | 2259 | 1842/2000 = 0.921000 [0.908355, 0.932031] | 1842/2259 = 0.815405 [0.798875, 0.830864] | 0/2259 = 0.000000 [0.000000, 0.001698] | 6.388 |
| 14/16 | 0.40 | 11/20 | 17112050 | 2000 | 2233 | 1998/2000 = 0.999000 [0.996361, 0.999726] | 1998/2233 = 0.894760 [0.881348, 0.906817] | 0/2233 = 0.000000 [0.000000, 0.001717] | 6.300 |
| 14/16 | 0.45 | 33/100 | 17112051 | 2000 | 2261 | 879/2000 = 0.439500 [0.417884, 0.461347] | 879/2261 = 0.388766 [0.368878, 0.409032] | 0/2261 = 0.000000 [0.000000, 0.001696] | 6.715 |
| 14/16 | 0.45 | 9/20 | 17112052 | 2000 | 2208 | 1694/2000 = 0.847000 [0.830559, 0.862111] | 1694/2208 = 0.767210 [0.749128, 0.784364] | 0/2208 = 0.000000 [0.000000, 0.001737] | 6.377 |
| 14/16 | 0.45 | 11/20 | 17112053 | 2000 | 2227 | 1963/2000 = 0.981500 [0.974605, 0.986549] | 1963/2227 = 0.881455 [0.867368, 0.894228] | 0/2227 = 0.000000 [0.000000, 0.001722] | 6.292 |
| 14/42 | 0.40 | 33/100 | 17112054 | 2000 | 2521 | 1495/2000 = 0.747500 [0.727998, 0.766053] | 1495/2521 = 0.593019 [0.573714, 0.612040] | 2/2521 = 0.000793 [0.000218, 0.002888] | 17.103 |
| 14/42 | 0.40 | 9/20 | 17112055 | 2000 | 2470 | 1979/2000 = 0.989500 [0.984001, 0.993122] | 1979/2470 = 0.801215 [0.785014, 0.816480] | 0/2470 = 0.000000 [0.000000, 0.001553] | 16.615 |
| 14/42 | 0.40 | 11/20 | 17112056 | 2000 | 2503 | 2000/2000 = 1.000000 [0.998083, 1.000000] | 2000/2503 = 0.799041 [0.782890, 0.814276] | 0/2503 = 0.000000 [0.000000, 0.001532] | 17.276 |
| 14/42 | 0.45 | 33/100 | 17112057 | 2000 | 2498 | 1269/2000 = 0.634500 [0.613155, 0.655329] | 1269/2498 = 0.508006 [0.488404, 0.527584] | 0/2498 = 0.000000 [0.000000, 0.001535] | 17.664 |
| 14/42 | 0.45 | 9/20 | 17112058 | 2000 | 2522 | 1913/2000 = 0.956500 [0.946651, 0.964599] | 1913/2522 = 0.758525 [0.741437, 0.774827] | 0/2522 = 0.000000 [0.000000, 0.001521] | 16.812 |
| 14/42 | 0.45 | 11/20 | 17112059 | 2000 | 2521 | 1996/2000 = 0.998000 [0.994869, 0.999222] | 1996/2521 = 0.791749 [0.775461, 0.807150] | 0/2521 = 0.000000 [0.000000, 0.001521] | 16.566 |

## G4: kept rows

write_rows and use_rows are pure functions over (tool, offset, setting, day) keys and complete count rows. They never sum alternative snapshots. Logs win equal response counts; kept rows win when logs have fewer responses. Writes enforce the model grammar, accepted efforts, 5000 distinct-count cap, and 180-day age boundary. The offset notice counts stored rows, not responses.

Each history spans 98 days, two tools, several valid settings, and four batches per day. Histograms include zero and positive counts, unknown responses, and Claude Code edit totals and failures. Runs begin during a random day and recur at random hours; current days can be incomplete. Before each run, only batches strictly older than 30 days can be removed, with whole-day and partial-day deletions. For short gaps, exact equality is asserted at every run for every day from the first run through that run, against full history available at the same instant. This checks every count field, not just response totals.

| scenario | seed | mismatching histories (95% CI) | missing rows | incomplete rows | missing responses | maximum missing responses/history | offset-isolation checks (95% CI) | ignored offset rows | seconds |
|---|---:|---|---:|---:|---:|---:|---|---:|---:|
| at most 29 days | 17116026 | 0/500 = 0.000000 [0.000000, 0.007624] | 0 | 0 | 0 | 0 | 500/500 = 1.000000 [0.992376, 1.000000] | 98000 | 3.193 |
| 31-45 days | 17116027 | 500/500 = 1.000000 [0.992376, 1.000000] | 5108 | 6222 | 633822 | 2943 | 500/500 = 1.000000 [0.992376, 1.000000] | 92892 | 2.128 |

Short-gap histories refreshed 5248 rows with larger response counts. They removed 150642 batches under whole-day deletion and 73893 under partial-day deletion across 3998 runs. Long-gap controls had 1999 runs.

Every offset check changes 0 to -480, +330, or +345 minutes, recomputes live day bins, asserts output equals fresh logs only, and asserts every old-offset row is counted as ignored. Writing the new offset leaves the old keys separate. Directed checks cover equal-count replacement, smaller-count preservation, larger-count replacement, input immutability, age 180 versus 181, grammar rejection, and 5000 versus 5001 distinct values.

Why the short-gap property holds: a completed day is observed at a run less than 29 days later, before any response on that day is old enough to be deleted. That complete snapshot wins over later subsets. A partial first snapshot is refreshed before expiry. This argument requires immutable records, no late backdated arrivals, stable offset, admitted rows, and a horizon within the retained window. It does not promise recovery of data already deleted before the first run. Separate edit-only retention or correction of records without increasing response counts is outside the tested deletion model.

## Decisions, surprises, and memo corrections

1. The reader uses None for a hidden name, not an absent setting. The spike selector preserves these identities using the reader raw lexical order and production override aliases. All 6000 record-path checks were rerun after adding that edge case. M2 needs the restated A1, not merely a claim that counts are not outcomes. With log structure fixed, selection is fixed under permutations of day values at fixed usable slots. Conditional exchangeability then justifies the rank reference distribution; a union bound over three measures gives the real-drop bound. At a single-measure margin, A3 and A4 plus the same conditional assumption justify the existing strict-count argument. Simulation does not prove these assumptions for real logs. The current A2 explicitly forbids after-period count selection, so the new record must revise A2 and its proof as well as A1.
2. The old rule picks the old setting in every short-current-history cell; the 14/42 cells show the less extreme case. M2 selects the current setting in all 6000 full-record checks and every generated compact history. The minor setting never wins by construction, so these are setting-change checks, not adversarial checks of every possible competitive selection rule.
3. G2a can violate conditional exchangeability without showing inflated unconditional error in this fixed-winner design. G2b is outside the assumption even if its finite rates remain below the gate. Neither passing a streak check nor these examples validates a user history.
4. M2 says the after period always contains a response, but explicit --since later than N is supported by the existing window code and gives an empty after period. Define that outcome and partial override behavior in the new record. M4 should say whether ignored offset counts mean rows, days, or responses; this spike counts rows. Its equality statement must be limited to admitted rows in the active window, since old rows are intentionally dropped after 180 days.
5. G4 loses data in every long-gap control. Retaining the larger snapshot cannot recover a day never captured complete. Actual filesystem atomicity, permissions, invalid-file handling, all-or-none writes, and CLI output are product implementation work, outside this pure-function spike.

## Re-run commands and timings

Run from the worktree. All output paths below are inside the requested scratch directory.

```sh
cd /Users/ajay/Developer/.arci-worktrees/wt-v2-logs
S0_DIR=/private/tmp/claude-501/-Users-ajay-Developer-agent-reliability-ci/39ca2335-7a5a-47d9-a374-69d92a47e1d0/scratchpad/s0
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B "$S0_DIR/spike.py" --gate all --workers 4 > "$S0_DIR/run.log" 2>&1
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B "$S0_DIR/retention.py" > "$S0_DIR/retention.log" 2>&1
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B "$S0_DIR/report.py"
```

For one table replace `--gate all` with `--gate G1`, `--gate G2`, or `--gate G3`; seeds and cell ids are unchanged. `--cell ID` reruns one saved cell (ids 0-11 G1, 12-15 G2, 16-33 G3). G4 uses retention.py. Individual cell times are printed in the tables. The following are sums of those elapsed cell times, not four-worker wall times:

- G1: 914.874 elapsed worker-seconds.
- G2: 228.797 elapsed worker-seconds.
- G3: 159.945 elapsed worker-seconds.
- All G1-G3 together: 332.035 wall seconds with 4 processes.
- G4: 5.321 seconds.

No cells were cut or reduced. G1 has 240000 histories; G2 has 80000; G3 has 41698 generated and 36000 tested histories. G4 has 1000 histories and 1000 offset checks. The full computation is below the 60-minute budget.

## Verification and boundaries

Record-path rerun: 80.790 seconds. Last line: `RECORD PATH PASS: 6000/6000; seconds=80.790`.

Commands:
```sh
.venv/bin/ruff format --no-cache "$S0_DIR"/*.py
.venv/bin/ruff check --no-cache "$S0_DIR"/*.py
.venv/bin/basedpyright --project pyproject.toml "$S0_DIR"/*.py
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B "$S0_DIR/spike.py" --smoke
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -B "$S0_DIR/spike.py" --verify-records
```

Validation output is in checks.log, smoke.log, and records.log. No pyright ignores are used. Existing strict project configuration is used. Product tests were not edited or rerun; direct production-path assertions are the spike checks. Product code, tests, docs, and git state were not changed.

All 1019 tracked-file hashes match the pre-spike snapshot; all 75 frozen hashes match FROZEN.sha256; git status is empty. Source HEAD: bc29799824d51fa08ca16ffbe4844b03267fa0d6. Bytecode writes and Ruff caches were disabled. verification.json and artifact-hashes.json preserve receipts.

One preliminary memory-registry search under .codex occurred before the brief prohibition was read; it returned no matching material and supplied no evidence. No further .codex or .claude directory was opened. No user session logs were read, no network command was issued, and no dependency was added. All generated files are in the requested scratch directory.

These results cover Claude Code's three measures for G1-G3, as in the reused self-check generator. They do not establish calibration for the Codex repeated-value measure, arbitrary usage patterns, serial dependence, retention-corrupted histories, or repeated daily looks. G4 covers count rows for both tools. Approval of this report is not acceptance evidence; the orchestrator must rerun the checks.
