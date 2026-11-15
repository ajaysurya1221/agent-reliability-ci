I wanted to know whether a 4B local model could replace a 12B one in a small tool-using agent. I ran it as an experiment, with the prediction written down before each run. Both models ran on Ollama on one laptop, at temperature 0.7, with no API.

## The set-up

- 24 order-desk tasks: refund an order, refund and add a note, check stock and add a note.
- Each task ran clean and under three injected tool faults: a timeout, a one-off error, an empty result. That makes 96 task-and-fault combinations per round.
- Baseline: gemma4 12B. Candidate: qwen3.5 4B. Same prompt, same tools, same retry settings.
- The rule for the verdict was fixed before the run: is the 4B within 10 points of the 12B?

## Run 1: my prediction lost

I predicted the 4B would be close enough. It was not. The 12B passed 96 of 96. The 4B passed 70 of 96, and the run stopped after one round with a verdict of BLOCK.

Most of the failures were one behaviour. In 21 of the 26, the 4B was asked to check stock for an order and its only call was to the stock tool, with the order id as the product code. It never looked the order up.

## A reader caught a flaw in the test

In my set-up that wrong call raised an exception and ended the trial. The model never saw "unknown SKU". So I had measured "makes a wrong first call, where a wrong call is fatal". I had not measured "cannot do the task". I published a correction and ran it again.

## Run 2: the error goes back to the model

One change, the same for both models: a tool's error is returned to the model as a message. My prediction, written first: inconclusive.

- 12B: 480 of 480.
- 4B: 428 of 480 (89%).
- The 4B made the wrong first call about as often as before: in 21 of 32 stock-note trials in run 1, and in 108 of 160 in run 2.
- Shown the error, it looked the order up next in 106 of those 108, and 68 of the 108 passed.
- Only 2 of 480 trials never did the lookup at all.

The test could not decide whether the 4B is within 10 points of the 12B. The gap landed at 10.8 points. So the verdict is INCONCLUSIVE: the run crossed neither the PASS nor the BLOCK threshold.

## Where it still breaks

Two things going wrong in one trial. When the 4B made the wrong first call and then the lookup came back empty (the injected fault), it passed 0 of 26. In 21 of the 26 it read the error, looked the order up once, got nothing back, and stopped. The 12B retried the empty lookup every time, 120 of 120.

Where the wrong first call was the only lasting problem (no injected fault, or a timeout that a retry clears), the 4B went on to pass 52 of 58.

## What I took from it

- Know whether your tools raise their errors or return them. Here it changed what the test measured: in run 2, 77 of the 4B's 428 passes came after a tool error that would have ended the trial under run 1's set-up.
- In this suite, looking at one problem at a time flattered the 4B. Half of its 52 failures in run 2 (26) were the compound case above.
- I did not see any of this by reading sample outputs. I saw it by counting what each trial did with its tools.

## Limits

One suite, one prompt, two models, one machine. The two runs used different seeds, so 73% against 89% is two observations, not a measured effect of returning errors. The breakdowns were chosen after seeing the data. None of this says anything about these models in general.

## Check it yourself

The harness is my own open-source tool, ARCI. It runs a baseline and a candidate on the same tasks with injected tool faults and gives PASS, BLOCK or INCONCLUSIVE with a stated error bound.

- [Both runs, both pre-registrations and the correction](https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/docs/results/order-desk-study.md)
- [The raw records of every trial, with the command that re-derives both verdicts](https://github.com/ajaysurya1221/agent-reliability-ci/tree/main/docs/results/order-desk-study)
- [The same comparison on your own two models](https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/docs/recipes/model-swap.md)
- [Repository](https://github.com/ajaysurya1221/agent-reliability-ci)

If you have measured this on other small models, I would like to know: does returning tool errors close most of the gap, or is that specific to this pair?
