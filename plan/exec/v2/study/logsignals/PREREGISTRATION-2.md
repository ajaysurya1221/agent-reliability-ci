# Pre-registration 2, log-signals study: Codex sessions only, a description and not a test

Status: registered. The maintainer approved this text on 19 Nov 2026 and it was then pushed.
Path: `plan/exec/v2/study/logsignals/PREREGISTRATION-2.md`. At the push of this text no signal value
and no outcome value had ever been in the same record, in either half.

**This text replaces an earlier one.** The first registration
(`PREREGISTRATION.md` beside this file, commit `ea3b762e3975fd80bf98e6d9e7d9b75ce6d71b98`,
SHA-256 `d47b0d2724c435ea7c23731471a517640c4a313cff53935dafa63de8224fc3e2`)
ended on 19 Nov 2026 before either of its stages ran, because one of its printed limits was
false and its own rule says a limit cannot be corrected. The note that ends
it is `FIRST-REGISTRATION-ENDED.md` beside this file; step 1 also publishes it as
`docs/results/log-signals-study-first-registration-ended.md` on the code branch. This text is
a new registration, not an amendment.

The question, the population, the two measures, the floors, the headline sentence, the
yardstick table, the README sentence and the dates are the same. Five of the differences matter
most, and a reader should look at them first. This is a summary; the full list is at the end.

- **Block definition 3.** Two readings that the first text left open are written down (changes
  7 and 8). Either can decide which block a session falls in.
- **The printed limits and the facts of each half** (changes 13 to 17). One limit was false and
  one had no count behind it.
- **Two failure reports** are specified more fully: a month label outside the six (change 10)
  and the note for a missed date (change 21). The numbers printed with a result are unchanged.
- **The order of work** is rewritten around code that already exists (change 22).
- **Privacy.** One more leftover is accepted and stated: printed numbers can show the size of a
  block that carries no weight (changes 30, 38 and 39).

Every difference between the two texts is listed as old words and new words in "Changes from
the first registration" at the end. The code was built under the first text and is reused;
"Order of work" says how.

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
   About 70% of the 855 sessions sit at 0% or at 100% (307 of 423 in the first half, 291 of
   432 in the second).
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
  eligible Codex session has it. The extractor checks this: it stops and writes nothing if an
  eligible session has fewer than 10. It did not stop.
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
case was coded with a fixed direction in both numbers, so it is not centred on zero. As coded,
both candidate tests passed it (0.050 and 0.042 at 1,000 data sets). With the direction drawn
per number, as the review recommends, the repository-blocked test reads 0.070 and the
month-blocked test 0.057. Either way the outcome was decided by other cases.

**What the simulations showed:**

- A plain shuffle of the signal inside each repository is not valid when the sessions of a
  repository depend on each other in time. With no session-level link it rejected in 0.12 of
  runs at moderate dependence, 0.35 at strong dependence and 0.52 with two independent random
  walks inside each repository (target 0.05; three implementations, 1,000 data sets each).
- Flipping the sign of each repository's number repairs that: 0.045 to 0.053 over the seven
  null cases of the round 2 brief, which include the three just named (the same three
  implementations), and at most 0.056 over ten further cases that the reviewer added (section 4
  of the round 2 review; one implementation, 1,000 data sets each).
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
  exceeds the bar by more than ten times the sampling error for both tests. The other cells
  above the bar exceed it by about two to eight times that error. In the fourth row the
  month-blocked test equals the bar at 1,000 sets and is 0.066 at 2,000. One implementer's own
  figures differ cell by cell
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
  and tied values are common here: most sessions sit at 0% or at 100%. The sums inside
  `rho_b` are made in exact rational
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
     with a known reasoning count. A response that carries no model name gives no vote. A tie
     goes to the name that sorts first as a string. A session in which no counted response
     carries a model name takes the name `unknown`, a name like any other.
   - A session's length `d` is the number of those responses.
   - Thirds are cut inside each repository-and-model group. Sort its `n` sessions by `d`, then
     by the earliest timestamp among the session's main-thread responses, counted or not (a
     session without one sorts after those with one), then by the transcript path as written in
     the pool manifest, which is unique; all ascending. Positions 1 to `floor(n/3)` are the
     low third, positions up to
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
  of the first half and 101 of the 432 of the second carry no user id, so it is not a
  protection against unidentified sharing.

No count of dropped blocks or repositories by reason is printed.

**Printed as checks, beside the figure this text fixes, with "same" or "different":** sessions
and repositories found; outcome sessions at 0%, at 100% and between; sessions with a first
measure of exactly 0; the six month counts. Also printed: how many sessions took the month
label `unknown` and how many the model name `unknown`. If stage 1 finds a month label other
than the six, it is printed as one more check row with the registered figure 0, so it reads
"different".

**Formats.** `rho_bar`: sign and three decimals (`format(x, "+.3f")`). The leave-one-out range
and the number without shared users: sign and two decimals (`format(x, "+.2f")`). Shares of
weight: whole percent (`format(100 * share, ".0f")`, which sends an exact half to the even
digit). Counts: integers.

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

"AR(1) 0.6" means each session's value leans on the one before it with weight 0.6. The rule
applies to nine null cases of round 3. The first row is the round 2 run of one of them
(independent sessions). The third row is a round 2 case that is not among the nine. The eighth
and the tenth rows are round 3 cases outside the nine. The tenth is a shared cause, not a
session-level link: one dated change that affects both records puts the number near +0.09.
The ninth row is one of the nine, but it has a coding fault found in review (the break had a
fixed direction in both numbers); it is kept because it was measured.

## Limits that are printed with the result

General limits, printed for both halves:

1. The first number is a weighted average, and a few large repositories hold most of the
   possible weight (see the facts of each half). Realized contributing weights may differ from
   the possible weights.
2. Most sessions sit at an outcome endpoint (see the facts of each half), so many sessions
   share the same outcome value.
3. Many sessions carry no user id (see the facts of each half). Blocking by repository does
   not separate differences between people from the number.
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
9. Each half's separate counts were inspected before the first registration was written, and
   more signal-side counts were made before this one (next section). The block definitions,
   the floors and the sentence were chosen knowing the first set. After the second set, two
   readings inside the third block definition were written down; nothing else in them was
   changed.
10. The yardstick table is all that is known about how large this number gets with no
    session-level link, and it is simulated.

Facts of the first reported half (counted before any pairing):

- The four largest repositories hold a little over three fifths of the possible weight.
- 307 of the 423 sessions sit at an outcome endpoint (79 at 0%, 228 at 100%).
- 168 of the 423 sessions carry no user id. 11 repositories mix sessions with and without one
  and hold about seven tenths of the possible weight (whether the four largest repositories
  are among these 11 was not counted); 4 repositories have no identified user.
- No repository shows two or more identified user ids: 29 show one and 4 show none.
- The 7 shared user ids hold 62 of the 423 sessions, in 11 repositories (whether these are the
  11 of the line above was not counted).

Facts of the second reported half (counted before any pairing):

