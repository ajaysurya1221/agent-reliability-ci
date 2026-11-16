# Reply for the second dev.to comment (draft; the maintainer posts it)

Post: https://dev.to/ajay_2112/i-tested-whether-a-4b-model-could-replace-a-12b-one-in-a-tool-using-agent-my-first-test-was-wrong-3jgf

Comment (account "Agentic Affairs", a follow-up to the first reply; seen on the public page
on 16 Nov 2026). It accepts the correction on 70 of 96 against 428 of 480, reads the compound
case as "a decision difference, not a missing policy", and asks: "The code-retry variant is
the test that would settle whether it's a capability gap — are you planning to run it, or is
the next post going a different direction?"

Sources: the run 2 store on `main`
(`docs/results/order-desk-study/run-2/`), counted on 16 Nov 2026 by two agents working
separately, neither of which read a write-up; both gave the same numbers. Under the
injected empty result the candidate called `lookup_order` a second time in 87 of 120
trials; 86 of those 87 passed (the other one used a malformed order id); none of the 33
without a second lookup passed. The roadmap on `main` says nothing is scheduled. The
second blog post (`docs/blog/2026-11-eval-noise.md`) is written and not yet published.

One sentence is the maintainer's to settle before posting: whether the variant will be
run. The text below says it is not scheduled. If it will be run, replace the paragraph
marked [PLAN] with the alternative under the reply.

Checked on 16 Nov 2026 by a third agent that counted every number again from the store and
read the code. Its corrections are applied: "None of the other 33 passed" (one of the 33
never called `lookup_order` at all); the conclusion no longer points at one step, because
32 of the 33 trials without a second lookup are stock-note tasks and only 7 of the 86
passes are, so the split is close to a split by task; the plan sentence has no "yet"; and
the reply says what a code retry cannot show. The sentence about the next post holds only
if the eval-noise post is the next one published.

---

Yes, that is how I read it too: the same instruction, and a different decision.

One more count from the run 2 records, since it bears on your question. Under the injected empty result the 4B read the order a second time in 87 of 120 trials, and 86 of those 87 passed. None of the other 33 passed. So in this run, 33 of the 34 failures under the empty result are trials with no second read. That does not show what those 33 would have done with the order: all but one of them are stock-note tasks, and only 7 of the 86 passes are. I chose this cut after seeing the data, so it is a description, not a test.

The code-retry variant is not scheduled. It would be the same change for both models: retry an empty lookup once in code. One limit of it: with the retry in code the model never sees the empty result, so it shows what happens when the decision is taken away from the model. If I run it, I will write the prediction down first, as for the first two runs, and post the result here.

The next post planned is on a different question: how often an unchanged agent looks worse on a small eval by chance alone.

---

Alternative for the third paragraph, only if the maintainer has decided to run it:

I am going to run the code-retry variant. It is the same change for both models: retry an empty lookup once in code. One limit of it: with the retry in code the model never sees the empty result, so it shows what happens when the decision is taken away from the model. The prediction will be written down before the run, as for the first two, and I will post the result here.
