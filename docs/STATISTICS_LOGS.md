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

For each setting and day in the window, the two rows are compared by the pair (number of
responses, number of file-edit results), in that order; the row from the logs is used when its
pair is at least as large, and otherwise the stored row is used. So the row from the logs wins a
tie, a day holding file-edit results and no response is decided by its file-edit count, and a
Codex row counts as 0 file-edit results. A row is used whole. Which row a day uses depends on
those two counts only. The candidates, the after-period counts of the setting choice, `v*`,
the usable days and the tests then run on the days as used, with no other change.

The kept table changes no claim. The claims are statements about the days the comparison uses.
The rule that picks a day's row reads which rows exist and their response and file-edit counts,
all part of the log structure defined under "What is claimed, and under which assumptions", and
never a day value or whether an edit failed, so
the proof below covers the days as used without change. What the table changes is which days
exist to be compared: it can supply before-days whose session files are gone. It also adds ways
for A1 to fail, listed below.

What it promises is limited to the case the spike behind this version tested, with all of its
conditions: records are immutable and no response arrives late with an earlier timestamp; only
batches strictly older than 30 times 24 hours are deleted; the retained history and the
undeleted history are compared at the same instant, with the same options, the same UTC offset
and the same window; each deleted day was captured whole by a `--keep` run before it was deleted,
and successful captures are at most 29 days apart; and the rows are rows the table admits, inside
the active window. Then, for each measure, the day lists of the two runs agree once `source` is
removed from them, and the results agree. Outside this case nothing is promised. A day never
captured whole cannot be recovered. Days that hold only file-edit results are outside the
promise.

Its limits: kept rows are not checked against logs again; they hold the counts as the readers
of the version that wrote them saw them; an edited table gives an edited result, and the seal
does not detect a table edited before the run. The output marks kept days (a count line, which
counts every day whose row came from the table, usable or not, and `source: "kept"` on each
usable such day in the JSON record, which the day-table digest covers). Rows
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
`p_streak ≤ 1/10`. A streaky measure is not tested, and one flagged measure stops the whole
comparison for the tool. The check flags an unusually small number of runs; the method
therefore withholds a result. A flag does not establish dependence: exchangeable days can be
ordered that way by chance, and passing the check does not establish A1 either.

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

The **log structure** of a run is: which responses of the tool exist in the window and which
file-edit results exist, the day of each, its setting (or none), and for a response its thread;
and, for the stored rows of the kept table, which rows exist and the same facts as each row
records them (its day, setting, number of responses and number of file-edit results). Reasoning
counts, whether a file-edit result failed, and day values are not part of it.

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
was fixed without reference to the reasoning counts, the failures of the file-edit results, or
the day values of the records compared, or by a rule that depends on the log structure only, so
that, given the log structure, the options carry no information about those values. Choosing a
date, model or effort because a measure looked low is excluded.

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
A2. When neighbouring days resemble each other, or when work comes in phases, A1 fails and the
bounds are no longer guaranteed. The self-check measures how far they can fail in the cases it
tests. The text output, the HTML page and each non-ERROR Markdown block print the worst of
its figures (the text and HTML in the closing limits paragraph, the Markdown in the footer):
the largest wrong REAL DROP rate of the rule as built over all generated histories,
over every no-change row with rho greater than 0 of the correlation table and every
no-change row of the weekly-cycle and regime table, with the design of that row
(`{rate_max}`, `{worst_after}`, `{worst_before}`; the rule is in record 0017, "Coverage of the
bound"). A test holds the printed values equal to the self-check file. The 2.4.0 self-check
gives 362/2000 = 0.181000 [0.164743, 0.198480] at 14 days after against 16 before, for days in
regimes (two states, switch probability 0.08, log amplitude 0.6; seed 18112185). Among the
histories of that cell that pass the streak check the rate is higher:
362/910 = 0.397802 [0.366496, 0.429968]. The largest rate in the correlation table is
215/2000 = 0.107500 [0.094670, 0.121835] at 5/10 (rho 0.7, seed 18112140).
These are rates for the generators tested. Another pattern can give more.

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
which rows exist and on the pair (responses, file-edit results) of each, all part of the
structure, with the logs row winning a tie. The candidates are the settings with a
main-thread response in the window, kept by `--model` and `--effort` (fixed by A2). Each
candidate's score is its number of main-thread responses dated `s` to `N` (or, when no candidate
has one, in the before period): a count over the structure. Ties go to the order of raw names,
also part of the structure. No step reads a reasoning count, whether a file-edit result failed,
or a day value. A permutation of the compared setting's
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
  back only from the kept table, and only if `--keep` ran while the files existed, with no gap
  longer than 29 days between those runs. A day never captured whole cannot be recovered. This
  tool does not change the Claude Code setting.
- **A setting adopted recently** has few earlier days, and its first days may differ from later
  ones, for example while the user learns it; A1 can then fail. In the spike for this version,
  with a generator whose first five days of a newly adopted setting ran 1.15 times its later
  days and no shift at the split, wrong REAL DROP was 535 of 20,000 histories at 14 days after
  against 16 before, and 415 of 20,000 at 7 after against 21 before. Those counts are from the
  S0 spike report, G2, seeds 17112040 and 17112041. The new 2.4.0 run gives
  539/20000 = 0.026950 [0.024795, 0.029287] at 14/16 (seed 18112056),
  and 424/20000 = 0.021200 [0.019294, 0.023290] at 7/21 (seed 18112057).
  Both cells are report only and break A1. The tool does not compare across
  a change of model or effort: the days of other settings never fill the compared setting's
  before period. When a setting was adopted after the split, its before period is empty and the
  result is CANNOT TELL (`too_few_days`).
- **Days that come in streaks break A1, and the streak check is only a partial guard.**
  The [self-check](results/logs-selfcheck.md) of 2.4.0, dated 2026-11-16, reports the tables
  below. Rates are proportions, copied without rounding; brackets are Wilson 95%
  intervals. Counts show the actual runs, not just the requested runs. These are simulation
  results for the stated generators, not evidence that a user's days satisfy A1; and a flag in a
  run is not evidence that they do not.

### Correlation and the cost of the check

The rule as built stops the whole comparison when any measure is streaky. In the new
AR(1) rows, its wrong REAL DROP point estimate exceeds 0.025 at 5/10 (rho 0.3, 0.5, 0.7); 7/21 (rho 0.3, 0.5); 14/16 (rho 0.3, 0.5, 0.7); 14/42 (rho 0.3).
Its wrong NO DROP point estimates in those AR(1) rows stay below 0.025. A1 fails in
the positive-correlation rows, so neither observation restores a bound. Conditional
columns use only histories that passed the stated check; the claimed bound does not
apply to those conditional rates. An empty conditional denominator prints as undefined.

At 14/42, log SD 0.40 and drop 9/20, REAL DROP falls from
1976/2000 = 0.988000 [0.982206, 0.991923] without a check, to
1814/2000 = 0.907000 [0.893480, 0.918960] with a per-measure check, to
1506/2000 = 0.753000 [0.733626, 0.771404] with the rule as built (seed 18112174).

AR(1) is stationary with independent Gaussian streams. Positive rho breaks A1. Weekly: random phase, seven-day sine, log amplitude 0.6. Regime: symmetric two-state chain, switch probability 0.08, log amplitude +/-0.6. Both break A1. Shares add round(10*(effect+1))/100 without clipping. Null reports wrong REAL DROP; exact token margin reports wrong NO DROP. The 9/20 row reports power. Per-measure passed means at least one measure passes; its conditional numerator uses the per-measure ladder. As-built passed means all three pass.

