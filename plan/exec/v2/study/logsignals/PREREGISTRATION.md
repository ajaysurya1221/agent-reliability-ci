# Pre-registration, log-signals study: Codex sessions only, a description and not a test

Status: registered. The maintainer approved this text on 19 Nov 2026 and it was pushed at this
path: `plan/exec/v2/study/logsignals/PREREGISTRATION.md`. At that push no signal value and no
outcome value had ever been in the same record, in either half.

## Read this first

1. **Codex sessions only.** This study compares no tool with another. A count fixed in advance
   found too few usable Claude Code sessions to include (`../../signals/SIGNALS.md`, entry of
   19 Nov 2026). That is a fact about the data available, not a finding about either tool.
2. **This study describes; it does not test.** It prints how two recorded numbers line up
   inside repositories. It does not say "an association is shown" and it does not say "no
   association". No p-value and no confidence interval is computed on the paired numbers. The
   reason is in "Why there is no test". This is a change to the approved plan, which asked for
   a test.
3. **Every number and every sentence that can be published is listed here.** Nothing else from
   the paired data is published, on the result page, in the post, or anywhere later.
4. The outcome is one capture tool's attribution share. It is not correctness and not quality.
   About 73% of the sessions sit at 0% or at 100%.
5. A second reasoning measure gets a short list of numbers and no sentence.

## Question

In Codex sessions of the SWE-chat dataset, inside the same repository: how does a session's
share of responses whose recorded reasoning-token count is 0 line up with the share of changed
lines that the capture tool attributes to the agent?

The answer is a set of numbers. They describe two records attached to the same session. They
give no order in time, no prediction and no cause.

A count of 0 means the record carries no reasoning tokens for that response. It does not mean
that no reasoning happened, and nothing here can tell the two apart.

## Data and population (fixed in the final-check brief before the counts existed)

- Dataset: SWE-chat (`SALT-NLP/SWE-chat` on Hugging Face, under the ODC-By licence). Cite:
  Baumann, Padmakumar, Li, Yang, Yang and Koyejo, "SWE-chat: Real-World AI Coding Sessions in
  the Wild". The maintainer downloaded it. It stays outside this repository.
- Pool: sessions whose agent is Claude Code or Codex, with a transcript, not flagged
  `compact_transcript_delta_only`, with the dataset's attribution metric in its version 2 and
  `total_lines_changed` above 0. 4,594 sessions; 1,444 of them Codex.
- Eligible: the unchanged Codex reader of `agent-reliability-ci` 2.4.1, called once on the
  transcript, returns at least 20 main-thread responses with a known reasoning count. 855 of the
  1,444 Codex pool sessions are eligible; 225 yield no such response at all.
- Halves: repositories are split by the parity of the first hex digit of
  `sha256("arci-logsignals-halves-2026-11-19:" + repo_id)`, `repo_id` stripped and UTF-8. The
  split is never rebalanced. The brief named the odd half "confirmation" and the even half
  "discovery". Since nothing is confirmed here, this text calls them the **first reported half**
  (odd) and the **second reported half** (even). The files keep the brief's names.
- The split fixes the order in which the two halves are described. It gives no independent
  confirmation: the halves share users (limit 4).
- First reported half: **423 Codex sessions in 33 repositories**. Second reported half: 432
  sessions in 32 repositories.
- All eligible sessions enter. No trimming, no transformation, no deletion.

## The two numbers per session

- **Signal, first measure:** `no_reasoning_share`. Over the session's main-thread responses with
  a known reasoning count: responses with a count of 0, divided by all of them. Held as the
  exact fraction.
- **Signal, second measure:** `reasoning_tokens`. The median of the counts above 0, held
  exactly (it can end in .5). The tool defines it with at least 10 such responses; every
  eligible Codex session has it.
- **Outcome:** `agent_percentage` from the dataset's sessions table: the share of
  `total_lines_changed` that the capture tool attributes to the agent, 0 to 100, used as the
  table gives it. The final-check brief called these "committed lines". What the tool counts as
  a changed line, and whether those lines stayed in a commit, is the tool's own definition and
  is not checked here.
