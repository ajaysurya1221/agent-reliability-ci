# Size-0: one model family at three sizes, after an empty lookup (registration)

Registered 27 November 2026, before any Size-0 preflight probe or trial. Study code only; nothing
in `src/arci` changes. Operator and orchestrator: an AI agent (Claude) working for the
maintainer. Consultant: a second AI model (GPT-6.2 Astra through Codex), read-only. This file
keeps its draft name because the digest list and the launcher pin it.

## The question

In Run 6 ([registration](../PREREGISTRATION-run-6.md), [result](../RESULT-run-6.md)) a 4B model
(`qwen3.5:4b-mlx`) never looked an order up again after an empty lookup result, although its
system prompt ends "Retry an empty lookup once.": 0 of 24 trials. A reader of the write-up asked
whether that is about model size, and proposed the test: one family at more than one size.

Size-0 asks: **in Run 6's exact setting, how often do three sizes of the Qwen 3.5 family (2B, 4B,
9B) call `lookup_order` again after the empty result?**

## What was known when this was written

- Run 6's counts for the 4B model (0 of 24 with the plain `null`, 24 of 24 with a reminder).
- A later reply on the public thread (22 November 2026) reported that Gemma 12B called the lookup
  again in 24 of 24 trials in the same setting. **This repository holds no trial records for
  that count**, and the reply's statement that it used "the same 24 scenario seeds" cannot be
  reproduced with the released tool, which gives each suite its own seeds. The count should be
  read as reported, not as checkable evidence. The Gemma row of this study exists to give that
  setting a count with stored records.
- Reply-0's control ([result](../reply-0/result.md)): under a different prompt, with no retry
  sentence, the same Gemma 12B passed 6 of 24 with the empty text and 24 of 24 with a sentence.
- Board-0 ([registration](../board-0/PREREGISTRATION-board-0.draft.md)): the orchestrator had
  seen its day-1 results for five local models, including `qwen3.5:4b-mlx` and `qwen2.5:7b`,
  under a prompt without the retry sentence. Board-0's day 2 had not run and no Board-0 result
  was published when this was written.
- No Size-0 task had been shown to the 2B or 9B model. They were downloaded on 27 November 2026
  after the maintainer approved the two downloads; only their identity was read before this
  registration.

## Models

Served by Ollama 0.32.14 on one laptop (Apple M5 Pro, 24 GB). Temperature 0.7, thinking
switched off in the request (`think: false`), no sampling seed, context 32768 through a
`-ctx32k` alias of each tag, as in Run 6. Size and number format are given as the server
reports them; [models.json](models.json) pins the full digests.

| Slot | Tag | Digest (sha256, first 12) | Size | Number format |
|---|---|---|---|---|
| q2 | `qwen3.5:2b-nvfp4-ctx32k` | `670c67138085` | 2.2B | nvfp4 |
| q4 | `qwen3.5:4b-mlx-ctx32k` | `c01efed5a364` | 4.5B | nvfp4 |
| q9 | `qwen3.5:9b-nvfp4-ctx32k` | `a798a1bd5ff3` | 9.4B | nvfp4 |
| g12 | `gemma4:12b-mlx-ctx32k` | `a5c533115db8` | 12.4B | nvfp4 |

The library's `-mlx` tags do not share one number format (by build id `4b-mlx` is the `nvfp4`
build, `2b-mlx` is the `mxfp8` build). The three Qwen builds here were chosen to share `nvfp4`,
so that size is not mixed with number format. [slots.json](slots.json) fixes each slot's family
and size range, and a slot whose installed build falls outside them does not run. `g12` is an
anchor outside the size rule.

## The setting: Run 6's plain-null arm, unchanged

Eight order-desk stock-note tasks ([tasks](agent/tasks.jsonl)). The harness scripts the opening
for the model: a wrong `check_stock` call with the order id as the SKU (`Error: unknown SKU`),
then the correct `lookup_order`, whose first result ARCI's released `empty_result` fault replaces
with `null`. From there the model acts alone, with Run 6's prompt, tools, budgets (12 tool
calls, 12 model steps, 120 s) and final-state check. A test in this folder compares the first
request with Run 6's plain-null arm byte for byte, for every order id; only the model name
differs.

## Runs

Each run is one `arci run` (released 2.4.1) used as the trial runner. Both arms are the same
plain-null agent of the same model (a self-comparison), because the released tool has no
single-arm mode. Its smallest admitted cap for this shape is 10 rounds, so a run is at most
10 rounds x 8 order ids x 2 arms = 160 trials. **The verdict of a self-comparison is not a result
of this study.** It is printed as a check only. All trials of all reached rounds are counted.

Per slot and day, in this order:
- `size0-d{day}-{slot}-clean`: the same opening without the fault (the lookup returns the order).
- `size0-d{day}-{slot}-null`: the opening with the `null`.

Day 1: q2, q4, q9, g12. Day 2: q9, q4, q2, on a later local calendar date. All runs of a day
start on one date. Fourteen runs. Both days' descriptors and the expected first request of every
assignment (2,240) are frozen and pushed before the first preflight probe. Each run has one
start; an interrupted run is never restarted and is reported as interrupted. Each suite has its
own seeded orders (the released tool derives them from the suite); the eight order ids are shared.

