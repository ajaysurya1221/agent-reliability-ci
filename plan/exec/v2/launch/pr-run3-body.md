## What

A third pre-registered run of the order-desk study, added to the public write-up with its sealed store and a test that re-derives its decision.

- `docs/results/order-desk-study.md`: a new introduction that separates runs 1 and 2 (two models) from run 3 (one model in both arms), and a section "Run 3" with its own table, what the verdict says and does not say, the registered counts, and two errata to the pre-registration.
- `docs/results/order-desk-study/run-3/`: the sealed store, byte for byte (`manifest.json`, `trials.jsonl`, `events.jsonl`, `decision.json`).
- `tests/unit/docs/test_order_desk_stores.py`: run 3 as a third case (re-derived decision equal to the stored one), its wealth figures and headline table cells read from the write-up, and a test that holds what the reading of the verdict rests on (arm labels, 13 / 3 / 0, no hard violation, 32 trials).
- The stores' README, the results index and the changelog.

## The run in short

The 4B model in both arms. One arm gets a fixed message in place of the `null` of an injected empty lookup; the other is run 2's set-up. 8 cells, chosen after run 2. The arm roles are swapped, because the test has no verdict for "better": the arm with the message is the baseline. Verdict: a statistical `BLOCK` at round 2 (16 pairs; 15 of 16 against 2 of 16). In this orientation that means the set-up without the message passes less often, by more than 10 percentage points on those 8 cells. It is a threshold decision, not a measured size.

It says nothing about the 12B model, about cause, about the other tasks and conditions, or about whether naming the next step is what helped.

## How it was checked

- Registered in a pushed commit (`c217ae6`) 19 seconds before the start script began. One start. A smoke run before the registration is disclosed and not pooled.
- Before the run: blind tests of the arm difference, a check through the real client path with a fake transport (800 request bodies; the only difference between the arms was the content of one tool message), and a review of the build.
- After the run: a recount from the store by an agent that had read no write-up (same numbers), an audit of the four registered conditions from the raw files (all hold), and a sentence check of the result file. The public section was then checked against the records and read by a first-time reader; its corrections are applied.
- Two errata to the pre-registration are stated in the write-up: the start script gained its guards after the smoke run, and one number about run 2 was wrong (33 of 34, not 32 of 34). Neither changes the grid, the rule or the verdict.
- Docs, outcomes and packaging suites: 472 passed, 1 skipped. Lint and type check clean. All 76 pinned hashes match.

No code change. No release is needed.