- All responses of the session are kept, including those after the table's `created_at`. What
  that field marks is not known.

The first measure carries the headline. The second gets `rho_bar`, the repository count, the
weight and the session count for each of the three block definitions, under the label "second
measure", and no sentence.

## Why there is no test

The approved plan asked for a test of association inside repositories. A design round chose a
weighted rank correlation inside repositories (defined below). Then two rounds of simulation on
synthetic data (rounds 2 and 3 in "Files"; round 1 was the design round) checked whether any
test of that number keeps its false-alarm rate at these sizes. A "null case" is a simulated
world with no link built in between a session's two numbers. Every figure in this section is
**simulated, not counted**.

**The rule, written down and hashed before the round 3 results were opened** (paraphrased and
shortened here; the file as written is committed beside this text as
`block-rule-2026-11-19.md` and bound by digest in "Files"):

> A test passes a null case when its rejection rate is at most 0.065 at 1,000 data sets. This
> is a screen with a sampling error of about 0.007, not proof of 0.05. A candidate must pass
> every applicable null case, not their average. If the month-blocked test passes all, register
> it. Else, if the repository-blocked test passes all, register it. Else register a description
> only: no p-value decides a sentence. No new candidate is searched for after the results.

The rule names its applicable null cases, taken from the round 3 brief: independent sessions; a
calendar drift shared by all repositories in both numbers, at 0.3 and at 0.6 of the variance;
one shared level per calendar month; one shared break date in each number; drift plus moderate
dependence in time; drift in the signal only; long constant runs; moderate dependence alone.
Two further scenarios of the brief decide nothing under the rule: a layout with every
repository spread over the whole window, and one dated event that moves both numbers. Under a
shared drift the two numbers can move together inside a repository with no session-level link;
that is the point of those cases. Rates for all cases are in the round 3 review. The break-date
case was coded with a fixed direction in both numbers, so it is not centred on zero; it carried
no weight in the decision.

**What the simulations showed:**

- A plain shuffle of the signal inside each repository is not valid when the sessions of a
  repository depend on each other in time. With no session-level link it rejected in 0.12 of
  runs at moderate dependence, 0.35 at strong dependence and 0.52 with two independent random
  walks inside each repository (target 0.05; three implementations, 1,000 data sets each).
- Flipping the sign of each repository's number repairs that: 0.045 to 0.053 over those seven
  cases (the same three implementations), and at most 0.056 over ten further cases (one
  implementation, 1,000 data sets each).
- It does not repair a calendar drift shared by all repositories in both numbers. Under the
  real layout of sessions over months, rejection rates with no session-level link:

  | Case | Repository blocks, 1,000 / 2,000 sets | Repository-and-month blocks, 1,000 / 2,000 sets |
  |---|---|---|
  | Shared drift, 0.3 of the variance | 0.107 / 0.099 | 0.083 / 0.077 |
  | Shared drift, 0.6 of the variance | 0.234 / 0.240 | 0.191 / 0.189 |
  | One shared level per month | 0.119 / 0.109 | 0.063 / 0.051 |
  | Drift plus moderate dependence | 0.076 / 0.085 | 0.065 / 0.066 |

  These are the reviewer's own run. At the rule's count of 1,000 the repository-blocked test is
  above the bar in all four rows and the month-blocked test in the first two. The 0.6 row
  exceeds the bar by more than ten times the sampling error for both tests. Some other cells
  exceed it by about two times that error. One implementer's own figures differ cell by cell
  and give the same outcome. The other implementer scaled the drift to about a fifth of the
  first row's strength; there the month-blocked test held everywhere (largest 0.061) and the
  repository-blocked test still failed at shared month levels (0.087). The stronger scaling is
  the one the brief's words describe. The variance shares are nominal: how strong a real drift
  is, nobody knows.
- A pattern carried only by session length passed the planned baseline gate in 0.12 to 0.25 of
  runs. The first measure's denominator is the session length, so no blocking separates them.

Neither candidate passed every case. So this is a description. The consultant (Astra,
read-only) gave the same instruction before the results: a failed calibration triggers the
descriptive fallback, and printing an inflated false-alarm rate does not make a test valid.

