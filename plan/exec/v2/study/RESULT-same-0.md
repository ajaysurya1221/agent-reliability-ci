# Result, Same-0: an unchanged agent compared with itself

**With identical configurations, 0 of 14 three-round comparisons showed the second copy ten points or more behind the first, and 3 of 14 showed it ten points or more ahead.**

That is the sentence fixed in the registration, word for word. The orchestrator predicted two drops in 14 comparisons and observed zero; its stated range was zero to four. In all three comparisons with a gap of ten points or more, the copy labelled "candidate" had more passes.

## Read this first

- This is a count on records that were already published, not a new run. The rule for the count was pushed before any of its numbers were computed ([registration](PREREGISTRATION-same-0.md), commit `e95fe53`).
- Size-0's 14 runs compare an agent with an exact copy of itself: the same model, prompt, tools and limits on both sides. Nothing was changed between the two sides.
- After three runs of the eight tasks on each side, two identical copies were ten points or more apart in 3 of 14 comparisons (0 behind plus 3 ahead). The other 11 comparisons stayed within ten points.
- In a secondary count, the copies' scores differed in 64 of 135 eight-task rounds (the second copy lower in 30, higher in 34, the same in 71), including 31 of 40 rounds for the 9B build and 0 of 20 for Gemma 12B.
- Two agents counted separately, each with its own code and without seeing the other. Their counts are equal, row by row.
- Size-0 used four local models and eight order ids. The separate Board-0 count covered five models and 16 tasks. All on one laptop. This gives no rate for any other agent, and that agents vary from run to run is already published by others.

## The 14 comparisons (rounds 1 to 3, 24 trials on each side)

A score is the number of trials with a correct final state. "Drop" means the side labelled candidate has 3 or more fewer passes than the side labelled baseline (12.5 points or more); "gain" means 3 or more passes more.

| Run | Baseline passes | Candidate passes | Difference | Result |
|---|---:|---:|---:|---|
| `size0-d1-q2-clean` | 5 | 4 | -1 | neither |
| `size0-d1-q2-null` | 1 | 0 | -1 | neither |
| `size0-d1-q4-clean` | 20 | 24 | +4 | gain |
| `size0-d1-q4-null` | 0 | 0 | 0 | neither |
| `size0-d1-q9-clean` | 16 | 17 | +1 | neither |
| `size0-d1-q9-null` | 5 | 9 | +4 | gain |
| `size0-d1-g12-clean` | 24 | 24 | 0 | neither |
| `size0-d1-g12-null` | 24 | 24 | 0 | neither |
| `size0-d2-q9-clean` | 13 | 18 | +5 | gain |
| `size0-d2-q9-null` | 7 | 9 | +2 | neither |
| `size0-d2-q4-clean` | 20 | 22 | +2 | neither |
| `size0-d2-q4-null` | 0 | 0 | 0 | neither |
| `size0-d2-q2-clean` | 2 | 2 | 0 | neither |
| `size0-d2-q2-null` | 1 | 0 | -1 | neither |

Drops: 0 of 14. Gains: 3 of 14. Neither: 11 of 14. Both sides are the same configuration, so "gain" here is a difference between two copies of one agent and nothing else.

## All blocks (descriptive)

Within each run, consecutive blocks that do not overlap, starting at round 1; an incomplete last block is dropped. "Ten points or more" is 1 pass of 8, 3 of 24 or 4 of 40. Tasks repeat across rounds, so the blocks are not independent of each other.

| Runs of the eight tasks per side | Blocks | Candidate fewer | Same | Candidate more | Ten points or more behind | Ten points or more ahead |
|---:|---:|---:|---:|---:|---:|---:|
| 1 | 135 | 30 | 71 | 34 | 30 | 34 |
| 3 | 41 | 12 | 17 | 12 | 3 | 4 |
| 5 | 26 | 8 | 12 | 6 | 1 | 4 |

One fewer pass of eight is already 12.5 points, so for a single run "different" and "ten points or more apart" are the same thing. That row describes how one run of a task list looks. It is not a claim about how anyone decides a release.

Single rounds, split (fewer / same / more):