- The four largest repositories hold a little over three fifths of the possible weight.
- 291 of the 432 sessions sit at an outcome endpoint (107 at 0%, 184 at 100%).
- 101 of the 432 sessions carry no user id.
- Some of the 32 repositories show two or more identified user ids.
- The 7 shared user ids hold 80 of the 432 sessions, in 8 repositories.

## What was looked at before writing this

Counts only, in two rounds. "No pairing" does not mean "no data inspected": everything below
was seen before this text was written.

### Before the first registration

Two programs produced these counts: one reads transcripts and knows no outcome, the other reads
the tables and knows no signal value.

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
- Second half, most of the same separate counts: 351 distinct values of the first measure, 18
  sessions at exactly 0, quartiles about 0.07, 0.20 and 0.34; outcome 107 at 0%, 184 at 100%,
  141 between, 141 distinct values, none missing; 27 repositories with at least 2 sessions, 25
  with at least 3, 22 with at least 5; by month 84, 116, 80, 40, 72, 40; 331 sessions with a
  user id, 35 distinct. Its second measure's counts were printed and are not quoted here. Its
  sessions per repository and month were not counted before the first registration.
- The facts of each half as the limits print them: the share of possible weight in the four
  largest repositories, the sessions without a user id, the first half's mixed repositories
  and its repositories with no identified user, and the sessions and repositories of the 7
  shared user ids.
- Printed by the same two programs and left out of the first text's list: in neither half does
  any session have a first measure of exactly 1; how many repositories with at least 3
  sessions show at least 2 distinct outcome values (all of them in the first half, most in the
  second); no outcome value lies outside 0 to 100; and how many sessions sit at each number's
  most common value. The same counts were printed for the Claude Code
  sessions, which are not analysed.
- The design round and two rounds of simulation on synthetic data. Two lines of the round 2
  brief were assumptions and not counts: a median session length of 60, and "1 to 3 model
  names per repository".

### Between the two registrations (19 Nov 2026)

All from the signal side alone, or from one side at a time. No program read a signal value and
an outcome value of the same session.

- **The two private tables were written**, each by a program that knows one side, at the code
  commit named in "Files". `signal.tsv`: 855 rows. The signal extractor read the 1,444 Codex
  transcripts and printed: every file present, 589 not eligible, no reader failure, 855
  written. `outcome.tsv`: 4,594 rows, one per pool session. The outcome extractor read two
  columns of the dataset's sessions table (the transcript path and `agent_percentage`; 17,968
  rows) and printed: 4,594 manifest paths, each found once, none without a value.
- **The check figures and the user-id counts were recounted** from `signal.tsv` and are the
  same for both halves: sessions, repositories, sessions at exactly 0, the six month counts,
  sessions with a user id, distinct user ids, user ids in both halves.
- **Model names per repository.** First half: 25 repositories show one name, 5 show two, 3 show
  three or more. Second half: 23, 8 and 1. The name `unknown` counts as a name. 6 sessions of
  the first half and none of the second take the name `unknown`. No session of either half
  takes the month label `unknown`.
- **Possible weight before any outcome is read**: the sum of `n_b - 1` over blocks of at least
  2 sessions, with the number of repositories holding such a block. Repository blocks: 390
  units in 24 repositories (first half) and 400 in 27 (second). Repository-and-month blocks: 376
  in 24 and 377 in 26; the second half's cells were counted here for the first time.
  Repository, model-name and session-length blocks: 321 in 16 and 325 in 24. These are upper
  bounds on `W` and `m`. The two repository figures follow from counts made before the first
  registration.
- **User ids per repository**, as now printed in the facts of each half. The orchestrating
  agent counted them with a short script after the consultant's finding, and the audit below
  counted them again.
- **An audit of the first text.** One agent listed every factual sentence of it. Two agents
  wrote separate count programs for the 59 sentences that can be recounted from `signal.tsv`,
  tested on made-up tables. Both programs give the same counts; 58 match the first text and
  one does not (its limit 3). Among the 58 are the shares behind "a little over three fifths",
  "about seven tenths" and "a small share"; they are as the first text says, and the exact
  weights are not printed. 269 of the 855 sessions carry no user id.
- **Computed, seen by the orchestrating agent in private output, and not published**, because
  they would break a disclosure rule: the possible weight restricted to blocks where a measure
  is not constant (beside the figures above it would isolate single blocks); the exact weights
  behind the shares in the facts of each half; how many repositories of the second half show
  two or more identified user ids, one, or none; and the largest number of user ids in one
  repository.
- **On the outcome side nothing was counted per half again.** The outcome figures in this text
  come from the count program that ran before the first registration. The only new outcome-side
  output is the outcome extractor's line above.