One file bound below reads differently and this is why. The round 3 review applied the rule
written into its own brief, which had a power condition and kept the repository-blocked test as
"primary" when the month-blocked one failed. That rule was replaced, before the results were
opened, by the stricter one quoted above. The review itself notes that the older rule "selects
the blocks whose measured rates on the triggering rows are the larger ones".

## What will be computed

For a set of **blocks** (groups of sessions), with the signal and the outcome of every session:

- `rho_b`: inside block `b`, replace each of the two numbers by its midranks (tied values all
  take the mean of the ranks they span), then take Pearson's correlation of the two midrank
  vectors. The short form `1 - 6 * sum(d^2) / (n^3 - n)` is not used; it is wrong under ties,
  and ties are the normal case here. The sums inside `rho_b` are made in exact rational
  arithmetic, with one square root in floating point at the end.
- A block carries weight when it has at least 2 sessions and neither the signal nor the outcome
  is constant inside it (exact comparison of the values as held). Its weight is
  `w_b = n_b - 1`.
- `T = sum of w_b * rho_b` and `W = sum of w_b` over weight-carrying blocks; `T` is summed with
  `math.fsum`, so the order of the blocks does not matter. The published number is
  `rho_bar = T / W`.
- A positive number means: inside the same block, sessions with a larger share of zero-count
  responses sit on a larger attributed share. It says how the two numbers move together. It
  says nothing about which one, if either, acts on the other, and the attributed share is a
  bookkeeping category, not a measure of work done.
- A repository **carries weight** for a block definition and a measure when at least one of its
  blocks does.

Three block definitions, all fixed now:

1. **Repository.** The headline.
2. **Repository and calendar month.** The month is the UTC month of the sessions table's
   `created_at`, as written in the pool manifest. It is a label and nothing more. A session
   with no month takes the label `unknown`, a label like any other.
3. **Repository, model name and session-length third.**
   - A session's model name is the most frequent model name among its main-thread responses
     with a known reasoning count; a tie goes to the name that sorts first as a string. A
     session with no model name takes the name `unknown`, a name like any other.
   - A session's length `d` is the number of those responses.
   - Thirds are cut inside each repository-and-model group. Sort its `n` sessions by `d`, then
     by the time of the session's first main-thread response (a session without one sorts after
     those with one), then by the transcript path as written in the pool manifest, which is
     unique; all ascending. Positions 1 to `floor(n/3)` are the low third, positions up to
     `floor(2n/3)` the middle third, the rest the high third. An empty third forms no block.
     The thirds are the same for both measures.

**Floor, per block definition and per measure:** that definition's numbers for that measure are
printed only when at least 10 repositories carry weight for it and its `W` is at least 150.
Otherwise every number of that definition for that measure is replaced by exactly
`not formed (k repositories, W units)`. For the repository blocks of the first measure, "not
formed" also fails condition 3 below. Elsewhere it fails no condition.

**Printed for each block definition, each measure:** `rho_bar`; the number of weight-carrying
repositories `m`; `W`; the number of sessions inside weight-carrying blocks.

**Printed for the repository blocks of the first measure only:**

- **Sign count.** How many weight-carrying repositories have `rho_r` above 0, below 0 and
  exactly 0, and the share of `W` carried by those above 0: their weight divided by the whole
  `W`.
- **Leave-one-out range.** For each weight-carrying repository `r`,
  `rho_(-r) = (T - w_r * rho_r) / (W - w_r)`. The smallest and the largest are printed. Each is
  a number over all weight-carrying repositories but one, so the range is printed only when at
  least 11 repositories carry weight; otherwise exactly `not formed`. The range shows how much
  one repository moves the number. It is not a confidence interval.
- **Without the repositories that share an identified user with the other half.** `rho_bar`
  recomputed without every repository that holds a session whose user id also appears in an
  eligible Codex session of the other half. Only the number is printed, with no count beside
  it, and only when at least 10 repositories still carry weight and `W` is still at least 150;
  otherwise exactly `not formed`. This removes identified sharing only. 168 of the 423 sessions
  carry no user id, so it is not a protection against unidentified sharing.

No count of dropped blocks or repositories by reason is printed.

