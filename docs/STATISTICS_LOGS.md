# The session-log contract (arci-logs/1)

The design record is [0016](design/0016-logs.md).

This document specifies `arci logs` (also installed as `realornoise`). It reads session logs
that Claude Code or Codex already wrote on the user's disk, reduces them to one number per
measure per day, and compares the days after a split date with the days before it. It runs no
model and no trial. Nothing in `STATISTICS_SUITE.md` or `STATISTICS_OUTCOMES.md` applies here:
there are no pairs, no rounds and no betting wealth. The data are observational, and the result
names are different on purpose. The sections "Record model" and "Fixed texts" of the design
record are part of this contract.

## What is compared

One comparison is made per tool (Claude Code, Codex), for one **setting** (a model id and an
effort setting), on the main thread only (sub-agent responses are left out).

- A **response** is one model reply as the tool recorded it (`LOG_FORMATS.md`). Its
  **reasoning count** is a non-negative integer, or unknown when the log does not give one.
- **Days.** The run reads the clock once: the start instant and the local zone's offset from
  UTC at that instant (`--utc` uses offset 0). Every timestamp is converted with that one
  offset, and days are calendar dates at that offset. This is a fixed-offset calendar, not
  historical local time across a daylight-saving change. A Claude Code response belongs to
  the day of its first line; a Codex response to the day of its token-count event; a
  file-edit result to the day of the result line. Records stamped later than the start
  instant, and timestamps without a zone, are left out and counted
  (`records_in_future`, `records_without_timezone`). If the window's dates cannot be
  represented in the calendar, the run is a usage error.
- **Window.** `N` is the newest day with a main-thread response of the tool, after the
  `--project` filter. The split date `s` is `N − 13` days unless the user gives `--since`. The
  after period is `s` to `N`. The before period is the 84 days ending the day before `s`. A
  `--since` later than `N` gives an after period with no days.
- **Setting.** A setting is a model id and an effort value as the log records them. The
  setting with the most main-thread responses over both periods together is compared; ties
  go to the setting whose raw (model id, effort) pair sorts first as text. `--model` and
  `--effort` override. Responses that lack a model or an effort belong to no setting. If no
  setting has a response in the window, the result is CANNOT TELL (`no_usable_setting`); the
  tool never switches to another setting because it has more usable days.
- If `s` is later than `N`, the after period has no days.
- A file-edit result takes the setting of the response whose tool call it answers. Results
  that were permission denials, and results that match no recorded tool call, are left out
  and counted.

## Measures

Each gating measure gives one exact rational per usable day, a direction of "worse", and a
margin fixed in this method version.

| Id | Day value | A day is usable with | Tools | Worse | Margin |
|---|---|---|---|---|---|
| `reasoning_tokens` | Median of the positive reasoning counts (an even number of them: the mean of the two middle ones) | 20 known counts, 10 of them positive | both | lower | 1/4 (the value falls to 3/4) |
| `no_reasoning_share` | Responses with a count of 0, over responses with a known count | 20 known counts | both | higher | 1/10 |
| `edit_failure_share` | Failed file-edit results over file-edit results | 10 file-edit results | Claude Code | higher | 3/100 |
| `repeated_value_share` | Positive counts equal to `v*`, over positive counts | 20 known counts, 10 of them positive | Codex | higher | 1/10 |

`v*` is the most common positive reasoning count among all responses of the setting in the
window (both periods together); ties go to the smallest count. It does not depend on which
period a response is in. Unknown counts are never treated as 0. The margin is always the adverse change: the record
stores `1/4`, `1/10`, `3/100`, and the token move is `(1 − margin) x`. Each tool has exactly three
gating measures. A measure has **enough days** with at least 5 usable after-days and 10
usable before-days; measures can differ in which days are usable.

A measure is a recorded quantity, not quality. Less reasoning is not a worse answer; easier
work needs less of it; a vendor can change how it counts tokens. The output says a measure
"sits lower" or "moved toward worse" and never says that a model, or its answers, got worse.

## The tests

For one measure with enough days let `x_1..x_n` be the before-day values and `y_1..y_m` the
after-day values, oriented so that larger is better (a higher-is-worse measure is negated).

**Real-drop test (exact conditional rank test).** Rank the pooled `n + m` values with
midranks; `W` is the sum of the after-days' midranks. `p_real` is the share, among all
`C(n+m, m)` ways to choose which pooled values are "after", of choices whose midrank sum is at
most `W`. It is counted by integer dynamic programming on doubled midranks and held as an
exact fraction. The measure is a **real drop** when `p_real ≤ α_real = (1/40) / 3`.

**No-drop test (strict count, fixed reference).** Move every before-day toward worse by the
margin: `x'_i = (3/4) x_i` for `reasoning_tokens`, `x'_i = x_i − margin` (in the
larger-is-better orientation) for the shares, in exact arithmetic, with no rounding or
clipping. `U` is the number of pairs `(i, j)` with `x'_i < y_j`, strictly. `G(n, m, u)` is the
probability that this count is at least `u` when `n + m` distinct values are arranged
uniformly at random; it depends on `n`, `m` and `u` only and is computed exactly.
`p_none = G(n, m, U)`; the record stores `U` as `u_none`. The measure is a **no-drop** when `p_none ≤ α_none = 1/40`.

