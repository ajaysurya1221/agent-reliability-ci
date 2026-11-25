# Result, benchmark Reply-0: fail. (a) met, (b) met, (c) missed, (d) not run

The registered rule was: all four criteria, or the product direction ends. Criterion (c) was
missed, so the direction "check a tool server's own failure replies" ends here, as decision
D-33 says. No code under `src/arci` was written for it.

## Read this first

A tool server answers a model's tool calls. Reply-0 asked: after a wrong call, does the reply
the server really sends let a model still finish the task, or would a reworded reply do
clearly better?

How a trial went. In the trials on the two reference servers (filesystem and git) the model's
opening tool call was scripted to be a wrong one. In the control the opening lookup was a
correct one and the harness blanked its result. One trial of each pair then showed the model
the reply as shipped (the candidate). The other showed a sentence that names the corrected call
(the baseline). The model also saw the question, the tool descriptions and the call history;
the missing-file questions named the folder. A fixed answer key graded the final answer, and
the instructions said to reply with the answer only, so a right answer wrapped in extra words
counts as a fail.

ARCI's released sequential rule read the pairs. BLOCK means the shipped reply is worse than the
sentence by more than ten percentage points on mean answer-key success over the kept tasks.
PASS establishes that it is not worse by more than that margin. CANNOT TELL means the cap was
reached without either.

What came out:

1. **The bare git header and the blanked control gave BLOCK on both models.** After git's
   `Commit history:` with nothing under it, the shipped reply scored 2 of 16 on the small model
   and 0 of 16 on the larger one, against 16 of 16 with the sentence.
2. **After the "no such file" error both models recovered the file.** On the small model the
   registered corrected read was made in all 120 trials of each arm. All 43 failed answers
   contained the right text with extra words: 29 with the shipped reply, 14 with the sentence.
   The answer-only scores were 91 of 120 and 106 of 120, and the rule could not tell. The
   larger model scored 80 of 80 trials in each arm.
3. **On git with the small model, a generic instruction did as well as the naming sentence.**
   "Check its arguments against the tool descriptions and make a corrected call" scored 80 of
   80, as did the sentence naming the call. This is one comparison on one model.

These are two small local models on one laptop. They say nothing about hosted models or real
agents. Spontaneous exposure was measured and was 0 of 16 trials in each of the six model and
cell combinations.

## Registration and order

- Registration and pinned inputs: commit `cd8f77a`; digest list: `3e54310`; descriptor digests,
  after the clean rows and before any deciding run: `394d396`. All pushed to `v2/phase0` before
  the step they precede. The launcher verified the pushed inputs when it admitted a run.
  Before each trial request it checked the active claim, the registration and descriptor
  digests, and the scheduled identity.
- Models: "4B" is `qwen3.5:4b-mlx-ctx32k`, "12B" is `gemma4:12b-mlx-ctx32k`, served by Ollama
  0.32.14, temperature 0.7, reasoning off, context 32768. Digests are in the registration.
- All trials finished on 25 November 2026 local time, the first of the three registered days.
  One live suite at a time.
- Order as registered: wiring check, clean rows, unscripted rows, control on 4B, F1 on 4B,
  F1 on 12B, then G1 and F2 on both models, then the shown-only rows (F0 and G2 on 4B, the
  control on 12B, one generic follow-up).

## Criteria

Every required BLOCK must be statistical and satisfy the reading conditions R1 to R4.

| Criterion | Outcome | Evidence |
|---|---|---|
| (a) Control C0 gives BLOCK on 4B | met | BLOCK at round 2; sentence 16/16, blanked result 0/16 |
| (b) A BLOCK among G1, F2, F1 on 4B or 12B | met | G1 on 4B and G1 on 12B |
| (c) A BLOCK on F1 | missed | F1 on 4B CANNOT TELL; F1 on 12B PASS |
| (d) That BLOCK again with the reply edited in the server, on held-out tasks | not run | no qualifying F1 |

Why F1 alone could meet (c): both rule-based checkers returned a pass on F1 and one of them
had assessed its `ENOENT` text. On G1 and F2 that checker excuses the reply because the server
marks an unknown value as a success, and flags it when the excuse is removed. So a BLOCK on
G1 or F2 can meet (b) and cannot meet (c).