**Printed as checks, beside the figure this text fixes, with "same" or "different":** sessions
and repositories found; outcome sessions at 0%, at 100% and between; sessions with a first
measure of exactly 0; the six month counts. Also printed: how many sessions took the month
label `unknown` and how many the model name `unknown`.

**Formats.** `rho_bar`: sign and three decimals (`format(x, "+.3f")`). The leave-one-out range
and the number without shared users: sign and two decimals. Shares of weight: whole percent.
Counts: integers.

No inferential probability is reported. No p-value, no permutation or sign-flip share, no
standard error and no interval is computed on the paired numbers.

## What will be published

One result page under `docs/results/log-signals-study/`, one short post under `docs/blog/`, and
one fixed sentence in the README's limits. The page carries, in this order:

1. The headline sentence below, filled from the result file.
2. The printed numbers listed above.
3. The yardstick table below, unchanged.
4. The limits below, unchanged.
5. For the second reported half, if it is run under the rule in "Order of work": the same
   headline sentence with its own counts, the same list of numbers, the general limits, and
   the second half's own facts as fixed below, under the label "second reported half, run after
   the first result was committed". The two halves stand side by side. Nothing is said about
   their agreement or disagreement. No half is called the better one, and no pooled number is
   computed.

The post contains only: the headline sentence, the yardstick table, the limits, the README
sentence and a link to the page. It adds no number, no adjective and no sentence of its own.
The same rule binds any later mention of this study.

**Headline sentence (fixed; brackets are filled from the result file):**

> In [N] Codex sessions from [R] repositories, inside the same repository, the weighted rank
> agreement between the share of responses whose recorded reasoning-token count is 0 and the
> share of changed lines attributed to the agent was **[X]** ([m] repositories carried weight,
> [W] units of weight). Inside repository-and-month blocks it was [Y, or the "not formed"
> form]. Inside repository, model-name and session-length blocks it was [Z, or the "not formed"
> form]. [a] of the [m] repositories had a number above 0, [b] below 0 and [c] exactly 0; those
> above 0 carry [S]% of the weight. Leaving out one repository at a time moves the first number
> between [lo] and [hi] (or: the leave-one-out range was not formed). No inferential test is applied to the paired data, because neither
> candidate test passed every required calibration case. This describes two records attached
> to the same session. It is not a cause, not a prediction, not a measure of quality, and it
> says nothing about order in time.

No adjective is added to a number: not "weak", not "clear", not "no link", not "tends to".

**README sentence (fixed, whatever the numbers are):**

> One study describes how a reasoning measure and an attribution share line up in public Codex
> sessions (`docs/results/log-signals-study/`). It is a description. It does not validate these
> measures against any outcome.

The README also gets the reader's limit, in the same pull request: 2,799 of the 3,150 Claude
Code pool sessions yield no countable response. That fits transcripts that record no `effort`
setting, but it is not a count of them.

**Yardstick table (simulated, not counted; fixed now; not recomputed, extended or trimmed after
the result).**

**Do not read significance from this table. Comparing the published number with these means or
spreads is not a test and supports no statement that the number is, or is not, larger than
chance.** The table shows only that the number moves by itself when no link is built in between
a session's two numbers, and by how much in ten simulated cases. From the round 3 reviewer's
implementation unless marked.

| Simulated case | Mean of `rho_bar` | SD of `rho_bar` | Data sets |
|---|---|---|---|
| Sessions independent (round 2, three implementations) | +0.00 | 0.05 | 3,000 |
| Moderate dependence in time (AR(1) 0.6) | +0.00 | 0.07 | 2,000 |
| Strong dependence in time (AR(1) 0.9), round 2 | -0.00 | 0.11 | 1,000 |
| Long constant runs, mean 15 sessions | -0.00 | 0.11 | 2,000 |
| Calendar drift shared by all repositories, 0.3 of the variance | +0.00 | 0.07 | 2,000 |
| The same at 0.6 of the variance | -0.01 | 0.17 | 2,000 |
| One shared level per calendar month | -0.00 | 0.09 | 2,000 |
| Every repository spread over the whole window, drift 0.3 | -0.01 | 0.19 | 1,000 |
| One shared break date in each number, as coded | +0.02 | 0.06 | 2,000 |
| One dated event that moves both numbers at once | +0.09 | 0.08 | 1,000 |

