# Replies for the r/LangChain thread (drafts; the maintainer posts them)

Thread: https://www.reddit.com/r/LangChain/comments/1xtror1/i_put_create_agent_behind_a_faultinjecting/

Plain text on purpose: Reddit refused the formatted post body on 12 Nov.

## 1. To u/Significant_Tune9219 (post first; it carries the promised run)

You were right, and the stored run confirmed it: the tool raised an exception, the model never saw "unknown SKU", and one wrong call ended the trial. So run 1 could not separate "reasons worse" from "needs a recoverable tool contract". I added a dated correction to the result and credited you.

I then pre-registered a second run with one change, the same in both arms: the tool's error is returned to the model instead of crashing the trial.

Result: INCONCLUSIVE after 5 rounds. 12B passed 480 of 480, 4B passed 428 of 480 (89.2%; it was 72.9% in run 1, on different seeds, so that is two observations and not a measured effect). The gap is 10.8 points against a 10-point margin, so the test could not decide either way in the registered budget.

The categories you asked for, 4B model, 480 trials:
- Never called the lookup at all: 2
- Had a tool failure with no injected fault, then passed: 77
- Had one, then failed: 47

It still makes the wrong first call as often (108 of 160 stock-note trials). Shown the error, it went on to look the order up in 106 of those 108, and 68 passed.

What is left is mostly one cell: stock-note tasks where the lookup returns an injected empty result. 7 of 40 passed there, and 0 of 26 after a wrong first call. Two things going wrong in one trial is where it breaks.

Your category idea is now in the tool: v2.1.0 prints this table in every report, and the quickstart compares two models with everything else equal.

Both runs and the correction: https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/docs/results/order-desk-study.md

## 2. To u/ChemicalExcellent463

Honest answer: in run 1 it answered with nothing. Its first and only call was the stock tool with the order id as the product code (sku: "ORD-103"), the tool raised, and the trial crashed before the model could say anything. That was 21 of the 23 unknown-SKU failures.

So "skipped the lookup" was mostly "crashed before it could look anything up". I re-ran with the error returned to the model (pre-registered again). Now only 2 of 480 trials end without a lookup; in 106 of 108 trials that start with the wrong call, it reads the error and looks the order up next.

When it still fails, it usually says so plainly: it reports that the order id is not a valid product code, or that the order came back empty, and stops instead of retrying.

Write-up of both runs: https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/docs/results/order-desk-study.md

## 3. To u/localhost_0000

Noted, that is one vote for interrupts, and "the human as one more flaky tool" is the framing I would use: an approval step that can time out, refuse, or answer late, declared as a fault like any other.

Today the adapter rejects interrupts outright rather than half-supporting them. I have not designed this yet, so no promise on timing. If you have a concrete flow (who approves what, and what should happen on no answer), I would like to see it.