- **The code was built and compared** with a second implementation on simulated data ("Order of
  work", step 2).

None of these counts changed the question, the population, the measures, the floors, the
printed numbers or the headline sentence. In the block definitions, two readings inside the
third were written down afterwards (changes 7 and 8); nothing else in them was changed.

An earlier entry in this repository (`../../signals/SIGNALS.md`, 19 Nov 2026) printed some of
these counts in more detail: the largest session counts for one repository and for one user.
In the commit that added the first text, that entry was changed to rounded shares. The
earlier form stays in the commit history; that is stated in "Privacy".

## Order of work (fixed)

Dates: steps 1 to 3 by 1 December 2026; steps 4 to 7 by 10 December 2026. These are the dates
of the first registration; the replacement does not move them. If a step misses its date the
study ends there. Then one note is published under `docs/results/` with exactly this content:
the line "Last step completed: N."; the check counts already committed, as the page prints
them; for a result file already committed, what the page carries for that half (the headline
sentence, the printed numbers, the yardstick table, the limits and that half's facts); and the
sentence "The study stopped at this step because its date passed; nothing was run after it."
The stop rule of 14 December 2026 (decision D-23) stands either way.

1. This text is approved by the maintainer, committed and pushed, together with the note that
   ends the first registration (beside this file, and as
   `docs/results/log-signals-study-first-registration-ended.md` on the code branch).
2. **The code exists and is reused.** `bench/logsignals/` was built on branch `v2/logsignals`
   under the first text, before this one was written (commit
   `c65ed3cee64f75394d0100e2bdb971ed697580c3`).
   It has two stages. Stage 1 prints only the check counts and pairs nothing. Stage 2 is the
   only code that ever puts a signal value beside an outcome value. A second agent, from the
   first text and a note on file formats alone, wrote its own implementation and the simulated
   data sets: one with a planted link, one with none, and the edge cases as four data sets (a
   constant block, a one-session block, a missing model name, a missing month, all outcomes at
   an endpoint, floors not met). Two requirements: the two implementations agree to within
   1e-9 on every number on all the sets; and on the planted set the repository-blocked
   `rho_bar` of the first measure is at least 0.10 above the same number on the set with none,
   with the sign that was planted. Both held on that commit: 660 values, none differing; the
   difference was 0.45 and 0.28 in the two simulated halves. The registered code refused the
   tables as the second agent wrote them, because their paths had another form. The comparison
   ran on copies with the paths renamed in the same string order, and a control shows that the
   rename moved no number. The hostile-input and canary tests passed before the extractors
   opened any real file. No agent has network access.

   **Under this text:** the code may change only where this text differs from the first (the
   fixed sentences that the page prints, and the comments and tests that quote them) or where
   the implementation record names a fault. After any change, the tests run again and the
   comparison runs again on the same simulated sets against the same second implementation.
   No code changes after the implementation record of step 3 is pushed. One correction of
   `analyze.py` is allowed. It was not used under the first text, and it is the same one
   allowance, not a new one. If either requirement fails a second time, no run happens, and
   that is published as the result. The second implementation is never run on the real
   tables.
3. An implementation record is committed and pushed: the digests of the code, the tests and the
   simulation files, the digests of the two private tables, a list of every place where the
   code had to choose a reading of this text, and any correction to this text. No reading may
   change an item that cannot be corrected. A
   correction is an arithmetic slip, a wrong digest, a typing error or a definition that two
   readers took differently, quoted as old words and new words. The question, the population,
   the measures, the block definitions, the floors, the list of printed numbers, the headline
   sentence, the yardstick table, the limits, the conditions and the README sentence cannot be
   corrected. Changing one of them ends this registration: that is published as a short note
   under `docs/results/`, and no run happens under this text. **No pairing happens in either
   half before that push.**
4. Stage 1 runs on the first half and its check counts are committed. If any check count
   differs from the figure this text fixes, stage 2 does not run: the page says "not an
   answer", prints the check counts and no other number computed from the data, and the study
   ends.
5. Stage 2 runs on the first half, then runs again from the same inputs. The two outputs must
   be equal byte for byte. These two runs are the one start; they are not two attempts. If they
   differ, both are committed, the page says "not an answer" with the difference, the first
   run's numbers are the ones printed, and no third run happens. The result file is committed.
   It records the registration commit, the implementation-record commit, the SHA-256 of
   `analyze.py` as it ran, the SHA-256 of the two private tables and the start time. The start
   time is taken once, by the first of the two runs (UTC, whole seconds); the second run uses
   the same value. Every other byte of the two files is produced by each run on its own.
6. A separate agent recounts every published number from the result file, checks condition 1,
   and checks the result file against the disclosure rules in "Privacy" before anything is
   published. A committed test at `tests/unit/logsignals/test_page_rederivation.py` re-derives
   every figure on the page from the result file and fails on any difference. It cannot
   re-derive the result file
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
   is not. The chain is checked on the records branch `v2/phase0`, where this text, the
   implementation record, the check counts and the result files are committed. The published
   folder on the code branch holds copies with the same bytes.
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

No prediction is registered. The maintainer was offered one sentence before the push of the
first text and added none. The offer is not made again for this text: more has been counted
since.

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

1. No value of a single session. A quartile of a share is one session's own value or lies
   between two, so shares are printed rounded to two decimals and never as the fraction of
   counts behind them.
2. No row per repository, no list of repository sizes, no exact weight of any single repository
   or of the largest few, no largest session count for one user, no largest count of user ids
   for one repository. The one exception is the second residual of rule 5.
3. No `rho` computed inside fewer than 10 weight-carrying repositories.
4. No two printed numbers may let a reader isolate, by subtraction, a number for fewer than 10
   repositories, except the two residuals accepted in rule 5. For that reason the number
   without shared users is printed alone, to two decimals, with no weight and no repository
   count beside it.
5. Two residuals are accepted and stated. The second one first, because it is new in this
   text. The result prints `m` and `W` for each block definition, and this text prints the
   possible weight of each ("What was looked at": 390 and 400 units for the repository blocks,
   and the figures for the other two definitions). The difference between a possible weight
   and the printed `W` is the summed size, less one each, of the blocks that carry no weight,
   and it tells a reader that their signal or their outcome is constant. When exactly one
   repository block carries no weight, the difference is that one repository's weight, and its
   session count is one more. That case is an exception to rules 2 and 4. The first text had
   the same residual for the repository blocks without stating it: 423 sessions, 33
   repositories and 24 with at least 2 sessions already give the 390. The first residual:
   each end of the leave-one-out range leaves out one repository. A reader who knows that
   repository's weight and guesses which repository it is
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

**The maintainer answered yes to all six on 19 Nov 2026, for the first text.**
On 19 Nov 2026 the maintainer chose to replace the first text, and approved this text as a whole.
The questions are kept as they were asked. Item 3 as built: the code is under
`bench/logsignals/` and its tests under `tests/unit/logsignals/`. It uses the standard library;
the signal extractor also calls the shipped `arci` reader, and the outcome extractor needs a
library that reads the dataset's table format, which is not a dependency of the package and is
used in a separate environment. The approval of this text is given knowing this. Each needed a
yes or a no. Items 1 to 3 hold the study up: a "no" to any of them means this text
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

Told to the maintainer with the six questions, and done in the commit that added the first
text: the change to the earlier `SIGNALS.md` entry described above, and the two rule files
committed beside this text.

## Files

SHA-256, in full. The first three files are private working data and stay outside the
repository. The two rule files are committed beside this text. The eleven simulation files are
committed under `bench/logsignals/calibration/`. Six are committed as they are. Five (the round
2 brief, the three round 2 scripts and the round 2 review) are committed as copies in which
the session counts of single repositories are replaced by a marker `[WITHHELD: ...]`. Nothing
else is withheld. The implementation record gives both digests of each. The digests in this
table are the originals'.

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

Files that the first text's table does not list:

| File | SHA-256 or commit |
|---|---|
| The first registration, `PREREGISTRATION.md` | `d47b0d2724c435ea7c23731471a517640c4a313cff53935dafa63de8224fc3e2` |
| The code, branch `v2/logsignals` | commit `c65ed3cee64f75394d0100e2bdb971ed697580c3` |
| `bench/logsignals/analyze.py` at that commit | `37aa10908e8497d179a2b7e4ae06d9b0b873bceeefd6ecc43e103dbce67fb268` |
| `bench/logsignals/extract_signal.py` at that commit; it wrote `signal.tsv` | `30b874c0bbda6091a6b54794c7bef69741c32de1297fe50a457c975612fa52cb` |
| `bench/logsignals/extract_outcome.py` at that commit; it wrote `outcome.tsv` | `ed6158ec92a69b6c6b819237cac58b8422fab064a30f99018c6ec65feb18f907` |
| `bench/logsignals/signal_counts.py` at that commit | `94b284d8d141c9a37ab038695ca54788fcb8a58410f649464de6cf74022fa23f` |
| Private table `signal.tsv`, written 19 Nov 2026 | `68f65e4efc6f6c37a8fbbc93a12917b6fc7ed394775892c9528136f409f9a2f6` |
| Private table `outcome.tsv`, written 19 Nov 2026 | `0207c517088c4b83b67a8a89953ea01badfcfb269d528df9be1726a1677fd29d` |
| Audit count program A (private) | `acf7280792bd370cd0f7f1af2097e3cea3443ab8c3abf78c08d45694a7c4d389` |
| Audit count program B (private) | `78a7bda17fdfd154e007d03fbb8a86bd16d00cbc0c4ee1537db8367db163ced1` |
| Private month table used by the round 3 scripts (made before the first registration and not in its table) | `3952cdfdaa23650787fd16cf5e27c9f4c465b70310d5f00a3a0ebebbe98a526b` |

The same code commit holds, under `bench/logsignals/comparison/`, the second implementation,
the program that writes the simulated sets, the digests of those sets, the expected outputs,
the comparison program and its report; and under `bench/logsignals/calibration/` the simulation
files. The month table has one row per repository of the first half (its session count and
its count per month) and is not committed; it can be rebuilt from `signal.tsv`, and the
implementation record says how.

The code digests above are of the code as built under the first text. If step 2 changes the
code, the implementation record gives the new commit and digests, and those are the ones
condition 1 uses.

## Who did what

The maintainer is one person. Agents did the work under the maintainer's approval: an
orchestrating agent, a read-only consultant agent (Astra), and separate agents for design,
simulation, review and blind tests. No person other than the maintainer read any of this before
publication.

The false sentence that ended the first registration was written by the orchestrating agent.
Two review rounds and the consultant read it before that registration and did not catch it.
The consultant caught it afterwards, while reviewing the implementation record. One reviewing
agent, working on the same record at the same time without the consultant's answer, reported
the same contradiction. The audit of the whole text was started because of that finding.

## Changes from the first registration

Every difference between the first text and this one. Changes 1 to 35 are in the order of
the text; changes 36 to 39 were added after review and sit where their headings say; the last
change is this section itself. This list
is generated from the same edits that produced this text from the first, so it is complete:
outside the passages below and this section, the two texts are the same byte for byte.
Indented blocks are quotations.

### Change 1: Title and status

Old words:

    # Pre-registration, log-signals study: Codex sessions only, a description and not a test

    Status: registered. The maintainer approved this text on 19 Nov 2026 and it was pushed at this
    path: `plan/exec/v2/study/logsignals/PREREGISTRATION.md`. At that push no signal value and no
    outcome value had ever been in the same record, in either half.

New words:

    # Pre-registration 2, log-signals study: Codex sessions only, a description and not a test

    Status: registered. The maintainer approved this text on 19 Nov 2026 and it was then pushed.
    Path: `plan/exec/v2/study/logsignals/PREREGISTRATION-2.md`. At the push of this text no signal value
    and no outcome value had ever been in the same record, in either half.

    **This text replaces an earlier one.** The first registration
    (`PREREGISTRATION.md` beside this file, commit `ea3b762e3975fd80bf98e6d9e7d9b75ce6d71b98`,
    SHA-256 `d47b0d2724c435ea7c23731471a517640c4a313cff53935dafa63de8224fc3e2`)
    ended on 19 Nov 2026 before either of its stages ran, because one of its printed limits was
    false and its own rule says a limit cannot be corrected. The note that ends
    it is `FIRST-REGISTRATION-ENDED.md` beside this file; step 1 also publishes it as
    `docs/results/log-signals-study-first-registration-ended.md` on the code branch. This text is
    a new registration, not an amendment.

    The question, the population, the two measures, the floors, the headline sentence, the
    yardstick table, the README sentence and the dates are the same. Five of the differences matter
    most, and a reader should look at them first. This is a summary; the full list is at the end.

    - **Block definition 3.** Two readings that the first text left open are written down (changes
      7 and 8). Either can decide which block a session falls in.
    - **The printed limits and the facts of each half** (changes 13 to 17). One limit was false and
      one had no count behind it.
    - **Two failure reports** are specified more fully: a month label outside the six (change 10)
      and the note for a missed date (change 21). The numbers printed with a result are unchanged.
    - **The order of work** is rewritten around code that already exists (change 22).
    - **Privacy.** One more leftover is accepted and stated: printed numbers can show the size of a
      block that carries no weight (changes 30, 38 and 39).

    Every difference between the two texts is listed as old words and new words in "Changes from
    the first registration" at the end. The code was built under the first text and is reused;
    "Order of work" says how.

Why: A new registration has to say what it replaces and why.

### Change 2: Read this first, item 4

Old words:

       About 73% of the sessions sit at 0% or at 100%.

New words:

       About 70% of the 855 sessions sit at 0% or at 100% (307 of 423 in the first half, 291 of
       432 in the second).

Why: 73% is the first half alone. The sentence spoke of "the sessions".

### Change 3: The two numbers per session, second measure

Old words:

    exactly (it can end in .5). The tool defines it with at least 10 such responses; every
      eligible Codex session has it.

New words:

    exactly (it can end in .5). The tool defines it with at least 10 such responses; every
      eligible Codex session has it. The extractor checks this: it stops and writes nothing if an
      eligible session has fewer than 10. It did not stop.

Why: The first text stated this without a check. The check now exists and has run.

### Change 4: Why there is no test, the break-date case

Old words:

    that is the point of those cases. Rates for all cases are in the round 3 review. The break-date
    case was coded with a fixed direction in both numbers, so it is not centred on zero; it carried
    no weight in the decision.

New words:

    that is the point of those cases. Rates for all cases are in the round 3 review. The break-date
    case was coded with a fixed direction in both numbers, so it is not centred on zero. As coded,
    both candidate tests passed it (0.050 and 0.042 at 1,000 data sets). With the direction drawn
    per number, as the review recommends, the repository-blocked test reads 0.070 and the
    month-blocked test 0.057. Either way the outcome was decided by other cases.

Why: "It carried no weight" did not fit a rule that requires every applicable case. What
happened is that both candidates passed it as coded, and the outcome came from other cases. The
re-coded figures are in the round 3 reviewer's results.

### Change 5: Why there is no test, the sign flip

Old words:

    - Flipping the sign of each repository's number repairs that: 0.045 to 0.053 over those seven
      cases (the same three implementations), and at most 0.056 over ten further cases (one
      implementation, 1,000 data sets each).

New words:

    - Flipping the sign of each repository's number repairs that: 0.045 to 0.053 over the seven
      null cases of the round 2 brief, which include the three just named (the same three
      implementations), and at most 0.056 over ten further cases that the reviewer added (section 4
      of the round 2 review; one implementation, 1,000 data sets each).

Why: "Those seven cases" pointed at a bullet that names three. The seven are the round 2
brief's null cases; the ten are the reviewer's own.

### Change 6: What will be computed, rho_b

Old words:

    vectors. The short form `1 - 6 * sum(d^2) / (n^3 - n)` is not used; it is wrong under ties,
      and ties are the normal case here. The sums inside `rho_b` are made in exact rational

New words:

    vectors. The short form `1 - 6 * sum(d^2) / (n^3 - n)` is not used; it is wrong under ties,
      and tied values are common here: most sessions sit at 0% or at 100%. The sums inside
      `rho_b` are made in exact rational

Why: "The normal case" had no count behind it. The endpoint counts do.

### Change 7: Block definition 3, the model name

Old words:

       - A session's model name is the most frequent model name among its main-thread responses
         with a known reasoning count; a tie goes to the name that sorts first as a string. A
         session with no model name takes the name `unknown`, a name like any other.

New words:

       - A session's model name is the most frequent model name among its main-thread responses
         with a known reasoning count. A response that carries no model name gives no vote. A tie
         goes to the name that sorts first as a string. A session in which no counted response
         carries a model name takes the name `unknown`, a name like any other.

Why: The first text did not say what a response without a name does. A missing field is not a
model: if it voted, a session could be called `unknown` although every named response agrees on
one model. This can decide which block a session falls in. It is also the reading the code
built under the first text already uses, and the private signal table was written with it; the
text is written to that reading, not the other way round.

### Change 8: Block definition 3, the sort inside a group

Old words:

         by the time of the session's first main-thread response (a session without one sorts after
         those with one), then by the transcript path as written in the pool manifest, which is
         unique; all ascending. Positions 1 to `floor(n/3)` are the low third, positions up to

New words:

         by the earliest timestamp among the session's main-thread responses, counted or not (a
         session without one sorts after those with one), then by the transcript path as written in
         the pool manifest, which is unique; all ascending. Positions 1 to `floor(n/3)` are the
         low third, positions up to

