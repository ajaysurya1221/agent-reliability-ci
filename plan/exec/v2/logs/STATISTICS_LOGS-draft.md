# The session-log contract (arci-logs/1)

Draft for review, 15 Nov 2026. Becomes `docs/STATISTICS_LOGS.md` and is hash-pinned at the
2.3.0 release. The design record is `0016-logs-draft.md` beside this file.

This document specifies `arci logs` (also installed as `realornoise`). It reads session logs
that Claude Code or Codex already wrote on the user's disk, reduces them to one number per
measure per day, and compares the days after a split date with the days before it. It runs no
model and no trial. Nothing in `STATISTICS_SUITE.md` or `STATISTICS_OUTCOMES.md` applies here:
there are no pairs, no rounds and no betting wealth. The data are observational, and the result
names are different on purpose.

## What is compared

One comparison is made per tool (Claude Code, Codex), for one model id and one effort setting,
on the main thread only (sub-agent responses are left out).

- A **response** is one model reply as the tool recorded it (`LOG_FORMATS.md` says how it is
  recovered from each format).
- A **day** is a local calendar day. A day is **usable** for a measure when it has at least 20
  responses of that model and effort (for the file-edit measure: at least 10 file-edit results
  that were not permission denials).
- The **split date** `s` is the first day of the after period. It is 13 days before the newest
  day in the logs unless the user gives `--since`. The after period is `s` to the newest day.
  The before period is the 84 days ending the day before `s`.
- The model and effort are those with the most main-thread responses in the after period,
  unless the user names a model. The choice uses response counts only.

## Measures

Each gating measure gives one value per usable day, a direction of "worse", and a margin fixed
in this method version.

| Id | Measure (day value) | Tools | Worse | Margin |
|---|---|---|---|---|
| `reasoning_tokens` | Median reasoning-token count over responses with a positive count | both | lower | a drop to 3/4 (25%) |
| `no_reasoning_share` | Share of responses with a reasoning-token count of 0 | both | higher | 1/10 (10 points) |
| `edit_failure_share` | Share of file-edit results marked as failed | Claude Code | higher | 3/100 (3 points) |
| `repeated_value_share` | Share, among responses with a positive count, at the single most common positive count pooled over all usable days of both periods | Codex | higher | 1/10 (10 points) |

Each tool has exactly three gating measures. Day values are exact rationals. The margins are
conventions, not findings; changing one is a new method version.

A measure is a recorded quantity, not quality. Less reasoning is not a worse answer; easier
work needs less of it; a vendor can change how it counts tokens. The output says "moved toward
worse" about a measure and never says that the model, or its answers, got worse.

## The test

For one measure let `x_1..x_n` be the before-day values and `y_1..y_m` the after-day values,
each oriented so that larger is better (values of a higher-is-worse measure are negated).

**Statistic.** `U(x, y)` is the number of pairs `(i, j)` with `y_j < x_i`, strictly. A tie
counts as no evidence.

**Reference distribution.** `F(n, m, u)` is the probability that the Mann-Whitney count of a
uniformly random arrangement of `n + m` distinct values is at least `u`. It is computed by
integer dynamic programming over arrangements and held as an exact fraction; it depends on
`n`, `m` and `u` only. The p-value is `p = F(n, m, U)`.

**Real drop for a measure:** `p_real = F(n, m, U(x, y)) ≤ α_real`, with `α_real = (1/40) / 3`.

**No drop for a measure:** move every before-day by the margin toward worse, `x'_i = g(x_i)`
(`g(x) = (3/4) x` for `reasoning_tokens`; `g(x) = x − margin` in the larger-is-better
orientation for the share measures), and test the other direction:
`p_none = F(m, n, U(y, x')) ≤ α_none`, with `α_none = 1/40`. `U(y, x')` counts pairs with
`x'_i < y_j`, strictly.

**Overall result for a tool.**

1. ERROR if the logs cannot be read as specified.
2. CANNOT TELL if any gating measure has fewer than 5 usable after-days or fewer than 10
   usable before-days.
3. REAL DROP if at least one gating measure is a real drop and the self-check below does not
   fire.
4. NO DROP if every gating measure is a no-drop.
5. CANNOT TELL otherwise.

The steps are tried in this order, so a REAL DROP takes precedence over a NO DROP.

**Self-check.** Order the usable before-days by date and cut them into a first half and a second
half (the extra day, if any, goes to the first half). Run the real-drop test with the first
half as "before" and the second half as "after", at the same `α_real`. If it rejects for any
gating measure, a REAL DROP becomes CANNOT TELL, and the output says a shift of the same kind
shows inside the before period. The self-check can only withdraw a REAL DROP.

Exit codes: NO DROP 0, REAL DROP 1, CANNOT TELL 2, ERROR 3. With two tools the process exits
with the largest of 1, 2 and 0 in the order REAL DROP, CANNOT TELL, NO DROP; ERROR for one tool
with a result for the other reports the other and exits by it, naming the tool it could not
read.

