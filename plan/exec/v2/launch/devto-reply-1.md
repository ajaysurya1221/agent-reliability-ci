# Reply for the first dev.to comment (draft; the maintainer posts it)

Post: https://dev.to/ajay_2112/i-tested-whether-a-4b-model-could-replace-a-12b-one-in-a-tool-using-agent-my-first-test-was-wrong-3jgf

Comment (account "Agentic Affairs", 15 Nov 2026):
https://dev.to/ajay_2112/i-tested-whether-a-4b-model-could-replace-a-12b-one-in-a-tool-using-agent-my-first-test-was-wrong-3jgf#comment-3l86a

Its question: is the compound case (wrong first call, then an empty lookup, 0 of 26) "a
capability gap, or just a retry policy the small model was never given?" It also reads
70 of 96 against 428 of 480 as the effect of returning the error.

Sources for the reply: the run 2 agent registered at `6fbdb1c`
(`plan/exec/v2/study/order-desk-recoverable/agent.py`: one system prompt for both arms,
ending "Retry an empty lookup once."; `ToolRetryMiddleware` with `max_retries=1` and
`retry_on=(TimeoutError, RuntimeError)` in both arms) and the run 2 store under
`docs/results/order-desk-study/run-2/`. The three counts
(120 of 120, 87 of 120, 21 of 26) were recounted from the store's `tool_start` events on
15 Nov 2026 by an agent that read no write-up: 26 of the 40 stock-note trials under the
empty result began with a call other than `lookup_order`, none of the 26 passed, and 21 of
them were `check_stock`, then one `lookup_order`, then no further tool call. The store shows
the injected empty result reaching the model as a successful call whose value is null.

---

Thanks for reading it this closely.

It was given the policy, and the same one as the 12B. Both models ran with one system prompt, and its last sentence is "Retry an empty lookup once." The retry in code covers only timeouts and tool errors, once. An empty result is not an error, so reading the order again was each model's own decision.

Under the injected empty result the 12B read the order a second time in 120 of 120 trials. The 4B did in 87 of 120. In the compound case (wrong first call, then the empty lookup) it stopped after one lookup in 21 of the 26.

So it is not a missing instruction. Whether to call it a capability gap, I can't say from this run. I have not tested a set-up where the code retries an empty result for the model, which is what would tell the two apart. I also chose these cuts after seeing the data.

One caution on 70 of 96 against 428 of 480: those are two separate runs with different seeds and a different number of rounds, so the difference is not a measured effect of returning the error.