"AR(1) 0.6" means each session's value leans on the one before it with weight 0.6. The last
three rows are not applicable null cases of the rule. The last one is a shared cause, not a
session-level link: one dated change that affects both records puts the number near +0.09. The
row above it has a coding fault found in review (the break had a fixed direction in both
numbers); it is kept because it was measured.

## Limits that are printed with the result

General limits, printed for both halves:

1. The first number is a weighted average, and a few large repositories hold most of the
   possible weight (see the facts of each half). Realized contributing weights may differ from
   the possible weights.
2. Most sessions sit at an outcome endpoint. Inside many repositories the outcome takes few
   distinct values, and ties carry much of the weight.
3. Many sessions carry no user id, and no repository shows two identified users. Repository and
   person cannot be told apart.
4. The halves are not independent: 7 user ids appear in both.
5. All sessions fall between April and September 2026. A shared change over those months in
   both numbers moves the first number with no session-level link.
6. The first measure's denominator is the session length. A pattern carried by length cannot be
   separated from it here.
7. The population is conditional on the reader finding 20 countable responses: 855 of 1,444
   Codex pool sessions.
8. The size gate of the brief (at least 1,000 eligible sessions in at least 30 repositories,
   both tools together) passed with 1,171 sessions in 104 repositories. 316 of them are Claude
   Code sessions that are not analysed. The analysed Codex population is 855 sessions in 65
   repositories. The gate is a floor for feasibility, not a statement of power.
9. Each half's separate counts were inspected before this text was written (next section). The
   block definitions, the floors and the sentence were chosen knowing them.
10. The yardstick table is all that is known about how large this number gets with no
    session-level link, and it is simulated.

Facts of the first reported half (counted before any pairing):

- The four largest repositories hold a little over three fifths of the possible weight.
- 307 of the 423 sessions sit at an outcome endpoint (79 at 0%, 228 at 100%).
- 168 of the 423 sessions carry no user id. 11 repositories mix sessions with and without one
  and hold about seven tenths of the possible weight; 4 repositories have no identified user.
- The 7 shared user ids hold 62 of the 423 sessions, in 11 repositories (whether these are the
  11 of the line above was not counted).

Facts of the second reported half (counted before any pairing):

- The four largest repositories hold a little over three fifths of the possible weight.
- 291 of the 432 sessions sit at an outcome endpoint (107 at 0%, 184 at 100%).
- 101 of the 432 sessions carry no user id.
- The 7 shared user ids hold 80 of the 432 sessions, in 8 repositories.

## What was looked at before writing this

Counts only. Two programs produced them: one reads transcripts and knows no outcome, the other
reads the tables and knows no signal value.

One thing did pass between the two programs: availability. The outcome counts were made on the
sessions where a measure is defined, so they are conditional on the signal side's selection.
The frozen brief accepted this for a count-only screen and required it to be stated here.

- The gates G1 to G3 of the final-check brief on the whole pool (`../../signals/SIGNALS.md`).
- First half, signal alone: 316 distinct values of the first measure, 25 sessions at exactly 0,
  quartiles about 0.08, 0.16 and 0.26; 211 distinct values of the second measure, quartiles 37,
  60 and 94.
- First half, outcome alone: 79 sessions at 0%, 228 at 100%, 116 between; 89 distinct values;
  none missing.
- First half, sessions per repository: 24 repositories with at least 2 sessions, 19 with at
  least 3, 14 with at least 5.
- First half, sessions per repository and month: 47 repository-month cells, 36 of them with at
  least 2 sessions. By month, April to September: 102, 76, 109, 104, 25, 7.
- First half, user ids: 255 sessions with one, 23 distinct.
- Second half, the same separate counts: 351 distinct values of the first measure, 18 sessions
  at exactly 0, quartiles about 0.07, 0.20 and 0.34; outcome 107 at 0%, 184 at 100%, 141
  between; 27 repositories with at least 2 sessions, 25 with at least 3, 22 with at least 5; by
  month 84, 116, 80, 40, 72, 40; 331 sessions with a user id, 35 distinct. Its sessions per
  repository and month were not counted.
