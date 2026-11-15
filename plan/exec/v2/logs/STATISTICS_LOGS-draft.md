# The session-log contract (arci-logs/1)

Draft 2 for review, 15 Nov 2026 (revised after `consults/L1-records-review-codex.md`, 13
findings, all taken). Becomes `docs/STATISTICS_LOGS.md` and is hash-pinned at the 2.3.0
release. The design record is `0016-logs-draft.md` beside this file.

This document specifies `arci logs` (also installed as `realornoise`). It reads session logs
that Claude Code or Codex already wrote on the user's disk, reduces them to one number per
measure per day, and compares the days after a split date with the days before it. It runs no
model and no trial. Nothing in `STATISTICS_SUITE.md` or `STATISTICS_OUTCOMES.md` applies here:
there are no pairs, no rounds and no betting wealth. The data are observational, and the result
names are different on purpose.

## What is compared

One comparison is made per tool (Claude Code, Codex), for one **setting** (a model id and an
effort setting), on the main thread only (sub-agent responses are left out).

- A **response** is one model reply as the tool recorded it (`LOG_FORMATS.md`). Its
  **reasoning count** is a non-negative integer, or unknown when the log does not give one.
- **Days.** The local time zone's offset from UTC is read once, at the start of the run, and
  used for every timestamp (`--utc` uses offset 0). A Claude Code response belongs to the day
  of its first line; a Codex response to the day of its token-count event; a file-edit result
  to the day of the result line. Records stamped later than the start of the run are left out
  and counted.
- **Window.** `N` is the newest day with a main-thread response of the tool, after the
  `--project` filter. The split date `s` is `N − 13` days unless the user gives `--since`. The
  after period is `s` to `N`. The before period is the 84 days ending the day before `s`. A
  `--since` later than `N` gives an after period with no days.
- **Setting.** The setting with the most main-thread responses over both periods together;
  ties go to the setting whose rendered name sorts first. `--model` and `--effort` override.
  The choice never looks at which period a response is in.
- A file-edit result takes the setting of the response whose tool call it answers. Results
  that were permission denials, and results that match no recorded tool call, are left out
  and counted.

## Measures

Each gating measure gives one exact rational per usable day, a direction of "worse", and a
margin fixed in this method version.

| Id | Day value | A day is usable with | Tools | Worse | Margin |
|---|---|---|---|---|---|
| `reasoning_tokens` | Median of the positive reasoning counts (an even number of them: the mean of the two middle ones) | 20 known counts, 10 of them positive | both | lower | to 3/4 of the value |
| `no_reasoning_share` | Responses with a count of 0, over responses with a known count | 20 known counts | both | higher | + 1/10 |
| `edit_failure_share` | Failed file-edit results over file-edit results | 10 file-edit results | Claude Code | higher | + 3/100 |
| `repeated_value_share` | Positive counts equal to `v*`, over positive counts | 20 known counts, 10 of them positive | Codex | higher | + 1/10 |

`v*` is the most common positive reasoning count among all responses of the setting in the
window (both periods together); ties go to the smallest count. It does not depend on which
period a response is in. Unknown counts are never treated as 0. Each tool has exactly three
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
`p_none = G(n, m, U)`. The measure is a **no-drop** when `p_none ≤ α_none = 1/40`.

**Self-check.** For each gating measure with enough days, order its usable before-days by
date and cut them into a first half and a second half (an odd day goes to the first half).
Run the real-drop test with the first half as "before" and the second half as "after" at
`α_real`; the minimum-day rule does not apply to the halves. The self-check **fires** when
any of these rejects.

**Result for a tool, in this order.**

1. ERROR when the logs cannot be read as specified (design record, reason codes).
2. CANNOT TELL (`too_few_days`) when no gating measure has enough days.
3. If any gating measure is a real drop: CANNOT TELL (`self_check_shift`) when the self-check
   fires, REAL DROP otherwise. Nothing below is evaluated.
4. NO DROP when all three gating measures have enough days and each is a no-drop.
5. CANNOT TELL (`not_enough_evidence`) otherwise.