| after/before | rho | log SD | drop | metric | seed | histories | no check (95% CI) | per-measure check (95% CI) | as built (95% CI) | per-measure passed | as-built passed | per-measure conditional (95% CI) | as-built conditional (95% CI) | seconds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5/10 | 0.0 | 0.45 | 0 | wrong REAL DROP | 18112134 | 2000 | 27/2000 = 0.013500 [0.009294, 0.019571] | 25/2000 = 0.012500 [0.008481, 0.018388] | 24/2000 = 0.012000 [0.008077, 0.017794] | 2000 | 1766 | 25/2000 = 0.012500 [0.008481, 0.018388] | 24/1766 = 0.013590 [0.009149, 0.020142] | 2.474 |
| 5/10 | 0.0 | 0.45 | 1/4 | wrong NO DROP | 18112135 | 2000 | 1/2000 = 0.000500 [0.000088, 0.002827] | 1/2000 = 0.000500 [0.000088, 0.002827] | 1/2000 = 0.000500 [0.000088, 0.002827] | 2000 | 1786 | 1/2000 = 0.000500 [0.000088, 0.002827] | 1/1786 = 0.000560 [0.000099, 0.003165] | 2.452 |
| 5/10 | 0.3 | 0.45 | 0 | wrong REAL DROP | 18112136 | 2000 | 143/2000 = 0.071500 [0.061010, 0.083633] | 135/2000 = 0.067500 [0.057313, 0.079345] | 111/2000 = 0.055500 [0.046291, 0.066413] | 1996 | 1444 | 135/1996 = 0.067635 [0.057428, 0.079503] | 111/1444 = 0.076870 [0.064225, 0.091760] | 2.404 |
| 5/10 | 0.3 | 0.45 | 1/4 | wrong NO DROP | 18112137 | 2000 | 8/2000 = 0.004000 [0.002028, 0.007873] | 7/2000 = 0.003500 [0.001696, 0.007207] | 7/2000 = 0.003500 [0.001696, 0.007207] | 2000 | 1452 | 7/2000 = 0.003500 [0.001696, 0.007207] | 7/1452 = 0.004821 [0.002337, 0.009918] | 2.385 |
| 5/10 | 0.5 | 0.45 | 0 | wrong REAL DROP | 18112138 | 2000 | 313/2000 = 0.156500 [0.141237, 0.173080] | 279/2000 = 0.139500 [0.125006, 0.155377] | 185/2000 = 0.092500 [0.080572, 0.105991] | 1994 | 1159 | 279/1994 = 0.139920 [0.125385, 0.155840] | 185/1159 = 0.159620 [0.139664, 0.181826] | 2.361 |
| 5/10 | 0.5 | 0.45 | 1/4 | wrong NO DROP | 18112139 | 2000 | 16/2000 = 0.008000 [0.004930, 0.012956] | 6/2000 = 0.003000 [0.001376, 0.006530] | 6/2000 = 0.003000 [0.001376, 0.006530] | 1990 | 1115 | 6/1990 = 0.003015 [0.001383, 0.006563] | 6/1115 = 0.005381 [0.002469, 0.011690] | 2.357 |
| 5/10 | 0.7 | 0.45 | 0 | wrong REAL DROP | 18112140 | 2000 | 522/2000 = 0.261000 [0.242224, 0.280693] | 422/2000 = 0.211000 [0.193681, 0.229427] | 215/2000 = 0.107500 [0.094670, 0.121835] | 1968 | 779 | 422/1968 = 0.214431 [0.196863, 0.233111] | 215/779 = 0.275995 [0.245761, 0.308427] | 2.319 |
| 5/10 | 0.7 | 0.45 | 1/4 | wrong NO DROP | 18112141 | 2000 | 43/2000 = 0.021500 [0.016001, 0.028834] | 11/2000 = 0.005500 [0.003074, 0.009822] | 11/2000 = 0.005500 [0.003074, 0.009822] | 1962 | 781 | 11/1962 = 0.005607 [0.003133, 0.010012] | 11/781 = 0.014085 [0.007882, 0.025043] | 2.274 |
| 7/21 | 0.0 | 0.45 | 0 | wrong REAL DROP | 18112142 | 2000 | 50/2000 = 0.025000 [0.019014, 0.032807] | 47/2000 = 0.023500 [0.017718, 0.031109] | 40/2000 = 0.020000 [0.014722, 0.027119] | 1999 | 1637 | 47/1999 = 0.023512 [0.017727, 0.031124] | 40/1637 = 0.024435 [0.017995, 0.033101] | 4.894 |
| 7/21 | 0.0 | 0.45 | 1/4 | wrong NO DROP | 18112143 | 2000 | 6/2000 = 0.003000 [0.001376, 0.006530] | 5/2000 = 0.002500 [0.001068, 0.005839] | 5/2000 = 0.002500 [0.001068, 0.005839] | 1999 | 1625 | 5/1999 = 0.002501 [0.001069, 0.005842] | 5/1625 = 0.003077 [0.001315, 0.007183] | 4.841 |
| 7/21 | 0.3 | 0.45 | 0 | wrong REAL DROP | 18112144 | 2000 | 176/2000 = 0.088000 [0.076361, 0.101219] | 140/2000 = 0.070000 [0.059623, 0.082026] | 86/2000 = 0.043000 [0.034951, 0.052801] | 1968 | 913 | 140/1968 = 0.071138 [0.060597, 0.083350] | 86/913 = 0.094195 [0.076912, 0.114879] | 4.682 |
| 7/21 | 0.3 | 0.45 | 1/4 | wrong NO DROP | 18112145 | 2000 | 20/2000 = 0.010000 [0.006483, 0.015396] | 7/2000 = 0.003500 [0.001696, 0.007207] | 7/2000 = 0.003500 [0.001696, 0.007207] | 1977 | 927 | 7/1977 = 0.003541 [0.001716, 0.007291] | 7/927 = 0.007551 [0.003663, 0.015504] | 4.630 |
| 7/21 | 0.5 | 0.45 | 0 | wrong REAL DROP | 18112146 | 2000 | 359/2000 = 0.179500 [0.163300, 0.196929] | 242/2000 = 0.121000 [0.107429, 0.136024] | 72/2000 = 0.036000 [0.028685, 0.045094] | 1820 | 386 | 242/1820 = 0.132967 [0.118138, 0.149342] | 72/386 = 0.186528 [0.150827, 0.228408] | 4.392 |
| 7/21 | 0.5 | 0.45 | 1/4 | wrong NO DROP | 18112147 | 2000 | 35/2000 = 0.017500 [0.012610, 0.024240] | 13/2000 = 0.006500 [0.003803, 0.011090] | 13/2000 = 0.006500 [0.003803, 0.011090] | 1828 | 362 | 13/1828 = 0.007112 [0.004161, 0.012130] | 13/362 = 0.035912 [0.021105, 0.060464] | 4.364 |
| 7/21 | 0.7 | 0.45 | 0 | wrong REAL DROP | 18112148 | 2000 | 705/2000 = 0.352500 [0.331863, 0.373702] | 304/2000 = 0.152000 [0.136934, 0.168401] | 40/2000 = 0.020000 [0.014722, 0.027119] | 1400 | 93 | 304/1400 = 0.217143 [0.196335, 0.239498] | 40/93 = 0.430108 [0.334235, 0.531525] | 4.119 |
| 7/21 | 0.7 | 0.45 | 1/4 | wrong NO DROP | 18112149 | 2000 | 72/2000 = 0.036000 [0.028685, 0.045094] | 3/2000 = 0.001500 [0.000510, 0.004401] | 3/2000 = 0.001500 [0.000510, 0.004401] | 1464 | 81 | 3/1464 = 0.002049 [0.000697, 0.006008] | 3/81 = 0.037037 [0.012675, 0.103323] | 4.126 |
| 14/16 | 0.0 | 0.45 | 0 | wrong REAL DROP | 18112150 | 2000 | 47/2000 = 0.023500 [0.017718, 0.031109] | 45/2000 = 0.022500 [0.016858, 0.029973] | 44/2000 = 0.022000 [0.016429, 0.029404] | 2000 | 1778 | 45/2000 = 0.022500 [0.016858, 0.029973] | 44/1778 = 0.024747 [0.018486, 0.033057] | 5.897 |
| 14/16 | 0.0 | 0.45 | 1/4 | wrong NO DROP | 18112151 | 2000 | 4/2000 = 0.002000 [0.000778, 0.005131] | 3/2000 = 0.001500 [0.000510, 0.004401] | 3/2000 = 0.001500 [0.000510, 0.004401] | 1999 | 1779 | 3/1999 = 0.001501 [0.000511, 0.004403] | 3/1779 = 0.001686 [0.000574, 0.004946] | 5.744 |
| 14/16 | 0.3 | 0.45 | 0 | wrong REAL DROP | 18112152 | 2000 | 195/2000 = 0.097500 [0.085261, 0.111283] | 169/2000 = 0.084500 [0.073093, 0.097500] | 128/2000 = 0.064000 [0.054087, 0.075585] | 1997 | 1289 | 169/1997 = 0.084627 [0.073203, 0.097646] | 128/1289 = 0.099302 [0.084147, 0.116838] | 5.727 |
| 14/16 | 0.3 | 0.45 | 1/4 | wrong NO DROP | 18112153 | 2000 | 28/2000 = 0.014000 [0.009704, 0.020160] | 19/2000 = 0.009500 [0.006090, 0.014790] | 19/2000 = 0.009500 [0.006090, 0.014790] | 1997 | 1293 | 19/1997 = 0.009514 [0.006099, 0.014813] | 19/1293 = 0.014695 [0.009427, 0.022837] | 5.594 |
| 14/16 | 0.5 | 0.45 | 0 | wrong REAL DROP | 18112154 | 2000 | 392/2000 = 0.196000 [0.179192, 0.213973] | 320/2000 = 0.160000 [0.144587, 0.176717] | 156/2000 = 0.078000 [0.067040, 0.090578] | 1960 | 776 | 320/1960 = 0.163265 [0.147564, 0.180284] | 156/776 = 0.201031 [0.174337, 0.230670] | 5.471 |
| 14/16 | 0.5 | 0.45 | 1/4 | wrong NO DROP | 18112155 | 2000 | 56/2000 = 0.028000 [0.021625, 0.036184] | 19/2000 = 0.009500 [0.006090, 0.014790] | 19/2000 = 0.009500 [0.006090, 0.014790] | 1962 | 748 | 19/1962 = 0.009684 [0.006208, 0.015076] | 19/748 = 0.025401 [0.016321, 0.039331] | 5.318 |
| 14/16 | 0.7 | 0.45 | 0 | wrong REAL DROP | 18112156 | 2000 | 713/2000 = 0.356500 [0.335802, 0.377748] | 454/2000 = 0.227000 [0.209175, 0.245872] | 131/2000 = 0.065500 [0.055469, 0.077197] | 1802 | 325 | 454/1802 = 0.251942 [0.232440, 0.272500] | 131/325 = 0.403077 [0.351181, 0.457237] | 5.134 |
| 14/16 | 0.7 | 0.45 | 1/4 | wrong NO DROP | 18112157 | 2000 | 92/2000 = 0.046000 [0.037657, 0.056084] | 11/2000 = 0.005500 [0.003074, 0.009822] | 11/2000 = 0.005500 [0.003074, 0.009822] | 1809 | 352 | 11/1809 = 0.006081 [0.003399, 0.010856] | 11/352 = 0.031250 [0.017537, 0.055083] | 5.030 |
| 14/42 | 0.0 | 0.45 | 0 | wrong REAL DROP | 18112158 | 2000 | 49/2000 = 0.024500 [0.018582, 0.032241] | 49/2000 = 0.024500 [0.018582, 0.032241] | 43/2000 = 0.021500 [0.016001, 0.028834] | 2000 | 1572 | 49/2000 = 0.024500 [0.018582, 0.032241] | 43/1572 = 0.027354 [0.020371, 0.036641] | 16.366 |
| 14/42 | 0.0 | 0.45 | 1/4 | wrong NO DROP | 18112159 | 2000 | 5/2000 = 0.002500 [0.001068, 0.005839] | 4/2000 = 0.002000 [0.000778, 0.005131] | 4/2000 = 0.002000 [0.000778, 0.005131] | 1999 | 1570 | 4/1999 = 0.002001 [0.000778, 0.005134] | 4/1570 = 0.002548 [0.000991, 0.006533] | 16.042 |
| 14/42 | 0.3 | 0.45 | 0 | wrong REAL DROP | 18112160 | 2000 | 215/2000 = 0.107500 [0.094670, 0.121835] | 139/2000 = 0.069500 [0.059160, 0.081490] | 58/2000 = 0.029000 [0.022500, 0.037305] | 1863 | 397 | 139/1863 = 0.074611 [0.063535, 0.087438] | 58/397 = 0.146096 [0.114745, 0.184230] | 15.009 |
| 14/42 | 0.3 | 0.45 | 1/4 | wrong NO DROP | 18112161 | 2000 | 22/2000 = 0.011000 [0.007275, 0.016599] | 5/2000 = 0.002500 [0.001068, 0.005839] | 5/2000 = 0.002500 [0.001068, 0.005839] | 1881 | 390 | 5/1881 = 0.002658 [0.001136, 0.006208] | 5/390 = 0.012821 [0.005488, 0.029656] | 14.822 |
| 14/42 | 0.5 | 0.45 | 0 | wrong REAL DROP | 18112162 | 2000 | 426/2000 = 0.213000 [0.195615, 0.231485] | 132/2000 = 0.066000 [0.055929, 0.077735] | 10/2000 = 0.005000 [0.002718, 0.009180] | 1154 | 31 | 132/1154 = 0.114385 [0.097287, 0.134042] | 10/31 = 0.322581 [0.185694, 0.498590] | 13.178 |
| 14/42 | 0.5 | 0.45 | 1/4 | wrong NO DROP | 18112163 | 2000 | 61/2000 = 0.030500 [0.023817, 0.038983] | 0/2000 = 0.000000 [0.000000, 0.001917] | 0/2000 = 0.000000 [0.000000, 0.001917] | 1186 | 26 | 0/1186 = 0.000000 [0.000000, 0.003229] | 0/26 = 0.000000 [0.000000, 0.128729] | 12.976 |
| 14/42 | 0.7 | 0.45 | 0 | wrong REAL DROP | 18112164 | 2000 | 739/2000 = 0.369500 [0.348615, 0.390885] | 80/2000 = 0.040000 [0.032257, 0.049507] | 0/2000 = 0.000000 [0.000000, 0.001917] | 360 | 0 | 80/360 = 0.222222 [0.182336, 0.267974] | 0/0 = undefined [undefined, undefined] | 12.425 |
| 14/42 | 0.7 | 0.45 | 1/4 | wrong NO DROP | 18112165 | 2000 | 104/2000 = 0.052000 [0.043100, 0.062618] | 0/2000 = 0.000000 [0.000000, 0.001917] | 0/2000 = 0.000000 [0.000000, 0.001917] | 349 | 0 | 0/349 = 0.000000 [0.000000, 0.010887] | 0/0 = undefined [undefined, undefined] | 12.341 |
| 28/84 | 0.0 | 0.45 | 0 | wrong REAL DROP | 18112166 | 1000 | 28/1000 = 0.028000 [0.019442, 0.040170] | 26/1000 = 0.026000 [0.017804, 0.037824] | 24/1000 = 0.024000 [0.016180, 0.035463] | 1000 | 789 | 26/1000 = 0.026000 [0.017804, 0.037824] | 24/789 = 0.030418 [0.020525, 0.044862] | 78.969 |
| 28/84 | 0.0 | 0.45 | 1/4 | wrong NO DROP | 18112167 | 1000 | 9/1000 = 0.009000 [0.004742, 0.017016] | 9/1000 = 0.009000 [0.004742, 0.017016] | 9/1000 = 0.009000 [0.004742, 0.017016] | 999 | 793 | 9/999 = 0.009009 [0.004747, 0.017033] | 9/793 = 0.011349 [0.005982, 0.021428] | 78.618 |
| 28/84 | 0.3 | 0.45 | 0 | wrong REAL DROP | 18112168 | 1000 | 107/1000 = 0.107000 [0.089323, 0.127685] | 44/1000 = 0.044000 [0.032938, 0.058552] | 7/1000 = 0.007000 [0.003395, 0.014378] | 755 | 50 | 44/755 = 0.058278 [0.043697, 0.077332] | 7/50 = 0.140000 [0.069508, 0.261862] | 75.400 |
| 28/84 | 0.3 | 0.45 | 1/4 | wrong NO DROP | 18112169 | 1000 | 24/1000 = 0.024000 [0.016180, 0.035463] | 1/1000 = 0.001000 [0.000177, 0.005643] | 1/1000 = 0.001000 [0.000177, 0.005643] | 728 | 48 | 1/728 = 0.001374 [0.000243, 0.007739] | 1/48 = 0.020833 [0.003687, 0.108992] | 75.573 |
| 28/84 | 0.5 | 0.45 | 0 | wrong REAL DROP | 18112170 | 1000 | 243/1000 = 0.243000 [0.217433, 0.270533] | 22/1000 = 0.022000 [0.014573, 0.033086] | 0/1000 = 0.000000 [0.000000, 0.003827] | 185 | 0 | 22/185 = 0.118919 [0.079858, 0.173484] | 0/0 = undefined [undefined, undefined] | 73.024 |
| 28/84 | 0.5 | 0.45 | 1/4 | wrong NO DROP | 18112171 | 1000 | 37/1000 = 0.037000 [0.026961, 0.050582] | 0/1000 = 0.000000 [0.000000, 0.003827] | 0/1000 = 0.000000 [0.000000, 0.003827] | 186 | 0 | 0/186 = 0.000000 [0.000000, 0.020235] | 0/0 = undefined [undefined, undefined] | 73.655 |
| 28/84 | 0.7 | 0.45 | 0 | wrong REAL DROP | 18112172 | 1000 | 385/1000 = 0.385000 [0.355336, 0.415544] | 1/1000 = 0.001000 [0.000177, 0.005643] | 0/1000 = 0.000000 [0.000000, 0.003827] | 10 | 0 | 1/10 = 0.100000 [0.017876, 0.404150] | 0/0 = undefined [undefined, undefined] | 72.261 |
| 28/84 | 0.7 | 0.45 | 1/4 | wrong NO DROP | 18112173 | 1000 | 68/1000 = 0.068000 [0.053992, 0.085314] | 0/1000 = 0.000000 [0.000000, 0.003827] | 0/1000 = 0.000000 [0.000000, 0.003827] | 8 | 0 | 0/8 = 0.000000 [0.000000, 0.324408] | 0/0 = undefined [undefined, undefined] | 73.022 |
| 14/42 | 0.0 | 0.4 | 9/20 | REAL DROP | 18112174 | 2000 | 1976/2000 = 0.988000 [0.982206, 0.991923] | 1814/2000 = 0.907000 [0.893480, 0.918960] | 1506/2000 = 0.753000 [0.733626, 0.771404] | 1999 | 1524 | 1814/1999 = 0.907454 [0.893957, 0.919388] | 1506/1524 = 0.988189 [0.981407, 0.992516] | 15.210 |