- The design round and two rounds of simulation on synthetic data.

Not counted before this text: how many distinct model names a repository shows, and the weight
of the third block definition. Both are counted from the signal side alone, before any pairing,
and written into the implementation record with the recount of the distinct user ids. They
change nothing in this text.

An earlier entry in this repository (`../../signals/SIGNALS.md`, 19 Nov 2026) printed some of
these counts in more detail: the largest session counts for one repository and for one user.
In the commit that adds this text, that entry is changed to rounded shares. The earlier form
stays in the commit history; that is stated in "Privacy".

## Order of work (fixed)

Dates: steps 1 to 3 by 1 December 2026; steps 4 to 7 by 10 December 2026. If a step misses its
date the study ends there. Then one note is published under `docs/results/` with exactly this
content: the last step completed; any check counts and result file already committed; and the
sentence "The study stopped at this step because its date passed; nothing was run after it."
The stop rule of 14 December 2026 (decision D-23) stands either way.

1. This text is approved by the maintainer, committed and pushed.
2. `bench/logsignals/analyze.py` is built on branch `v2/logsignals` from this text alone, in
   two stages. Stage 1 prints only the check counts and pairs nothing. Stage 2 is the only code
   that ever puts a signal value beside an outcome value. A second agent, from this text alone,
   writes its own implementation and three simulated data sets: one with a planted link, one
   with none, one of edge cases (a constant block, a one-session block, a missing model name, a
   missing month, all outcomes at an endpoint, floors not met). Two requirements: the two
   implementations agree to within 1e-9 on every number on all three sets; and on the planted
   set the repository-blocked `rho_bar` of the first measure is at least 0.10 above the same
   number on the set with none, with the sign that was planted. One correction of `analyze.py`
   is allowed. If either requirement fails a second time, no run happens, and that is published
   as the result. The hostile-input and canary tests are written and pass before any real file
   is opened. No agent has network access.
3. An implementation record is committed and pushed: the digests of the code, the tests and the
   simulation files, the signal-side counts named above, and any correction to this text. A
   correction is an arithmetic slip, a wrong digest, a typing error or a definition that two
   readers took differently, quoted as old words and new words. The question, the population,
   the measures, the block definitions, the floors, the list of printed numbers, the headline
   sentence, the yardstick table, the limits, the conditions and the README sentence cannot be
   corrected. Changing one of them ends this registration: that is published as a short note
   under `docs/results/`, and no run happens under this text. **No pairing happens in either
   half before that push.**
4. Stage 1 runs on the first half and its check counts are committed. If any check count
   differs from the figure this text fixes, stage 2 does not run: the page says "not an
   answer", prints the check counts, and the study ends.
5. Stage 2 runs on the first half, then runs again from the same inputs. The two outputs must
   be equal byte for byte. These two runs are the one start; they are not two attempts. If they
   differ, both are committed, the page says "not an answer" with the difference, the first
   run's numbers are the ones printed, and no third run happens. The result file is committed.
   It records the registration commit, the implementation-record commit, the SHA-256 of
   `analyze.py` as it ran and the start time.
6. A separate agent recounts every published number from the result file, checks condition 1,
   and checks the result file against the disclosure rules in "Privacy" before anything is
   published. A committed test under `bench/logsignals/tests/` re-derives every figure on the
   page from the result file and fails on any difference. It cannot re-derive the result file
   itself, because the paired table stays private; the recount is the only check on that.
7. **The second half: decided now, not after the first result.** If the first run met every
   condition below, the same unchanged code runs on the second half by 10 December 2026,
   whatever the first numbers were: stage 1 first, against the second half's check figures
   fixed in the section above (432 sessions in 32 repositories; 107, 184 and 141; 18 sessions
   at 0; the six month counts), then stage 2 twice only if every second-half check matches. A
   mismatch stops the study before second-half pairing and is reported under step 4. For the
   second half, condition 2 uses these second-half targets; steps 5 and 6 and all other
   conditions apply unchanged. If the first run failed a condition, the second half is not
   run.