Why: "First" could mean first in the file or earliest in time, and among all main-thread
responses or only the counted ones. A transcript need not be in time order, so the earliest
timestamp is the reading that does not depend on file layout. This can decide which third a
session falls in when two sessions of a group have the same length. It is also the reading the
code built under the first text already uses, and the private signal table was written with it.

### Change 9: Without the repositories that share an identified user

Old words:

    otherwise exactly `not formed`. This removes identified sharing only. 168 of the 423 sessions
      carry no user id, so it is not a protection against unidentified sharing.

New words:

    otherwise exactly `not formed`. This removes identified sharing only. 168 of the 423 sessions
      of the first half and 101 of the 432 of the second carry no user id, so it is not a
      protection against unidentified sharing.

Why: The number is printed for both halves; the sentence gave the first half's count only.

### Change 10: Printed as checks

Old words:

    measure of exactly 0; the six month counts. Also printed: how many sessions took the month
    label `unknown` and how many the model name `unknown`.

New words:

    measure of exactly 0; the six month counts. Also printed: how many sessions took the month
    label `unknown` and how many the model name `unknown`. If stage 1 finds a month label other
    than the six, it is printed as one more check row with the registered figure 0, so it reads
    "different".

Why: The six registered counts add up to all sessions of a half, so another label can only
appear on a page that already says "not an answer". Without the extra row that page would not
show where the sessions went.