### Power of the rule as built

Drop 0 is the no-change design. Tested means the tests ran, not that the result was decisive.

Each cell stops at 2000 tested histories: all measures have enough days and the whole-comparison streak check passes. Generated includes stopped histories. No timing pilot. Wilson intervals with a stopped denominator are descriptive.

| after/before | scenario | log SD | drop | seed | requested | generated | tested | stopped | REAL DROP (95% CI) | NO DROP (95% CI) | moved measure no drop (95% CI) | REAL DROP / tested (95% CI) | NO DROP / tested (95% CI) | choices old/current/rival | seconds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5/10 | independent | 0.35 | 0 | 18112058 | 2000 | 2239 | 2000 | 239 | 49/2239 = 0.021885 [0.016594, 0.028814] | 12/2239 = 0.005360 [0.003069, 0.009345] | n/a | 49/2000 = 0.024500 [0.018582, 0.032241] | 12/2000 = 0.006000 [0.003436, 0.010458] | n/a | 2.927 |
| 5/10 | independent | 0.35 | 33/100 | 18112059 | 2000 | 2239 | 2000 | 239 | 496/2239 = 0.221527 [0.204811, 0.239197] | 0/2239 = 0.000000 [0.000000, 0.001713] | n/a | 496/2000 = 0.248000 [0.229569, 0.267398] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 2.908 |
| 5/10 | independent | 0.35 | 9/20 | 18112060 | 2000 | 2237 | 2000 | 237 | 1147/2237 = 0.512740 [0.492023, 0.533414] | 0/2237 = 0.000000 [0.000000, 0.001714] | n/a | 1147/2000 = 0.573500 [0.551704, 0.595014] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 2.839 |
| 5/10 | independent | 0.35 | 1/2 | 18112061 | 2000 | 2269 | 2000 | 269 | 1413/2269 = 0.622741 [0.602606, 0.642462] | 0/2269 = 0.000000 [0.000000, 0.001690] | n/a | 1413/2000 = 0.706500 [0.686162, 0.726046] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 2.846 |
| 5/10 | independent | 0.35 | 11/20 | 18112062 | 2000 | 2268 | 2000 | 268 | 1713/2268 = 0.755291 [0.737176, 0.772543] | 0/2268 = 0.000000 [0.000000, 0.001691] | n/a | 1713/2000 = 0.856500 [0.840451, 0.871182] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 2.955 |
| 5/10 | independent | 0.45 | 0 | 18112063 | 2000 | 2260 | 2000 | 260 | 59/2260 = 0.026106 [0.020293, 0.033528] | 7/2260 = 0.003097 [0.001501, 0.006380] | n/a | 59/2000 = 0.029500 [0.022939, 0.037865] | 7/2000 = 0.003500 [0.001696, 0.007207] | n/a | 3.103 |
| 5/10 | independent | 0.45 | 33/100 | 18112064 | 2000 | 2249 | 2000 | 249 | 307/2249 = 0.136505 [0.122934, 0.151316] | 0/2249 = 0.000000 [0.000000, 0.001705] | n/a | 307/2000 = 0.153500 [0.138367, 0.169961] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 3.073 |
| 5/10 | independent | 0.45 | 9/20 | 18112065 | 2000 | 2269 | 2000 | 269 | 721/2269 = 0.317761 [0.298925, 0.337213] | 0/2269 = 0.000000 [0.000000, 0.001690] | n/a | 721/2000 = 0.360500 [0.339743, 0.381792] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 3.051 |
| 5/10 | independent | 0.45 | 1/2 | 18112066 | 2000 | 2242 | 2000 | 242 | 900/2242 = 0.401427 [0.381322, 0.421870] | 0/2242 = 0.000000 [0.000000, 0.001710] | n/a | 900/2000 = 0.450000 [0.428313, 0.471878] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 2.734 |
| 5/10 | independent | 0.45 | 11/20 | 18112067 | 2000 | 2235 | 2000 | 235 | 1226/2235 = 0.548546 [0.527849, 0.569076] | 0/2235 = 0.000000 [0.000000, 0.001716] | n/a | 1226/2000 = 0.613000 [0.591457, 0.634110] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 2.703 |
| 5/10 | independent | 0.55 | 0 | 18112068 | 2000 | 2246 | 2000 | 246 | 45/2246 = 0.020036 [0.015007, 0.026703] | 11/2246 = 0.004898 [0.002737, 0.008749] | n/a | 45/2000 = 0.022500 [0.016858, 0.029973] | 11/2000 = 0.005500 [0.003074, 0.009822] | n/a | 2.835 |
| 5/10 | independent | 0.55 | 33/100 | 18112069 | 2000 | 2267 | 2000 | 267 | 183/2267 = 0.080723 [0.070206, 0.092659] | 1/2267 = 0.000441 [0.000078, 0.002495] | n/a | 183/2000 = 0.091500 [0.079635, 0.104931] | 1/2000 = 0.000500 [0.000088, 0.002827] | n/a | 2.824 |
| 5/10 | independent | 0.55 | 9/20 | 18112070 | 2000 | 2252 | 2000 | 252 | 422/2252 = 0.187389 [0.171810, 0.204033] | 0/2252 = 0.000000 [0.000000, 0.001703] | n/a | 422/2000 = 0.211000 [0.193681, 0.229427] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 3.170 |
| 5/10 | independent | 0.55 | 1/2 | 18112071 | 2000 | 2269 | 2000 | 269 | 634/2269 = 0.279418 [0.261340, 0.298242] | 1/2269 = 0.000441 [0.000078, 0.002492] | n/a | 634/2000 = 0.317000 [0.296975, 0.337727] | 1/2000 = 0.000500 [0.000088, 0.002827] | n/a | 3.180 |
| 5/10 | independent | 0.55 | 11/20 | 18112072 | 2000 | 2244 | 2000 | 244 | 799/2244 = 0.356061 [0.336510, 0.376103] | 0/2244 = 0.000000 [0.000000, 0.001709] | n/a | 799/2000 = 0.399500 [0.378247, 0.421139] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 3.140 |
| 7/21 | independent | 0.35 | 0 | 18112073 | 2000 | 2428 | 2000 | 428 | 36/2428 = 0.014827 [0.010729, 0.020458] | 56/2428 = 0.023064 [0.017804, 0.029831] | n/a | 36/2000 = 0.018000 [0.013030, 0.024818] | 56/2000 = 0.028000 [0.021625, 0.036184] | n/a | 6.164 |
| 7/21 | independent | 0.35 | 33/100 | 18112074 | 2000 | 2379 | 2000 | 379 | 1017/2379 = 0.427491 [0.407744, 0.447471] | 0/2379 = 0.000000 [0.000000, 0.001612] | n/a | 1017/2000 = 0.508500 [0.486595, 0.530373] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 5.652 |
| 7/21 | independent | 0.35 | 9/20 | 18112075 | 2000 | 2398 | 2000 | 398 | 1742/2398 = 0.726439 [0.708245, 0.743908] | 0/2398 = 0.000000 [0.000000, 0.001599] | n/a | 1742/2000 = 0.871000 [0.855595, 0.884982] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 5.528 |
| 7/21 | independent | 0.35 | 1/2 | 18112076 | 2000 | 2415 | 2000 | 415 | 1916/2415 = 0.793375 [0.776767, 0.809051] | 0/2415 = 0.000000 [0.000000, 0.001588] | n/a | 1916/2000 = 0.958000 [0.948296, 0.965948] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 5.549 |
| 7/21 | independent | 0.35 | 11/20 | 18112077 | 2000 | 2374 | 2000 | 374 | 1982/2374 = 0.834878 [0.819404, 0.849270] | 0/2374 = 0.000000 [0.000000, 0.001616] | n/a | 1982/2000 = 0.991000 [0.985818, 0.994300] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 5.467 |
| 7/21 | independent | 0.45 | 0 | 18112078 | 2000 | 2368 | 2000 | 368 | 47/2368 = 0.019848 [0.014959, 0.026292] | 43/2368 = 0.018159 [0.013509, 0.024369] | n/a | 47/2000 = 0.023500 [0.017718, 0.031109] | 43/2000 = 0.021500 [0.016001, 0.028834] | n/a | 5.876 |
| 7/21 | independent | 0.45 | 33/100 | 18112079 | 2000 | 2407 | 2000 | 407 | 586/2407 = 0.243457 [0.226729, 0.261002] | 0/2407 = 0.000000 [0.000000, 0.001593] | n/a | 586/2000 = 0.293000 [0.273465, 0.313329] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 5.763 |
| 7/21 | independent | 0.45 | 9/20 | 18112080 | 2000 | 2380 | 2000 | 380 | 1316/2380 = 0.552941 [0.532897, 0.572815] | 0/2380 = 0.000000 [0.000000, 0.001611] | n/a | 1316/2000 = 0.658000 [0.636925, 0.678470] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 5.608 |
| 7/21 | independent | 0.45 | 1/2 | 18112081 | 2000 | 2369 | 2000 | 369 | 1589/2369 = 0.670747 [0.651560, 0.689381] | 0/2369 = 0.000000 [0.000000, 0.001619] | n/a | 1589/2000 = 0.794500 [0.776235, 0.811636] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 5.502 |
| 7/21 | independent | 0.45 | 11/20 | 18112082 | 2000 | 2378 | 2000 | 378 | 1799/2378 = 0.756518 [0.738863, 0.773345] | 0/2378 = 0.000000 [0.000000, 0.001613] | n/a | 1799/2000 = 0.899500 [0.885548, 0.911921] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 5.463 |
| 7/21 | independent | 0.55 | 0 | 18112083 | 2000 | 2416 | 2000 | 416 | 59/2416 = 0.024421 [0.018980, 0.031372] | 31/2416 = 0.012831 [0.009054, 0.018155] | n/a | 59/2000 = 0.029500 [0.022939, 0.037865] | 31/2000 = 0.015500 [0.010941, 0.021917] | n/a | 5.953 |
| 7/21 | independent | 0.55 | 33/100 | 18112084 | 2000 | 2401 | 2000 | 401 | 362/2401 = 0.150771 [0.137016, 0.165641] | 0/2401 = 0.000000 [0.000000, 0.001597] | n/a | 362/2000 = 0.181000 [0.164743, 0.198480] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 5.830 |
| 7/21 | independent | 0.55 | 9/20 | 18112085 | 2000 | 2385 | 2000 | 385 | 896/2385 = 0.375681 [0.356459, 0.395303] | 0/2385 = 0.000000 [0.000000, 0.001608] | n/a | 896/2000 = 0.448000 [0.426326, 0.469873] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 5.682 |
| 7/21 | independent | 0.55 | 1/2 | 18112086 | 2000 | 2408 | 2000 | 408 | 1157/2408 = 0.480482 [0.460573, 0.500452] | 0/2408 = 0.000000 [0.000000, 0.001593] | n/a | 1157/2000 = 0.578500 [0.556728, 0.599971] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 5.712 |
| 7/21 | independent | 0.55 | 11/20 | 18112087 | 2000 | 2378 | 2000 | 378 | 1460/2378 = 0.613961 [0.594225, 0.633330] | 0/2378 = 0.000000 [0.000000, 0.001613] | n/a | 1460/2000 = 0.730000 [0.710116, 0.749002] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 5.551 |
| 14/16 | independent | 0.35 | 0 | 18112088 | 2000 | 2261 | 2000 | 261 | 58/2261 = 0.025652 [0.019896, 0.033017] | 111/2261 = 0.049093 [0.040927, 0.058789] | n/a | 58/2000 = 0.029000 [0.022500, 0.037305] | 111/2000 = 0.055500 [0.046291, 0.066413] | n/a | 6.611 |
| 14/16 | independent | 0.35 | 33/100 | 18112089 | 2000 | 2277 | 2000 | 277 | 1403/2277 = 0.616162 [0.596007, 0.635925] | 1/2277 = 0.000439 [0.000078, 0.002484] | n/a | 1403/2000 = 0.701500 [0.681074, 0.721153] | 1/2000 = 0.000500 [0.000088, 0.002827] | n/a | 6.285 |
| 14/16 | independent | 0.35 | 9/20 | 18112090 | 2000 | 2265 | 2000 | 265 | 1948/2265 = 0.860044 [0.845146, 0.873723] | 0/2265 = 0.000000 [0.000000, 0.001693] | n/a | 1948/2000 = 0.974000 [0.966065, 0.980118] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 6.126 |
| 14/16 | independent | 0.35 | 1/2 | 18112091 | 2000 | 2253 | 2000 | 253 | 1993/2253 = 0.884598 [0.870746, 0.897142] | 0/2253 = 0.000000 [0.000000, 0.001702] | n/a | 1993/2000 = 0.996500 [0.992793, 0.998304] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 6.109 |
| 14/16 | independent | 0.35 | 11/20 | 18112092 | 2000 | 2271 | 2000 | 271 | 1999/2271 = 0.880229 [0.866229, 0.892945] | 0/2271 = 0.000000 [0.000000, 0.001689] | n/a | 1999/2000 = 0.999500 [0.997173, 0.999912] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 6.174 |
| 14/16 | independent | 0.45 | 0 | 18112093 | 2000 | 2272 | 2000 | 272 | 49/2272 = 0.021567 [0.016352, 0.028397] | 82/2272 = 0.036092 [0.029172, 0.044577] | n/a | 49/2000 = 0.024500 [0.018582, 0.032241] | 82/2000 = 0.041000 [0.033153, 0.050606] | n/a | 6.689 |
| 14/16 | independent | 0.45 | 33/100 | 18112094 | 2000 | 2231 | 2000 | 231 | 932/2231 = 0.417750 [0.397443, 0.438339] | 0/2231 = 0.000000 [0.000000, 0.001719] | n/a | 932/2000 = 0.466000 [0.444224, 0.487907] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 6.265 |
| 14/16 | independent | 0.45 | 9/20 | 18112095 | 2000 | 2241 | 2000 | 241 | 1673/2241 = 0.746542 [0.728121, 0.764119] | 0/2241 = 0.000000 [0.000000, 0.001711] | n/a | 1673/2000 = 0.836500 [0.819650, 0.852060] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 6.088 |
| 14/16 | independent | 0.45 | 1/2 | 18112096 | 2000 | 2251 | 2000 | 251 | 1843/2251 = 0.818747 [0.802295, 0.834114] | 0/2251 = 0.000000 [0.000000, 0.001704] | n/a | 1843/2000 = 0.921500 [0.908888, 0.932496] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 6.124 |
| 14/16 | independent | 0.45 | 11/20 | 18112097 | 2000 | 2241 | 2000 | 241 | 1958/2241 = 0.873717 [0.859322, 0.886833] | 0/2241 = 0.000000 [0.000000, 0.001711] | n/a | 1958/2000 = 0.979000 [0.971737, 0.984426] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 6.010 |
| 14/16 | independent | 0.55 | 0 | 18112098 | 2000 | 2241 | 2000 | 241 | 64/2241 = 0.028559 [0.022428, 0.036303] | 59/2241 = 0.026328 [0.020465, 0.033811] | n/a | 64/2000 = 0.032000 [0.025139, 0.040655] | 59/2000 = 0.029500 [0.022939, 0.037865] | n/a | 6.609 |
| 14/16 | independent | 0.55 | 33/100 | 18112099 | 2000 | 2266 | 2000 | 266 | 616/2266 = 0.271845 [0.253924, 0.290538] | 2/2266 = 0.000883 [0.000242, 0.003213] | n/a | 616/2000 = 0.308000 [0.288151, 0.328585] | 2/2000 = 0.001000 [0.000274, 0.003639] | n/a | 6.450 |
| 14/16 | independent | 0.55 | 9/20 | 18112100 | 2000 | 2225 | 2000 | 225 | 1281/2225 = 0.575730 [0.555081, 0.596118] | 0/2225 = 0.000000 [0.000000, 0.001724] | n/a | 1281/2000 = 0.640500 [0.619219, 0.661242] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 6.231 |
| 14/16 | independent | 0.55 | 1/2 | 18112101 | 2000 | 2267 | 2000 | 267 | 1563/2267 = 0.689457 [0.670103, 0.708171] | 0/2267 = 0.000000 [0.000000, 0.001692] | n/a | 1563/2000 = 0.781500 [0.762859, 0.799061] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 6.276 |
| 14/16 | independent | 0.55 | 11/20 | 18112102 | 2000 | 2234 | 2000 | 234 | 1751/2234 = 0.783796 [0.766246, 0.800371] | 0/2234 = 0.000000 [0.000000, 0.001717] | n/a | 1751/2000 = 0.875500 [0.860307, 0.889253] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 6.206 |
| 14/42 | independent | 0.35 | 0 | 18112103 | 2000 | 2508 | 2000 | 508 | 58/2508 = 0.023126 [0.017932, 0.029778] | 236/2508 = 0.094099 [0.083285, 0.106154] | n/a | 58/2000 = 0.029000 [0.022500, 0.037305] | 236/2000 = 0.118000 [0.104588, 0.132876] | n/a | 19.479 |
| 14/42 | independent | 0.35 | 33/100 | 18112104 | 2000 | 2534 | 2000 | 534 | 1754/2534 = 0.692186 [0.673934, 0.709856] | 0/2534 = 0.000000 [0.000000, 0.001514] | n/a | 1754/2000 = 0.877000 [0.861879, 0.890676] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 18.480 |
| 14/42 | independent | 0.35 | 9/20 | 18112105 | 2000 | 2529 | 2000 | 529 | 1992/2529 = 0.787663 [0.771294, 0.803160] | 0/2529 = 0.000000 [0.000000, 0.001517] | n/a | 1992/2000 = 0.996000 [0.992127, 0.997972] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 18.228 |
| 14/42 | independent | 0.35 | 1/2 | 18112106 | 2000 | 2556 | 2000 | 556 | 2000/2556 = 0.782473 [0.766061, 0.798036] | 0/2556 = 0.000000 [0.000000, 0.001501] | n/a | 2000/2000 = 1.000000 [0.998083, 1.000000] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 18.135 |
| 14/42 | independent | 0.35 | 11/20 | 18112107 | 2000 | 2579 | 2000 | 579 | 2000/2579 = 0.775494 [0.758988, 0.791182] | 0/2579 = 0.000000 [0.000000, 0.001487] | n/a | 2000/2000 = 1.000000 [0.998083, 1.000000] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 18.335 |
| 14/42 | independent | 0.45 | 0 | 18112108 | 2000 | 2615 | 2000 | 615 | 45/2615 = 0.017208 [0.012886, 0.022947] | 165/2615 = 0.063098 [0.054404, 0.073072] | n/a | 45/2000 = 0.022500 [0.016858, 0.029973] | 165/2000 = 0.082500 [0.071228, 0.095373] | n/a | 20.031 |
| 14/42 | independent | 0.45 | 33/100 | 18112109 | 2000 | 2552 | 2000 | 552 | 1247/2552 = 0.488636 [0.469274, 0.508033] | 1/2552 = 0.000392 [0.000069, 0.002216] | n/a | 1247/2000 = 0.623500 [0.602048, 0.644478] | 1/2000 = 0.000500 [0.000088, 0.002827] | n/a | 18.772 |
| 14/42 | independent | 0.45 | 9/20 | 18112110 | 2000 | 2563 | 2000 | 563 | 1909/2563 = 0.744830 [0.727595, 0.761333] | 0/2563 = 0.000000 [0.000000, 0.001497] | n/a | 1909/2000 = 0.954500 [0.944463, 0.962795] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 18.450 |
| 14/42 | independent | 0.45 | 1/2 | 18112111 | 2000 | 2570 | 2000 | 570 | 1976/2570 = 0.768872 [0.752179, 0.784761] | 0/2570 = 0.000000 [0.000000, 0.001493] | n/a | 1976/2000 = 0.988000 [0.982206, 0.991923] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 18.357 |
| 14/42 | independent | 0.45 | 11/20 | 18112112 | 2000 | 2605 | 2000 | 605 | 1997/2605 = 0.766603 [0.749974, 0.782446] | 0/2605 = 0.000000 [0.000000, 0.001472] | n/a | 1997/2000 = 0.998500 [0.995599, 0.999490] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 18.588 |
| 14/42 | independent | 0.55 | 0 | 18112113 | 2000 | 2591 | 2000 | 591 | 58/2591 = 0.022385 [0.017357, 0.028828] | 141/2591 = 0.054419 [0.046326, 0.063832] | n/a | 58/2000 = 0.029000 [0.022500, 0.037305] | 141/2000 = 0.070500 [0.060085, 0.082562] | n/a | 19.866 |
| 14/42 | independent | 0.55 | 33/100 | 18112114 | 2000 | 2638 | 2000 | 638 | 864/2638 = 0.327521 [0.309874, 0.345669] | 1/2638 = 0.000379 [0.000067, 0.002144] | n/a | 864/2000 = 0.432000 [0.410441, 0.453819] | 1/2000 = 0.000500 [0.000088, 0.002827] | n/a | 20.555 |
| 14/42 | independent | 0.55 | 9/20 | 18112115 | 2000 | 2550 | 2000 | 550 | 1656/2550 = 0.649412 [0.630680, 0.667694] | 0/2550 = 0.000000 [0.000000, 0.001504] | n/a | 1656/2000 = 0.828000 [0.810836, 0.843906] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 19.411 |
| 14/42 | independent | 0.55 | 1/2 | 18112116 | 2000 | 2560 | 2000 | 560 | 1856/2560 = 0.725000 [0.707376, 0.741950] | 0/2560 = 0.000000 [0.000000, 0.001498] | n/a | 1856/2000 = 0.928000 [0.915832, 0.938527] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 19.309 |
| 14/42 | independent | 0.55 | 11/20 | 18112117 | 2000 | 2601 | 2000 | 601 | 1957/2601 = 0.752403 [0.735451, 0.768610] | 0/2601 = 0.000000 [0.000000, 0.001475] | n/a | 1957/2000 = 0.978500 [0.971166, 0.983999] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 19.409 |
| 28/84 | independent | 0.35 | 0 | 18112118 | 2000 | 2567 | 2000 | 567 | 43/2567 = 0.016751 [0.012460, 0.022486] | 588/2567 = 0.229061 [0.213217, 0.245715] | n/a | 43/2000 = 0.021500 [0.016001, 0.028834] | 588/2000 = 0.294000 [0.274443, 0.314347] | n/a | 186.876 |
| 28/84 | independent | 0.35 | 33/100 | 18112119 | 2000 | 2563 | 2000 | 563 | 1996/2563 = 0.778775 [0.762295, 0.794420] | 0/2563 = 0.000000 [0.000000, 0.001497] | n/a | 1996/2000 = 0.998000 [0.994869, 0.999222] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 183.904 |
| 28/84 | independent | 0.35 | 9/20 | 18112120 | 2000 | 2567 | 2000 | 567 | 2000/2567 = 0.779120 [0.762661, 0.794744] | 0/2567 = 0.000000 [0.000000, 0.001494] | n/a | 2000/2000 = 1.000000 [0.998083, 1.000000] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 184.297 |
| 28/84 | independent | 0.35 | 1/2 | 18112121 | 2000 | 2550 | 2000 | 550 | 2000/2550 = 0.784314 [0.767929, 0.799844] | 0/2550 = 0.000000 [0.000000, 0.001504] | n/a | 2000/2000 = 1.000000 [0.998083, 1.000000] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 182.358 |
| 28/84 | independent | 0.35 | 11/20 | 18112122 | 2000 | 2514 | 2000 | 514 | 2000/2514 = 0.795545 [0.779335, 0.810854] | 0/2514 = 0.000000 [0.000000, 0.001526] | n/a | 2000/2000 = 1.000000 [0.998083, 1.000000] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 181.049 |
| 28/84 | independent | 0.45 | 0 | 18112123 | 2000 | 2554 | 2000 | 554 | 45/2554 = 0.017619 [0.013194, 0.023494] | 512/2554 = 0.200470 [0.185398, 0.216441] | n/a | 45/2000 = 0.022500 [0.016858, 0.029973] | 512/2000 = 0.256000 [0.237354, 0.275582] | n/a | 188.739 |
| 28/84 | independent | 0.45 | 33/100 | 18112124 | 2000 | 2553 | 2000 | 553 | 1878/2553 = 0.735605 [0.718153, 0.752349] | 1/2553 = 0.000392 [0.000069, 0.002215] | n/a | 1878/2000 = 0.939000 [0.927646, 0.948671] | 1/2000 = 0.000500 [0.000088, 0.002827] | n/a | 186.524 |
| 28/84 | independent | 0.45 | 9/20 | 18112125 | 2000 | 2574 | 2000 | 574 | 1999/2574 = 0.776612 [0.760116, 0.792284] | 0/2574 = 0.000000 [0.000000, 0.001490] | n/a | 1999/2000 = 0.999500 [0.997173, 0.999912] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 186.213 |
| 28/84 | independent | 0.45 | 1/2 | 18112126 | 2000 | 2554 | 2000 | 554 | 2000/2554 = 0.783085 [0.766683, 0.798638] | 0/2554 = 0.000000 [0.000000, 0.001502] | n/a | 2000/2000 = 1.000000 [0.998083, 1.000000] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 185.132 |
| 28/84 | independent | 0.45 | 11/20 | 18112127 | 2000 | 2533 | 2000 | 533 | 2000/2533 = 0.789578 [0.773271, 0.805007] | 0/2533 = 0.000000 [0.000000, 0.001514] | n/a | 2000/2000 = 1.000000 [0.998083, 1.000000] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 183.867 |
| 28/84 | independent | 0.55 | 0 | 18112128 | 2000 | 2532 | 2000 | 532 | 32/2532 = 0.012638 [0.008966, 0.017787] | 404/2532 = 0.159558 [0.145811, 0.174336] | n/a | 32/2000 = 0.016000 [0.011356, 0.022499] | 404/2000 = 0.202000 [0.184983, 0.220160] | n/a | 189.180 |
| 28/84 | independent | 0.55 | 33/100 | 18112129 | 2000 | 2558 | 2000 | 558 | 1605/2558 = 0.627443 [0.608529, 0.645975] | 1/2558 = 0.000391 [0.000069, 0.002211] | n/a | 1605/2000 = 0.802500 [0.784479, 0.819361] | 1/2000 = 0.000500 [0.000088, 0.002827] | n/a | 188.355 |
| 28/84 | independent | 0.55 | 9/20 | 18112130 | 2000 | 2573 | 2000 | 573 | 1984/2573 = 0.771084 [0.754454, 0.786907] | 0/2573 = 0.000000 [0.000000, 0.001491] | n/a | 1984/2000 = 0.992000 [0.987044, 0.995070] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 187.475 |
| 28/84 | independent | 0.55 | 1/2 | 18112131 | 2000 | 2607 | 2000 | 607 | 1997/2607 = 0.766015 [0.749379, 0.781867] | 0/2607 = 0.000000 [0.000000, 0.001471] | n/a | 1997/2000 = 0.998500 [0.995599, 0.999490] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 188.234 |
| 28/84 | independent | 0.55 | 11/20 | 18112132 | 2000 | 2533 | 2000 | 533 | 2000/2533 = 0.789578 [0.773271, 0.805007] | 0/2533 = 0.000000 [0.000000, 0.001514] | n/a | 2000/2000 = 1.000000 [0.998083, 1.000000] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 185.077 |
| 14/42 | independent | 0.4 | 9/20 | 18112133 | 2000 | 2561 | 2000 | 561 | 1963/2561 = 0.766497 [0.749721, 0.782476] | 0/2561 = 0.000000 [0.000000, 0.001498] | n/a | 1963/2000 = 0.981500 [0.974605, 0.986549] | 0/2000 = 0.000000 [0.000000, 0.001917] | n/a | 17.637 |


