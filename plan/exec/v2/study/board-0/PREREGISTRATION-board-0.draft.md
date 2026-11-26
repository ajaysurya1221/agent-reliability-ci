# Registration, benchmark Board-0: after an empty tool result, which local models still finish

Registered 27 November 2026, before any Board task was shown to any model in this study. The
file keeps its draft name because the digest list and the launcher pin it. Decision D-35 in
`plan/exec/v2/DECISIONS.md` gives the reasons for the design.

## The question, in plain words

An agent is a language model that calls tools, such as "look up this order". Sometimes a tool
answers with nothing at all. Board-0 asks, for five small models that run on one laptop:

1. After a lookup comes back empty, does the model still finish the task?
2. Does one stock sentence in place of the empty text fix it?

Each model gets one comparison, run on two days. The result would be a small table with one row
per model. The criteria below say when such a table is worth keeping, and when it is not.

## What was done before this registration

- A check of four sources for a prior result (arXiv 2609.35381, 2611.11581, 2610.10062 and
  tool-eval-bench): none reports recovery after an empty tool result split by reply wording on
  local models. Two of the papers were not read to the end.
- Two consults with Astra (GPT-6.2, a different maker's model), on the design and on grading.
- Three models were downloaded with `ollama pull` and given a 32768-token context alias.
- A capability probe: three requests to each downloaded model with a made-up tool
  (`read_marker`) and an ask that is in no task. It showed that these models often answer in
  plain text instead of calling an answer tool, so the answer tool of the first design was
  removed. In each of the three single requests with an empty tool text the model answered
  without calling the tool again. No Board task and no Board reply text was shown.
- Offline rehearsals of the harness with a stand-in for the model, a hostile review of the
  harness by a separate agent, three rounds of fixes, and one native rehearsal of the live path
  against a fake model server (no real model was running).
- The two models installed earlier have seen the eight order-desk questions in Reply-0 and
  runs 2 to 6 (a different prompt, a different sentence, and "answer only" grading). In
  Reply-0's control the empty arm scored 0 of 16 on the 4B model and 6 of 24 on the 12B model.
  The calendar tasks are new to every model.

## Models

Ollama `0.32.14`, one request at a time, temperature 0.7, reasoning off, context 32768, no
sampling seed sent. Tags and digests as `ollama` reports them; `models.json` pins them.

| Slot | Tag | Digest (sha256) | Maker |
|---|---|---|---|
| M1 | `qwen3.5:4b-mlx-ctx32k` | `c01efed5a36459ab6ffffa0b158636a014d8b30b4d5493167cba9916ed558430` | Alibaba |
| M2 | `gemma4:12b-mlx-ctx32k` | `a5c533115db870b8db2e39657686a8742a5e7182bd00403b851dd1af28e4efbc` | Google |
| M3 | `llama3.1:8b-ctx32k` | `d3d6951729aeb9bbb6a4e89e5b401a3880c215bbf2dd8b22e5ac5809b0e03da5` | Meta |
| M4 | `mistral-nemo:12b-ctx32k` | `5db84f35b28438e5eb4e04f8853c8f4480a87d035b23e2f9228a63b787060869` | Mistral |
| M5 | `granite3.3:8b-ctx32k` | `dafa440a1f5ba3bd1f636f0c584ed7b8005a1e764ffc4027d08c69e978eb65d9` | IBM |

M3 to M5 are `FROM` the library tags `llama3.1:8b` (`46e0c10c039e`), `mistral-nemo:12b`
(`e7e06d107c6c`) and `granite3.3:8b` (`fd429f23b909`) with `PARAMETER num_ctx 32768` and
nothing else. M1 is "the 4B model" of the earlier runs.

Pin check, per model, after the push and before any Board task: 20 probes in which the model
itself must call a toy tool and then answer with a random token that appears only in the toy
result; at least 16 of 20 must pass. Two more probes check that an empty tool text is sent as
`""` and that the next response completes. No probe requires a retry. A model that fails its
pin is replaced once by the next spare, `qwen2.5:7b` and then `llama3.2:3b` (same alias
recipe, same pin), through one pushed amendment that names the failed pin output, before that
slot's clean row. If fewer than five models pass a pin, the board runs with those that do and
K1 to K4 are read as written, with the missing model-days counted as undecided.

## Tasks, arms and the trial

- Sixteen tasks a round, in two families of eight with equal weight: `orders` (`O-o1` to
  `O-o8`, "How many cents were paid in total for order ORD-...?") and `calendar` (`K-k1` to
  `K-k8`, six different fields of an event, both integers and strings). The calendar family was
  written by a worker that was told not to read any earlier run or result. Values come from a
  seeded world; a different seed gives different values.
- System prompt, the same for every trial: "You answer questions by using the tools you are
  given. Call a tool when you need information. Never invent a tool result. When you know the
  answer, reply with the answer." No retry hint anywhere.
- Opening: the harness makes the task's correct lookup. ARCI's `empty_result` fault blanks that
  first result once. The audit checks the original result against the seeded record, the
  blanking, and the exact text sent in each arm. After that the model is free.
- Candidate arm, `empty-as-given`: the tool message is the empty string.
- Baseline arm, `stock-sentence`: the tool message is "The lookup returned no data. Repeat the
  same call with the same arguments."
- So BLOCK means: with the empty text this model is worse than with the sentence by more than
  ten points. PASS means: it is not worse by more than ten points.
- Budget per trial: 12 charged tool calls, eight chat requests, 120 seconds, 20 seconds grading.
- The trial ends at the model's first message without a tool call. That text is graded.

## Grading: one right value and no wrong one

The key is the asked field of the seeded record. Decoys are every other value of the same type
(integer or string) anywhere in that seeded world; field names are not values. The row's own order or event id is removed
from the text first.

- Integer key: PASS if a number in the text equals the key and no number in the text equals a
  decoy. Thousands separators are allowed; digits inside a longer number or a decimal do not
  count.
- String key: PASS if the text contains the key, case-sensitive, as whole words, and contains
  no decoy, the longest match winning where two overlap.
- Empty text, no final message within the budget, or a timeout: FAIL.

Astra advised a stricter rule (a fixed list of sentence forms). It was not taken: Reply-0 lost
14 to 36 of 120 trials per arm on the 4B model to right answers in extra words, and a list of
forms would fail correct wordings at rates that differ by model. The rule here can pass a text
that names the right value while denying it; that needs the model to know the value. Every
final text is published, and the number of answers that equal the key exactly is shown beside
each arm, so a reader can apply a stricter rule.

## Rule and size

Released ARCI 2.4.1: alpha 1/20, margin 1/10, stakes 1/4 and 1/2, threshold 40 each way,
per-round scenario seeds, read at round ends, four tolerated errored pairs. At most 26 rounds of
16 pairs (416 pairs, 832 trials) per model and day: the largest cap for which the released
`arci plan` gives exact projections for the whole grid below (30 and 32 rounds exceed its work
limit). Projections for 16 by 26, independent arms, the same rates in every task and round, no
errors (`projections/registered-rows.json` has the exact fractions and the 20-round rows):

| Sentence/empty | PASS | BLOCK | CANNOT TELL | Mean pairs |
|---|---:|---:|---:|---:|
| 100/100 | 1.000 | 0.000 | 0.000 | 80 |
| 90/90 | 0.973 | 0.000 | 0.027 | 173 |
| 75/75 | 0.719 | 0.000 | 0.281 | 273 |
| 50/50 | 0.543 | 0.000 | 0.457 | 311 |
| 90/80 | 0.012 | 0.011 | 0.977 | 411 |
| 90/70 | 0.000 | 0.839 | 0.161 | 240 |
| 75/55 | 0.000 | 0.638 | 0.362 | 295 |
| 75/45 | 0.000 | 0.999 | 0.001 | 112 |
| 100/25 | 0.000 | 1.000 | 0.000 | 26 |

A true gap of exactly ten points almost always ends in CANNOT TELL. That is the rule working as
designed and it counts against K4.

## Clean row, days and order

- Clean row, per model and day, before its measured run: every task twice with the opening
  lookup not blanked (32 trials). A model-day is "rated" if in each family at least 6 of the 8
  tasks pass at least one of their two clean trials. All 16 tasks stay in the measured run. An
  unrated model-day still runs and is reported as "not rated"; it is not a decision.
- Day 1: pin M1 to M5, then clean and measured run for M1, M2, M3, M4, M5 in that order.
- Day 2, on a later local calendar date: clean and measured run for M5, M4, M3, M2, M1.
- The descriptors of both days are generated and their digests pushed before day 1, so both
  days' seeds are fixed, and they differ between the days.
- One start per run. One live run at a time. An interrupted run is not restarted and counts
  as undecided. The clock ends at 23:59 local time on 29 November 2026.

## Criteria

A "decision" is a statistical PASS or BLOCK of a rated model-day whose run satisfies R1 to R4.
CANNOT TELL, ERROR, not rated, not run and a hard-violation BLOCK are not decisions.

- **K1, reach.** On day 1 at least 2 of M2 to M5 give BLOCK, and on at least one of those the
  empty arm is 20 percentage points or more below the sentence arm in each family.
- **K2, a reason for a table.** On day 1 at least one model gives BLOCK and at least one other
  gives PASS, and that PASS model passes at least 75% of its empty-arm trials in each family.
- **K3, the same on both days.** No model has PASS on one day and BLOCK on the other. Of the
  day-1 decisions, at least 80% (rounded up) are the same decision on day 2. No day-1 decision
  at all fails K3.
- **K4, decided at a usable cost.** At least 7 of the 10 model-days are decisions, and the
  median time of a model-day (clean plus measured run, claim to end of verification) is at
  most 60 minutes.
- **K5, checkable.** A fresh agent with one evidence zip, its separately published digest, the
  study checker and released ARCI, working offline, reproduces 10 of 10 stored verdicts,
  regrades every trial, and rejects 3 of 3 copies altered in one grade, the rule, or the
  decision.

Reading conditions for every run that counts:

- R1. This registration, the input digests and the descriptor digests were pushed first; model
  digests, Ollama version and context match at admission.
- R2. One ledger record and one receipt per scheduled trial through the stopping round; the
  original opening result equals the seeded record; the delivered text is the arm's text.
- R3. No crash; at most 5% of an arm's trials hit 120 seconds.
- R4. `arci gate` prints `stored decision: MATCH`; the audit is clean; the two independent
  counts agree.

**What a miss stops** (the maintainer's choice of 26 November): if K1, K2 or K3 misses, the
numbers are published and work on the Board stops. Any other feature needs its own evidence
first. If only K4 or K5 misses, one registered repair and one rerun are allowed; a second miss
stops the Board. On a pass of all five: the dated table, both days' counts by family, the exact
prompt and texts, the evidence zip and rerun instructions are published in the repository, and
an `arci board` command may then be built as additive modules. Thirty days after that, one row
run and sent in by someone outside the project, or three outside questions about recovery,
count as it having mattered; otherwise the table is frozen as a dated record.

## Predictions

- The consultant (Astra): about 25% that all five criteria hold; K2 the likeliest miss, about
  60%, because both earlier models struggled with the blank and no model is known to recover
  unaided at 75% in each family.
- The orchestrator (Claude): M1 BLOCK and M2 BLOCK on both days. At least one of M3 to M5
  BLOCK, so K1 holds. No rated PASS with 75% in each family on day 1, so K2 misses and the
  table is flat. K3 holds if read. K4 holds unless two models fail the clean rating. Overall:
  fail, about 25% pass.
- The maintainer: none supplied before registration.

## Not claimed, now or after a pass

That reply wording changes recovery (arXiv 2609.35381, 2611.11581, 2610.10062, 2609.00072,
2610.32555). That a recovery benchmark on local models, an empty-result test, a fault proxy or
grading without a judge model is new (tool-eval-bench, AgentCheck, MCP-Injector,
mcp-fault-bench). That five small local models, three of them from 2024 and 2025, speak for
hosted models, for larger models or for real agents. That the opening lookup happens this way
in real use: it is scripted and blanked by the harness. That BLOCK means "ship this sentence".
That anyone asked for this table. Nothing is filed on anyone else's tracker.

## Launch and publication

Runs start only from a neutral checkout at the pushed commit, with the pinned environment.
Before any live request the launcher verifies that every pinned input exists at the pushed
commit with the registered digest. Claims are taken atomically in one study-wide directory and
kept after an interruption. Publish only the allowlist of `harness/INTERFACE.md`: this file,
the digest lists, `models.json`, `tasks/`, `orderdesk/`, the three calendar files,
`projections/`, the harness sources, `pins/`, `clean/`, `scenario-collisions.json`, the files
of each scheduled `runs/RUN/`, and `result.md`. Scan everything for personal paths first.
Report every scheduled, missed, refused and interrupted run. No retries, extra rounds or tasks.
A blind recount by an agent that reads no write-up precedes the result.
