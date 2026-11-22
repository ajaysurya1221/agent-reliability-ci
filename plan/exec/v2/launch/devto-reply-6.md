Maintainer only — this answers Agentic Affairs’ 22 Nov reply to run 5
about the compound case and the 12B model. Approve the reply and post it yourself.
Reply text below — 166 words.

I scripted the same opening for both arms. A stock check used the order ID as the SKU and failed. The next lookup came back empty. Both prompts said “Retry an empty lookup once.” One arm saw a generic reminder to repeat the call with the same input. The other saw `null`. [Run 6 registration](https://github.com/ajaysurya1221/agent-reliability-ci/blob/0ca504d311b343a3d7e000fbd1e2cffad9881df3/plan/exec/v2/study/PREREGISTRATION-run-6.md)

I got BLOCK at round 3. Generic passed 18/24 and raw null passed 0/24. Under the registered assumptions, that supports a raw-null shortfall greater than ten percentage points on average across the eight tasks. The model tried the lookup again in all 24 generic trials and none of the raw-null trials. [Per-task counts](https://github.com/ajaysurya1221/agent-reliability-ci/blob/v2/phase0/plan/exec/v2/study/RESULT-run-6.md#in-plain-numbers)

The “0 of 26” came from run 2. Of the 4B stock-note trials assigned an empty first lookup, 26 began with the wrong call. None passed. Only 25 received the empty result.

I tested one model and one prompt on eight tasks sharing one sentence. The 12B model was in neither arm, so policy versus capability remains open.
