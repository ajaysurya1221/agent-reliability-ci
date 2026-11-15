# The session-log contract (arci-logs/2)

The design record is [0017](design/0017-logs-2.md). Record [0016](design/0016-logs.md) is the
record of `arci-logs/1` and is needed only for `arci-logs/1` records.

This document specifies `arci logs` (also installed as `realornoise`). It reads session logs
that Claude Code or Codex already wrote on the user's disk, reduces them to one number per
measure per day, and compares the days after a split date with the days before it. It runs no
model and no trial. Nothing in `STATISTICS_SUITE.md` or `STATISTICS_OUTCOMES.md` applies here:
there are no pairs, no rounds and no betting wealth. The data are observational, and the result
names are different on purpose. The sections "Record model", "Fixed texts" and "The kept day
table" of record 0017 are part of this contract.

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
  represented in the calendar, the run is a usage error. A row of the kept day table carries
  the offset of the run that wrote it; only rows at the current run's offset are used.
- **Window.** `N` is the newest day with a main-thread response of the tool in the logs, after
  the `--project` filter. Kept rows never set `N`. The split date `s` is `N − 13` days unless the user gives `--since`. The
  after period is `s` to `N`. The before period is the 84 days ending the day before `s`. A
  `--since` later than `N` gives an after period with no days.
- **Setting (changed in `arci-logs/2`).** A setting is a model id and an effort value as the
  log records them. The candidates are the settings with at least one main-thread response in
  the window, on the days as used (section "Days from the kept table"); `--model` and
  `--effort` keep only the candidates with those rendered names. The candidate with the most
  main-thread responses in the after period, `s` to `N`, is compared; ties go to the candidate
  whose raw model id is first in code-point order, and with equal model ids to the one whose raw
  effort is first in code-point order. A response counts whether or not its reasoning count is
  known; no reasoning count and no file-edit result enters the choice. When no candidate has an
  after-period response, the same count rule runs over the before period, with the same ties.
  Responses that lack a model or an effort belong to no setting. If no candidate remains (no
  setting has a main-thread response in the window, or none has the names given with `--model`
  and `--effort`), the result is CANNOT TELL (`no_usable_setting`); the tool never switches to
  another setting because it has more usable days. Section "Proof" shows that this choice
  depends on the log structure only.
  `arci-logs/1` counted responses over both periods together; on a real machine with a long
  history that chose a setting with no response in the last 14 days.
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

## Days from the kept table

With `--keep`, a table of daily counts (schema `realornoise-days/1`, record 0017) is written
outside the vendors' folders. Each row holds, for one tool, UTC offset, setting and day, the
number of main-thread responses, the frequency of each known reasoning count (0 included), the
number of unknown counts, and for Claude Code the file-edit results and the failed ones. That is
enough to compute every day value of the table above.

For each setting and day in the window, the row from the logs is used when it has at least as
many responses as the stored row; otherwise the stored row is used. Which row a day uses depends
on response counts only. The candidates, the after-period counts of the setting choice, `v*`,
the usable days and the tests then run on the days as used, with no other change.

The kept table changes no claim. The claims are statements about the days the comparison uses.
The rule that picks a day's row reads response counts, which are part of the log structure
defined in the proof, and never a day value, so the proof below covers the days as used without
change. What the table changes is which days exist to be compared: it can supply before-days
whose session files are gone. It also adds ways for A1 to fail, listed below.

Its limits: kept rows are not checked against logs again; they hold the counts as the readers
of the version that wrote them saw them; an edited table gives an edited result, and the seal
does not detect a table edited before the run. The output marks kept days (a count line, and
`source: "kept"` on each such day in the JSON record, which the day-table digest covers). Rows
are kept only for settings whose names pass the bounded name rules, and for at most 180 days
before `N`. A row, from the logs or kept, can hold only part of a day: a kept row written before
its day ended, or a log row after some of the day's session files were deleted; its value then
describes only those responses. Kept days are almost always before-days, so any difference
between kept and log rows, such as a reader change between versions or a partial day, falls on
one period and breaks A1. Where clocks change for daylight saving, rows written before a change are at another offset and
are not used after it (counted in F25); `--utc` keeps one offset all year.

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
2. CANNOT TELL (`no_usable_setting`) when no candidate setting remains.
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

The **log structure** of a run is: which responses of the tool exist in the window, the day of
each, its setting (or none) and its thread, and, for days from the kept table, the same facts
as the row records them (its day, setting and number of responses). Reasoning counts, file-edit
results and day values are not part of it.

**A1 (days are interchangeable when nothing changes; restated in `arci-logs/2`).** If the
tool's behaviour did not change at the split, then, given the log structure, the options of the
run and which days are usable for a measure, the usable day values of the compared setting for
that measure are exchangeable: every assignment of those values to those days is equally
likely. When a measure changed, the same holds for the values the days would have shown without
the change, given the log structure, options and usable days of the run. Treating the structure
as fixed does not make this true; it is assumed. It fails, for example, when a day's value
depends on how many responses the setting had that day, in level or in spread; a median or
share over more responses varies less, so when the compared setting has more responses per day
after the split than before, A1 can fail with no change in behaviour. arci-logs/1 did not need
this, because it treated the counts as interchangeable too. It also fails when neighbouring days
resemble each other.