### Null and exact reasoning-margin boundary

Legacy direct-day generators: independent or identical oriented ranks. The shared-rank response counts depend on values; this legacy table checks unconditional day-value exchangeability, not the conditional A1 of logs/2. The next two gates exercise that conditional assumption through records.

| after/before | dependence | log SD | drop | seed | requested | generated | tested | stopped | REAL DROP (95% CI) | NO DROP (95% CI) | moved measure no drop (95% CI) | REAL DROP / tested (95% CI) | NO DROP / tested (95% CI) | choices old/current/rival | seconds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5/10 | independent | 0.45 | 0 | 18112026 | 20000 | 20000 | 17733 | 2267 | 348/20000 = 0.017400 [0.015678, 0.019307] | 75/20000 = 0.003750 [0.002993, 0.004698] | n/a | 348/17733 = 0.019624 [0.017685, 0.021772] | 75/17733 = 0.004229 [0.003376, 0.005298] | n/a | 24.706 |
| 5/10 | independent | 0.45 | 1/4 | 18112027 | 20000 | 20000 | 17720 | 2280 | 1490/20000 = 0.074500 [0.070942, 0.078221] | 9/20000 = 0.000450 [0.000237, 0.000855] | 358/20000 = 0.017900 [0.016153, 0.019832] | 1490/17720 = 0.084086 [0.080089, 0.088263] | 9/17720 = 0.000508 [0.000267, 0.000965] | n/a | 24.726 |
| 5/10 | shared | 0.45 | 0 | 18112028 | 20000 | 20000 | 19234 | 766 | 122/20000 = 0.006100 [0.005112, 0.007278] | 1421/20000 = 0.071050 [0.067571, 0.074693] | n/a | 122/19234 = 0.006343 [0.005315, 0.007568] | 1421/19234 = 0.073880 [0.070267, 0.077662] | n/a | 23.982 |
| 5/10 | shared | 0.45 | 1/4 | 18112029 | 20000 | 20000 | 19173 | 827 | 1325/20000 = 0.066250 [0.062886, 0.069781] | 351/20000 = 0.017550 [0.015821, 0.019465] | 351/20000 = 0.017550 [0.015821, 0.019465] | 1325/19173 = 0.069108 [0.065603, 0.072785] | 351/19173 = 0.018307 [0.016504, 0.020303] | n/a | 23.824 |
| 7/21 | independent | 0.45 | 0 | 18112030 | 20000 | 20000 | 16613 | 3387 | 383/20000 = 0.019150 [0.017341, 0.021144] | 359/20000 = 0.017950 [0.016200, 0.019885] | n/a | 383/16613 = 0.023054 [0.020880, 0.025449] | 359/16613 = 0.021610 [0.019507, 0.023934] | n/a | 52.133 |
| 7/21 | independent | 0.45 | 1/4 | 18112031 | 20000 | 20000 | 16693 | 3307 | 2623/20000 = 0.131150 [0.126542, 0.135899] | 31/20000 = 0.001550 [0.001092, 0.002199] | 414/20000 = 0.020700 [0.018817, 0.022767] | 2623/16693 = 0.157132 [0.151690, 0.162731] | 31/16693 = 0.001857 [0.001309, 0.002635] | n/a | 51.071 |
| 7/21 | shared | 0.45 | 0 | 18112032 | 20000 | 20000 | 18884 | 1116 | 161/20000 = 0.008050 [0.006903, 0.009386] | 2343/20000 = 0.117150 [0.112766, 0.121681] | n/a | 161/18884 = 0.008526 [0.007311, 0.009941] | 2343/18884 = 0.124073 [0.119448, 0.128852] | n/a | 48.887 |
| 7/21 | shared | 0.45 | 1/4 | 18112033 | 20000 | 20000 | 18870 | 1130 | 2705/20000 = 0.135250 [0.130580, 0.140060] | 437/20000 = 0.021850 [0.019914, 0.023970] | 437/20000 = 0.021850 [0.019914, 0.023970] | 2705/18870 = 0.143349 [0.138422, 0.148422] | 437/18870 = 0.023158 [0.021108, 0.025403] | n/a | 49.837 |
| 14/16 | independent | 0.45 | 0 | 18112034 | 20000 | 20000 | 17786 | 2214 | 455/20000 = 0.022750 [0.020773, 0.024910] | 760/20000 = 0.038000 [0.035438, 0.040740] | n/a | 455/17786 = 0.025582 [0.023362, 0.028007] | 760/17786 = 0.042730 [0.039855, 0.045803] | n/a | 61.355 |
| 14/16 | independent | 0.45 | 1/4 | 18112035 | 20000 | 20000 | 17683 | 2317 | 4018/20000 = 0.200900 [0.195405, 0.206510] | 40/20000 = 0.002000 [0.001469, 0.002722] | 429/20000 = 0.021450 [0.019532, 0.023552] | 4018/17683 = 0.227224 [0.221107, 0.233459] | 40/17683 = 0.002262 [0.001662, 0.003079] | n/a | 60.130 |
| 14/16 | shared | 0.45 | 0 | 18112036 | 20000 | 20000 | 19333 | 667 | 151/20000 = 0.007550 [0.006441, 0.008848] | 2695/20000 = 0.134750 [0.130088, 0.139552] | n/a | 151/19333 = 0.007810 [0.006664, 0.009153] | 2695/19333 = 0.139399 [0.134588, 0.144353] | n/a | 56.143 |
| 14/16 | shared | 0.45 | 1/4 | 18112037 | 20000 | 20000 | 19366 | 634 | 4188/20000 = 0.209400 [0.203817, 0.215095] | 464/20000 = 0.023200 [0.021203, 0.025380] | 464/20000 = 0.023200 [0.021203, 0.025380] | 4188/19366 = 0.216255 [0.210514, 0.222110] | 464/19366 = 0.023960 [0.021898, 0.026210] | n/a | 58.176 |
| 14/42 | independent | 0.45 | 0 | 18112038 | 20000 | 20000 | 15644 | 4356 | 397/20000 = 0.019850 [0.018007, 0.021877] | 1389/20000 = 0.069450 [0.066009, 0.073057] | n/a | 397/15644 = 0.025377 [0.023027, 0.027961] | 1389/15644 = 0.088788 [0.084431, 0.093347] | n/a | 158.864 |
| 14/42 | independent | 0.45 | 1/4 | 18112039 | 20000 | 20000 | 15472 | 4528 | 5162/20000 = 0.258100 [0.252082, 0.264211] | 73/20000 = 0.003650 [0.002904, 0.004586] | 419/20000 = 0.020950 [0.019055, 0.023029] | 5162/15472 = 0.333635 [0.326247, 0.341105] | 73/15472 = 0.004718 [0.003755, 0.005928] | n/a | 155.965 |
| 14/42 | shared | 0.45 | 0 | 18112040 | 20000 | 20000 | 18441 | 1559 | 146/20000 = 0.007300 [0.006211, 0.008578] | 4348/20000 = 0.217400 [0.211738, 0.223171] | n/a | 146/18441 = 0.007917 [0.006737, 0.009303] | 4348/18441 = 0.235779 [0.229708, 0.241960] | n/a | 130.979 |
| 14/42 | shared | 0.45 | 1/4 | 18112041 | 20000 | 20000 | 18425 | 1575 | 6044/20000 = 0.302200 [0.295874, 0.308602] | 420/20000 = 0.021000 [0.019103, 0.023081] | 420/20000 = 0.021000 [0.019103, 0.023081] | 6044/18425 = 0.328033 [0.321290, 0.334847] | 420/18425 = 0.022795 [0.020737, 0.025052] | n/a | 147.950 |
| 28/84 | independent | 0.45 | 0 | 18112042 | 20000 | 20000 | 15575 | 4425 | 387/20000 = 0.019350 [0.017531, 0.021353] | 3990/20000 = 0.199500 [0.194020, 0.205096] | n/a | 387/15575 = 0.024848 [0.022518, 0.027412] | 3990/15575 = 0.256180 [0.249385, 0.263095] | n/a | 1473.808 |
| 28/84 | independent | 0.45 | 1/4 | 18112043 | 20000 | 20000 | 15590 | 4410 | 10355/20000 = 0.517750 [0.510822, 0.524671] | 105/20000 = 0.005250 [0.004339, 0.006351] | 401/20000 = 0.020050 [0.018198, 0.022087] | 10355/15590 = 0.664208 [0.656755, 0.671580] | 105/15590 = 0.006735 [0.005567, 0.008146] | n/a | 1460.167 |
| 28/84 | shared | 0.45 | 0 | 18112044 | 20000 | 20000 | 18401 | 1599 | 149/20000 = 0.007450 [0.006349, 0.008740] | 10532/20000 = 0.526600 [0.519676, 0.533514] | n/a | 149/18401 = 0.008097 [0.006901, 0.009499] | 10532/18401 = 0.572360 [0.565198, 0.579493] | n/a | 801.892 |
| 28/84 | shared | 0.45 | 1/4 | 18112045 | 20000 | 20000 | 18425 | 1575 | 12195/20000 = 0.609750 [0.602969, 0.616489] | 393/20000 = 0.019650 [0.017817, 0.021668] | 393/20000 = 0.019650 [0.017817, 0.021668] | 12195/18425 = 0.661872 [0.655009, 0.668669] | 393/18425 = 0.021330 [0.019341, 0.023518] | n/a | 1317.975 |