### Change 11: Formats

Old words:

    **Formats.** `rho_bar`: sign and three decimals (`format(x, "+.3f")`). The leave-one-out range
    and the number without shared users: sign and two decimals. Shares of weight: whole percent.
    Counts: integers.

New words:

    **Formats.** `rho_bar`: sign and three decimals (`format(x, "+.3f")`). The leave-one-out range
    and the number without shared users: sign and two decimals (`format(x, "+.2f")`). Shares of
    weight: whole percent (`format(100 * share, ".0f")`, which sends an exact half to the even
    digit). Counts: integers.

Why: The first text gave the code form for one of the three formats only, and did not say how
an exact half rounds.

### Change 12: The note under the yardstick table

Old words:

    "AR(1) 0.6" means each session's value leans on the one before it with weight 0.6. The last
    three rows are not applicable null cases of the rule. The last one is a shared cause, not a
    session-level link: one dated change that affects both records puts the number near +0.09. The
    row above it has a coding fault found in review (the break had a fixed direction in both
    numbers); it is kept because it was measured.

New words:

    "AR(1) 0.6" means each session's value leans on the one before it with weight 0.6. The rule
    applies to nine null cases of round 3. The first row is the round 2 run of one of them
    (independent sessions). The third row is a round 2 case that is not among the nine. The eighth
    and the tenth rows are round 3 cases outside the nine. The tenth is a shared cause, not a
    session-level link: one dated change that affects both records puts the number near +0.09.
    The ninth row is one of the nine, but it has a coding fault found in review (the break had a
    fixed direction in both numbers); it is kept because it was measured.

Why: The first text called the break-date row not applicable here and applicable in "Why there
is no test". The rule file lists it as applicable. The table itself is unchanged.

### Change 13: General limit 2

Old words:

    2. Most sessions sit at an outcome endpoint. Inside many repositories the outcome takes few
       distinct values, and ties carry much of the weight.

New words:

    2. Most sessions sit at an outcome endpoint (see the facts of each half), so many sessions
       share the same outcome value.

Why: No count stands behind "inside many repositories" or "much of the weight". The new
sentence says only what the endpoint counts show.

### Change 14: General limit 3 (the sentence that ended the first registration)

Old words:

    3. Many sessions carry no user id, and no repository shows two identified users. Repository and
       person cannot be told apart.

New words:

    3. Many sessions carry no user id (see the facts of each half). Blocking by repository does
       not separate differences between people from the number.

Why: "No repository shows two identified users" is false for the second half. The count is now
a fact of each half, and the general limit says only what holds for both.

### Change 15: General limit 9

Old words:

    9. Each half's separate counts were inspected before this text was written (next section). The
       block definitions, the floors and the sentence were chosen knowing them.

New words:

    9. Each half's separate counts were inspected before the first registration was written, and
       more signal-side counts were made before this one (next section). The block definitions,
       the floors and the sentence were chosen knowing the first set. After the second set, two
       readings inside the third block definition were written down; nothing else in them was
       changed.

Why: More was counted between the two texts. The limit has to say so.

### Change 16: Facts of the first reported half

Old words:

    - 168 of the 423 sessions carry no user id. 11 repositories mix sessions with and without one
      and hold about seven tenths of the possible weight; 4 repositories have no identified user.

New words:

    - 168 of the 423 sessions carry no user id. 11 repositories mix sessions with and without one
      and hold about seven tenths of the possible weight (whether the four largest repositories
      are among these 11 was not counted); 4 repositories have no identified user.
    - No repository shows two or more identified user ids: 29 show one and 4 show none.

Why: The user structure is now stated per half.

### Change 17: Facts of the second reported half

Old words:

    - 101 of the 432 sessions carry no user id.
    - The 7 shared user ids hold 80 of the 432 sessions, in 8 repositories.

New words:

    - 101 of the 432 sessions carry no user id.
    - Some of the 32 repositories show two or more identified user ids.
    - The 7 shared user ids hold 80 of the 432 sessions, in 8 repositories.

Why: This is what the first text's limit 3 got wrong. The number of such repositories is not
printed: beside the other printed counts it would bound the number of user ids in one
repository.

### Change 18: What was looked at, the heading and the first paragraph

Old words:

    ## What was looked at before writing this

    Counts only. Two programs produced them: one reads transcripts and knows no outcome, the other
    reads the tables and knows no signal value.

New words:

    ## What was looked at before writing this

    Counts only, in two rounds. "No pairing" does not mean "no data inspected": everything below
    was seen before this text was written.

    ### Before the first registration

    Two programs produced these counts: one reads transcripts and knows no outcome, the other reads
    the tables and knows no signal value.

Why: There are now two rounds of counts, and the reader should see which came when.

### Change 19: What was looked at, the second half's list

