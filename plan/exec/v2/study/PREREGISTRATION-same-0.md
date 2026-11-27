# Same-0: an unchanged agent compared with itself (registration of a count on published records)

Registered 28 November 2026, before any number below was computed. This is not a new run. It
is a count on trial records that are already published. Operator and orchestrator: an AI agent
(Claude) working for the maintainer. Consultant: a second AI model (GPT-6.2 Astra through
Codex), read-only; the primary question and the block rule are its design.

## The question

Size-0's 14 runs are self-comparisons: both sides of every pair are the same model, prompt,
tools and budgets, and a pair shares its scenario seed. Nothing differs between the two sides
except the model's own sampling. The released tool labels the sides "baseline" and "candidate".

**After three repeats of the eight order ids on each side, how often did the side labelled
"candidate" score ten percentage points or more below the side labelled "baseline", although
the two are identical?**

## Records

- Size-0: `size0-evidence/claims.zip`, SHA-256
  `fcb0bb543a83392927558f850e6e70f976dcced81d80347a847841a66a7516be`, the sealed `trials.jsonl`
  of each of the 14 runs. Result page: [RESULT-size-0.md](RESULT-size-0.md).
- Board-0 (secondary count only): `board0-evidence.zip`, SHA-256
  `35f70d9b3a787a1e429fd623dd550b80d77b99da60ea7ce2291d74d9204e5340`, the `trials.jsonl` of the
  ten clean runs, in which every task was run twice with nothing different.

A trial's score is its stored final-state outcome (`PASS` or not). A round is the number at
the start of the trial id. A round of a Size-0 run holds eight order ids on each side.

## What was already known when this was written

The orchestrator had read the two result pages and the registered reports. That includes each
run's total trials and total passes, the passes per order id pooled over both sides and all
rounds, the stopping rounds, and the 14 stored verdicts of the released rule (7 PASS,
7 INCONCLUSIVE, 0 BLOCK). No count per side, per round or per block had been computed or seen,
and no count of differing clean pairs in Board-0 beyond the per-task pass totals (0, 1 or 2 of
2) printed in the blind recount, from which the secondary count below can already be derived by
hand. That count is therefore a restatement, not a test.

## Primary count

For each of the 14 runs take rounds 1, 2 and 3 (every run reached at least round 6): 24 trials
on each side. The run "shows a drop" if candidate passes are 3 or more below baseline passes
(a difference of 12.5 points or more; 2 of 24 is 8.3 points). It "shows a gain" if they are 3
or more above. Each run has one vote. Reported: X of 14 show a drop, Y of 14 show a gain, the
rest neither, with the two pass counts of every run.

**The headline sentence, fixed now, whatever X and Y are:** "With identical configurations, X of
14 three-round comparisons showed the second copy ten points or more behind the first, and Y of
14 showed it ten points or more ahead."

## Secondary counts (descriptive)

Within each run, starting at round 1, consecutive blocks that do not overlap; an incomplete
last block is dropped. By the stopping rounds this gives 135 single rounds, 41 three-round
blocks and 26 five-round blocks. For each width: the number of blocks in which the candidate
side has fewer passes, the same, or more; and the number in which the difference is ten points
or more in either direction (1 of 8, 3 of 24, 4 of 40). Each is also split into clean and null
runs and by model. One fewer pass of eight is already 12.5 points, so the single-round count is
a description of how one run of the task list looks, not a claim about how anyone decides.

Board-0's clean rows: of the 160 task-pairs (10 runs, 16 tasks, two trials each), the number
whose two outcomes differ, by model.

Beside these, the stored verdicts of the released rule on the same 14 runs are printed as they
are: 7 PASS, 7 INCONCLUSIVE, 0 BLOCK. They are not compared with the counts above as "errors
avoided": the budgets differ (a verdict used up to 80 pairs), a score difference is not a
release decision, PASS concerns the allowed loss, and half the runs ended undecided.

## Checks

Two agents count independently from the unpacked records, each with code of its own and
without seeing the other's result or any write-up. The page is written only if their counts
are equal; a difference is investigated and reported.

## Predictions, written before any count

- Orchestrator: X = 2 (plausibly 0 to 4), Y = 2 (0 to 4). The two Gemma runs, the two 4B null
  runs and the two 2B null runs can hardly move, because their pass rates are at or near 0% or
  100%; the drops, if any, come from the 9B runs and the clean 4B and 2B runs. Single rounds:
  the candidate side has fewer passes in about 25% of the 135 rounds.
- Consultant: none given.
- Maintainer: none.

## Not claimed

- That run-to-run variation of agents is new. It is published (for example arXiv 2610.10062,
  which reports the same end state in 63.3% of repeated fault-free runs, and tau-bench's
  pass^k measure).
- A rate for any other agent, model, task or temperature. These are four local models at
  temperature 0.7 with no sampling seed, on one task sentence in eight variants, on one laptop.
  Tasks repeat across rounds and blocks, so the blocks are not independent.
- That developers decide releases from three runs, or from any of the widths counted here.
- That the released rule "made no mistakes". See the note on the stored verdicts above.
- Anything about hosted models or real agents.

## Publication

The counts, both agents' code and outputs, and a page are published whatever X and Y are.
