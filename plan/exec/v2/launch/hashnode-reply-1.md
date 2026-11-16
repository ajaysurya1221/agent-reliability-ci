# Reply for the first Hashnode comment (draft; the maintainer posts it)

Post: https://realornoise.hashnode.dev/i-tested-whether-a-4b-model-could-replace-a-12b-one-in-a-tool-using-agent-my-first-test-was-wrong

Comment (account "Halfcycle", the first comment on the Hashnode post; seen on the public
page on 16 Nov 2026). It proposes a third run with the next step written into the error
text and asks: "Did you try varying the error wording?"

This version replaces the draft of 16 Nov ("I have not tested that"), which was never
posted: the maintainer approved a third run the same day and it has been run. Sources: the
run 2 store (108, 106, 52, 34, 32) and `plan/exec/v2/study/RESULT-run-3.md` (run 3). Post
it only after the run 3 write-up is on `main`, so that the link works.

---

Thank you. I had not varied it when you asked. Run 2 used one wording for that error: the tool's own text, "unknown SKU", passed back to the model as "Error: unknown SKU". It does not say what to do next.

Even so, with only that bare text the 4B usually went straight to the lookup: it made the wrong first call in 108 trials, and in 106 of them its next call was the order lookup. Most of the failures were one step on, at the empty lookup. That reaches the model as a successful call whose whole result is the text `null`, with no explanation and no next step. Of the 4B's 52 failures, 34 were under that fault, and in 32 of those it got the empty result and never read the order again. I chose these cuts after seeing the data.

So I ran your idea at that point. Same 4B model in both arms, on the 8 stock-note tasks under the empty result. One arm gets `null`, as before. The other gets "lookup_order returned an empty result. Call lookup_order again with the same order_id." The rule and the message were registered before the first trial.

Both arms already had "Retry an empty lookup once." in the system prompt. A small smoke run came before the registration; its trials are not counted.

Result: 15 of 16 passed with the message, 2 of 16 without. The test stopped at round 2. Its verdict was BLOCK, and in this run BLOCK favours the message: I put the message arm in the baseline seat on purpose, because the test has no verdict for "better". Under the test's stated assumptions this supports an advantage of more than 10 points on these 8 tasks. It is a threshold decision, not a measured gain, and it says nothing about the full suite.

What it does not show: whether naming the next step is what helped, since I tested one wording against `null` and no control message. It says nothing about the 12B model. The 8 tasks were chosen from run 2's failures, and the run stopped early, so 15 and 2 are counts, not rates.

Run 3, with its pre-registration and raw records: https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/docs/results/order-desk-study.md