### Setting changes (gate)

These are synthetic daily medians. The response records encode each median with
half the positive counts at 1 and half at twice the median minus 1. This keeps
the reference value at 1 under every exact-margin move.

14/16 days; independent day values given all response counts. Known counts 20/40/60/80/100; shares on a tenths grid; edits denominator 100. The competitive cell uses 40 known and 0..4 unknown responses per day for each rival. Old setting ends before adoption. All histories run production selection, reduction and decision. Null gates wrong REAL DROP; each single-measure exact-margin cell gates wrong NO DROP at <= 566/20000.

| after/before | scenario | log SD | drop | seed | requested | generated | tested | stopped | REAL DROP (95% CI) | NO DROP (95% CI) | moved measure no drop (95% CI) | REAL DROP / tested (95% CI) | NO DROP / tested (95% CI) | choices old/current/rival | seconds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 14/16 | null | 0.45 | 0 | 18112046 | 20000 | 20000 | 17808 | 2192 | 400/20000 = 0.020000 [0.018150, 0.022034] | 329/20000 = 0.016450 [0.014778, 0.018308] | n/a | 400/17808 = 0.022462 [0.020386, 0.024743] | 329/17808 = 0.018475 [0.016598, 0.020559] | 0/20000/0 | 247.162 |
| 14/16 | reasoning_tokens | 0.45 | 1/4 | 18112047 | 20000 | 20000 | 17875 | 2125 | 4080/20000 = 0.204000 [0.198472, 0.209641] | 19/20000 = 0.000950 [0.000608, 0.001483] | 466/20000 = 0.023300 [0.021299, 0.025484] | 4080/17875 = 0.228252 [0.222158, 0.234463] | 19/17875 = 0.001063 [0.000681, 0.001660] | 0/20000/0 | 246.414 |
| 14/16 | no_reasoning_share | 0.45 | 1/10 | 18112048 | 20000 | 20000 | 17825 | 2175 | 13990/20000 = 0.699500 [0.693108, 0.705815] | 0/20000 = 0.000000 [0.000000, 0.000192] | 7/20000 = 0.000350 [0.000170, 0.000722] | 13990/17825 = 0.784853 [0.778759, 0.790823] | 0/17825 = 0.000000 [0.000000, 0.000215] | 0/20000/0 | 244.297 |
| 14/16 | edit_failure_share | 0.45 | 3/100 | 18112049 | 20000 | 20000 | 17813 | 2187 | 1740/20000 = 0.087000 [0.083173, 0.090986] | 39/20000 = 0.001950 [0.001427, 0.002664] | 254/20000 = 0.012700 [0.011239, 0.014348] | 1740/17813 = 0.097681 [0.093408, 0.102128] | 39/17813 = 0.002189 [0.001602, 0.002991] | 0/20000/0 | 247.622 |