Before its runs each slot gets a preflight: five probes of a toy tool that appears in no task,
recording model identity, loaded context, whether a native tool call was parsed, and seconds.
Identity and context must match the table above or the slot does not run. Tool-call success in
the preflight is recorded and does not decide anything.

## What is counted

- **Exposed trial**: the `null` was delivered and the model completed a response to the request
  that carried it. A trial where the `null` was delivered but no response completed is
  "unexposed": listed, and in neither part of the rate.
- **Read again**: in an exposed trial, a `lookup_order` call that reached the tool boundary
  after the first model step following the `null`, with any arguments. A malformed call that is
  rejected before dispatch is not visible.
- **Rate** of a slot on a day: read again / exposed, pooled over both arms.
- Shown beside it: read again with the right order id, final-state passes split by read again or
  not, counts by order id, and exact 95% binomial limits as a reference only (trials share
  seeds within a pair, tasks repeat, and stopping can depend on outcomes).
- **Rated**: on that day the slot's clean run has a correct final state in at least half of its
  trials for at least 6 of the 8 order ids.
- **Complete**: the null run has at least 80 exposed trials.

Two counters written separately must agree, and a third independent checker recounts from the
stored records, re-runs `arci gate` on every store and compares every request receipt with the
frozen expected request.

## How the result will be read

The size reading uses q2, q4, q9 only, and needs all three rated and complete on both days.
Otherwise the size reading is withheld and the rows are published as they are.

- **"Ordered by size"**: on each day the q2 and q9 rates differ by at least 25 percentage points
  in the same direction, and the q4 rate lies between them (ties allowed). The sentence will be:
  "On both days, retry rates were ordered by size, and the endpoints differed by at least 25
  percentage points on these assignments", naming which end retried more. Either direction counts.
- **"Close"**: on each day the highest and lowest of the three rates differ by at most 10
  percentage points. The sentence will be: "Across these three builds, the observed retry rates
  were within ten percentage points on both days."
- **Anything else** is reported as the pattern it is (for example a middle-size peak, or a
  reversal between days), with no size sentence.

The Gemma row is published however it lands, next to the 24 of 24 reported on the thread.

## Predictions, written before any trial

- Consultant: 2B about 5% (plausibly 0 to 50%), 4B about 3% (0 to 15%), 9B about 35% (0 to
  90%). "The likeliest mistake is calling a repeatable difference proof that parameter count
  caused it."
- Orchestrator: 4B at most 5%. 2B not rated on at least one day (about 40%); if rated, at most
  10%. 9B about 50%, very unsure. "Ordered by size" about 30%, "close" about 30%, withheld or
  another pattern about 40%. Gemma 12B at least 90%.
- Maintainer: none.

## What this cannot show

- That parameter count causes anything. These are three separately released builds of one
  family; their training, any distillation and their templates can differ along with size.
- Anything beyond one family, one prompt, one scripted mistake, one task sentence in eight
  variants, one laptop and one server version. Nothing about hosted models or real agents.
- A controlled comparison between slots: each suite has its own seeded orders, and slots run one
  after another, not interleaved.
- Run 6's reminder arm is not repeated, so this does not show whether a reminder helps the 2B
  or the 9B.

## Where this departs from the consultant's advice

The consultant proposed 48 fixed assignments per size and day, sizes interleaved in blocks with
shared seeded orders, a 16-of-20 toy-tool pin as a gate, and a 24-trial Gemma anchor. The
released tool admits no run shorter than 10 rounds for this shape and does not share seeded
orders between suites, and this study writes no trial runner of its own. So: up to 160 trials per
run, whole suites in order and reversed on day 2, the clean run as the gate with the preflight
as a recorded check, and the same two runs for Gemma. The thresholds (25 and 10 points) are the
consultant's, restated as percentages.

## Order with Board-0, clock and publication

When Size-0 was registered, the orchestrator had seen Board-0's day-1 results and Board-0's
day 2 had yet to run. The first plan was to start after Board-0's last run. On 27 November the
maintainer moved Size-0's day 1 forward to that date, into the idle hours between Board-0's two
days on the same laptop and model server. The two studies never run at the same moment: a
Size-0 run holds Board-0's lock while it runs. No Size-0 run starts after 21:00 local time (IST)
on 27 November, and a Size-0 run still going at 23:15 is interrupted, so that Board-0's day 2
(00:05 on 28 November) starts on an idle server. Size-0's day 2 starts only after Board-0's last
run has finished.

The launcher admits runs strictly in the order above. An interrupted run, or a day-1 run not
started by 21:00, therefore blocks every later run. The finished rows are then published as
they are and the size reading is withheld.

Each slot gets a first preflight before any run is claimed, and the orchestrator uses those
probe times, and nothing else, to judge whether all eight day-1 runs fit before 21:00. If they
do not, no run is claimed on 27 November and day 1 starts after Board-0's last run instead.
That choice is made before any trial and is stated in the write-up.

The clock ends at 23:59 local time on 1 December 2026; runs not started by then are reported as
not started. Everything is published whatever it shows: this registration, the digest lists,
stores, receipts, counts and a write-up. No product code depends on the outcome.
