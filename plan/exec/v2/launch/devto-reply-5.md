Maintainer only — this answers Agentic Affairs’ reply of 21 Nov asking “Worth a run 5?”
Approve the exact reply and post it yourself.
Reply text below — 161 words.

I [registered run 5](https://github.com/ajaysurya1221/agent-reliability-ci/blob/6c0a5a04af4e9f782289bea84f5a606e512dd8d1/plan/exec/v2/study/PREREGISTRATION-run-5.md) before its first live trial. Both arms used one small model and the same prompt, ending “Retry an empty lookup once.”

The named message read “lookup_order returned an empty result. Call lookup_order again with the same order_id.”

The generic message read “The previous tool call returned an empty result. Repeat that call with the same input.”

I got PASS at round 13 (“non-inferiority established”). Named passed 86/104 and generic 92/104. Under the registered assumptions, that supports a generic shortfall smaller than ten percentage points, a tie or a lead, averaged across eight order IDs. I didn’t test superiority.

After an empty result, I counted another lookup in 97/100 named trials and 103/103 generic trials. All eight tasks shared one sentence. Named passed 30/32 in run 4.

I didn’t measure capability or test the 12B model, so policy versus capability remains open. The consultant and orchestrator both predicted INCONCLUSIVE and were wrong again. [Per-task results](https://github.com/ajaysurya1221/agent-reliability-ci/blob/v2/phase0/plan/exec/v2/study/RESULT-run-5.md#in-plain-numbers) and [full counts](https://github.com/ajaysurya1221/agent-reliability-ci/blob/addddde7e7c152755f6fc79e74fdaa493f9ac26e/plan/exec/v2/study/run-5-counts-a.json).
