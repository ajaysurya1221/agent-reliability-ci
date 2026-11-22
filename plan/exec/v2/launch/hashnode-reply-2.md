Maintainer only: this answers Halfcycle's second comment on the Hashnode post (seen 22 Nov 2026, about two days after it was written; it had not been noticed).
Approve the exact reply and post it yourself. Not posted.
Reply text below: 187 words, reviewed by the consultant on 22 Nov 2026.

Sorry I missed your reply. I tested that control for another reader. The neutral message said, “lookup_order returned an empty result. This lookup_order result is for the supplied order_id.” It names the tool and input without prescribing a next step. The shared prompt still said, “Retry an empty lookup once.”

In [Run 4](https://github.com/ajaysurya1221/agent-reliability-ci/blob/v2/phase0/plan/exec/v2/study/RESULT-run-4.md#in-plain-numbers), 30/32 trials passed with the explicit retry instruction versus 14/32 with the neutral message (BLOCK, round 4). After an empty result, another lookup followed in 31/31 explicit trials and 14/31 neutral trials. I measured actions and final order states. Neither reveals whether the model noticed. A later call could already have been queued. I didn’t compare the neutral message directly with a bare empty result.

In [Run 5](https://github.com/ajaysurya1221/agent-reliability-ci/blob/v2/phase0/plan/exec/v2/study/RESULT-run-5.md#in-plain-numbers), both messages prescribed a retry. “Repeat that call with the same input” passed 92/104 versus 86/104 for the named retry (PASS, round 13). That supports a generic shortfall smaller than ten percentage points, a tie or a lead. I didn’t test whether generic was better.

I used one 4B model, one prompt and eight versions of one stock-note task. Sixteen smoke trials preceded run 4’s registration.