**A2 (nothing was chosen by looking).** Any `--since`, `--model`, `--effort` or `--project`
was fixed without reference to the reasoning counts, file-edit results or day values of the
records compared, or by a rule that depends on the log structure only, so that, given the log
structure, the options carry no information about those values. Choosing a date, model or
effort because a measure looked low is excluded.

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

**How far the bound can fail.** Both claims need A1, and Claim 2 also A3 and A4, together with
A2. When neighbouring days resemble each other, A1 fails and the bounds are no longer
guaranteed. The self-check measures how far they can fail in the cases it tests. The text
output, the HTML page and each non-ERROR Markdown block print two of its figures (the text and
HTML in the closing limits paragraph, the Markdown in the footer): the largest wrong REAL DROP
rate of the rule as built, over the tested positive correlations, with 5 days after the split
against 10 before (`{rate_5_10}`) and with 7 against 21 (`{rate_7_21}`). A test holds the
printed figures equal to the self-check file. In the 2.3.0 self-check these two figures were
0.118000 and 0.035500; the 2.4.0 self-check replaces them.

Nothing is claimed about cause, about answer quality, or about a change to a model. Between
the periods the user's tasks, prompts, projects, client version and habits may have changed,
and A1 fails when they did. The streak check does not establish any assumption. ARCI checks
none of A1 to A4 and says so in every output. Running the command again and again and
stopping at the first REAL DROP is outside both claims.

## Proof

*The choice depends on the log structure only.* Statement: fix the log structure, the options
and, for each measure, which days are usable. Then the compared setting, the split, the window
and the source of each day are the same for every assignment of the compared setting's usable
day values to its usable days. In particular, the choice is the same in every permutation of
those values with the group sizes fixed.

Proof. `N` is the newest day with a main-thread response in the logs: a function of the
structure. The split is `N - 13`, or the `--since` date, which A2 fixes without reference to
values. The window follows from `N` and the split. Which row a day uses (logs or kept) depends on
two response counts, both part of the structure. The candidates are the settings with a
main-thread response in the window, kept by `--model` and `--effort` (fixed by A2). Each
candidate's score is its number of main-thread responses dated `s` to `N` (or, when no candidate
has one, in the before period): a count over the structure. Ties go to the order of raw names,
also part of the structure. No step reads a reasoning count, a file-edit result or a day value. A permutation of the compared setting's
usable day values with the group sizes fixed changes values only, so it changes none of these
inputs, and the chosen setting, split, window and day sources are the same. The usable days, and
so `n` and `m`, are held fixed by the statement.

*Selection keeps interchangeability.* By the statement, under A2 the selection is fixed once
the structure and the usable days are fixed. `v*` depends on the unordered collection of the
setting's counts in the window and not on period labels. A1 then says directly that the
compared setting's usable day values are exchangeable given the log structure, the options and
the usable days, so given how many usable
days fall in each period, every assignment of those values to the after period is equally
likely. This is what the tests below need. Choosing by after-period counts was excluded in
`arci-logs/1` because A1 was then stated without conditioning on the structure; under that A1,
a choice by after-period counts could make a wrong REAL DROP certain (the 2.3.0 self-check's
counterexample). That construction links response counts to day values, so it breaks the
restated A1 and remains a demonstration of A1 failing.

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
`(x_1..x_n, w_1..w_m)` are exchangeable by A1, applied to the values without the change, given
the run's log structure, options and usable days; A4 keeps those usable days, the setting and
`v*` the same. Let `g` be the margin move;
it is strictly increasing, so `(g(x_i), g(w_j))` are exchangeable, and `y_j ≤ g(w_j)` because
`δ ≥ margin`. The count `U` of pairs with `x'_i < y_j` is non-decreasing in each `y_j`, so it
is at most the count with `g(w_j)` in place of `y_j`, to which the previous paragraph
applies. Hence measure `k` is a no-drop with probability at most `α_none`. NO DROP needs every
gating measure to be a no-drop, measure `k` included; the streak check and the precedence of
REAL DROP only remove NO DROP results.

## What the method cannot see

- A measure with fewer than 5 usable after-days or 10 usable before-days is not tested. A
  period in which every response has a reasoning count of 0 has no usable day for
  `reasoning_tokens`, so the result cannot be NO DROP.