Old words:

    - Second half, the same separate counts: 351 distinct values of the first measure, 18 sessions
      at exactly 0, quartiles about 0.07, 0.20 and 0.34; outcome 107 at 0%, 184 at 100%, 141
      between; 27 repositories with at least 2 sessions, 25 with at least 3, 22 with at least 5; by
      month 84, 116, 80, 40, 72, 40; 331 sessions with a user id, 35 distinct. Its sessions per
      repository and month were not counted.
    - The design round and two rounds of simulation on synthetic data.

New words:

    - Second half, most of the same separate counts: 351 distinct values of the first measure, 18
      sessions at exactly 0, quartiles about 0.07, 0.20 and 0.34; outcome 107 at 0%, 184 at 100%,
      141 between, 141 distinct values, none missing; 27 repositories with at least 2 sessions, 25
      with at least 3, 22 with at least 5; by month 84, 116, 80, 40, 72, 40; 331 sessions with a
      user id, 35 distinct. Its second measure's counts were printed and are not quoted here. Its
      sessions per repository and month were not counted before the first registration.
    - The facts of each half as the limits print them: the share of possible weight in the four
      largest repositories, the sessions without a user id, the first half's mixed repositories
      and its repositories with no identified user, and the sessions and repositories of the 7
      shared user ids.
    - Printed by the same two programs and left out of the first text's list: in neither half does
      any session have a first measure of exactly 1; how many repositories with at least 3
      sessions show at least 2 distinct outcome values (all of them in the first half, most in the
      second); no outcome value lies outside 0 to 100; and how many sessions sit at each number's
      most common value. The same counts were printed for the Claude Code
      sessions, which are not analysed.
    - The design round and two rounds of simulation on synthetic data. Two lines of the round 2
      brief were assumptions and not counts: a median session length of 60, and "1 to 3 model
      names per repository".

Why: "The same separate counts" was not true: the list differs. Some printed counts and the
facts of each half were missing from the list, and two assumptions of a brief could be taken
for counts.

### Change 20: What was looked at, what had not been counted

Old words:

    Not counted before this text: how many distinct model names a repository shows, and the weight
    of the third block definition. Both are counted from the signal side alone, before any pairing,
    and written into the implementation record with the recount of the distinct user ids. They
    change nothing in this text.

