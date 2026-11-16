# Reply for the first Hashnode comment (draft; the maintainer posts it)

Post: https://realornoise.hashnode.dev/i-tested-whether-a-4b-model-could-replace-a-12b-one-in-a-tool-using-agent-my-first-test-was-wrong

Comment (account "Halfcycle", the first comment on the Hashnode post; seen on the public
page on 16 Nov 2026). It proposes a third run with the next step written into the error
text ("unknown SKU; this looks like an order id, look the order up first") and asks: "Did
you try varying the error wording?"

Sources: the run 2 agent and tools registered at `6fbdb1c`
(`plan/exec/v2/study/order-desk-recoverable/`: `tools.py` raises `ValueError("unknown SKU")`;
`agent.py` returns a tool's `ValueError` to the model as `Error: <message>`; the system
prompt ends "Retry an empty lookup once.") and the run 2 store on `main`
(`docs/results/order-desk-study/run-2/`), counted on 16 Nov 2026 by two agents working
separately, neither of which read a write-up; both gave the same numbers:

- 108 of the candidate's 160 stock-note trials began with a call other than `lookup_order`;
  in 106 of them the next call was `lookup_order`; in 2 it was never called.
- The store holds one error text for all 108 wrong first calls (`ValueError: unknown SKU`).
  It does not hold the message the model saw; that wording is taken from the code.
- The injected empty result is stored as a successful `lookup_order` call whose value is
  null, with no error.
- The candidate failed 52 trials; 34 of them were under the empty-result fault. In 32 of
  those 34 it received the empty result and did not call `lookup_order` again; in 1 it never
  called `lookup_order`; in 1 it called it again with a malformed order id.

Checked on 16 Nov 2026 by a third agent that counted every number again from the store and
read the code path of the empty result (`perturb.py`, the tool box, the LangChain adapter,
and the pinned langchain-core, which turns a `None` result into the text `null` with status
success). Its corrections are applied: "one wording for that error" (the run also had two
other tool error texts, 9 and 1 times); no claim that the bare text "was enough" (the
prompt also said "Read the order first."); "most of the failures" instead of "the gap"
(34 of 52; 18 are under the other conditions); "a run with both versions side by side
could show" instead of "would show"; the caveat moved directly under the numbers. For the
maintainer: the lookup tool itself never returns nothing; the empty value is put there by
the injected fault, so trying the commenter's idea means changing what the fault delivers.

---

Thank you. No, I did not vary it. Run 2 used one wording for that error: the tool's own text, "unknown SKU", passed back to the model as "Error: unknown SKU". It does not say what to do next.

Even so, with only that bare text the 4B usually went straight to the lookup. It made the wrong first call in 108 trials, and in 106 of them its next call was the order lookup. So in this run a better message there had little left to fix: 2 trials of 108.

Most of the failures are at the empty lookup, not at the SKU error. The injected empty lookup reaches the model as a successful call whose whole result is `null`, so there is no error text at all. Of the 4B's 52 failures, 34 were under that fault, and in 32 of those it got the empty result and never read the order again. The prompt did say "Retry an empty lookup once." I chose these cuts after seeing the data, so they describe this run and are not a test.

So your idea fits the empty result better than the SKU error: have the lookup say what to do when it comes back empty, instead of a bare `null`. I have not tested that. A run with both versions side by side could show whether an instruction at the point of failure helps in the trials where the same instruction in the prompt did not.