| Group | Rounds | Candidate fewer | Same | Candidate more |
|---|---:|---:|---:|---:|
| clean runs | 66 | 19 | 22 | 25 |
| null runs | 69 | 11 | 49 | 9 |
| 2B build | 40 | 12 | 20 | 8 |
| 4B build | 35 | 3 | 22 | 10 |
| 9B build | 40 | 15 | 9 | 16 |
| Gemma 12B | 20 | 0 | 20 | 0 |

Three-round blocks ten points or more apart: 7 of 41 (3 behind, 4 ahead); six of the seven are in the 9B build's runs and one in the 4B build's. Five-round blocks: 5 of 26 (1 behind, 4 ahead). The full splits by condition and model for every width are in [same-0/a/counts.md](same-0/a/counts.md).

## The same task run twice (Board-0's clean rows)

In Board-0's clean rows every task was run twice with nothing different. Of the 160 task-pairs, 5 have two different outcomes: 2 for Gemma 12B (M2), 3 for Mistral NeMo 12B (M4), none for the other three models; 4 on day 1 and 1 on day 2. As the registration says, this number could already be read off the published per-task counts; it is a restatement, not a test.

## The released rule on the same 14 runs

The stored verdicts of the released rule on these 14 self-comparisons are 7 PASS, 7 INCONCLUSIVE and 0 BLOCK. A BLOCK would have said that one copy is worse than the other by more than the margin. This is printed as it is and is **not** a score of "mistakes avoided": the rule used up to 80 pairs where the counts above use 8, 24 or 40 per side, a score difference is not a release decision, PASS is a statement about the allowed loss, and half of the runs ended undecided.

## Predictions against outcomes

| Registered prediction (orchestrator) | Outcome |
|---|---|
| Drops: 2 of 14 (plausibly 0 to 4) | 0 of 14. Inside the range, below the estimate. |
| Gains: 2 of 14 (0 to 4) | 3 of 14. Inside the range. |
| Gemma runs and the 4B and 2B null runs can hardly move | Their six primary differences are 0, 0, 0, 0, -1 and -1. |
| Any drops would come from the 9B runs or the clean 4B or 2B runs | There were no drops to locate. (The three gains are two 9B runs and one clean 4B run; the prediction did not cover gains.) |
| Single rounds: candidate fewer in about 25% of 135 | 30 of 135 (22.2%). |

The consultant and the maintainer gave no prediction.

## Checks

Two agents counted from the unpacked published records, each with its own code, without seeing the other's result or any write-up. Their 14 primary rows are equal, their 41 three-round blocks are equal, and their totals for every width and for Board-0 are equal. Both verified that every one of the 135 rounds holds exactly eight trials on each side. Code and outputs: [same-0/a/](same-0/a/counts.md) and [same-0/b/](same-0/b/counts.md). The records are `size0-evidence/claims.zip` (SHA-256 `fcb0bb543a83392927558f850e6e70f976dcced81d80347a847841a66a7516be`) and `board0-evidence.zip` (SHA-256 `35f70d9b3a787a1e429fd623dd550b80d77b99da60ea7ce2291d74d9204e5340`).

## What was known beforehand

The orchestrator had read both result pages before writing the registration: every run's total trials and passes, passes per order id pooled over both sides, the stopping rounds and the 14 stored verdicts. The differences counted here were recoverable from the published records before the registration: each run's stored decision file holds the pair counts of every round. The orchestrator reports that it had not examined them. The registration's sentence that no count per side, per round or per block "had been computed or seen" should be read with that limit: none had been computed or looked at by the orchestrator, but they were not hidden from it.

## Not claimed

- That run-to-run variation of agents is new. It is published, for example in arXiv 2610.10062 (the same end state in 63.3% of repeated fault-free runs) and in tau-bench's pass^k measure.
- A rate for any other agent, model, task or temperature. These are four local models at temperature 0.7 with no sampling seed, on one task sentence in eight variants, on one laptop.
- That 3 of 14 is a stable rate. It is 14 comparisons, and the three gains come from two models.
- That the direction means anything. Both sides are the same configuration.
- That developers decide releases from one, three or five runs.
- That the released rule "made no mistakes". See the section above.
- Anything about hosted models or real agents.