No agent other than the orchestrator runs anything on the real files. Sub-agents work on
simulated data only.

## Conditions for reading the numbers as an answer (fixed now)

The numbers are read as an answer to the question only if all of these hold. Otherwise the page
says "not an answer", gives the failed condition, and prints what the steps above allow. If any
privacy check fails (the canary test, the hostile-input test, or the check of the result file
against the disclosure rules), only a notice without any number is published.

1. The registration commit is an ancestor of the implementation-record commit; that commit is
   an ancestor of the commit that holds the result file; the result file's recorded code digest
   matches the implementation record; and the recorded start time is later than the
   implementation record's commit date. Commit dates are what the committer wrote; the ancestry
   is not.
2. Stage 1 finds 423 sessions in 33 repositories in the first half and reproduces the separate
   counts: 79, 228 and 116 for the outcome; 25 sessions at 0 for the first measure; the six
   month counts.
3. The repository blocks of the first measure meet the floor: at least 10 repositories carry
   weight and `W` is at least 150.
4. The two runs are equal byte for byte, and the hostile-input and canary tests pass (no
   transcript text, path, session id, repository name or user name in any output).

## One start

One start per half, in the order above. If a run fails a condition, that is published as the
result. There is no second attempt: no change to the reader, no other dataset, no other
outcome, no other minimum count, no other split, no other block definition, no subgroup looked
for after the result.

## Prediction

No prediction is registered. The maintainer was offered one sentence before the push and added
none.

## What will not be claimed, whatever the numbers

- No cause, no prediction, no order in time.
- Not that either measure tracks quality, correctness or success, and not that `realornoise` is
  validated. It compares one user's days; this compares other people's sessions.
- Nothing about Claude Code, about a vendor, or about a change on any date.
- Not "an association" and not "no association". No significance statement. The simulated
  false-alarm rates above belong to tests that were examined and not registered; they are not
  applied to the result.
- Not that the number is below any threshold, and not that any link has been ruled out.
- Nothing about sessions outside the 855.
- No comparison of the two halves as a replication.

## Privacy

The paired table is private working data outside the repository. The result file holds the
printed numbers and nothing per session or per repository.

Disclosure rules, fixed now. They cover numbers computed from signal or outcome values;
counts of repositories and units of weight are structure and may be printed.

1. No value of a single session. A quartile of a share is one session's own value, so shares
   are printed rounded to two decimals and never as the fraction of counts behind them.
2. No row per repository, no list of repository sizes, no exact weight of any single repository
   or of the largest few, no largest session count for one user.
3. No `rho` computed inside fewer than 10 weight-carrying repositories.
4. No two printed numbers may let a reader isolate, by subtraction, a number for fewer than 10
   repositories. For that reason the number without shared users is printed alone, to two
   decimals, with no weight and no repository count beside it.
5. One residual is accepted and stated. Each end of the leave-one-out range leaves out one
   repository. A reader who knows that repository's weight and guesses which repository it is
   can estimate its own rank correlation from the range. Per-repository weights are not printed
   here, but the largest repository's session count is in this repository's commit history
   (see "What was looked at"). The estimate would be one rank correlation over that
   repository's sessions, not any session's value. The range is rounded to two decimals to
   keep it coarse.

What these rules do not do: they do not make anything anonymous. The dataset is public under
its own terms, and anyone who holds it can recompute every number here, per repository and per
session. The rules limit what this page adds; they do not limit what the dataset already
allows. Anyone who accepts the dataset's terms can rerun the published code.

## Changes to the approved plan: six questions for the maintainer

**The maintainer answered yes to all six on 19 Nov 2026.** The questions are kept as they were
asked. Each needed a yes or a no. Items 1 to 3 hold the study up: a "no" to any of them means this text
is not pushed and the study ends with a short note on the simulation finding alone.

1. **A description instead of a test: yes or no?** The plan said "Primary test: association
   within a repository, exact permutation (`src/arci/logs/rank_test.py`)". Neither candidate
   test passed the calibration; the shipped module is a two-sample test and has no correlation
   test.