No random number is drawn anywhere. The same day table gives the same result on any machine.

## What is claimed, and under which assumptions

Write `Z_d` for everything the logs record about day `d` for the chosen tool, model and effort.

**A1 (days are interchangeable when nothing changes).** If the tool's behaviour did not change
at the split, the joint distribution of the days' records is the same under any reordering of
the days.

**A2 (the split was fixed without looking).** The split date, the model and the effort were not
chosen by looking at these measures. The default split depends only on the newest day in the
logs.

**A3 (a change moves every day alike).** If behaviour changed by an amount `δ`, each after-day
value is what that day would have shown without the change, moved by `g_δ` (multiplied by
`1 − δ` for `reasoning_tokens`, shifted by `δ` for the shares).

**Claim 1 (wrong REAL DROP).** Under A1 and A2, if nothing changed, the probability that a tool's
result is REAL DROP is at most 1/40 (2.5%).

**Claim 2 (wrong NO DROP).** Under A1, A2 and A3, if at least one gating measure moved toward
worse by its margin or more, the probability that the tool's result is NO DROP is at most 1/40.

Nothing is claimed about cause. Between the two periods the user's tasks, prompts, projects,
client version and habits also changed, and A1 fails when they did. ARCI checks none of A1 to
A3 and says so in every output. Running the command every day and stopping at the first REAL
DROP is outside both claims.

## Proof

*Validity of the p-value with ties.* Under A1 and A2 with no change, the `n + m` day values are
exchangeable. Break ties among them by an independent uniformly random order; the resulting
strict ranking is a uniformly random arrangement, so its Mann-Whitney count `U*` satisfies
`P(U* ≥ u) = F(n, m, u)`. The strict count never exceeds it, `U ≤ U*`, because every strictly
ordered pair is ordered the same way after tie-breaking. `F` is non-increasing in `u`, so
`F(n, m, U) ≥ F(n, m, U*)`, and `P(F(n, m, U) ≤ α) ≤ P(F(n, m, U*) ≤ α) ≤ α`. The last step is
the usual validity of an exact p-value of a discrete statistic.

*Claim 1.* Each gating measure's real-drop test rejects with probability at most `α_real` by
the paragraph above. The usable-day rule depends only on each day's own record, so it keeps
exchangeability. Three measures at `(1/40)/3` give at most `1/40` by the union bound, whatever
the dependence between measures. The self-check only removes rejections.

*Claim 2.* Suppose measure `k` moved by `δ ≥ margin`. Under A3 each after-day value is
`y_j = g_δ(w_j)`, where `w_j` is the unchanged value, and `(x_1..x_n, w_1..w_m)` is exchangeable
by A1. `g` is strictly increasing, so `(g(x_i), g(w_j))` is exchangeable too, where `g` is the
margin move. Because `δ ≥ margin`, `y_j ≤ g(w_j)` for every `j`. `U(y, x')` counts pairs with
`x'_i < y_j`, so it is non-decreasing in each `y_j`: `U(y, x') ≤ U(g(w), x')`. By the first
paragraph applied to the exchangeable values `(x', g(w))`, the test with `g(w)` rejects with
probability at most `α_none`; with the smaller count it rejects no more often. NO DROP needs
every gating measure to be a no-drop, in particular measure `k`, so its probability is at most
`α_none = 1/40`. No correction across measures is needed for an all-must-pass rule, and the
precedence of REAL DROP only removes NO DROP results.

## What the method cannot see

- With fewer than 5 usable after-days or 10 usable before-days the result is always CANNOT
  TELL. Claude Code deletes old session files after a retention period, which limits the before
  period.
- Power (simulated, day values log-normal with a day-to-day standard deviation of the log
  between 0.35 and 0.55, as measured on one machine): the table below is regenerated by
  `bench/selfcheck_logs.py` and must be quoted with its assumptions.

  *(table inserted from the spike's `sim.py` output)*

- A drop of 10 to 20% is not detectable within 12 weeks at these variances.
- A change that began before the before period, a change in how a vendor counts tokens, and a
  change in what the user works on all look the same to the test.
- One person's logs say nothing about another person's.

## Checks that agents run (`bench/selfcheck_logs.py`)

1. `F(n, m, u)` equals brute-force enumeration for every `n + m ≤ 14` and every `u`.
2. For every `n + m ≤ 14` and tie patterns (none; values from three levels; all equal), the
   share of labelings on which a test at `α` rejects is at most `α`.
3. Null simulation, 20,000 seeded day tables per design (5/10, 7/21, 14/42, 28/84): the rate
   of REAL DROP with independent measures and with identical ranks across measures is at most
   0.0283; the rate of NO DROP with one measure exactly at its margin is at most 0.0283.
4. Power table and the planted-shift check (a 45% drop at 14/42 with log standard deviation
   0.40 gives REAL DROP in at least 95% of runs).
5. Reported, not gated: the wrong-REAL rate when day values follow an AR(1) process with
   coefficient 0.5, which breaks A1.
