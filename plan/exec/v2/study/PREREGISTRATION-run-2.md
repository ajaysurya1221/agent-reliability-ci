# Pre-registration, run 2: the same comparison with tool errors shown to the model

Written and pushed on 2026-11-13 before any run 2 trial. Run 1's pre-registration is
`PREREGISTRATION.md`; its result and correction are in `RESULT.md`.

## Why a second run

A reader of the r/LangChain thread (u/Significant_Tune9219) pointed out that run 1 could
not separate "the 4B model reasons worse" from "the 4B model needs tighter tool contracts":
a tool's `ValueError` crashed the trial, so the model never saw the error. Run 1's verdict
(BLOCK at round 1) stands for the experiment it registered. Run 2 asks a different
question. It is a second campaign on related data, chosen after seeing run 1, and it is
reported as such: the two results are not to be pooled, and neither replaces the other.

## Question

With a tool's `ValueError` returned to the model as an error message, is the agent built
on `qwen3.5:4b-mlx` non-inferior to the same agent built on `gemma4:12b-mlx`, within 10
percentage points of suite-mean success, on the same 24 tasks and four fault conditions?

## The one change from run 1

`order-desk-recoverable/agent.py` adds a middleware, `ReturnToolErrors`, after the retry
middleware, identical in both arms. It catches a `ValueError` raised by a tool and returns
`Error: <message>` to the model as a tool message with error status. No retry is added.
Everything else is as run 1: tools, system prompt, tasks, check, both models, temperature
0.7, reasoning off, 32k context, `per_round` seeds, budgets (12 tool calls, 12 model steps,
120 s), and the rule (alpha 1/20, delta 1/10, stakes {1/4, 1/2}, at most 5 rounds of 96
cells, errored-pair tolerance 5). Suite id:
`order-desk-gemma4-12b-vs-qwen3.5-4b-recoverable`.

## Software

ARCI 2.0.0 installed from PyPI (run 1 used a checkout at `804157a`; the adapter code is
the same). langchain 1.4.10, langchain-core 1.7.7, langgraph 1.2.20, langgraph-prebuilt
1.1.1, langchain-ollama 1.1.0. Ollama: ollama version is 0.32.14. Model ids: `gemma4:12b-mlx-ctx32k`
a5c533115db8, `qwen3.5:4b-mlx-ctx32k` c01efed5a364. Apple M5 Pro 24 GB, one worker.

File digests (SHA-256, first 16 hex): `arci.yaml` 53fe93623d8cf49f, `tasks.jsonl` d55e57de5a46df3e, `agent.py` 36e3bacf82fc61e6, `tools.py` 16a220b2f9d27664, `check.py` 42d579c6954ed2a2, `configuration.py` ea9dcf74c7b472aa, 

## What I looked at before writing this, and my expectation

A 12-trial smoke test of this configuration under a different suite id (not evidence):
the baseline passed 6 of 6; the candidate passed 4 of 6, hit a tool error in 4 trials and
recovered in 2 of them.

Expectation: **INCONCLUSIVE after 5 rounds**, with low confidence. I expect the candidate
to recover from some wrong first calls, which should bring the gap near the 10-point
margin, where this test needs many pairs. BLOCK is the next most likely outcome. I predicted
PASS for run 1 and was wrong.

## What will be published

The verdict whatever it is; per-arm success; the per-condition table; fault accounting;
and three descriptive counts from the stored trials, per arm: trials that never called
`lookup_order`, trials that received a tool error and passed, and trials that received a
tool error and failed. The descriptive counts decide nothing. No budget is changed after
the run. If the run ends in ERROR it is published as ERROR.

## Command

```sh
cd plan/exec/v2/study/order-desk-recoverable
export ARCI_QUICKSTART_BASELINE='ollama:gemma4:12b-mlx-ctx32k'
export ARCI_QUICKSTART_CANDIDATE='ollama:qwen3.5:4b-mlx-ctx32k'
export ARCI_QUICKSTART_TEMPERATURE=0.7
LANGSMITH_TRACING=false arci run arci.yaml --workers 1 --out ../runs-run-2
```