2. **Drop "a signal counts only if it adds to them": yes or no?** The numbers inside month
   blocks and inside model-and-length blocks are printed beside the headline. Nothing is
   claimed about adding to length or model.
3. **New code under `bench/logsignals/`, standard library only: yes or no?** Nothing under
   `src/arci` changes.
4. **Describe the second half too, by the fixed rule of step 7: yes or no?** The plan said "Run
   once". On "no", step 7 and item 5 of "What will be published" are struck and only the first
   half is run.
5. **Accept that the study cannot come out "positive": yes or no?** On 14 December the row
   "study positive" of the plan's table cannot apply. The README sentence above replaces the
   plan's "no shown link" wording and is used whatever the numbers are. This follows from
   item 1.
6. **Drop the plan's secondary outcomes judged by a model (`session_success`, pushback): yes or
   no?** One outcome only. On "no", this text needs a new section before it can be pushed.

Told to the maintainer with the six questions, and done in the commit that adds this text: the
change to the earlier `SIGNALS.md` entry described above, and the two rule files committed
beside this text.

## Files

SHA-256, in full. The first three files are private working data and stay outside the
repository. The two rule files are committed beside this text. The simulation files are
committed under `bench/logsignals/calibration/` with the implementation record.

| File | SHA-256 |
|---|---|
| Pool manifest | `53f3a0277d10d0b8dd177c5835619a9f08440110d0e6ab8aaa85fb3e62363638` |
| Signal count program `signal_summary.py` | `923f09ef5db8fe3d67904798cd5d931f32bd21bc317ddae9134dd0cec414396d` |
| Outcome count program `outcome_summary.py` | `7c92201f447bab041f713c9186ff0a5b058f3d7b3fd88ec5a8fed3ecc9bb556c` |
| The rule, `block-rule-2026-11-19.md` | `333b51169511b7ea42100a29d3283e6e8c98a960e83ccf5af07f2897389d9ea3` |
| The rule applied, `block-rule-outcome-2026-11-19.md` | `f1f1339d8703a6832d80ed57e8feacdd575a1b47480d3df526d433b6eb7248a8` |
| Round 2 brief `SPEC_D.md` | `baf916b8c005b9ff327867f0b7b710c3bfb0ba96e82c42d73c5e1beb7b791d27` |
| Round 2 script A | `3e0e563980f0e666e724b516d3fd54fd511cf35a71efde89cc53118c17340cb4` |
| Round 2 script B | `d320308f631c1049e5a734f2b3e1430580b087621aa108140647952a1d6eef51` |
| Round 2 reviewer's script | `ae1031582567f23f21d454310c02c005afdac0663dad03b26345a743ea0189c9` |
| Round 2 review | `000dfdef15be7c3579160e5b71f211473d22abc361b781cc66a4533de2857241` |
| Round 3 brief `SPEC_E.md` | `bd1a8e30d3e887f4f08cf26d9aa3cd0391375106f73c044806490daeee8dafd3` |
| Round 3 script A | `ad9c89b30348d5d50a7557488fb581f485708431993193d060e61d2f13743a3f` |
| Round 3 script B | `7d91a196a76d7cc20da79cdf4f84e4f22c7c561e2409a7808da1744ed1a1307a` |
| Round 3 reviewer's script | `fef5968f34b74fc3d41ea4b42208433f9c65e3a6491765d6736f443bb9303fc9` |
| Round 3 reviewer's results | `efada83ca36ee73a285f7c22ff8bed6abf8bb4458f941445b288c869a41aa7ef` |
| Round 3 review | `03cc28e5cd927ce67a251cce2f79a9c7729f5947d42d71ab8270d08b3ed0f6cb` |

One figure in the round 2 review is wrong and is corrected here: it says repositories with no
identified user hold 37% of the weight. The recount gives 4 such repositories with a small
share of the weight; the facts of the first half above have the real structure. The rule
applied file carries its own dated correction of the counts it quotes.

## Who did what

The maintainer is one person. Agents did the work under the maintainer's approval: an
orchestrating agent, a read-only consultant agent (Astra), and separate agents for design,
simulation, review and blind tests. No person other than the maintainer read any of this before
publication.