### Competitive setting choice (gate)

14/16 days; independent day values given all response counts. Known counts 20/40/60/80/100; shares on a tenths grid; edits denominator 100. The competitive cell uses 40 known and 0..4 unknown responses per day for each rival. Old setting ends before adoption. All histories run production selection, reduction and decision. Null gates wrong REAL DROP; each single-measure exact-margin cell gates wrong NO DROP at <= 566/20000.

| after/before | scenario | log SD | drop | seed | requested | generated | tested | stopped | REAL DROP (95% CI) | NO DROP (95% CI) | moved measure no drop (95% CI) | REAL DROP / tested (95% CI) | NO DROP / tested (95% CI) | choices old/current/rival | seconds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 14/16 | null | 0.45 | 0 | 18112050 | 20000 | 20000 | 17814 | 2186 | 367/20000 = 0.018350 [0.016580, 0.020305] | 341/20000 = 0.017050 [0.015346, 0.018939] | n/a | 367/17814 = 0.020602 [0.018617, 0.022793] | 341/17814 = 0.019142 [0.017231, 0.021261] | 0/9425/10575 | 277.878 |
| 14/16 | reasoning_tokens | 0.45 | 1/4 | 18112051 | 20000 | 20000 | 17896 | 2104 | 4079/20000 = 0.203950 [0.198423, 0.209591] | 22/20000 = 0.001100 [0.000727, 0.001665] | 411/20000 = 0.020550 [0.018674, 0.022610] | 4079/17896 = 0.227928 [0.221841, 0.234132] | 22/17896 = 0.001229 [0.000812, 0.001861] | 0/9509/10491 | 277.742 |
| 14/16 | no_reasoning_share | 0.45 | 1/10 | 18112052 | 20000 | 20000 | 17754 | 2246 | 13931/20000 = 0.696550 [0.690141, 0.702883] | 0/20000 = 0.000000 [0.000000, 0.000192] | 4/20000 = 0.000200 [0.000078, 0.000514] | 13931/17754 = 0.784668 [0.778561, 0.790653] | 0/17754 = 0.000000 [0.000000, 0.000216] | 0/9598/10402 | 275.597 |
| 14/16 | edit_failure_share | 0.45 | 3/100 | 18112053 | 20000 | 20000 | 17794 | 2206 | 1751/20000 = 0.087550 [0.083712, 0.091547] | 50/20000 = 0.002500 [0.001897, 0.003294] | 324/20000 = 0.016200 [0.014541, 0.018045] | 1751/17794 = 0.098404 [0.094114, 0.102867] | 50/17794 = 0.002810 [0.002132, 0.003702] | 0/9491/10509 | 279.701 |


