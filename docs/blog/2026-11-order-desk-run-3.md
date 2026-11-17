# Readers asked for a third test of my 4B agent. I changed one tool message.

*The same 4B model on both sides: the text `null` against a short message when an order
lookup comes back empty. What the test decided on 8 selected cases, and what it cannot say.*

In my last post I tested whether a 4B local model could replace a 12B one in a small
order-desk agent. Readers asked for one more test. This one runs the same 4B model in two
set-ups, which I call sides. When an order lookup comes back empty, one side gets the text
`null`, as before. The other side gets a short message. With the message, 15 of 16 trials
passed. With `null`, 2 of 16. These are counts from a run that stopped early, on 8 cases I
picked because the model had failed there before. They are not rates.

## What the readers asked

On dev.to, "Agentic Affairs" asked whether I would run a variant in which the code retries
an empty lookup. On Hashnode, "Halfcycle" proposed writing the next step into the error text
and asked: "Did you try varying the error wording?" I had not.

I adapted the second idea. The empty lookup is not an error. It reaches the model as a
successful call whose whole result is the text `null`. I tested one message at that point,
because in run 2 (the second test in my last post) 34 of the 4B's 52 failures were in trials
with that fault.

I did not run the retry in code. It is a useful question about system design, and I have not
tested it with a model. A scripted test with no model, in the working records linked from
the write-up, shows how such a retry behaves.

## The set-up

- The same model on both sides: qwen3.5 4B, with the same prompt and tools.
- 8 stock-note tasks. They are one task sentence with eight different order ids.
- In every trial the harness is set to make the first order lookup come back empty on
  purpose. That is the injected fault.
- I chose these tasks and this fault from run 2's failures.
- Both sides already had "Retry an empty lookup once." in the system prompt.

One side gets the empty result as it did in run 2:

```
null
```

The other side gets:

```
lookup_order returned an empty result. Call lookup_order again with the same order_id.
```

A trial passes when the order ends with the right stock note and no refund.

The rule for the verdict and the message were pre-registered: pushed in a public commit
before the first registered trial. Unlike the first two runs, I wrote no prediction first.

A smoke run (a short run to check the set-up) came before the registration, and I saw its
results: 6 of 8 with the message, 3 of 8 without. They are not evidence and are not counted.

## Why the verdict reads BLOCK

The test compares a baseline (the reference) with a candidate (the set-up under test). A
round runs every task once on each side. The two trials of one task in a round are a pair.
The test looks at the pairs after each round. It has three verdicts:

- PASS: the test decides that the candidate is not worse than the baseline by more than 10
  percentage points of pass rate.
- BLOCK: the test decides that it is worse by more than that.
- INCONCLUSIVE: the registered rounds ended with neither decision.

No verdict says "better". The tool can also stop with ERROR, or force a BLOCK when a hard
rule is broken. Neither happened here.

Because no verdict says "better", I put the side with the message in the baseline seat and
run 2's set-up in the candidate seat. In this run, BLOCK means the test decided that the
side with `null` passes less often than the side with the message, by more than 10
percentage points of mean pass rate.

## The result

BLOCK after 2 rounds, which is 16 pairs.

- With the message: 15 of 16 passed.
- With `null`: 2 of 16 passed.
- In 13 pairs only the side with the message passed. In 2 both passed. In 1 both failed. In
  none did only the side with `null` pass.

The registered test decided that the side with the message passes more often, by more than
10 percentage points of mean pass rate over the 8 tasks. The decision is about these 8 tasks
under the empty result, this 4B model, this prompt and this one wording, and nothing wider.

It rests on the test's assumptions, which the tool does not check: for example, that tasks
and rounds are independent and that it does not matter which side runs first. The write-up
lists them. It is a threshold decision, not a measured size. The run stopped after 2 rounds,
as soon as it reached a verdict, so 15 of 16 and 2 of 16 are raw counts, not estimates of
the two pass rates.

## What it does not show

- Whether naming the next step is what helped. I compared one wording with `null`. I did not
  test a message that names no next step.
- Anything about the 12B model. It was on neither side.
- Anything about the other 16 tasks, the other conditions of the first two runs (no fault, a
  timeout, a one-off error) or the full suite.
- Anything from comparing these counts with run 2's. Run 2 used other random seeds and
  another version of the test tool.

This is a third experiment on related data, chosen after seeing the first two. I claim no
error guarantee across the three.

## Two mistakes in my registration

- It says nothing was changed after the smoke run. That is not true of the script that
  starts the run. Start checks and a check-only mode were added to it after the smoke run
  and before the registration. As far as file times show, the files of the study folder
  itself did not change.
- It says 32 of the 4B's 34 failures under the empty result in run 2 were on these tasks.
  The records give 33 of 34.

The second changes nothing in the tasks, the rule or the verdict. For the first, the version
of the script that ran is the version the registration recorded.

## Check it yourself

The harness is my own open-source tool, ARCI.

- Run 3: the write-up, with both errata:
  <https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/docs/results/order-desk-study.md#run-3-2026-11-16-a-message-at-the-empty-lookup-one-model-in-both-arms>
- The pre-registration commit:
  <https://github.com/ajaysurya1221/agent-reliability-ci/commit/c217ae6>
- The raw records of every trial:
  <https://github.com/ajaysurya1221/agent-reliability-ci/tree/main/docs/results/order-desk-study>
- The first post:
  <https://realornoise.hashnode.dev/i-tested-whether-a-4b-model-could-replace-a-12b-one-in-a-tool-using-agent-my-first-test-was-wrong>
- Repository: <https://github.com/ajaysurya1221/agent-reliability-ci>

I have not tested a message that reports the empty lookup but names no next step. If you
have tried one, what did you see?