New words:

    ### Between the two registrations (19 Nov 2026)

    All from the signal side alone, or from one side at a time. No program read a signal value and
    an outcome value of the same session.

    - **The two private tables were written**, each by a program that knows one side, at the code
      commit named in "Files". `signal.tsv`: 855 rows. The signal extractor read the 1,444 Codex
      transcripts and printed: every file present, 589 not eligible, no reader failure, 855
      written. `outcome.tsv`: 4,594 rows, one per pool session. The outcome extractor read two
      columns of the dataset's sessions table (the transcript path and `agent_percentage`; 17,968
      rows) and printed: 4,594 manifest paths, each found once, none without a value.
    - **The check figures and the user-id counts were recounted** from `signal.tsv` and are the
      same for both halves: sessions, repositories, sessions at exactly 0, the six month counts,
      sessions with a user id, distinct user ids, user ids in both halves.
    - **Model names per repository.** First half: 25 repositories show one name, 5 show two, 3 show
      three or more. Second half: 23, 8 and 1. The name `unknown` counts as a name. 6 sessions of
      the first half and none of the second take the name `unknown`. No session of either half
      takes the month label `unknown`.
    - **Possible weight before any outcome is read**: the sum of `n_b - 1` over blocks of at least
      2 sessions, with the number of repositories holding such a block. Repository blocks: 390
      units in 24 repositories (first half) and 400 in 27 (second). Repository-and-month blocks: 376
      in 24 and 377 in 26; the second half's cells were counted here for the first time.
      Repository, model-name and session-length blocks: 321 in 16 and 325 in 24. These are upper
      bounds on `W` and `m`. The two repository figures follow from counts made before the first
      registration.
    - **User ids per repository**, as now printed in the facts of each half. The orchestrating
      agent counted them with a short script after the consultant's finding, and the audit below
      counted them again.
    - **An audit of the first text.** One agent listed every factual sentence of it. Two agents
      wrote separate count programs for the 59 sentences that can be recounted from `signal.tsv`,
      tested on made-up tables. Both programs give the same counts; 58 match the first text and
      one does not (its limit 3). Among the 58 are the shares behind "a little over three fifths",
      "about seven tenths" and "a small share"; they are as the first text says, and the exact
      weights are not printed. 269 of the 855 sessions carry no user id.
    - **Computed, seen by the orchestrating agent in private output, and not published**, because
      they would break a disclosure rule: the possible weight restricted to blocks where a measure
      is not constant (beside the figures above it would isolate single blocks); the exact weights
      behind the shares in the facts of each half; how many repositories of the second half show
      two or more identified user ids, one, or none; and the largest number of user ids in one
      repository.
    - **On the outcome side nothing was counted per half again.** The outcome figures in this text
      come from the count program that ran before the first registration. The only new outcome-side
      output is the outcome extractor's line above.
    - **The code was built and compared** with a second implementation on simulated data ("Order of
      work", step 2).

    None of these counts changed the question, the population, the measures, the floors, the
    printed numbers or the headline sentence. In the block definitions, two readings inside the
    third were written down afterwards (changes 7 and 8); nothing else in them was changed.

Why: The first text promised these counts for its implementation record. They exist now, with
others, and a new registration has to list everything seen before it.

### Change 21: Order of work, the dates and the note for a missed date

Old words:

    Dates: steps 1 to 3 by 1 December 2026; steps 4 to 7 by 10 December 2026. If a step misses its
    date the study ends there. Then one note is published under `docs/results/` with exactly this
    content: the last step completed; any check counts and result file already committed; and the
    sentence "The study stopped at this step because its date passed; nothing was run after it."
    The stop rule of 14 December 2026 (decision D-23) stands either way.

    1. This text is approved by the maintainer, committed and pushed.

New words:

    Dates: steps 1 to 3 by 1 December 2026; steps 4 to 7 by 10 December 2026. These are the dates
    of the first registration; the replacement does not move them. If a step misses its date the
    study ends there. Then one note is published under `docs/results/` with exactly this content:
    the line "Last step completed: N."; the check counts already committed, as the page prints
    them; for a result file already committed, what the page carries for that half (the headline
    sentence, the printed numbers, the yardstick table, the limits and that half's facts); and the
    sentence "The study stopped at this step because its date passed; nothing was run after it."
    The stop rule of 14 December 2026 (decision D-23) stands either way.

    1. This text is approved by the maintainer, committed and pushed, together with the note that
       ends the first registration (beside this file, and as
       `docs/results/log-signals-study-first-registration-ended.md` on the code branch).

Why: "Any result file already committed" did not say what of it is printed. Numbers are never
printed without their limits, so the note carries what the page carries for that half.

### Change 22: Order of work, step 2

Old words:

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

New words:

    2. **The code exists and is reused.** `bench/logsignals/` was built on branch `v2/logsignals`
       under the first text, before this one was written (commit
       `c65ed3cee64f75394d0100e2bdb971ed697580c3`).
       It has two stages. Stage 1 prints only the check counts and pairs nothing. Stage 2 is the
       only code that ever puts a signal value beside an outcome value. A second agent, from the
       first text and a note on file formats alone, wrote its own implementation and the simulated
       data sets: one with a planted link, one with none, and the edge cases as four data sets (a
       constant block, a one-session block, a missing model name, a missing month, all outcomes at
       an endpoint, floors not met). Two requirements: the two implementations agree to within
       1e-9 on every number on all the sets; and on the planted set the repository-blocked
       `rho_bar` of the first measure is at least 0.10 above the same number on the set with none,
       with the sign that was planted. Both held on that commit: 660 values, none differing; the
       difference was 0.45 and 0.28 in the two simulated halves. The registered code refused the
       tables as the second agent wrote them, because their paths had another form. The comparison
       ran on copies with the paths renamed in the same string order, and a control shows that the
       rename moved no number. The hostile-input and canary tests passed before the extractors
       opened any real file. No agent has network access.

       **Under this text:** the code may change only where this text differs from the first (the
       fixed sentences that the page prints, and the comments and tests that quote them) or where
       the implementation record names a fault. After any change, the tests run again and the
       comparison runs again on the same simulated sets against the same second implementation.
       No code changes after the implementation record of step 3 is pushed. One correction of
       `analyze.py` is allowed. It was not used under the first text, and it is the same one
       allowance, not a new one. If either requirement fails a second time, no run happens, and
       that is published as the result. The second implementation is never run on the real
       tables.

Why: The first text said the code would be built from it. The code now exists, built under the
first text. The requirements are the same; what is new is the check after a change.

### Change 23: Order of work, step 3

Old words:

    3. An implementation record is committed and pushed: the digests of the code, the tests and the
       simulation files, the signal-side counts named above, and any correction to this text.

New words:

    3. An implementation record is committed and pushed: the digests of the code, the tests and the
       simulation files, the digests of the two private tables, a list of every place where the
       code had to choose a reading of this text, and any correction to this text. No reading may
       change an item that cannot be corrected.

Why: The signal-side counts are now in this text. The record instead names the tables and the
readings.

### Change 24: Order of work, step 4

Old words:

       differs from the figure this text fixes, stage 2 does not run: the page says "not an
       answer", prints the check counts, and the study ends.

New words:

       differs from the figure this text fixes, stage 2 does not run: the page says "not an
       answer", prints the check counts and no other number computed from the data, and the study
       ends.

Why: States what else that page may carry: nothing computed from the data.

### Change 25: Order of work, step 5

Old words:

       run's numbers are the ones printed, and no third run happens. The result file is committed.
       It records the registration commit, the implementation-record commit, the SHA-256 of
       `analyze.py` as it ran and the start time.

New words:

       run's numbers are the ones printed, and no third run happens. The result file is committed.
       It records the registration commit, the implementation-record commit, the SHA-256 of
       `analyze.py` as it ran, the SHA-256 of the two private tables and the start time. The start
       time is taken once, by the first of the two runs (UTC, whole seconds); the second run uses
       the same value. Every other byte of the two files is produced by each run on its own.

Why: Two runs that each stamp their own clock differ whenever the two readings differ. The
table digests say which tables a result came from.

### Change 26: Order of work, step 6

Old words:

       published. A committed test under `bench/logsignals/tests/` re-derives every figure on the
       page from the result file and fails on any difference. It cannot re-derive the result file

New words:

       published. A committed test at `tests/unit/logsignals/test_page_rederivation.py` re-derives
       every figure on the page from the result file and fails on any difference. It cannot
       re-derive the result file

Why: The repository's pinned test configuration collects tests under `tests/` only; a test
under `bench/` would not be collected.

### Change 27: Condition 1

Old words:

       matches the implementation record; and the recorded start time is later than the
       implementation record's commit date. Commit dates are what the committer wrote; the ancestry
       is not.

New words:

       matches the implementation record; and the recorded start time is later than the
       implementation record's commit date. Commit dates are what the committer wrote; the ancestry
       is not. The chain is checked on the records branch `v2/phase0`, where this text, the
       implementation record, the check counts and the result files are committed. The published
       folder on the code branch holds copies with the same bytes.

Why: The code branch does not descend from the records branch, so the chain can only hold on
the records branch. The first text did not say where it is checked.

### Change 28: Prediction

Old words:

    No prediction is registered. The maintainer was offered one sentence before the push and added
    none.

New words:

    No prediction is registered. The maintainer was offered one sentence before the push of the
    first text and added none. The offer is not made again for this text: more has been counted
    since.

Why: States which push the offer belonged to, and why it is not repeated.

### Change 29: Privacy, rule 1

Old words:

    1. No value of a single session. A quartile of a share is one session's own value, so shares
       are printed rounded to two decimals and never as the fraction of counts behind them.

New words:

    1. No value of a single session. A quartile of a share is one session's own value or lies
       between two, so shares are printed rounded to two decimals and never as the fraction of
       counts behind them.

Why: Most of the printed quartiles fall between two sessions' values.

### Change 30: Privacy, rule 2

Old words:

    2. No row per repository, no list of repository sizes, no exact weight of any single repository
       or of the largest few, no largest session count for one user.

New words:

    2. No row per repository, no list of repository sizes, no exact weight of any single repository
       or of the largest few, no largest session count for one user, no largest count of user ids
       for one repository. The one exception is the second residual of rule 5.

Why: The count of user ids per repository now exists, so the rule names it. The exception is
explained in change 39.

### Change 31: Changes to the approved plan

Old words:

    **The maintainer answered yes to all six on 19 Nov 2026.** The questions are kept as they were
    asked. Each needed a yes or a no. Items 1 to 3 hold the study up: a "no" to any of them means this text

New words:

    **The maintainer answered yes to all six on 19 Nov 2026, for the first text.**
    On 19 Nov 2026 the maintainer chose to replace the first text, and approved this text as a whole.
    The questions are kept as they were asked. Item 3 as built: the code is under
    `bench/logsignals/` and its tests under `tests/unit/logsignals/`. It uses the standard library;
    the signal extractor also calls the shipped `arci` reader, and the outcome extractor needs a
    library that reads the dataset's table format, which is not a dependency of the package and is
    used in a separate environment. The approval of this text is given knowing this. Each needed a
    yes or a no. Items 1 to 3 hold the study up: a "no" to any of them means this text

Why: The six answers were given for the first text. Item 3 said "standard library only"; what
was built needs two things more, stated here.

### Change 32: Changes to the approved plan, the closing paragraph

Old words:

    Told to the maintainer with the six questions, and done in the commit that adds this text: the
    change to the earlier `SIGNALS.md` entry described above, and the two rule files committed
    beside this text.

New words:

    Told to the maintainer with the six questions, and done in the commit that added the first
    text: the change to the earlier `SIGNALS.md` entry described above, and the two rule files
    committed beside this text.

Why: Those things were done with the first text's commit.

### Change 33: Files, the opening paragraph

Old words:

    SHA-256, in full. The first three files are private working data and stay outside the
    repository. The two rule files are committed beside this text. The simulation files are
    committed under `bench/logsignals/calibration/` with the implementation record.

New words:

    SHA-256, in full. The first three files are private working data and stay outside the
    repository. The two rule files are committed beside this text. The eleven simulation files are
    committed under `bench/logsignals/calibration/`. Six are committed as they are. Five (the round
    2 brief, the three round 2 scripts and the round 2 review) are committed as copies in which
    the session counts of single repositories are replaced by a marker `[WITHHELD: ...]`. Nothing
    else is withheld. The implementation record gives both digests of each. The digests in this
    table are the originals'.

Why: Four of the files hold the session counts of single repositories and one names the
largest, which Privacy rule 2 does not allow in print. The first text's sentence and its own
rule could not both be followed.

### Change 34: Files, the closing paragraph

Old words:

    share of the weight; the facts of the first half above have the real structure. The rule
    applied file carries its own dated correction of the counts it quotes.

New words:

    share of the weight; the facts of the first half above have the real structure. The rule
    applied file carries its own dated correction of the counts it quotes.

    Files that the first text's table does not list:

    | File | SHA-256 or commit |
    |---|---|
    | The first registration, `PREREGISTRATION.md` | `d47b0d2724c435ea7c23731471a517640c4a313cff53935dafa63de8224fc3e2` |
    | The code, branch `v2/logsignals` | commit `c65ed3cee64f75394d0100e2bdb971ed697580c3` |
    | `bench/logsignals/analyze.py` at that commit | `37aa10908e8497d179a2b7e4ae06d9b0b873bceeefd6ecc43e103dbce67fb268` |
    | `bench/logsignals/extract_signal.py` at that commit; it wrote `signal.tsv` | `30b874c0bbda6091a6b54794c7bef69741c32de1297fe50a457c975612fa52cb` |
    | `bench/logsignals/extract_outcome.py` at that commit; it wrote `outcome.tsv` | `ed6158ec92a69b6c6b819237cac58b8422fab064a30f99018c6ec65feb18f907` |
    | `bench/logsignals/signal_counts.py` at that commit | `94b284d8d141c9a37ab038695ca54788fcb8a58410f649464de6cf74022fa23f` |
    | Private table `signal.tsv`, written 19 Nov 2026 | `68f65e4efc6f6c37a8fbbc93a12917b6fc7ed394775892c9528136f409f9a2f6` |
    | Private table `outcome.tsv`, written 19 Nov 2026 | `0207c517088c4b83b67a8a89953ea01badfcfb269d528df9be1726a1677fd29d` |
    | Audit count program A (private) | `acf7280792bd370cd0f7f1af2097e3cea3443ab8c3abf78c08d45694a7c4d389` |
    | Audit count program B (private) | `78a7bda17fdfd154e007d03fbb8a86bd16d00cbc0c4ee1537db8367db163ced1` |
    | Private month table used by the round 3 scripts (made before the first registration and not in its table) | `3952cdfdaa23650787fd16cf5e27c9f4c465b70310d5f00a3a0ebebbe98a526b` |

    The same code commit holds, under `bench/logsignals/comparison/`, the second implementation,
    the program that writes the simulated sets, the digests of those sets, the expected outputs,
    the comparison program and its report; and under `bench/logsignals/calibration/` the simulation
    files. The month table has one row per repository of the first half (its session count and
    its count per month) and is not committed; it can be rebuilt from `signal.tsv`, and the
    implementation record says how.

    The code digests above are of the code as built under the first text. If step 2 changes the
    code, the implementation record gives the new commit and digests, and those are the ones
    condition 1 uses.

Why: A new registration lists what exists when it is written.

### Change 35: Who did what

Old words:

    simulation, review and blind tests. No person other than the maintainer read any of this before
    publication.

New words:

    simulation, review and blind tests. No person other than the maintainer read any of this before
    publication.

    The false sentence that ended the first registration was written by the orchestrating agent.
    Two review rounds and the consultant read it before that registration and did not catch it.
    The consultant caught it afterwards, while reviewing the implementation record. One reviewing
    agent, working on the same record at the same time without the consultant's answer, reported
    the same contradiction. The audit of the whole text was started because of that finding.

Why: Who made the error and who found it.

### Change 36: Why there is no test, the cells above the bar

Old words:

    exceeds the bar by more than ten times the sampling error for both tests. Some other cells
      exceed it by about two times that error. One implementer's own figures differ cell by cell

New words:

    exceeds the bar by more than ten times the sampling error for both tests. The other cells
      above the bar exceed it by about two to eight times that error. In the fourth row the
      month-blocked test equals the bar at 1,000 sets and is 0.066 at 2,000. One implementer's own
      figures differ cell by cell

Why: "About two times" fits two of the four cells; the other two exceed the bar by six to eight
times the error. The fourth row's month-blocked cell passes only by equalling the bar.

### Change 37: What was looked at, the earlier SIGNALS entry

Old words:

    In the commit that adds this text, that entry is changed to rounded shares. The earlier form
    stays in the commit history; that is stated in "Privacy".

New words:

    In the commit that added the first text, that entry was changed to rounded shares. The
    earlier form stays in the commit history; that is stated in "Privacy".

Why: That change was made with the first text's commit, not with this one.

### Change 38: Privacy, rule 4

Old words:

    4. No two printed numbers may let a reader isolate, by subtraction, a number for fewer than 10
       repositories. For that reason the number without shared users is printed alone, to two
       decimals, with no weight and no repository count beside it.

New words:

    4. No two printed numbers may let a reader isolate, by subtraction, a number for fewer than 10
       repositories, except the two residuals accepted in rule 5. For that reason the number
       without shared users is printed alone, to two decimals, with no weight and no repository
       count beside it.

Why: Rule 4 as written forbade what rule 5 accepts.

### Change 39: Privacy, rule 5

Old words:

    5. One residual is accepted and stated. Each end of the leave-one-out range leaves out one
       repository. A reader who knows that repository's weight and guesses which repository it is

New words:

    5. Two residuals are accepted and stated. The second one first, because it is new in this
       text. The result prints `m` and `W` for each block definition, and this text prints the
       possible weight of each ("What was looked at": 390 and 400 units for the repository blocks,
       and the figures for the other two definitions). The difference between a possible weight
       and the printed `W` is the summed size, less one each, of the blocks that carry no weight,
       and it tells a reader that their signal or their outcome is constant. When exactly one
       repository block carries no weight, the difference is that one repository's weight, and its
       session count is one more. That case is an exception to rules 2 and 4. The first text had
       the same residual for the repository blocks without stating it: 423 sessions, 33
       repositories and 24 with at least 2 sessions already give the 390. The first residual:
       each end of the leave-one-out range leaves out one repository. A reader who knows that
       repository's weight and guesses which repository it is

Why: A reviewer showed that the printed `m` and `W`, beside counts both texts print, can give
the size of a block that carries no weight. It cannot be removed without changing the printed
numbers, so it is stated, and rules 2 and 4 point to it.

### Change 40: this section

New. The first text has no such section.