### Assumption failures (report only)

The busy-cell daily medians and zero shares are drawn from per-response samples
with 20 known responses before and 100 after, then encoded as response records.
Unknown responses are added separately. The tested daily distributions therefore
have different spreads even though the sampling law has no split-date change.

Both generators break A1. Busy: same per-response law, 20 before vs 100 after, so medians/shares have count-dependent spread. New-model: first five days multiplied by 1.15, no shift at the split. A low rate does not establish A1.

| after/before | scenario | log SD | drop | seed | requested | generated | tested | stopped | REAL DROP (95% CI) | NO DROP (95% CI) | moved measure no drop (95% CI) | REAL DROP / tested (95% CI) | NO DROP / tested (95% CI) | choices old/current/rival | seconds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 14/16 | busy | 0.45 | 0 | 18112054 | 20000 | 20000 | 17581 | 2419 | 587/20000 = 0.029350 [0.027100, 0.031781] | 2095/20000 = 0.104750 [0.100582, 0.109070] | n/a | 587/17581 = 0.033388 [0.030833, 0.036147] | 2095/17581 = 0.119163 [0.114457, 0.124035] | 0/20000/0 | 254.501 |
| 7/21 | busy | 0.45 | 0 | 18112055 | 20000 | 20000 | 16659 | 3341 | 235/20000 = 0.011750 [0.010348, 0.013340] | 1451/20000 = 0.072550 [0.069037, 0.076228] | n/a | 235/16659 = 0.014106 [0.012424, 0.016013] | 1451/16659 = 0.087100 [0.082913, 0.091478] | 0/20000/0 | 227.350 |
| 14/16 | new-model | 0.45 | 0 | 18112056 | 20000 | 20000 | 17746 | 2254 | 539/20000 = 0.026950 [0.024795, 0.029287] | 254/20000 = 0.012700 [0.011239, 0.014348] | n/a | 539/17746 = 0.030373 [0.027948, 0.033001] | 254/17746 = 0.014313 [0.012668, 0.016169] | 0/20000/0 | 247.527 |
| 7/21 | new-model | 0.45 | 0 | 18112057 | 20000 | 20000 | 16870 | 3130 | 424/20000 = 0.021200 [0.019294, 0.023290] | 103/20000 = 0.005150 [0.004249, 0.006241] | n/a | 424/16870 = 0.025133 [0.022877, 0.027606] | 103/16870 = 0.006106 [0.005037, 0.007399] | 0/20000/0 | 226.099 |


### Weekly cycles and regime switches (report only)

AR(1) is stationary with independent Gaussian streams. Positive rho breaks A1. Weekly: random phase, seven-day sine, log amplitude 0.6. Regime: symmetric two-state chain, switch probability 0.08, log amplitude +/-0.6. Both break A1. Shares add round(10*(effect+1))/100 without clipping. Null reports wrong REAL DROP; exact token margin reports wrong NO DROP. The 9/20 row reports power. Per-measure passed means at least one measure passes; its conditional numerator uses the per-measure ladder. As-built passed means all three pass.