**Streak check.** For each gating measure with enough days, take its usable before-days in
date order and their median `M` (an even number of days: the mean of the two middle values).
Leave out days equal to `M`; mark each other day above or below `M`; let `R` be the number of
runs of equal marks, with `a` days above and `b` below. `p_streak` is the probability of `R`
or fewer runs when `a` above-marks and `b` below-marks are arranged uniformly at random
(the exact runs distribution; 1 when `a` or `b` is 0). The measure is **streaky** when
`p_streak ≤ 1/10`. A streaky measure is not tested, and one streaky measure stops the whole
comparison for the tool: when good days follow good days in any recorded measure, the days
are not interchangeable, and a two-period comparison cannot tell a streak from a drop.

**Result for a tool, in this order.**

1. ERROR (`no_logs`) when a requested tool has no log file; ERROR (`read_error`) when none of
   its files can be read; ERROR (`format_not_recognised`) when files were read and no
   response was recovered. A tool that was not requested is left out.
2. CANNOT TELL (`no_usable_setting`) when no setting has a response in the window.
3. Every gating measure gets a finding. Without enough days: `too_few_days`. Otherwise
   `streaky` if its before-days are streaky; else `real_drop`; else `no_drop`; else
   `cannot_tell`.
4. CANNOT TELL (`too_few_days`) when every finding is `too_few_days`.
5. CANNOT TELL (`streaky_days`) when any finding is `streaky`. The other measures keep the
   findings their own tests gave, and the output marks them as not used.
6. REAL DROP when any finding is `real_drop`.
7. NO DROP when all three findings are `no_drop`.
8. CANNOT TELL (`not_enough_evidence`) otherwise.

**Process exit code.** Among tools without ERROR: 1 if any is REAL DROP; otherwise 2 if any is
CANNOT TELL; otherwise 0. If every requested tool is ERROR, 3. A usage error, or a requested
output file that cannot be written, exits 3 whatever the results. Each tool's result is shown
separately from the one exit code.

No random number is drawn anywhere. The same day table gives the same result on any machine.

## What is claimed, and under which assumptions

All statements are per tool and for one comparison.

**A1 (days are interchangeable when nothing changes).** If the tool's behaviour did not change
at the split, then, given the window as the procedure above selects it, the joint
distribution of the window's daily records, for all settings together, is the same under any
reordering of the days. Treating the window as fixed does not make this true; it is assumed.

**A2 (nothing was chosen by looking).** Any `--since`, `--model`, `--effort` or `--project`
was fixed without reference to the records compared, or by a rule that does not depend on
which period a record is in. That excludes choosing by response counts in one period as much
as choosing by the measures.

**A3 (a change moves every day alike).** Each measure has its own shift `δ`. If a measure
changed, each after-day value is exactly what that day would have shown without the change,
moved by `δ` in exact arithmetic: multiplied by `1 − δ` for `reasoning_tokens`, shifted by
`δ` toward worse for a share. This is a model of the daily value, not of how a model
computes. It applies only where the moved value is one the measure can take (a positive
half-integer median, a share in [0, 1]); changes that round, clip, or differ from day to day
are outside it.