## Main runs

"Sentence" is the baseline arm and "reply" is the candidate arm, each as passes out of trials.
Minus counts pairs where the sentence passed and the reply failed; plus is the reverse. No pair
errored and no trial hit the 120-second limit in any run. Every run below is "verified": the
audit is clean, the two independent counts agree, and `arci gate` printed
`stored decision: MATCH`.

| Run | Cell and model | Verdict | Round | Sentence | Reply | Minus / zero / plus |
|---|---|---|---:|---:|---:|---:|
| `reply0-main-4B-C0` | control, 4B | BLOCK | 2 | 16/16 | 0/16 | 16 / 0 / 0 |
| `reply0-main-4B-F1` | file not found, 4B | CANNOT TELL | 15 | 106/120 | 91/120 | 18 / 99 / 3 |
| `reply0-main-12B-F1` | file not found, 12B | PASS | 10 | 80/80 | 80/80 | 0 / 80 / 0 |
| `reply0-main-4B-G1` | git log, bad date, 4B | BLOCK | 2 | 16/16 | 2/16 | 14 / 2 / 0 |
| `reply0-main-12B-G1` | git log, bad date, 12B | BLOCK | 2 | 16/16 | 0/16 | 16 / 0 / 0 |
| `reply0-main-4B-F2` | file search, no wildcard, 4B | CANNOT TELL | 15 | 113/120 | 102/120 | 16 / 99 / 5 |
| `reply0-main-12B-F2` | file search, no wildcard, 12B | PASS | 10 | 80/80 | 80/80 | 0 / 80 / 0 |

Shown only, not part of any criterion:

| Run | Cell and model | Verdict | Round | Sentence | Reply | Minus / zero / plus |
|---|---|---|---:|---:|---:|---:|
| `reply0-main-4B-F0` | F0, 4B (7 kept tasks) | CANNOT TELL | 18 | 90/126 | 89/126 | 18 / 91 / 17 |
| `reply0-main-4B-G2` | G2, 4B | PASS | 10 | 80/80 | 80/80 | 0 / 80 / 0 |
| `reply0-main-12B-C0` | control, 12B | BLOCK | 3 | 24/24 | 6/24 | 18 / 6 / 0 |
| `reply0-generic-4B-G1` | git log, 4B: naming sentence against generic sentence | PASS | 10 | 80/80 | 80/80 | 0 / 80 / 0 |

Notes on single runs:

- F1 on 4B. Both arms made the registered corrected read in 120 of 120 trials. The score gap
  is in the form of the answer, not in finding the file: every one of the 43 failed answers
  held the right text plus extra words (for example "The third item on the to-do list is: ...").
  The gap sits in two of the eight tasks, `F1-n1` (sentence 8 of 15, reply 2 of 15) and `F1-n7`
  (9 against 2). The final BLOCK wealth was 0.92 against a threshold of 40.
- F2 on 4B. Of the 25 failed answers, 23 held the right text plus extra words (7 with the
  sentence, 16 with the shipped `No matches found` reply); 2 with the shipped reply did not.
  Most of the gap is one task, `F2-n1` (12 against 6 of 15).
- F0 on 4B. 72 of the 73 failed answers held the right text plus extra words, 36 in each arm.
- G1. These failures are of the other kind: with the bare header the model almost never
  called `git_log` again (2 of 16 trials on 4B, 0 of 16 on 12B) and answered from the empty
  history.
- Generic follow-up. The registration names one follow-up. The pinned note in
  `harness/DEVIATIONS.md` fixes its target: the earliest statistical BLOCK in the order F1 on
  4B, F1 on 12B, G1 on 4B, F2 on 4B, G1 on 12B, F2 on 12B. Neither F1 run gave BLOCK, so the
  target was G1 on 4B. The generic sentence is "The previous tool call did not return a usable
  result. Check its arguments against the tool descriptions and make a corrected call." All 80
  generic trials called `git_log` again and passed, 64 of them with a registered corrected
  call. As registered, this PASS limits what the G1 BLOCK can be credited to: the comparison
  "bare header against a sentence", not "naming the call".

## Clean rows, unscripted rows, wiring

- Wiring check: both models accepted a scripted call with non-empty tool text and one with
  empty tool text, so the control's candidate text stayed the empty string.