**Process exit code.** Among tools without ERROR: 1 if any is REAL DROP; otherwise 2 if any is
CANNOT TELL; otherwise 0. If every tool is ERROR, or no logs are found, 3. Each tool's result
is shown separately from the one exit code.

No random number is drawn anywhere. The same day table gives the same result on any machine.

## What is claimed, and under which assumptions

All statements are per tool, for the window defined above, which is treated as fixed.

**A1 (days are interchangeable when nothing changes).** If the tool's behaviour did not change
at the split, the joint distribution of the window's daily records, for all settings together,
is the same under any reordering of the days.

**A2 (nothing was chosen by looking).** The split date, and any `--model`, `--effort` or
`--project` given, were not chosen by looking at these measures.

**A3 (a change moves every day alike).** If a measure changed by `δ`, each after-day value is
exactly what that day would have shown without the change, moved by `δ` in exact arithmetic:
multiplied by `1 − δ` for `reasoning_tokens`, shifted by `δ` toward worse for a share. This
is a model of the daily value, not of how a model computes; it leaves out changes that round,
clip at 0 or 1, or differ from day to day, and Claim 2 says nothing about those.

**A4 (a change leaves the days and the setting as they were).** The change does not alter
which days are usable for a measure, nor which setting is selected.

**Claim 1 (wrong REAL DROP).** Under A1 and A2, if nothing changed, the probability that a
tool's result is REAL DROP is at most 1/40 (2.5%).

**Claim 2 (wrong NO DROP).** Under A1 to A4, if at least one gating measure moved toward worse
by its margin or more, the probability that the tool's result is NO DROP is at most 1/40.

With two tools, the chance that at least one shows a wrong REAL DROP is at most 5%.

Nothing is claimed about cause, about answer quality, or about a change to a model. Between
the periods the user's tasks, prompts, projects, client version and habits may have changed,
and A1 fails when they did. ARCI checks none of A1 to A4 and says so in every output. Running
the command day after day and stopping at the first REAL DROP is outside both claims.

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
`1/40` whatever the dependence between measures. The self-check only removes rejections.

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
gating measure to be a no-drop, measure `k` included, and step 3 only removes NO DROP results.

## What the method cannot see

- A measure with fewer than 5 usable after-days or 10 usable before-days is not tested. A
  period in which every response has a reasoning count of 0 has no usable day for
  `reasoning_tokens`, so the result cannot be NO DROP. Claude Code deletes old session files
  after a retention period, which limits the before period.
- Power is limited at the sizes most people have. `bench/selfcheck_logs.py` regenerates a
  table of rejection rates for named designs (usable days after and before, size of the
  drop, day-to-day spread, seed and number of simulations), computed with this document's
  final rule. Any figure quoted from it carries those conditions. The simulation thresholds
  are checks of the implementation; the bounds above are proved, not simulated.
- A change that began before the before period, a change in how a vendor counts tokens, and a
  change in what the user works on all look the same to the test.
- One person's logs say nothing about another person's.

## Checks that agents run (`bench/selfcheck_logs.py`)

1. `G(n, m, u)` and `p_real` equal brute-force enumeration for every `n + m ≤ 14` (for
   `p_real` on tie patterns: none; three levels; all equal).
2. For those cases, the share of labelings on which each test rejects at `α` is at most `α`.
3. Null simulation with the final rule, including setting selection, usable-day rules and the
   self-check: 20,000 seeded day tables per design (5/10, 7/21, 14/42, 28/84), measures
   independent and measures with identical ranks; the rate of REAL DROP is at most 0.0283.
   With one measure exactly at its margin and the others unchanged, the rate of NO DROP is at
   most 0.0283.
4. The rejection-rate table, and the planted-shift check (a 45% drop at 14/42 with a log
   standard deviation of 0.40 gives REAL DROP in at least 95% of runs).
5. Reported, not gated: the wrong-REAL rate when day values follow an AR(1) process with
   coefficient 0.5, which breaks A1; and the reviewer's two counterexamples (selection by
   after-period counts; a change that swaps which days are usable), each shown to break the
   bound when its assumption is dropped.
