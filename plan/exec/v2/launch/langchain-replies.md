# Replies for the r/LangChain thread (drafts; the maintainer posts them)

Thread: https://www.reddit.com/r/LangChain/comments/1xtror1/i_put_create_agent_behind_a_faultinjecting/

Plain text on purpose: Reddit refused the formatted post body on 12 Nov.

State of the thread on 14 Nov 2026, 12:47 (from the maintainer's saved copy): the first
three replies (to u/Significant_Tune9219, u/ChemicalExcellent463 and the comment a moderator
later removed) were posted on 13 Nov, before v2.1.0. Two comments are unanswered, and one
side thread is open. The replies below are for those.

Every number below was recounted from the stored run 2 trials on 14 Nov by an agent that
did not use the write-ups, and the wording was reviewed by a second one
(`wf_d99c3c71-887`). Changes that review forced are listed at the end.

## A. To u/Significant_Tune9219, under "Thanks for rerunning it. With the gap at 10.8 against a 10 point margin, breaking the 4B failures down by error category might show..."

The breakdown points that way, with one limit: in run 2 both models had the error returned, so it shows where the 4B still failed, not what returning the error changed.

51 of the 52 4B failures are on the stock-note tasks. On those tasks the 4B passed:

- no injected fault: 34 of 40
- injected timeout: 38 of 40
- injected error, once: 30 of 40
- injected empty result: 7 of 40

The most common wrong step is the same in every row: the stock tool called first, with the order id as the product code. That happened in 108 of the 160 trials, and 40 of the 51 failures began that way. After that wrong first call the 4B passed:

- no injected fault, or injected timeout: 52 of 58
- injected error, once: 16 of 24
- injected empty result: 0 of 26

In 21 of those 26 it got "unknown SKU", looked the order up once, got the empty result, and stopped. The empty result went with failure even without the wrong first call: 7 of the other 14 trials in that row failed. Across all tasks under the empty result, the 12B looked the order up a second time in 120 of 120 trials; the 4B in 87 of 120.

So in this run a wrong first call on its own was usually followed by a pass, and a wrong first call plus an empty lookup never was. Caveats: I chose these cuts after seeing the data, they are all counted by hand from the stored trials, and it is one run.

Your earlier idea is in the tool now: since 2.1.0 the suite report prints, per model, the tool failures that were not injected, split by pass or fail.

## B. To u/ChemicalExcellent463, under "...saw the error. did the 4B clear your original PASS rule on the rerun?" (the reply below the second answer to them)

No. Same rule as run 1: a 10-point margin, at most 5 rounds, and at most a 2.5% chance each of a wrong PASS or a wrong BLOCK (under the independence assumptions the report prints). It ended INCONCLUSIVE: 12B passed 480 of 480, 4B passed 428 of 480.

The observed gap is 10.8 points, almost on the margin, which is where this test needs the most paired trials. Each of the two tests keeps a score that starts at 1 and has to reach 40 to decide. PASS ended at 0.02 and BLOCK at 0.49, so neither was close. I registered 5 rounds and did not extend the budget after seeing the result.

So the rerun does not show the 4B is within 10 points, and does not show it is outside. Run 1's BLOCK stands for run 1's set-up, where a wrong call ended the trial.

## C. Optional, to u/Ludynia_Keyko, under "with tool calling you also get the reverse where the fault fires twice on a retry loop and skews the latency numbers"

Fair point. In this suite each faulted condition declares one fault, on the first call to the lookup tool. A retry is a new call and runs without it, so the fault fires at most once per trial; you would have to declare a second fault on the second call to hit the retry too. The report counts injections and the trials where it fired, and each attempt gets its own start and finish record.

The gate report has no latency numbers; each trial is scored pass or fail. The only timing in my write-ups is a median seconds per trial for each model, and that includes any retry, so I have not solved the skew you describe.

## Already posted on 13 Nov (kept for the record)

- To u/Significant_Tune9219: the run 2 result and the three category counts. That reply says "89.2%, up from 72.9% in run 1" and "a tool error of its own making". The records were later reworded: the two runs differ in rounds and seeds, so the difference is not a measured effect, and the trace shows a tool failure with no injected fault, not its cause.
- To u/ChemicalExcellent463: what the 4B model answered when it skipped the lookup.
- To the comment a moderator removed: one vote for interrupts, no promise.

## What the 14 Nov review changed in the first draft of A, B and C

- A opened with "That is what the breakdown shows" and closed with "returning the error covers a single mistake and does nothing for a mistake plus an empty lookup". Both arms had the error returned, so the run cannot say what returning it changed. Reworded to describe the run.
- A said "The mistake is the same in every row". Only 40 of the 51 stock-note failures begin with the wrong first call (5 of 6, 1 of 2, 8 of 10, 26 of 33 by row). Reworded, and the error-once row (16 of 24) and the 7 of 14 line added so no row is left out.
- A said 2.1.0 prints the counts "in every report". It is in suite reports only (Markdown, HTML, JSON), not v1 reports, JUnit or the gate summary. The repeated link was dropped.
- B said "5% error bound". The records state 2.5% per direction, under assumptions; "evidence 0.02" had no scale, so the start value 1 is now stated.
- C said "it fires at most once per trial" as if general. True for one fault declared on one tool and one call; a user can declare more. C also said "I do not report latency at all"; the study write-ups give a median seconds per trial.