**A4 (a change leaves the comparison's frame as it was).** The change does not alter which
days are usable for a measure, which setting is selected, the reference count `v*`, or any
before-day value.

**Claim 1 (wrong REAL DROP).** Under A1 and A2, if nothing changed, the probability that a
tool's result is REAL DROP is at most 1/40 (2.5%).

**Claim 2 (wrong NO DROP).** Under A1 to A4, if at least one gating measure moved toward worse
by its margin or more, the probability that the tool's result is NO DROP is at most 1/40.

With two tools, the chance that at least one shows a wrong REAL DROP is at most 5%.

Nothing is claimed about cause, about answer quality, or about a change to a model. Between
the periods the user's tasks, prompts, projects, client version and habits may have changed,
and A1 fails when they did. The streak check does not establish any assumption. ARCI checks
none of A1 to A4 and says so in every output. Running the command again and again and
stopping at the first REAL DROP is outside both claims.

## Proof

*Selection keeps interchangeability.* The setting, `v*` and the usable-day rule are functions
of the window's records that do not use period labels: the setting and `v*` depend on the
unordered collection of records, and usability on each day's own record. Under A1 and A2 with
no change, the selected measure's usable day values are therefore exchangeable, and given how
many usable days fall in each period, every assignment of those values to the after period is
equally likely.

*Real-drop test.* Given the pooled multiset of values and the group sizes, the after group is
a uniformly random choice of `m` of the `n + m` values, which is exactly the reference
distribution of `p_real`. So `P(p_real ≤ α) ≤ α` for every `α`, with any ties.

*Claim 1.* At most three measures are tested, each at `(1/40)/3`; the union bound gives
`1/40` whatever the dependence between measures. The streak check only turns results into
CANNOT TELL, so the probability of a REAL DROP result is no larger with it than without it.

*No-drop test with ties.* Let `a_1..a_n, b_1..b_m` be exchangeable. Break ties by an
independent uniformly random order; the strict ranking is then a uniformly random
arrangement, so the count `U*` of pairs with `a_i` ranked below `b_j` satisfies
`P(U* ≥ u) = G(n, m, u)`. The strict count never exceeds it, `U ≤ U*`, and `G` is
non-increasing in `u`, so `P(G(n, m, U) ≤ α) ≤ P(G(n, m, U*) ≤ α) ≤ α`. The tie-breaking is a
device of the proof; the implementation draws nothing.

*Claim 2.* Suppose measure `k` moved by `δ ≥ margin`. By A3 and A4, its usable after-day
values are `y_j = g_δ(w_j)`, where `w_j` is the value without the change, and
`(x_1..x_n, w_1..w_m)` are exchangeable by the first paragraph. Let `g` be the margin move;
it is strictly increasing, so `(g(x_i), g(w_j))` are exchangeable, and `y_j ≤ g(w_j)` because
`δ ≥ margin`. The count `U` of pairs with `x'_i < y_j` is non-decreasing in each `y_j`, so it
is at most the count with `g(w_j)` in place of `y_j`, to which the previous paragraph
applies. Hence measure `k` is a no-drop with probability at most `α_none`. NO DROP needs every
gating measure to be a no-drop, measure `k` included; the streak check and the precedence of
REAL DROP only remove NO DROP results.

## What the method cannot see

- A measure with fewer than 5 usable after-days or 10 usable before-days is not tested. A
  period in which every response has a reasoning count of 0 has no usable day for
  `reasoning_tokens`, so the result cannot be NO DROP. Claude Code deletes old session files
  after a retention period, which limits the before period.
- **Days that come in streaks break A1, and the streak check is only a partial guard.**
  The final [self-check](results/logs-selfcheck.md), dated 2026-11-15, reports the tables
  below. Rates are proportions, copied without rounding; brackets are Wilson 95%
  intervals. Counts show the actual runs, not just the requested runs. These are simulation
  results for the stated generators, not evidence that a user's days satisfy A1.

### Correlation and the cost of the check

The table compares no check, a per-measure check, and the rule as built, which stops the
whole comparison when any measure is streaky. At positive correlation, the measured wrong
REAL DROP rate for the rule as built stays above 2.5% at 5/10 days for every tested positive
correlation, and at 7/21 days for correlations 0.3 and 0.5. The corresponding wrong NO DROP
point estimates for the rule as built stay below 2.5%; this does not restore a bound when A1 fails.

The independent-day power row at 14/42, log SD 0.40 and drop 9/20 shows the cost: REAL DROP
falls from 1975/2000 = 0.987500 [0.981612, 0.991519] without a check, to
1836/2000 = 0.918000 [0.905159, 0.929238] with a per-measure check, to
1524/2000 = 0.762000 [0.742845, 0.780150] with the rule as built (seed 16114135).
The rho=0 error rows also show the effect on independent days.

rho=0 has independent days; positive rho breaks A1. At drop=0, REAL DROP is the directional error; at drop=1/4, NO DROP is the directional error. The power row reports REAL DROP at a 45% drop and log SD 0.40. Section 4 builds day tables directly from the same generator (unit-checked against full Response/EditResult reduction); the production exact tests and decide_tool still run. No timing-based count reductions in this section.

| after/before | rho | log SD | drop | metric | seed | histories | no check (95% CI) | per-measure check (95% CI) | as built (95% CI) | seconds |
|---|---|---|---|---|---:|---:|---|---|---|---:|
| 5/10 | 0.0 | 0.45 | 0 | wrong REAL DROP | 16114103 | 2000 | 43/2000 = 0.021500 [0.016001, 0.028834] | 41/2000 = 0.020500 [0.015147, 0.027691] | 38/2000 = 0.019000 [0.013874, 0.025970] | 1.47 |
| 5/10 | 0.0 | 0.45 | 1/4 | wrong NO DROP | 16114104 | 2000 | 0/2000 = 0.000000 [0.000000, 0.001917] | 0/2000 = 0.000000 [0.000000, 0.001917] | 0/2000 = 0.000000 [0.000000, 0.001917] | 1.46 |
| 5/10 | 0.3 | 0.45 | 0 | wrong REAL DROP | 16114105 | 2000 | 147/2000 = 0.073500 [0.062863, 0.085773] | 137/2000 = 0.068500 [0.058236, 0.080418] | 117/2000 = 0.058500 [0.049036, 0.069657] | 1.47 |
| 5/10 | 0.3 | 0.45 | 1/4 | wrong NO DROP | 16114106 | 2000 | 7/2000 = 0.003500 [0.001696, 0.007207] | 4/2000 = 0.002000 [0.000778, 0.005131] | 4/2000 = 0.002000 [0.000778, 0.005131] | 1.46 |
| 5/10 | 0.5 | 0.45 | 0 | wrong REAL DROP | 16114107 | 2000 | 279/2000 = 0.139500 [0.125006, 0.155377] | 241/2000 = 0.120500 [0.106955, 0.135500] | 161/2000 = 0.080500 [0.069365, 0.093243] | 1.47 |
| 5/10 | 0.5 | 0.45 | 1/4 | wrong NO DROP | 16114108 | 2000 | 14/2000 = 0.007000 [0.004174, 0.011716] | 10/2000 = 0.005000 [0.002718, 0.009180] | 10/2000 = 0.005000 [0.002718, 0.009180] | 1.46 |
| 5/10 | 0.7 | 0.45 | 0 | wrong REAL DROP | 16114109 | 2000 | 539/2000 = 0.269500 [0.250510, 0.289374] | 436/2000 = 0.218000 [0.200455, 0.236627] | 236/2000 = 0.118000 [0.104588, 0.132876] | 1.45 |
| 5/10 | 0.7 | 0.45 | 1/4 | wrong NO DROP | 16114110 | 2000 | 38/2000 = 0.019000 [0.013874, 0.025970] | 22/2000 = 0.011000 [0.007275, 0.016599] | 22/2000 = 0.011000 [0.007275, 0.016599] | 1.44 |
| 7/21 | 0.0 | 0.45 | 0 | wrong REAL DROP | 16114111 | 2000 | 47/2000 = 0.023500 [0.017718, 0.031109] | 44/2000 = 0.022000 [0.016429, 0.029404] | 42/2000 = 0.021000 [0.015574, 0.028263] | 2.88 |
| 7/21 | 0.0 | 0.45 | 1/4 | wrong NO DROP | 16114112 | 2000 | 3/2000 = 0.001500 [0.000510, 0.004401] | 0/2000 = 0.000000 [0.000000, 0.001917] | 0/2000 = 0.000000 [0.000000, 0.001917] | 2.85 |
| 7/21 | 0.3 | 0.45 | 0 | wrong REAL DROP | 16114113 | 2000 | 167/2000 = 0.083500 [0.072160, 0.096437] | 136/2000 = 0.068000 [0.057775, 0.079882] | 66/2000 = 0.033000 [0.026023, 0.041768] | 2.86 |
| 7/21 | 0.3 | 0.45 | 1/4 | wrong NO DROP | 16114114 | 2000 | 14/2000 = 0.007000 [0.004174, 0.011716] | 9/2000 = 0.004500 [0.002369, 0.008531] | 9/2000 = 0.004500 [0.002369, 0.008531] | 2.82 |
| 7/21 | 0.5 | 0.45 | 0 | wrong REAL DROP | 16114115 | 2000 | 327/2000 = 0.163500 [0.147940, 0.180350] | 211/2000 = 0.105500 [0.092785, 0.119728] | 71/2000 = 0.035500 [0.028240, 0.044541] | 2.84 |
| 7/21 | 0.5 | 0.45 | 1/4 | wrong NO DROP | 16114116 | 2000 | 46/2000 = 0.023000 [0.017288, 0.030541] | 10/2000 = 0.005000 [0.002718, 0.009180] | 10/2000 = 0.005000 [0.002718, 0.009180] | 2.81 |
| 7/21 | 0.7 | 0.45 | 0 | wrong REAL DROP | 16114117 | 2000 | 697/2000 = 0.348500 [0.327925, 0.369655] | 312/2000 = 0.156000 [0.140758, 0.172560] | 28/2000 = 0.014000 [0.009704, 0.020160] | 2.81 |
| 7/21 | 0.7 | 0.45 | 1/4 | wrong NO DROP | 16114118 | 2000 | 65/2000 = 0.032500 [0.025581, 0.041212] | 1/2000 = 0.000500 [0.000088, 0.002827] | 1/2000 = 0.000500 [0.000088, 0.002827] | 2.78 |
| 14/42 | 0.0 | 0.45 | 0 | wrong REAL DROP | 16114119 | 2000 | 40/2000 = 0.020000 [0.014722, 0.027119] | 39/2000 = 0.019500 [0.014297, 0.026545] | 31/2000 = 0.015500 [0.010941, 0.021917] | 10.53 |
| 14/42 | 0.0 | 0.45 | 1/4 | wrong NO DROP | 16114120 | 2000 | 7/2000 = 0.003500 [0.001696, 0.007207] | 4/2000 = 0.002000 [0.000778, 0.005131] | 4/2000 = 0.002000 [0.000778, 0.005131] | 11.48 |
| 14/42 | 0.3 | 0.45 | 0 | wrong REAL DROP | 16114121 | 2000 | 207/2000 = 0.103500 [0.090901, 0.117619] | 122/2000 = 0.061000 [0.051329, 0.072354] | 34/2000 = 0.017000 [0.012191, 0.023661] | 10.37 |
| 14/42 | 0.3 | 0.45 | 1/4 | wrong NO DROP | 16114122 | 2000 | 33/2000 = 0.016500 [0.011773, 0.023081] | 8/2000 = 0.004000 [0.002028, 0.007873] | 8/2000 = 0.004000 [0.002028, 0.007873] | 10.29 |
| 14/42 | 0.5 | 0.45 | 0 | wrong REAL DROP | 16114123 | 2000 | 411/2000 = 0.205500 [0.188364, 0.223765] | 113/2000 = 0.056500 [0.047205, 0.067495] | 5/2000 = 0.002500 [0.001068, 0.005839] | 10.24 |
| 14/42 | 0.5 | 0.45 | 1/4 | wrong NO DROP | 16114124 | 2000 | 62/2000 = 0.031000 [0.024257, 0.039541] | 1/2000 = 0.000500 [0.000088, 0.002827] | 1/2000 = 0.000500 [0.000088, 0.002827] | 10.18 |
| 14/42 | 0.7 | 0.45 | 0 | wrong REAL DROP | 16114125 | 2000 | 742/2000 = 0.371000 [0.350095, 0.392400] | 74/2000 = 0.037000 [0.029575, 0.046200] | 0/2000 = 0.000000 [0.000000, 0.001917] | 10.07 |
| 14/42 | 0.7 | 0.45 | 1/4 | wrong NO DROP | 16114126 | 2000 | 102/2000 = 0.051000 [0.042190, 0.061532] | 0/2000 = 0.000000 [0.000000, 0.001917] | 0/2000 = 0.000000 [0.000000, 0.001917] | 10.57 |
| 28/84 | 0.0 | 0.45 | 0 | wrong REAL DROP | 16114127 | 1000 | 27/1000 = 0.027000 [0.018621, 0.038999] | 26/1000 = 0.026000 [0.017804, 0.037824] | 22/1000 = 0.022000 [0.014573, 0.033086] | 69.13 |
| 28/84 | 0.0 | 0.45 | 1/4 | wrong NO DROP | 16114128 | 1000 | 9/1000 = 0.009000 [0.004742, 0.017016] | 7/1000 = 0.007000 [0.003395, 0.014378] | 7/1000 = 0.007000 [0.003395, 0.014378] | 69.00 |
| 28/84 | 0.3 | 0.45 | 0 | wrong REAL DROP | 16114129 | 1000 | 104/1000 = 0.104000 [0.086571, 0.124460] | 36/1000 = 0.036000 [0.026116, 0.049436] | 3/1000 = 0.003000 [0.001021, 0.008783] | 68.36 |
| 28/84 | 0.3 | 0.45 | 1/4 | wrong NO DROP | 16114130 | 1000 | 26/1000 = 0.026000 [0.017804, 0.037824] | 1/1000 = 0.001000 [0.000177, 0.005643] | 1/1000 = 0.001000 [0.000177, 0.005643] | 68.48 |
| 28/84 | 0.5 | 0.45 | 0 | wrong REAL DROP | 16114131 | 1000 | 218/1000 = 0.218000 [0.193515, 0.244643] | 21/1000 = 0.021000 [0.013776, 0.031890] | 0/1000 = 0.000000 [0.000000, 0.003827] | 67.95 |
| 28/84 | 0.5 | 0.45 | 1/4 | wrong NO DROP | 16114132 | 1000 | 38/1000 = 0.038000 [0.027809, 0.051727] | 0/1000 = 0.000000 [0.000000, 0.003827] | 0/1000 = 0.000000 [0.000000, 0.003827] | 68.06 |
| 28/84 | 0.7 | 0.45 | 0 | wrong REAL DROP | 16114133 | 1000 | 381/1000 = 0.381000 [0.351410, 0.411500] | 0/1000 = 0.000000 [0.000000, 0.003827] | 0/1000 = 0.000000 [0.000000, 0.003827] | 67.21 |
| 28/84 | 0.7 | 0.45 | 1/4 | wrong NO DROP | 16114134 | 1000 | 71/1000 = 0.071000 [0.056670, 0.088614] | 0/1000 = 0.000000 [0.000000, 0.003827] | 0/1000 = 0.000000 [0.000000, 0.003827] | 67.96 |
| 14/42 | 0.0 | 0.4 | 9/20 | REAL DROP | 16114135 | 2000 | 1975/2000 = 0.987500 [0.981612, 0.991519] | 1836/2000 = 0.918000 [0.905159, 0.929238] | 1524/2000 = 0.762000 [0.742845, 0.780150] | 10.72 |


### Power of the rule as built

Power is limited at the sizes most people have. The following table uses the final rule,
including the whole-comparison streak check. Reasoning counts are log-normal, quantized to
multiples of 100 before exact changes. Independent shares are rounded
`0.10 + 0.25 Phi(Z)` and `0.05 + 0.25 Phi(Z)`, with denominator 100.
Claude Code's measures pass through response and edit records, day reduction, and the
production decision rule. Pilot timing alone reduced some run counts; the denominators
are the runs actually made. A drop of 0 is the no-change design, not power against a drop.
The simulation thresholds check the implementation; the bounds above are proved, not
simulated. Seeds, designs, requested counts and intervals are copied from the self-check.

| after/before | log SD | drop | seed | requested | REAL DROP (95% CI) | NO DROP (95% CI) | seconds |
|---|---|---|---:|---:|---|---|---:|
| 5/10 | 0.35 | 0 | 16113042 | 2000 | 47/2000 = 0.023500 [0.017718, 0.031109] | 13/2000 = 0.006500 [0.003803, 0.011090] | 3.13 |
| 5/10 | 0.35 | 33/100 | 16113043 | 2000 | 453/2000 = 0.226500 [0.208690, 0.245358] | 0/2000 = 0.000000 [0.000000, 0.001917] | 3.07 |
| 5/10 | 0.35 | 9/20 | 16113044 | 2000 | 1043/2000 = 0.521500 [0.499587, 0.543331] | 0/2000 = 0.000000 [0.000000, 0.001917] | 3.04 |
| 5/10 | 0.35 | 1/2 | 16113045 | 2000 | 1292/2000 = 0.646000 [0.624780, 0.666660] | 0/2000 = 0.000000 [0.000000, 0.001917] | 3.05 |
| 5/10 | 0.35 | 11/20 | 16113046 | 2000 | 1499/2000 = 0.749500 [0.730044, 0.767999] | 0/2000 = 0.000000 [0.000000, 0.001917] | 3.01 |
| 5/10 | 0.45 | 0 | 16113047 | 2000 | 37/2000 = 0.018500 [0.013451, 0.025395] | 10/2000 = 0.005000 [0.002718, 0.009180] | 3.07 |
| 5/10 | 0.45 | 33/100 | 16113048 | 2000 | 301/2000 = 0.150500 [0.135500, 0.166840] | 2/2000 = 0.001000 [0.000274, 0.003639] | 3.05 |
| 5/10 | 0.45 | 9/20 | 16113049 | 2000 | 609/2000 = 0.304500 [0.284722, 0.325028] | 0/2000 = 0.000000 [0.000000, 0.001917] | 3.05 |
| 5/10 | 0.45 | 1/2 | 16113050 | 2000 | 824/2000 = 0.412000 [0.390618, 0.433720] | 0/2000 = 0.000000 [0.000000, 0.001917] | 3.03 |
| 5/10 | 0.45 | 11/20 | 16113051 | 2000 | 1093/2000 = 0.546500 [0.524614, 0.568208] | 0/2000 = 0.000000 [0.000000, 0.001917] | 3.02 |
| 5/10 | 0.55 | 0 | 16113052 | 2000 | 36/2000 = 0.018000 [0.013030, 0.024818] | 12/2000 = 0.006000 [0.003436, 0.010458] | 3.75 |
| 5/10 | 0.55 | 33/100 | 16113053 | 2000 | 168/2000 = 0.084000 [0.072626, 0.096969] | 1/2000 = 0.000500 [0.000088, 0.002827] | 3.06 |
| 5/10 | 0.55 | 9/20 | 16113054 | 2000 | 394/2000 = 0.197000 [0.180157, 0.215005] | 0/2000 = 0.000000 [0.000000, 0.001917] | 3.06 |
| 5/10 | 0.55 | 1/2 | 16113055 | 2000 | 546/2000 = 0.273000 [0.253924, 0.292946] | 0/2000 = 0.000000 [0.000000, 0.001917] | 3.43 |
| 5/10 | 0.55 | 11/20 | 16113056 | 2000 | 733/2000 = 0.366500 [0.345657, 0.387855] | 0/2000 = 0.000000 [0.000000, 0.001917] | 3.04 |
| 7/21 | 0.35 | 0 | 16113057 | 2000 | 24/1389 = 0.017279 [0.011638, 0.025582] | 42/1389 = 0.030238 [0.022447, 0.040619] | 4.08 |
| 7/21 | 0.35 | 33/100 | 16113058 | 2000 | 620/1396 = 0.444126 [0.418250, 0.470308] | 0/1396 = 0.000000 [0.000000, 0.002744] | 4.05 |
| 7/21 | 0.35 | 9/20 | 16113059 | 2000 | 1044/1402 = 0.744650 [0.721178, 0.766786] | 0/1402 = 0.000000 [0.000000, 0.002732] | 4.05 |
| 7/21 | 0.35 | 1/2 | 16113060 | 2000 | 1111/1408 = 0.789062 [0.766981, 0.809571] | 0/1408 = 0.000000 [0.000000, 0.002721] | 4.05 |
| 7/21 | 0.35 | 11/20 | 16113061 | 2000 | 1095/1351 = 0.810511 [0.788744, 0.830517] | 0/1351 = 0.000000 [0.000000, 0.002835] | 3.88 |
| 7/21 | 0.45 | 0 | 16113062 | 2000 | 28/1383 = 0.020246 [0.014044, 0.029105] | 25/1383 = 0.018077 [0.012274, 0.026549] | 4.06 |
| 7/21 | 0.45 | 33/100 | 16113063 | 2000 | 349/1404 = 0.248575 [0.226675, 0.271848] | 1/1404 = 0.000712 [0.000126, 0.004023] | 4.10 |
| 7/21 | 0.45 | 9/20 | 16113064 | 2000 | 748/1397 = 0.535433 [0.509218, 0.561454] | 0/1397 = 0.000000 [0.000000, 0.002742] | 4.04 |
| 7/21 | 0.45 | 1/2 | 16113065 | 2000 | 899/1397 = 0.643522 [0.618044, 0.668213] | 0/1397 = 0.000000 [0.000000, 0.002742] | 4.03 |
| 7/21 | 0.45 | 11/20 | 16113066 | 2000 | 1081/1440 = 0.750694 [0.727703, 0.772352] | 0/1440 = 0.000000 [0.000000, 0.002661] | 4.15 |
| 7/21 | 0.55 | 0 | 16113067 | 2000 | 23/1389 = 0.016559 [0.011059, 0.024725] | 20/1389 = 0.014399 [0.009340, 0.022136] | 4.08 |
| 7/21 | 0.55 | 33/100 | 16113068 | 2000 | 229/1406 = 0.162873 [0.144496, 0.183088] | 1/1406 = 0.000711 [0.000126, 0.004018] | 4.58 |
| 7/21 | 0.55 | 9/20 | 16113069 | 2000 | 376/961 = 0.391259 [0.360895, 0.422489] | 0/961 = 0.000000 [0.000000, 0.003981] | 3.01 |
| 7/21 | 0.55 | 1/2 | 16113070 | 2000 | 730/1415 = 0.515901 [0.489854, 0.541862] | 0/1415 = 0.000000 [0.000000, 0.002707] | 4.11 |
| 7/21 | 0.55 | 11/20 | 16113071 | 2000 | 869/1415 = 0.614134 [0.588494, 0.639157] | 0/1415 = 0.000000 [0.000000, 0.002707] | 4.08 |
| 14/42 | 0.35 | 0 | 16113072 | 2000 | 11/538 = 0.020446 [0.011454, 0.036238] | 43/538 = 0.079926 [0.059877, 0.105930] | 4.37 |
| 14/42 | 0.35 | 33/100 | 16113073 | 2000 | 383/546 = 0.701465 [0.661782, 0.738333] | 0/546 = 0.000000 [0.000000, 0.006986] | 4.34 |
| 14/42 | 0.35 | 9/20 | 16113074 | 2000 | 397/492 = 0.806911 [0.769708, 0.839357] | 0/492 = 0.000000 [0.000000, 0.007747] | 3.92 |
| 14/42 | 0.35 | 1/2 | 16113075 | 2000 | 402/514 = 0.782101 [0.744391, 0.815626] | 0/514 = 0.000000 [0.000000, 0.007418] | 4.07 |
| 14/42 | 0.35 | 11/20 | 16113076 | 2000 | 398/523 = 0.760994 [0.722625, 0.795558] | 0/523 = 0.000000 [0.000000, 0.007291] | 4.13 |
| 14/42 | 0.45 | 0 | 16113077 | 2000 | 8/483 = 0.016563 [0.008416, 0.032339] | 44/483 = 0.091097 [0.068561, 0.120087] | 3.90 |
| 14/42 | 0.45 | 33/100 | 16113078 | 2000 | 230/459 = 0.501089 [0.455529, 0.546632] | 0/459 = 0.000000 [0.000000, 0.008300] | 3.67 |
| 14/42 | 0.45 | 9/20 | 16113079 | 2000 | 364/500 = 0.728000 [0.687367, 0.765156] | 0/500 = 0.000000 [0.000000, 0.007624] | 3.98 |
| 14/42 | 0.45 | 1/2 | 16113080 | 2000 | 387/519 = 0.745665 [0.706488, 0.781232] | 0/519 = 0.000000 [0.000000, 0.007347] | 4.11 |
| 14/42 | 0.45 | 11/20 | 16113081 | 2000 | 387/494 = 0.783401 [0.744963, 0.817465] | 0/494 = 0.000000 [0.000000, 0.007716] | 3.93 |
| 14/42 | 0.55 | 0 | 16113082 | 2000 | 12/480 = 0.025000 [0.014358, 0.043185] | 18/480 = 0.037500 [0.023850, 0.058494] | 3.90 |
| 14/42 | 0.55 | 33/100 | 16113083 | 2000 | 166/517 = 0.321083 [0.282284, 0.362522] | 0/517 = 0.000000 [0.000000, 0.007375] | 4.16 |
| 14/42 | 0.55 | 9/20 | 16113084 | 2000 | 327/514 = 0.636187 [0.593728, 0.676625] | 0/514 = 0.000000 [0.000000, 0.007418] | 4.76 |
| 14/42 | 0.55 | 1/2 | 16113085 | 2000 | 348/486 = 0.716049 [0.674388, 0.754322] | 0/486 = 0.000000 [0.000000, 0.007842] | 4.24 |
| 14/42 | 0.55 | 11/20 | 16113086 | 2000 | 399/518 = 0.770270 [0.732134, 0.804427] | 0/518 = 0.000000 [0.000000, 0.007361] | 4.15 |
| 28/84 | 0.35 | 0 | 16113087 | 2000 | 2/60 = 0.033333 [0.009189, 0.113638] | 15/60 = 0.250000 [0.157765, 0.372321] | 4.33 |
| 28/84 | 0.35 | 33/100 | 16113088 | 2000 | 41/53 = 0.773585 [0.644737, 0.865454] | 0/53 = 0.000000 [0.000000, 0.067582] | 3.90 |
| 28/84 | 0.35 | 9/20 | 16113089 | 2000 | 42/58 = 0.724138 [0.597953, 0.822476] | 0/58 = 0.000000 [0.000000, 0.062118] | 4.13 |
| 28/84 | 0.35 | 1/2 | 16113090 | 2000 | 39/59 = 0.661017 [0.533725, 0.768623] | 0/59 = 0.000000 [0.000000, 0.061129] | 4.13 |
| 28/84 | 0.35 | 11/20 | 16113091 | 2000 | 36/54 = 0.666667 [0.533610, 0.777586] | 0/54 = 0.000000 [0.000000, 0.066414] | 3.85 |
| 28/84 | 0.45 | 0 | 16113092 | 2000 | 1/53 = 0.018868 [0.003338, 0.099429] | 11/53 = 0.207547 [0.120046, 0.334577] | 3.88 |
| 28/84 | 0.45 | 33/100 | 16113093 | 2000 | 43/53 = 0.811321 [0.686415, 0.894147] | 0/53 = 0.000000 [0.000000, 0.067582] | 3.97 |
| 28/84 | 0.45 | 9/20 | 16113094 | 2000 | 49/60 = 0.816667 [0.700802, 0.894422] | 0/60 = 0.000000 [0.000000, 0.060172] | 4.44 |
| 28/84 | 0.45 | 1/2 | 16113095 | 2000 | 43/53 = 0.811321 [0.686415, 0.894147] | 0/53 = 0.000000 [0.000000, 0.067582] | 3.97 |
| 28/84 | 0.45 | 11/20 | 16113096 | 2000 | 40/59 = 0.677966 [0.551050, 0.783124] | 0/59 = 0.000000 [0.000000, 0.061129] | 4.21 |
| 28/84 | 0.55 | 0 | 16113097 | 2000 | 3/60 = 0.050000 [0.017150, 0.137005] | 5/60 = 0.083333 [0.036120, 0.180689] | 4.20 |
| 28/84 | 0.55 | 33/100 | 16113098 | 2000 | 32/52 = 0.615385 [0.479599, 0.735295] | 0/52 = 0.000000 [0.000000, 0.068792] | 3.89 |
| 28/84 | 0.55 | 9/20 | 16113099 | 2000 | 38/52 = 0.730769 [0.597478, 0.832310] | 0/52 = 0.000000 [0.000000, 0.068792] | 4.15 |
| 28/84 | 0.55 | 1/2 | 16113100 | 2000 | 33/42 = 0.785714 [0.640602, 0.882942] | 0/42 = 0.000000 [0.000000, 0.083799] | 3.35 |
| 28/84 | 0.55 | 11/20 | 16113101 | 2000 | 55/68 = 0.808824 [0.699894, 0.884727] | 0/68 = 0.000000 [0.000000, 0.053471] | 5.03 |
| 14/42 | 0.4 | 9/20 | 16113102 | 2000 | 397/495 = 0.802020 [0.764649, 0.834740] | 0/495 = 0.000000 [0.000000, 0.007701] | 3.94 |


- A change that began before the before period, a change in how a vendor counts tokens, and a
  change in what the user works on all look the same to the test.
- One person's logs say nothing about another person's.

## Checks that agents run (`bench/selfcheck_logs.py`)

1. `G(n, m, u)` and `p_real` equal brute-force enumeration for every `n + m ≤ 14` (for
   `p_real` on tie patterns: none; three levels; all equal).
2. For those cases, the share of labelings on which each test rejects at `α` is at most `α`.
3. Null simulation with the final rule, including setting selection, usable-day rules and the
   streak check: 20,000 seeded day tables per design (5/10, 7/21, 14/42, 28/84), measures
   independent and measures with identical ranks; the rate of REAL DROP is at most 0.0283.
   With one measure exactly at its margin and the others unchanged, the rate of NO DROP is at
   most 0.0283.
4. The rejection-rate table for the final rule, including the 45% reasoning-token drop at
   14/42 with a log standard deviation of 0.40, each cell with its generator, seed, number of
   simulations and sampling error. There is no power threshold: the streak check alone caps
   power near 78% at 42 before-days.
5. The exact runs distribution equals brute-force enumeration for every `a + b ≤ 14`.
6. Reported, not gated: the wrong-REAL and wrong-NO-DROP rates when day values follow an AR(1)
   process with coefficient 0.3, 0.5 and 0.7, which breaks A1, with no check, with a
   per-measure check, and with the rule as built; and the reviewer's two counterexamples (selection by
   after-period counts; a change that swaps which days are usable), each shown to break the
   bound when its assumption is dropped.