- **Claude Code keeps session files for 30 days by default.** Its setting `cleanupPeriodDays`
  sets how long Claude Code keeps session files before it deletes them, with a default of 30
  days (https://code.claude.com/docs/en/settings-reference, read 15 Nov 2026). With the default
  and the default split, the after period takes 14 of those days, so the before period has at
  most about 16 days of files, not 84. At least 10 of them must be usable for a measure to be
  tested, so a default user often gets CANNOT TELL (`too_few_days`) on Claude Code. The output
  then names the first date a test is possible in the best case. Days whose files are gone come
  back only from the kept table, and only if `--keep` ran while the files existed. This tool
  does not change the Claude Code setting.
- **A setting adopted recently** has few earlier days, and its first days may differ from later
  ones, for example while the user learns it; A1 can then fail. The tool does not compare across
  a change of model or effort: the days of other settings never fill the compared setting's
  before period. When a setting was adopted after the split, its before period is empty and the
  result is CANNOT TELL (`too_few_days`).
- **Days that come in streaks break A1, and the streak check is only a partial guard.**
  The [self-check](results/logs-selfcheck.md) of 2.3.0, dated 2026-11-15, reports the tables
  below; the 2.4.0 self-check replaces them. Rates are proportions, copied without rounding; brackets are Wilson 95%
  intervals. Counts show the actual runs, not just the requested runs. These are simulation
  results for the stated generators, not evidence that a user's days satisfy A1.

### Correlation and the cost of the check

The table compares no check, a per-measure check, and the rule as built, which stops the
whole comparison when any measure is streaky. In the 2.3.0 self-check, at positive
correlation, the measured wrong
REAL DROP rate for the rule as built stays above 0.025 at 5/10 days for every tested positive
correlation, and at 7/21 days for correlations 0.3 and 0.5. The corresponding wrong NO DROP
point estimates for the rule as built stay below 0.025; this does not restore a bound when A1 fails.

The independent-day power row at 14/42, log SD 0.40 and drop 9/20 shows the cost (2.3.0
figures): REAL DROP
falls from 1975/2000 = 0.987500 [0.981612, 0.991519] without a check, to
1836/2000 = 0.918000 [0.905159, 0.929238] with a per-measure check, to
1524/2000 = 0.762000 [0.742845, 0.780150] with the rule as built (seed 16114135).
The rho=0 error rows also show the effect on independent days.

rho=0 has independent days; positive rho breaks A1. At drop=0, REAL DROP is the directional error; at drop=1/4, NO DROP is the directional error. The power row reports REAL DROP at a 45% drop and log SD 0.40. Section 4 builds day tables directly from the same generator (unit-checked against full Response/EditResult reduction); the production exact tests and decide_tool still run. No timing-based count reductions in this section.

figures from the 2.3.0 self-check; replaced at the 2.4.0 self-check

| after/before | rho | log SD | drop | metric | seed | histories | no check (95% CI) | per-measure check (95% CI) | as built (95% CI) | seconds |
|---|---|---|---|---|---:|---:|---|---|---|---:|
| 5/10 | 0.0 | 0.45 | 0 | wrong REAL DROP | 16114103 | 2000 | 43/2000 = 0.021500 [0.016001, 0.028834] | 41/2000 = 0.020500 [0.015147, 0.027691] | 38/2000 = 0.019000 [0.013874, 0.025970] | 2.24 |
| 5/10 | 0.0 | 0.45 | 1/4 | wrong NO DROP | 16114104 | 2000 | 0/2000 = 0.000000 [0.000000, 0.001917] | 0/2000 = 0.000000 [0.000000, 0.001917] | 0/2000 = 0.000000 [0.000000, 0.001917] | 2.23 |
| 5/10 | 0.3 | 0.45 | 0 | wrong REAL DROP | 16114105 | 2000 | 147/2000 = 0.073500 [0.062863, 0.085773] | 137/2000 = 0.068500 [0.058236, 0.080418] | 117/2000 = 0.058500 [0.049036, 0.069657] | 2.16 |
| 5/10 | 0.3 | 0.45 | 1/4 | wrong NO DROP | 16114106 | 2000 | 7/2000 = 0.003500 [0.001696, 0.007207] | 4/2000 = 0.002000 [0.000778, 0.005131] | 4/2000 = 0.002000 [0.000778, 0.005131] | 2.13 |
| 5/10 | 0.5 | 0.45 | 0 | wrong REAL DROP | 16114107 | 2000 | 279/2000 = 0.139500 [0.125006, 0.155377] | 241/2000 = 0.120500 [0.106955, 0.135500] | 161/2000 = 0.080500 [0.069365, 0.093243] | 2.55 |
| 5/10 | 0.5 | 0.45 | 1/4 | wrong NO DROP | 16114108 | 2000 | 14/2000 = 0.007000 [0.004174, 0.011716] | 10/2000 = 0.005000 [0.002718, 0.009180] | 10/2000 = 0.005000 [0.002718, 0.009180] | 2.14 |
| 5/10 | 0.7 | 0.45 | 0 | wrong REAL DROP | 16114109 | 2000 | 539/2000 = 0.269500 [0.250510, 0.289374] | 436/2000 = 0.218000 [0.200455, 0.236627] | 236/2000 = 0.118000 [0.104588, 0.132876] | 2.05 |
| 5/10 | 0.7 | 0.45 | 1/4 | wrong NO DROP | 16114110 | 2000 | 38/2000 = 0.019000 [0.013874, 0.025970] | 22/2000 = 0.011000 [0.007275, 0.016599] | 22/2000 = 0.011000 [0.007275, 0.016599] | 2.02 |
| 7/21 | 0.0 | 0.45 | 0 | wrong REAL DROP | 16114111 | 2000 | 47/2000 = 0.023500 [0.017718, 0.031109] | 44/2000 = 0.022000 [0.016429, 0.029404] | 42/2000 = 0.021000 [0.015574, 0.028263] | 4.41 |
| 7/21 | 0.0 | 0.45 | 1/4 | wrong NO DROP | 16114112 | 2000 | 3/2000 = 0.001500 [0.000510, 0.004401] | 0/2000 = 0.000000 [0.000000, 0.001917] | 0/2000 = 0.000000 [0.000000, 0.001917] | 4.36 |
| 7/21 | 0.3 | 0.45 | 0 | wrong REAL DROP | 16114113 | 2000 | 167/2000 = 0.083500 [0.072160, 0.096437] | 136/2000 = 0.068000 [0.057775, 0.079882] | 66/2000 = 0.033000 [0.026023, 0.041768] | 4.21 |
| 7/21 | 0.3 | 0.45 | 1/4 | wrong NO DROP | 16114114 | 2000 | 14/2000 = 0.007000 [0.004174, 0.011716] | 9/2000 = 0.004500 [0.002369, 0.008531] | 9/2000 = 0.004500 [0.002369, 0.008531] | 4.15 |
| 7/21 | 0.5 | 0.45 | 0 | wrong REAL DROP | 16114115 | 2000 | 327/2000 = 0.163500 [0.147940, 0.180350] | 211/2000 = 0.105500 [0.092785, 0.119728] | 71/2000 = 0.035500 [0.028240, 0.044541] | 3.97 |
| 7/21 | 0.5 | 0.45 | 1/4 | wrong NO DROP | 16114116 | 2000 | 46/2000 = 0.023000 [0.017288, 0.030541] | 10/2000 = 0.005000 [0.002718, 0.009180] | 10/2000 = 0.005000 [0.002718, 0.009180] | 3.92 |
| 7/21 | 0.7 | 0.45 | 0 | wrong REAL DROP | 16114117 | 2000 | 697/2000 = 0.348500 [0.327925, 0.369655] | 312/2000 = 0.156000 [0.140758, 0.172560] | 28/2000 = 0.014000 [0.009704, 0.020160] | 3.67 |
| 7/21 | 0.7 | 0.45 | 1/4 | wrong NO DROP | 16114118 | 2000 | 65/2000 = 0.032500 [0.025581, 0.041212] | 1/2000 = 0.000500 [0.000088, 0.002827] | 1/2000 = 0.000500 [0.000088, 0.002827] | 3.68 |
| 14/42 | 0.0 | 0.45 | 0 | wrong REAL DROP | 16114119 | 2000 | 40/2000 = 0.020000 [0.014722, 0.027119] | 39/2000 = 0.019500 [0.014297, 0.026545] | 31/2000 = 0.015500 [0.010941, 0.021917] | 14.79 |
| 14/42 | 0.0 | 0.45 | 1/4 | wrong NO DROP | 16114120 | 2000 | 7/2000 = 0.003500 [0.001696, 0.007207] | 4/2000 = 0.002000 [0.000778, 0.005131] | 4/2000 = 0.002000 [0.000778, 0.005131] | 14.63 |
| 14/42 | 0.3 | 0.45 | 0 | wrong REAL DROP | 16114121 | 2000 | 207/2000 = 0.103500 [0.090901, 0.117619] | 122/2000 = 0.061000 [0.051329, 0.072354] | 34/2000 = 0.017000 [0.012191, 0.023661] | 13.61 |
| 14/42 | 0.3 | 0.45 | 1/4 | wrong NO DROP | 16114122 | 2000 | 33/2000 = 0.016500 [0.011773, 0.023081] | 8/2000 = 0.004000 [0.002028, 0.007873] | 8/2000 = 0.004000 [0.002028, 0.007873] | 13.03 |
| 14/42 | 0.5 | 0.45 | 0 | wrong REAL DROP | 16114123 | 2000 | 411/2000 = 0.205500 [0.188364, 0.223765] | 113/2000 = 0.056500 [0.047205, 0.067495] | 5/2000 = 0.002500 [0.001068, 0.005839] | 12.10 |
| 14/42 | 0.5 | 0.45 | 1/4 | wrong NO DROP | 16114124 | 2000 | 62/2000 = 0.031000 [0.024257, 0.039541] | 1/2000 = 0.000500 [0.000088, 0.002827] | 1/2000 = 0.000500 [0.000088, 0.002827] | 12.18 |
| 14/42 | 0.7 | 0.45 | 0 | wrong REAL DROP | 16114125 | 2000 | 742/2000 = 0.371000 [0.350095, 0.392400] | 74/2000 = 0.037000 [0.029575, 0.046200] | 0/2000 = 0.000000 [0.000000, 0.001917] | 11.72 |
| 14/42 | 0.7 | 0.45 | 1/4 | wrong NO DROP | 16114126 | 2000 | 102/2000 = 0.051000 [0.042190, 0.061532] | 0/2000 = 0.000000 [0.000000, 0.001917] | 0/2000 = 0.000000 [0.000000, 0.001917] | 11.30 |
| 28/84 | 0.0 | 0.45 | 0 | wrong REAL DROP | 16114127 | 1000 | 27/1000 = 0.027000 [0.018621, 0.038999] | 26/1000 = 0.026000 [0.017804, 0.037824] | 22/1000 = 0.022000 [0.014573, 0.033086] | 75.41 |
| 28/84 | 0.0 | 0.45 | 1/4 | wrong NO DROP | 16114128 | 1000 | 9/1000 = 0.009000 [0.004742, 0.017016] | 7/1000 = 0.007000 [0.003395, 0.014378] | 7/1000 = 0.007000 [0.003395, 0.014378] | 74.46 |
| 28/84 | 0.3 | 0.45 | 0 | wrong REAL DROP | 16114129 | 1000 | 104/1000 = 0.104000 [0.086571, 0.124460] | 36/1000 = 0.036000 [0.026116, 0.049436] | 3/1000 = 0.003000 [0.001021, 0.008783] | 71.64 |
| 28/84 | 0.3 | 0.45 | 1/4 | wrong NO DROP | 16114130 | 1000 | 26/1000 = 0.026000 [0.017804, 0.037824] | 1/1000 = 0.001000 [0.000177, 0.005643] | 1/1000 = 0.001000 [0.000177, 0.005643] | 71.65 |
| 28/84 | 0.5 | 0.45 | 0 | wrong REAL DROP | 16114131 | 1000 | 218/1000 = 0.218000 [0.193515, 0.244643] | 21/1000 = 0.021000 [0.013776, 0.031890] | 0/1000 = 0.000000 [0.000000, 0.003827] | 69.81 |
| 28/84 | 0.5 | 0.45 | 1/4 | wrong NO DROP | 16114132 | 1000 | 38/1000 = 0.038000 [0.027809, 0.051727] | 0/1000 = 0.000000 [0.000000, 0.003827] | 0/1000 = 0.000000 [0.000000, 0.003827] | 70.00 |
| 28/84 | 0.7 | 0.45 | 0 | wrong REAL DROP | 16114133 | 1000 | 381/1000 = 0.381000 [0.351410, 0.411500] | 0/1000 = 0.000000 [0.000000, 0.003827] | 0/1000 = 0.000000 [0.000000, 0.003827] | 68.41 |
| 28/84 | 0.7 | 0.45 | 1/4 | wrong NO DROP | 16114134 | 1000 | 71/1000 = 0.071000 [0.056670, 0.088614] | 0/1000 = 0.000000 [0.000000, 0.003827] | 0/1000 = 0.000000 [0.000000, 0.003827] | 69.36 |
| 14/42 | 0.0 | 0.4 | 9/20 | REAL DROP | 16114135 | 2000 | 1975/2000 = 0.987500 [0.981612, 0.991519] | 1836/2000 = 0.918000 [0.905159, 0.929238] | 1524/2000 = 0.762000 [0.742845, 0.780150] | 13.46 |


### Power of the rule as built

Power is limited at the sizes most people have. The following table uses the final rule,
including the whole-comparison streak check. Reasoning counts are log-normal, quantized to
multiples of 100 before exact changes. Independent shares are rounded
`0.10 + 0.25 Phi(Z)` and `0.05 + 0.25 Phi(Z)`, with denominator 100.
The day tables are built directly from the generator and decided by the production
decision rule; a unit test checks them against the path through response and edit records
and the day reduction. Pilot timing alone reduced some run counts; the denominators
are the runs actually made. A drop of 0 is the no-change design, not power against a drop.
The simulation thresholds check the implementation; the bounds above are proved, not
simulated. Seeds, designs, requested counts and intervals are copied from the self-check.

figures from the 2.3.0 self-check; replaced at the 2.4.0 self-check

| after/before | log SD | drop | seed | requested | actual | REAL DROP (95% CI) | NO DROP (95% CI) | seconds |
|---|---|---|---:|---:|---:|---|---|---:|
| 5/10 | 0.35 | 0 | 16113042 | 2000 | 2000 | 47/2000 = 0.023500 [0.017718, 0.031109] | 13/2000 = 0.006500 [0.003803, 0.011090] | 2.20 |
| 5/10 | 0.35 | 33/100 | 16113043 | 2000 | 2000 | 453/2000 = 0.226500 [0.208690, 0.245358] | 0/2000 = 0.000000 [0.000000, 0.001917] | 2.19 |
| 5/10 | 0.35 | 9/20 | 16113044 | 2000 | 2000 | 1043/2000 = 0.521500 [0.499587, 0.543331] | 0/2000 = 0.000000 [0.000000, 0.001917] | 2.11 |
| 5/10 | 0.35 | 1/2 | 16113045 | 2000 | 2000 | 1292/2000 = 0.646000 [0.624780, 0.666660] | 0/2000 = 0.000000 [0.000000, 0.001917] | 2.09 |
| 5/10 | 0.35 | 11/20 | 16113046 | 2000 | 2000 | 1499/2000 = 0.749500 [0.730044, 0.767999] | 0/2000 = 0.000000 [0.000000, 0.001917] | 2.07 |
| 5/10 | 0.45 | 0 | 16113047 | 2000 | 2000 | 37/2000 = 0.018500 [0.013451, 0.025395] | 10/2000 = 0.005000 [0.002718, 0.009180] | 2.19 |
| 5/10 | 0.45 | 33/100 | 16113048 | 2000 | 2000 | 301/2000 = 0.150500 [0.135500, 0.166840] | 2/2000 = 0.001000 [0.000274, 0.003639] | 2.17 |
| 5/10 | 0.45 | 9/20 | 16113049 | 2000 | 2000 | 609/2000 = 0.304500 [0.284722, 0.325028] | 0/2000 = 0.000000 [0.000000, 0.001917] | 2.15 |
| 5/10 | 0.45 | 1/2 | 16113050 | 2000 | 2000 | 824/2000 = 0.412000 [0.390618, 0.433720] | 0/2000 = 0.000000 [0.000000, 0.001917] | 2.14 |
| 5/10 | 0.45 | 11/20 | 16113051 | 2000 | 2000 | 1093/2000 = 0.546500 [0.524614, 0.568208] | 0/2000 = 0.000000 [0.000000, 0.001917] | 2.11 |
| 5/10 | 0.55 | 0 | 16113052 | 2000 | 2000 | 36/2000 = 0.018000 [0.013030, 0.024818] | 12/2000 = 0.006000 [0.003436, 0.010458] | 2.21 |
| 5/10 | 0.55 | 33/100 | 16113053 | 2000 | 2000 | 168/2000 = 0.084000 [0.072626, 0.096969] | 1/2000 = 0.000500 [0.000088, 0.002827] | 2.18 |
| 5/10 | 0.55 | 9/20 | 16113054 | 2000 | 2000 | 394/2000 = 0.197000 [0.180157, 0.215005] | 0/2000 = 0.000000 [0.000000, 0.001917] | 2.17 |
| 5/10 | 0.55 | 1/2 | 16113055 | 2000 | 2000 | 546/2000 = 0.273000 [0.253924, 0.292946] | 0/2000 = 0.000000 [0.000000, 0.001917] | 2.16 |
| 5/10 | 0.55 | 11/20 | 16113056 | 2000 | 2000 | 733/2000 = 0.366500 [0.345657, 0.387855] | 0/2000 = 0.000000 [0.000000, 0.001917] | 2.41 |
| 7/21 | 0.35 | 0 | 16113057 | 2000 | 1865 | 37/1865 = 0.019839 [0.014427, 0.027225] | 54/1865 = 0.028954 [0.022259, 0.037586] | 4.11 |
| 7/21 | 0.35 | 33/100 | 16113058 | 2000 | 1867 | 819/1867 = 0.438672 [0.416311, 0.461284] | 0/1867 = 0.000000 [0.000000, 0.002053] | 3.98 |
| 7/21 | 0.35 | 9/20 | 16113059 | 2000 | 1957 | 1440/1957 = 0.735820 [0.715838, 0.754878] | 0/1957 = 0.000000 [0.000000, 0.001959] | 4.44 |
| 7/21 | 0.35 | 1/2 | 16113060 | 2000 | 1846 | 1463/1846 = 0.792524 [0.773428, 0.810406] | 0/1846 = 0.000000 [0.000000, 0.002077] | 3.78 |
| 7/21 | 0.35 | 11/20 | 16113061 | 2000 | 1913 | 1561/1913 = 0.815996 [0.798004, 0.832721] | 0/1913 = 0.000000 [0.000000, 0.002004] | 3.93 |
| 7/21 | 0.45 | 0 | 16113062 | 2000 | 1634 | 32/1634 = 0.019584 [0.013906, 0.027515] | 30/1634 = 0.018360 [0.012890, 0.026089] | 3.61 |
| 7/21 | 0.45 | 33/100 | 16113063 | 2000 | 1788 | 461/1788 = 0.257830 [0.238088, 0.278610] | 2/1788 = 0.001119 [0.000307, 0.004069] | 3.84 |
| 7/21 | 0.45 | 9/20 | 16113064 | 2000 | 1805 | 961/1805 = 0.532410 [0.509348, 0.555335] | 1/1805 = 0.000554 [0.000098, 0.003132] | 3.74 |
| 7/21 | 0.45 | 1/2 | 16113065 | 2000 | 1944 | 1234/1944 = 0.634774 [0.613124, 0.655892] | 0/1944 = 0.000000 [0.000000, 0.001972] | 4.38 |
| 7/21 | 0.45 | 11/20 | 16113066 | 2000 | 2000 | 1517/2000 = 0.758500 [0.739259, 0.776750] | 0/2000 = 0.000000 [0.000000, 0.001917] | 4.11 |
| 7/21 | 0.55 | 0 | 16113067 | 2000 | 1794 | 30/1794 = 0.016722 [0.011738, 0.023772] | 27/1794 = 0.015050 [0.010364, 0.021809] | 3.92 |
| 7/21 | 0.55 | 33/100 | 16113068 | 2000 | 1868 | 302/1868 = 0.161670 [0.145672, 0.179057] | 2/1868 = 0.001071 [0.000294, 0.003896] | 4.03 |
| 7/21 | 0.55 | 9/20 | 16113069 | 2000 | 1888 | 742/1888 = 0.393008 [0.371216, 0.415236] | 0/1888 = 0.000000 [0.000000, 0.002031] | 3.96 |
| 7/21 | 0.55 | 1/2 | 16113070 | 2000 | 1927 | 989/1927 = 0.513233 [0.490912, 0.535501] | 0/1927 = 0.000000 [0.000000, 0.001990] | 4.06 |
| 7/21 | 0.55 | 11/20 | 16113071 | 2000 | 1930 | 1197/1930 = 0.620207 [0.598336, 0.641601] | 0/1930 = 0.000000 [0.000000, 0.001986] | 3.99 |
| 14/42 | 0.35 | 0 | 16113072 | 2000 | 634 | 12/634 = 0.018927 [0.010860, 0.032790] | 52/634 = 0.082019 [0.063094, 0.105979] | 4.74 |
| 14/42 | 0.35 | 33/100 | 16113073 | 2000 | 677 | 466/677 = 0.688331 [0.652461, 0.722076] | 0/677 = 0.000000 [0.000000, 0.005642] | 4.47 |
| 14/42 | 0.35 | 9/20 | 16113074 | 2000 | 582 | 464/582 = 0.797251 [0.762687, 0.827916] | 0/582 = 0.000000 [0.000000, 0.006557] | 4.23 |
| 14/42 | 0.35 | 1/2 | 16113075 | 2000 | 618 | 479/618 = 0.775081 [0.740521, 0.806242] | 0/618 = 0.000000 [0.000000, 0.006178] | 4.02 |
| 14/42 | 0.35 | 11/20 | 16113076 | 2000 | 624 | 472/624 = 0.756410 [0.721229, 0.788454] | 0/624 = 0.000000 [0.000000, 0.006119] | 4.02 |
| 14/42 | 0.45 | 0 | 16113077 | 2000 | 538 | 11/538 = 0.020446 [0.011454, 0.036238] | 48/538 = 0.089219 [0.067954, 0.116310] | 3.79 |
| 14/42 | 0.45 | 33/100 | 16113078 | 2000 | 584 | 298/584 = 0.510274 [0.469796, 0.550618] | 0/584 = 0.000000 [0.000000, 0.006535] | 3.94 |
| 14/42 | 0.45 | 9/20 | 16113079 | 2000 | 583 | 430/583 = 0.737564 [0.700379, 0.771639] | 0/583 = 0.000000 [0.000000, 0.006546] | 3.85 |
| 14/42 | 0.45 | 1/2 | 16113080 | 2000 | 628 | 469/628 = 0.746815 [0.711376, 0.779253] | 0/628 = 0.000000 [0.000000, 0.006080] | 4.09 |
| 14/42 | 0.45 | 11/20 | 16113081 | 2000 | 579 | 447/579 = 0.772021 [0.736121, 0.804334] | 0/579 = 0.000000 [0.000000, 0.006591] | 3.78 |
| 14/42 | 0.55 | 0 | 16113082 | 2000 | 528 | 13/528 = 0.024621 [0.014444, 0.041665] | 19/528 = 0.035985 [0.023156, 0.055517] | 3.74 |
| 14/42 | 0.55 | 33/100 | 16113083 | 2000 | 601 | 199/601 = 0.331115 [0.294667, 0.369708] | 0/601 = 0.000000 [0.000000, 0.006351] | 4.13 |
| 14/42 | 0.55 | 9/20 | 16113084 | 2000 | 622 | 401/622 = 0.644695 [0.606299, 0.681314] | 0/622 = 0.000000 [0.000000, 0.006138] | 4.12 |
| 14/42 | 0.55 | 1/2 | 16113085 | 2000 | 566 | 405/566 = 0.715548 [0.677024, 0.751165] | 0/566 = 0.000000 [0.000000, 0.006741] | 3.73 |
| 14/42 | 0.55 | 11/20 | 16113086 | 2000 | 627 | 482/627 = 0.768740 [0.734160, 0.800047] | 0/627 = 0.000000 [0.000000, 0.006089] | 4.10 |
| 28/84 | 0.35 | 0 | 16113087 | 2000 | 61 | 2/61 = 0.032787 [0.009038, 0.111895] | 16/61 = 0.262295 [0.168388, 0.384367] | 4.43 |
| 28/84 | 0.35 | 33/100 | 16113088 | 2000 | 39 | 30/39 = 0.769231 [0.616637, 0.873542] | 0/39 = 0.000000 [0.000000, 0.089667] | 2.96 |
| 28/84 | 0.35 | 9/20 | 16113089 | 2000 | 61 | 45/61 = 0.737705 [0.615633, 0.831612] | 0/61 = 0.000000 [0.000000, 0.059244] | 4.23 |
| 28/84 | 0.35 | 1/2 | 16113090 | 2000 | 60 | 39/60 = 0.650000 [0.523626, 0.758322] | 0/60 = 0.000000 [0.000000, 0.060172] | 4.35 |
| 28/84 | 0.35 | 11/20 | 16113091 | 2000 | 55 | 37/55 = 0.672727 [0.541032, 0.781869] | 0/55 = 0.000000 [0.000000, 0.065285] | 3.83 |
| 28/84 | 0.45 | 0 | 16113092 | 2000 | 53 | 1/53 = 0.018868 [0.003338, 0.099429] | 11/53 = 0.207547 [0.120046, 0.334577] | 3.86 |
| 28/84 | 0.45 | 33/100 | 16113093 | 2000 | 53 | 43/53 = 0.811321 [0.686415, 0.894147] | 0/53 = 0.000000 [0.000000, 0.067582] | 3.90 |
| 28/84 | 0.45 | 9/20 | 16113094 | 2000 | 62 | 50/62 = 0.806452 [0.691482, 0.885662] | 0/62 = 0.000000 [0.000000, 0.058344] | 4.46 |
| 28/84 | 0.45 | 1/2 | 16113095 | 2000 | 54 | 44/54 = 0.814815 [0.691641, 0.896173] | 0/54 = 0.000000 [0.000000, 0.066414] | 4.25 |
| 28/84 | 0.45 | 11/20 | 16113096 | 2000 | 60 | 41/60 = 0.683333 [0.557662, 0.786941] | 0/60 = 0.000000 [0.000000, 0.060172] | 4.18 |
| 28/84 | 0.55 | 0 | 16113097 | 2000 | 61 | 3/61 = 0.049180 [0.016866, 0.134911] | 5/61 = 0.081967 [0.035520, 0.177947] | 4.25 |
| 28/84 | 0.55 | 33/100 | 16113098 | 2000 | 52 | 32/52 = 0.615385 [0.479599, 0.735295] | 0/52 = 0.000000 [0.000000, 0.068792] | 3.83 |
| 28/84 | 0.55 | 9/20 | 16113099 | 2000 | 53 | 39/53 = 0.735849 [0.604193, 0.835626] | 0/53 = 0.000000 [0.000000, 0.067582] | 3.86 |
| 28/84 | 0.55 | 1/2 | 16113100 | 2000 | 54 | 42/54 = 0.777778 [0.650613, 0.868046] | 0/54 = 0.000000 [0.000000, 0.066414] | 3.93 |
| 28/84 | 0.55 | 11/20 | 16113101 | 2000 | 71 | 57/71 = 0.802817 [0.695803, 0.878745] | 0/71 = 0.000000 [0.000000, 0.051328] | 5.10 |
| 14/42 | 0.4 | 9/20 | 16113102 | 2000 | 581 | 465/581 = 0.800344 [0.765914, 0.830829] | 0/581 = 0.000000 [0.000000, 0.006568] | 4.04 |


- A change that began before the before period, a change in how a vendor counts tokens, and a
  change in what the user works on all look the same to the test.
- One person's logs say nothing about another person's.

## Checks that agents run (`bench/selfcheck_logs.py`)

1. `G(n, m, u)` and `p_real` equal brute-force enumeration for every `n + m ≤ 14` (for
   `p_real` on tie patterns: none; three levels; all equal).
2. For those cases, the share of labelings on which each test rejects at `α` is at most `α`.
3. Null simulation with the final rule, including the streak check: exactly 20,000 seeded day tables per design (5/10, 7/21, 14/42, 28/84),
   measures independent and measures with identical ranks; the rate of REAL DROP is at most
   0.0283. With one measure exactly at its margin and the others unchanged, the rate of NO
   DROP is at most 0.0283. A gated cell is never run on fewer tables than stated; the script
   fails if it would be. The day tables are built directly from the generator. A unit test checks,
   for several seeds per design and both dependence cases, that the same generator
   passed through response and edit records and the day reduction, with a second
   unusable setting present, gives the same day table and the same result. Setting
   selection and the usable-day boundaries are checked exactly by a separate gate.
4. The rejection-rate table for the final rule, including the 45% reasoning-token drop at
   14/42 with a log standard deviation of 0.40, each cell with its generator, seed, number of
   simulations and sampling error. There is no power threshold: the streak check lowers
   power (in the 2.3.0 self-check, at 14/42 with independent days, from 0.918000 with a
   per-measure check to 0.762000 with the rule as built, 2,000 runs each).
5. The exact runs distribution equals brute-force enumeration for every `a + b ≤ 14`.
6. Reported, not gated: the wrong-REAL and wrong-NO-DROP rates when day values follow an AR(1)
   process with coefficient 0.3, 0.5 and 0.7, which breaks A1, with no check, with a
   per-measure check, and with the rule as built; and the reviewer's two counterexamples
   (selection by after-period counts with day values tied to response counts, which breaks A1
   as restated; a change that swaps which days are usable, which breaks A4), each shown to
   break the bound when its assumption is dropped.

The 2.4.0 self-check adds:

7. The null gate with setting changes under the setting rule of `arci-logs/2`: exactly 20,000
   histories per design, each holding two or three settings and a change of setting inside the
   window, built through response records so that the setting choice runs; the compared
   setting's responses per day after the split are drawn larger than before (for example 3
   times), and day values are computed from those responses; the rates of wrong REAL DROP and
   wrong NO DROP are each at most 0.0283. A report-only cell has the same imbalance and one
   setting.
8. Each streak-check rate is also given conditional on passing the check: among the histories
   the check does not stop, the share with a wrong result, with its count and interval.
9. Power cells run until the stated number of tested histories is reached; the table says what
   each count is (histories generated, histories tested, histories stopped by the check).
10. The design 14 after against 16 before (Claude Code's default retention) in the null,
    correlation and power tables.
11. Report only: days from a weekly cycle and days from a regime-switching generator, with no
    check, a per-measure check and the rule as built.
12. The two figures printed in every output (section "How far the bound can fail"), read from
    the correlation table; a test holds the printed figures equal to this file.
13. The kept-table rules: when deletion removes whole days and a `--keep` run happened after
    each deleted day ended, a run with the kept table gives the same day table as the run before
    the deletion. One further case has a session file that spans the deletion boundary.
14. The first counterexample of item 6 prints as `Demonstration outside A1 (arci-logs/2): ...`.

The streak check itself is unchanged in this version. Open: one pre-stated check instead of the
three variants reported; an unknown split date; repeated daily looks.
