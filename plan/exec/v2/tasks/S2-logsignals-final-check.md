# S2: one final count before the registration (proposed freeze, 19 Nov 2026, before the counts exist)

Decision D-23 and the spike brief `S1-logsignals-spike.md` are the authority. This file
fixes one more count-only check and the numbers that decide it. It was written after
Stage A and Stage B of the spike and before any transcript outside the 300-session sample
was opened. It produces no paired signal and outcome values and no estimate of an
association. The maintainer decides whether the study goes ahead in this form.

Data: SWE-chat version 2 (`SALT-NLP/SWE-chat` on Hugging Face, licence ODC-By; Baumann,
Padmakumar, Li, Yang, Yang and Koyejo, "SWE-chat: Real-World AI Coding Sessions in the
Wild").

## What the spike found (counts only)

- The spike report concludes that the four go tests of S1 hold by the letter. In a
  hash-chosen sample, Stage B found a shipped signal at the tool's own minimum count in 42
  of 102 complete sessions that have an attribution record with changed lines, in 31
  repositories (exact 95% interval 31.5% to 51.4%; the bar was 21.8%). That is Stage B's
  coverage, counted over all responses and both signals. It is not the coverage of the
  population retained below.
- The picture behind that number is narrower than the question:
  - The unchanged Claude Code reader returned no usable response for 231 of 260 sampled
    sessions (88.8%). A count of raw fields is consistent with the reader's requirement
    of an `effort` setting on the response: 233 of the 260 transcripts never record one.
  - The failed-edit signal, as the reader ships, is nearly empty: 387 file-edit results in
    the whole sample, 3 failed. It is too sparse in this sample to justify retaining it.
  - Claude Code records `thinking_tokens`, Codex records `reasoning_output_tokens`. These
    are different quantities.
  - The table's `created_at` is not shown to be the moment the attribution was computed:
    in 30 of the 63 sampled sessions with response times, responses continue after it.

## The narrower question (proposed; the maintainer decides)

Within each tool separately: does a session's recorded reasoning go with the share of
committed lines that the capture tool attributes to the agent?

- The failed-edit signal is dropped from this study. The reader is not changed.
- Claude Code and Codex are never pooled.
- All main-thread responses with a known reasoning count are retained across the whole
  session, including those after `created_at`; counts of 0 stay in. The study is a
  description of two records attached to the same session. It claims no order in time,
  no prediction and no cause.

## The population (fixed)

A session is in the *pool* if its agent is Claude Code or Codex, it has a transcript, it
is not flagged `compact_transcript_delta_only`, its attribution record uses metric version
2, and `total_lines_changed` is above 0. Stage A puts the pool at 4,594 sessions.

A pool session is *eligible* if the unchanged reader of its tool, called once on its
transcript, returns at least 20 main-thread responses with a known reasoning count. That
is the tool's own minimum for its reasoning measures.

The two measures are the tool's own, taken over the session's main-thread responses with
a known count. The first is the share with a count of 0; it is defined for every eligible
session. The second is the median of the counts above 0; the tool defines it only with at
least 10 such responses, so it is defined for a subset of the eligible sessions. Each
measure has its own *cohort*: the pool sessions where that measure is defined and the
outcome is present.

Repositories are split in two by the parity of the first hex digit of
`sha256("arci-logsignals-halves-2026-11-19:" + repo_id)`, with `repo_id` stripped of
surrounding white space and encoded as UTF-8: even is the discovery half, odd is the
confirmation half. The split is never rebalanced after the counts are seen. The
confirmation half stays disjoint by repository, but its marginal counts are inspected
here, and the registration says so.

## The two summaries (count only)

They are produced by two programs. The first reads transcripts and knows no outcome. It
writes its summary and, for each measure, a list of the transcript paths where that
measure is defined, with no value in it. The second reads the tables and those lists and
knows no signal value. So no paired signal and outcome values exist anywhere, and no
association is estimated. What does pass between them is availability: the outcome
summary is conditional on a measure being defined, which carries selection information.
That is accepted for this screen and is stated in the registration. The path lists are
private working data outside the repository; only aggregates are published.

1. Eligibility and the signal alone, by tool and by half: eligible sessions;
   repositories with at least 1, 2, 3 and 5 eligible sessions; the largest number of
   eligible sessions in one repository; eligible sessions by month; eligible sessions with
   a user id, distinct user ids, and the largest number of eligible sessions for one user
   id; for each measure, how many sessions have it defined, its quartiles, its number of
   distinct values and the share of sessions at its most common value.
2. The outcome alone, for each measure's cohort, by tool and by half: sessions at 0%, at
   100%, in between and missing; the number of distinct values and the number of sessions
   at the most common value; the number of repositories with at least 3 cohort sessions,
   and how many of those show at least 2 distinct outcome values.

## What decides it (fixed now)

- **G1, the original gate on the retained population:** at least 1,000 eligible sessions
  in at least 30 repositories, both tools together. Fails: no-go.
- **G2, per tool and per measure, in the confirmation half:** the measure's cohort holds
  at least 150 sessions, and at least 10 repositories with 3 or more cohort sessions each.
- **G3, per tool and per measure that passed G2, in the confirmation half:**
  - outcome, within the cohort: no single value holds more than 90% of the sessions, and
    at least 10 repositories with 3 or more cohort sessions show at least 2 distinct
    outcome values;
  - signal: over the sessions where the measure is defined, it takes at least 10 distinct
    values and no single value holds more than 50% of them.
  A measure that fails G2 or G3 for a tool is not analysed for that tool. A tool with no
  measure left is not analysed.
- These numbers are floors for feasibility: they reject sparse or nearly constant data.
  They are not a statement of statistical power.
- **No tool left: no-go.** One tool left: the study is about that tool only and says so in
  its title.

No second attempt follows a failure: no change to the reader, no other dataset, no other
outcome, no other minimum count, no other split. A no-go is written up as a short note
under `docs/results/`, and the reader's limit on transcripts without an `effort` setting
goes into the README's limits either way, in the same final pull request.

## Rules

Those of S1 hold unchanged: counts only, no transcript text or identifier in any output,
data outside the repository, no network for agents, the maintainer downloads, identical
output on a second run, hostile-input and canary tests before any real file is read.
