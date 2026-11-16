# Reply for the second dev.to comment (draft; the maintainer posts it)

Post: https://dev.to/ajay_2112/i-tested-whether-a-4b-model-could-replace-a-12b-one-in-a-tool-using-agent-my-first-test-was-wrong-3jgf

Comment (account "Agentic Affairs", a follow-up to the first reply; seen on the public page
on 16 Nov 2026). It reads the compound case as "a decision difference, not a missing
policy", and asks: "The code-retry variant is the test that would settle whether it's a
capability gap — are you planning to run it, or is the next post going a different
direction?"

This version replaces the draft of 16 Nov ("not scheduled"), which was never posted: the
maintainer approved a third run the same day and it has been run. Sources: the run 2 store
(87 of 120, 86 of 87, 33) and `plan/exec/v2/study/RESULT-run-3.md` (run 3). Post it only
after the run 3 write-up is on `main`, so that the link works.

---

The records show different actions under the same instruction. They do not establish a capability gap.

One more count from the run 2 records. Under the injected empty result the 4B read the order a second time in 87 of 120 trials, and 86 of those 87 passed. None of the other 33 passed. I chose this cut after seeing the data, so it is a description, not a test.

I did not run the code-retry variant. A code retry would test the whole system with the recovery handed to code. It would not isolate what the model decides, and it would not by itself make the task succeed. A scripted test with no model in the repository shows how such a retry behaves.

I ran the neighbouring test instead, where the model still has to decide but is told at the point of failure. Same 4B model in both arms, on the 8 stock-note tasks under the empty result. One arm gets the empty result as `null`, as in run 2. The other gets "lookup_order returned an empty result. Call lookup_order again with the same order_id." The rule and the message were registered before the first trial.

Both arms already had "Retry an empty lookup once." in the system prompt. A small smoke run came before the registration; its trials are not counted.

Result: 15 of 16 passed with the message, 2 of 16 without. The test stopped at round 2. Its verdict was BLOCK, and in this run BLOCK favours the message: I put the message arm in the baseline seat on purpose, because the test has no verdict for "better". Under the test's stated assumptions this supports an advantage of more than 10 points on these 8 tasks. It is a threshold decision, not a measured gain, and it says nothing about the full suite.

What it does not show: anything about the 12B model or a capability gap (it was in neither arm), or whether naming the next step is what helped (one wording, no control message). The 8 tasks were chosen from run 2's failures, and the run stopped early, so 15 and 2 are counts, not rates.

Run 3, with its pre-registration and raw records: https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/docs/results/order-desk-study.md
