TITLE:
A 4B model passed 73% of a 12B's tool tasks when a wrong tool call crashed the run, and 89% in a second run where the error was returned to it. Pre-registered, with the place it still breaks.

BODY:
I wanted to know if a 4B local model could replace a 12B one in a small tool-using agent, so I ran it as an experiment with the prediction written down first. Both models on Ollama, one laptop, temperature 0.7, no API.

Set-up: 24 order-desk tasks (refund, refund and add a note, check stock and add a note), each run clean and under three injected tool faults: a timeout, a one-off error, an empty result. Baseline gemma4 12B, candidate qwen3.5 4B. Same prompt, same tools, same retry settings.

**Run 1.** I predicted the 4B would be close enough. It was not: 12B passed 96 of 96, 4B passed 70 of 96. Almost every failure was one behaviour: asked to check stock for an order, the 4B called the stock tool with the order id as the product code, without looking the order up first.

**A reader caught a flaw.** In my set-up that wrong call raised an exception and ended the trial. The model never saw "unknown SKU". So I had measured "makes a wrong first call, where a wrong call is fatal", not "cannot do the task". I published a correction and ran it again.

**Run 2.** One change, the same for both models: a tool's error is returned to the model as a message. Prediction written first: inconclusive.

* 12B: 480 of 480.
* 4B: 428 of 480 (89%).
* The 4B still made the wrong first call just as often: 108 of 160 stock tasks.
* Shown the error, it looked the order up next in 106 of those 108, and 68 of the 108 passed.
* Only 2 of 480 trials never did the lookup at all.

The test could not decide whether the 4B is within 10 points of the 12B: the gap landed at 10.8. So the honest verdict is inconclusive, not "good enough".

**Where it still breaks.** Two things going wrong in one trial. When the 4B made the wrong first call and then the lookup came back empty (the injected fault), it passed 0 of 26. It read the error, did the right thing next, got nothing back, and stopped. The 12B retried the empty lookup every time, 120 of 120. With only the wrong first call going wrong (clean and timeout conditions), it went on to pass 52 of 58.

What I took from it:

* If you are testing a small model with tools, check whether your tools raise or return their errors. In run 2, 77 of the 4B's 428 passes came after an error that would have ended the trial in run 1.
* Single-fault tests flattered the small model. The gap was in the compound case.
* Reading sample outputs would not have shown any of this. Counting what each trial did with its tools did.

Limits: one suite, one prompt, two models, one machine. The two runs used different seeds, so 73% against 89% is two observations, not a measured effect. The breakdowns were chosen after seeing the data. It says nothing about these models in general.

The harness is my own open-source tool (ARCI, a regression gate for agents: it runs baseline and candidate on the same tasks with injected tool faults and gives a verdict with a stated error bound). Both runs, the pre-registrations and the correction are here:

Both runs and the correction: https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/docs/results/order-desk-study.md

To try the same comparison on your own two models: https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/docs/recipes/model-swap.md

Repo: https://github.com/ajaysurya1221/agent-reliability-ci

Has anyone measured the same thing on other small models: does returning tool errors close most of the gap, or is that specific to this pair?