| after/before | generator | log SD | drop | metric | seed | histories | no check (95% CI) | per-measure check (95% CI) | as built (95% CI) | per-measure passed | as-built passed | per-measure conditional (95% CI) | as-built conditional (95% CI) | seconds |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 5/10 | weekly | 0.45 | 0 | wrong REAL DROP | 18112175 | 2000 | 28/2000 = 0.014000 [0.009704, 0.020160] | 25/2000 = 0.012500 [0.008481, 0.018388] | 21/2000 = 0.010500 [0.006878, 0.015999] | 1998 | 1457 | 25/1998 = 0.012513 [0.008490, 0.018406] | 21/1457 = 0.014413 [0.009446, 0.021934] | 2.642 |
| 5/10 | weekly | 0.45 | 1/4 | wrong NO DROP | 18112176 | 2000 | 0/2000 = 0.000000 [0.000000, 0.001917] | 0/2000 = 0.000000 [0.000000, 0.001917] | 0/2000 = 0.000000 [0.000000, 0.001917] | 1997 | 1421 | 0/1997 = 0.000000 [0.000000, 0.001920] | 0/1421 = 0.000000 [0.000000, 0.002696] | 2.637 |
| 5/10 | regime | 0.45 | 0 | wrong REAL DROP | 18112177 | 2000 | 359/2000 = 0.179500 [0.163300, 0.196929] | 320/2000 = 0.160000 [0.144587, 0.176717] | 252/2000 = 0.126000 [0.112170, 0.141264] | 1996 | 1369 | 320/1996 = 0.160321 [0.144879, 0.177067] | 252/1369 = 0.184076 [0.164441, 0.205479] | 2.628 |
| 5/10 | regime | 0.45 | 1/4 | wrong NO DROP | 18112178 | 2000 | 17/2000 = 0.008500 [0.005314, 0.013571] | 12/2000 = 0.006000 [0.003436, 0.010458] | 12/2000 = 0.006000 [0.003436, 0.010458] | 1994 | 1328 | 12/1994 = 0.006018 [0.003446, 0.010490] | 12/1328 = 0.009036 [0.005177, 0.015728] | 2.632 |
| 7/21 | weekly | 0.45 | 0 | wrong REAL DROP | 18112179 | 2000 | 1/2000 = 0.000500 [0.000088, 0.002827] | 1/2000 = 0.000500 [0.000088, 0.002827] | 1/2000 = 0.000500 [0.000088, 0.002827] | 1905 | 540 | 1/1905 = 0.000525 [0.000093, 0.002968] | 1/540 = 0.001852 [0.000327, 0.010414] | 4.951 |
| 7/21 | weekly | 0.45 | 1/4 | wrong NO DROP | 18112180 | 2000 | 0/2000 = 0.000000 [0.000000, 0.001917] | 0/2000 = 0.000000 [0.000000, 0.001917] | 0/2000 = 0.000000 [0.000000, 0.001917] | 1914 | 593 | 0/1914 = 0.000000 [0.000000, 0.002003] | 0/593 = 0.000000 [0.000000, 0.006436] | 4.937 |
| 7/21 | regime | 0.45 | 0 | wrong REAL DROP | 18112181 | 2000 | 590/2000 = 0.295000 [0.275422, 0.315364] | 431/2000 = 0.215500 [0.198034, 0.234056] | 162/2000 = 0.081000 [0.069830, 0.093776] | 1877 | 482 | 431/1877 = 0.229622 [0.211158, 0.249190] | 162/482 = 0.336100 [0.295372, 0.379419] | 4.785 |
| 7/21 | regime | 0.45 | 1/4 | wrong NO DROP | 18112182 | 2000 | 41/2000 = 0.020500 [0.015147, 0.027691] | 11/2000 = 0.005500 [0.003074, 0.009822] | 11/2000 = 0.005500 [0.003074, 0.009822] | 1875 | 445 | 11/1875 = 0.005867 [0.003279, 0.010475] | 11/445 = 0.024719 [0.013858, 0.043716] | 4.863 |
| 14/16 | weekly | 0.45 | 0 | wrong REAL DROP | 18112183 | 2000 | 8/2000 = 0.004000 [0.002028, 0.007873] | 5/2000 = 0.002500 [0.001068, 0.005839] | 5/2000 = 0.002500 [0.001068, 0.005839] | 1979 | 942 | 5/1979 = 0.002527 [0.001080, 0.005901] | 5/942 = 0.005308 [0.002269, 0.012365] | 6.098 |
| 14/16 | weekly | 0.45 | 1/4 | wrong NO DROP | 18112184 | 2000 | 0/2000 = 0.000000 [0.000000, 0.001917] | 0/2000 = 0.000000 [0.000000, 0.001917] | 0/2000 = 0.000000 [0.000000, 0.001917] | 1978 | 960 | 0/1978 = 0.000000 [0.000000, 0.001938] | 0/960 = 0.000000 [0.000000, 0.003986] | 6.009 |
| 14/16 | regime | 0.45 | 0 | wrong REAL DROP | 18112185 | 2000 | 745/2000 = 0.372500 [0.351575, 0.393914] | 629/2000 = 0.314500 [0.294523, 0.335188] | 362/2000 = 0.181000 [0.164743, 0.198480] | 1967 | 910 | 629/1967 = 0.319776 [0.299534, 0.340721] | 362/910 = 0.397802 [0.366496, 0.429968] | 5.897 |
| 14/16 | regime | 0.45 | 1/4 | wrong NO DROP | 18112186 | 2000 | 60/2000 = 0.030000 [0.023378, 0.038424] | 25/2000 = 0.012500 [0.008481, 0.018388] | 25/2000 = 0.012500 [0.008481, 0.018388] | 1975 | 883 | 25/1975 = 0.012658 [0.008589, 0.018620] | 25/883 = 0.028313 [0.019250, 0.041462] | 5.787 |
| 14/42 | weekly | 0.45 | 0 | wrong REAL DROP | 18112187 | 2000 | 4/2000 = 0.002000 [0.000778, 0.005131] | 1/2000 = 0.000500 [0.000088, 0.002827] | 0/2000 = 0.000000 [0.000000, 0.001917] | 1619 | 159 | 1/1619 = 0.000618 [0.000109, 0.003490] | 0/159 = 0.000000 [0.000000, 0.023590] | 14.887 |
| 14/42 | weekly | 0.45 | 1/4 | wrong NO DROP | 18112188 | 2000 | 0/2000 = 0.000000 [0.000000, 0.001917] | 0/2000 = 0.000000 [0.000000, 0.001917] | 0/2000 = 0.000000 [0.000000, 0.001917] | 1623 | 145 | 0/1623 = 0.000000 [0.000000, 0.002361] | 0/145 = 0.000000 [0.000000, 0.025809] | 14.834 |
| 14/42 | regime | 0.45 | 0 | wrong REAL DROP | 18112189 | 2000 | 829/2000 = 0.414500 [0.393094, 0.436234] | 322/2000 = 0.161000 [0.145545, 0.177755] | 27/2000 = 0.013500 [0.009294, 0.019571] | 1299 | 48 | 322/1299 = 0.247883 [0.225169, 0.272084] | 27/48 = 0.562500 [0.422750, 0.692987] | 14.179 |
| 14/42 | regime | 0.45 | 1/4 | wrong NO DROP | 18112190 | 2000 | 82/2000 = 0.041000 [0.033153, 0.050606] | 3/2000 = 0.001500 [0.000510, 0.004401] | 3/2000 = 0.001500 [0.000510, 0.004401] | 1281 | 56 | 3/1281 = 0.002342 [0.000797, 0.006863] | 3/56 = 0.053571 [0.018386, 0.146073] | 13.927 |
| 28/84 | weekly | 0.45 | 0 | wrong REAL DROP | 18112191 | 1000 | 0/1000 = 0.000000 [0.000000, 0.003827] | 0/1000 = 0.000000 [0.000000, 0.003827] | 0/1000 = 0.000000 [0.000000, 0.003827] | 553 | 9 | 0/553 = 0.000000 [0.000000, 0.006899] | 0/9 = 0.000000 [0.000000, 0.299145] | 80.472 |
| 28/84 | weekly | 0.45 | 1/4 | wrong NO DROP | 18112192 | 1000 | 0/1000 = 0.000000 [0.000000, 0.003827] | 0/1000 = 0.000000 [0.000000, 0.003827] | 0/1000 = 0.000000 [0.000000, 0.003827] | 547 | 10 | 0/547 = 0.000000 [0.000000, 0.006974] | 0/10 = 0.000000 [0.000000, 0.277533] | 80.913 |
| 28/84 | regime | 0.45 | 0 | wrong REAL DROP | 18112193 | 1000 | 458/1000 = 0.458000 [0.427339, 0.488982] | 59/1000 = 0.059000 [0.046014, 0.075361] | 0/1000 = 0.000000 [0.000000, 0.003827] | 232 | 0 | 59/232 = 0.254310 [0.202591, 0.314034] | 0/0 = undefined [undefined, undefined] | 80.086 |
| 28/84 | regime | 0.45 | 1/4 | wrong NO DROP | 18112194 | 1000 | 52/1000 = 0.052000 [0.039873, 0.067556] | 0/1000 = 0.000000 [0.000000, 0.003827] | 0/1000 = 0.000000 [0.000000, 0.003827] | 210 | 1 | 0/210 = 0.000000 [0.000000, 0.017964] | 0/1 = 0.000000 [0.000000, 0.793451] | 79.635 |


### Kept-table checks

Immutable records, no late backdated arrivals, whole-file deletion strictly after 720 hours. Captures at most 29 days apart. Both tools, admitted rows, fixed offsets 0/+330/-480, identical instant/options/window. Day lists agree after removing source; results and exact tests agree. The long-gap control names the limit: a day never captured whole stays lost.

| case | seed | histories | comparisons | mismatching histories (95% CI) |
|---|---:|---:|---:|---|
| promise | 18122026 | 500 | 8124 | 0/500 = 0.000000 [0.000000, 0.007624] |
| boundary-spanning file | 18132026 | 500 | 8092 | 0/500 = 0.000000 [0.000000, 0.007624] |
| never captured whole (outside promise) | 18142026 | 500 | 3000 | 500/500 = 1.000000 [0.992376, 1.000000] |
Each row uses seeds seed through seed+histories-1. No filesystem logs are read.


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
   unusable setting present, gives the same day table and the same result. The choice by
   after-period counts and the usable-day boundaries are checked in the self-check. The
   fall-back to the before period, the tie order of raw names, the filters of `--model` and
   `--effort` and settings present only in kept rows are held by unit and acceptance tests.
4. The rejection-rate table for the final rule, including the 45% reasoning-token drop at
   14/42 with a log standard deviation of 0.40, each cell with its generator, seed, number of
   simulations and sampling error. There is no power threshold: the streak check lowers
   power (in the 2.4.0 self-check, at 14/42 with independent days, from
   1814/2000 = 0.907000 [0.893480, 0.918960] with a per-measure check to
   1506/2000 = 0.753000 [0.733626, 0.771404] with the rule as built, seed 18112174).
5. The exact runs distribution equals brute-force enumeration for every `a + b ≤ 14`.
6. Reported, not gated: the wrong-REAL and wrong-NO-DROP rates when day values follow an AR(1)
   process with coefficient 0.3, 0.5 and 0.7, which breaks A1, with no check, with a
   per-measure check, and with the rule as built; and the reviewer's two counterexamples
   (selection by after-period counts with day values tied to response counts, which breaks A1
   as restated; a change that swaps which days are usable, which breaks A4), each shown to
   break the bound when its assumption is dropped.

The 2.4.0 self-check adds:

7. A gate with setting changes under the setting rule of `arci-logs/2`, from a generator that
   keeps A1. Each history holds two or three settings and a change of setting inside the window,
   is built through response records so that the setting choice runs, and draws each day value
   independently of that day's number of responses, so the compared setting's usable day values
   stay exchangeable given the response structure. The cells are separate, with exactly 20,000
   histories each: a null cell, in which nothing changed and the rate of REAL DROP is at most
   0.0283; and one cell per gating measure, in which that measure sits exactly at its margin and
   the others are unchanged. Both the tool's NO DROP rate and the moved measure's own
   `no drop` finding rate are at most 0.0283. Under the null, NO DROP
   is not an error and is not counted as one; in a margin cell, REAL DROP is not an error.
8. A second gate of the same kind, with the same cells, denominators of 20,000 histories and
   bounds, in which two settings have close after-period counts, so the choice is exercised and
   is not fixed by construction. Each margin cell gates both the tool's NO DROP count and
   the moved measure's own `no drop` count. Its generator keeps A1 in the same way.
9. Report only, never gated, each cell naming the assumption it breaks, on 20,000 histories per
   cell: a generator in which the compared setting has many more responses per day after the
   split than before (it breaks A1, since a median or a share over more responses varies less);
   and a generator whose newly adopted setting runs its first five days 1.15 times its later
   days, with no shift at the split (it breaks A1, since the early before-days differ from the
   later ones). In the spike for this version the second gave wrong REAL DROP 535 of 20,000 at
   14 days after against 16 before, and 415 of 20,000 at 7 after against 21 before. A low rate
   in a cell like these would not establish A1, and the claims do not cover them.
10. Each streak-check rate is also given conditional on passing the check: among the histories
    the check does not stop, the share with a wrong result, with its count and interval.
11. Power cells run until the stated number of tested histories is reached; the table says what
    each count is (histories generated, histories tested, histories stopped by the check).
12. The design 14 after against 16 before (Claude Code's default retention) in the null,
    correlation and power tables.
13. Report only: days from a weekly cycle and days from a regime-switching generator, with no
    check, a per-measure check and the rule as built.
14. The figure printed in every output (section "How far the bound can fail") and its design,
    read from the correlation table and the weekly-cycle and regime table; a test holds the
    printed values equal to this file.
15. The kept-table rules under every condition of the promise in the section "Days from the kept
    table": immutable records, no late arrival with an earlier timestamp, deletion only of
    batches strictly older than 30 times 24 hours, the same instant, options, offset and window
    for both runs, each deleted day captured whole beforehand, and successful captures at most 29
    days apart. Then the day lists of the two runs agree once `source` is removed, and the
    results agree. One further case has a session file that spans the deletion boundary; one has
    a day that was never captured whole, which stays lost and is recorded as the stated limit.
16. The first counterexample of item 6 prints as `Demonstration outside A1 (arci-logs/2): ...`.

The streak check itself is unchanged in this version. Open: one pre-stated check instead of the
three variants reported; an unknown split date; repeated daily looks.