- Clean rows (first call scripted to the right one, no fault): 256 trials. Tasks dropped
  because neither trial passed: on 4B `F0-n7`, the held-out `F1-d3` and `F1-d4`, and the
  held-out `F2-d4` and `F2-d8`. Nothing was dropped on 12B. Average speed per model and cell
  was 1.1 to 2.3 seconds per trial on 4B and 1.3 to 3.9 on 12B.
- Unscripted rows (no scripted call, no sentence): 96 trials. No trial showed a reply fitting
  a cell's rule: 0/16 for each of 4B G1, 4B F2, 4B F1, 12B G1, 12B F2 and 12B F1. Three
  unscripted trials on 4B still failed the answer key (`F1-n1`, `F2-n4`, `G1-g6`). These
  fixtures do not establish how often such calls happen in real use.

## Blind recount

Reported by the operator: a separate agent was given the raw trial records, ledgers and stored
decisions, and neither this write-up nor the two harness counts. It wrote its own counter. For
all ten main suites and the generic suite it found the same trials, passes per arm, pair
signs, stopping round and verdict as the tables above. It found 0 of 96 exposed unscripted
trials and the same five dropped clean tasks. It also showed that `F1-n1` and `F1-n7`, the two
tasks carrying the F1 gap on 4B, each passed one of their two clean trials. The consultant,
reviewing this page, regraded all 1,868 trials and found no mismatch.

## Every scheduled slot

- Run and complete: 2 wiring checks, 128 clean pairs, 48 unscripted pairs, 10 main suites and
  1 generic suite: 1,868 trials in all (256 clean, 96 unscripted, 1,356 main, 160 generic).
- Not run, by the registered rules: both confirmation slots (no qualifying F1) and the five
  other generic slots (one follow-up is registered and G1 on 4B was the one selected).
- Interrupted or errored: none. Reported by the operator: one launch of the unscripted rows
  was refused by the launcher before any request, because the clean rows of the other model
  were not yet complete. No claim was taken. The rows were then started in the right order.
- Departures from the registration in the harness are listed in `harness/DEVIATIONS.md`. Its
  checks are built to catch faults of the harness, the servers, the transport and the model
  server. They are not built to catch an operator who rewrites stored evidence.

## Predictions against outcomes

| | Consultant (Astra) | Orchestrator (Claude) | Outcome |
|---|---|---|---|
| (a) | 75% a valid BLOCK | BLOCK | BLOCK |
| (b) | 70% given (a), G1 likeliest | met, by G1 on 4B | met, by G1 on both models |
| (c) | 25% given (a) | not met, PASS or CANNOT TELL on both | not met: CANNOT TELL and PASS |
| (d) | most likely not run; 55% a confirming BLOCK if reached | not run | not run |
| Overall | about 10% pass | fail | fail |

The maintainer supplied no prediction before registration.

## What this does and does not show

- It shows, for two small local models and these fixtures: the bare git header and the blanked
  control gave BLOCK on both models. The shipped `No matches found` reply scored 102 of 120 on
  4B and 80 of 80 on 12B. After `ENOENT` both models re-read the right file. On git with 4B,
  the generic instruction to check the arguments and call again scored 80 of 80, as did the
  naming sentence.
- It does not show that a maintainer of either server should change anything. BLOCK here does
  not mean "ship this sentence". No maintainer asked for this and no issue was filed.
- It does not show anything about hosted models, larger models, other servers, or how often
  these wrong calls happen in real use.
- Not claimed as new: that the wording of a failure reply changes recovery, or that naming the
  call helps (arXiv 2609.35381; 2609.00072, 2611.11581, 2610.10062, 2610.32555); fault
  proxies, an empty-result test, grading without a judge model, or provoking real servers
  (tool-eval-bench, AgentCheck, MCP-Injector, mcp-fault-bench, `mcp-linter`, `mcp-lint`).
- The F1 result on 4B is a miss under the registered rule. As a design calculation in the
  registration (independent arms, the same rates for every task and round, no errors), a true
  90% against 70% ends in CANNOT TELL about three times in four. So this run cannot tell a
  small real gap from none, and the gap it did see is in answer form.

## What happens next

D-33 names the fallback: Board-0, the recovery board. No product code follows from Reply-0.
