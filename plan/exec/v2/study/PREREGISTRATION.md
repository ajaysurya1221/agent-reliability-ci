# Pre-registration: can a 4B local model replace a 12B one on the order-desk suite?

Written and pushed on 2026-11-11 before any study trial was run. The run command at the end
is the only one that produces study evidence. Every attempt is kept, including invalid ones.

## Question

On the 24-task order-desk suite under four tool-fault conditions, is the agent built on
`qwen3.5:4b-mlx` (candidate) non-inferior to the same agent built on `gemma4:12b-mlx`
(baseline), within a margin of 10 percentage points of suite-mean success?

## What is registered (`order-desk/arci.yaml`, `order-desk/tasks.jsonl`)

| Item | Value |
|---|---|
| Baseline | `ollama:gemma4:12b-mlx-ctx32k` |
| Candidate | `ollama:qwen3.5:4b-mlx-ctx32k` |
| Everything else | identical in both arms: tools, system prompt, tool-retry middleware (one retry), temperature 0.7, reasoning mode off, 32k context |
| Tasks | 24 (`desk-01` to `desk-24`) |
| Conditions | clean, `tool_timeout`, `tool_error_once`, `empty_result`, each on the first `lookup_order` call |
| Cells | 96 |
| Rule | defaults: alpha 1/20, delta 1/10, stakes {1/4, 1/2}, at most 5 rounds (480 pairs, 960 sessions), errored-pair tolerance 5 |
| Seeds | `per_round` |
| Budgets per trial | 12 tool calls, 12 model steps, 120 s |
| Check | `order-desk/check.py`, unchanged from the example |
| Software | ARCI at commit `804157a` (branch `v2/integration`), langchain 1.4.10, langchain-ollama 1.1.0, Ollama 0.32.14, Apple M5 Pro 24 GB, one worker |

The only change from the shipped example: both arms keep the retry middleware, so the arms
differ in the model alone (`agent.py`, one line).

File digests (SHA-256, first 16 hex): `arci.yaml` 8719c6d8d4c8462d, `tasks.jsonl`
d55e57de5a46df3e, `agent.py` 8d2eb5c11f0dcc2e, `tools.py` 16a220b2f9d27664, `check.py`
42d579c6954ed2a2.

## Expectation, written before the run

PASS, with low confidence. In the pilot at temperature 0 (an earlier version of the check)
qwen passed 79% of clean sessions and gemma 67%. A 12-trial smoke test of this exact
configuration, under a different suite id, passed 12 of 12 on both models. I do not know
how either model behaves under `tool_error_once` and `empty_result`, which the pilot did
not cover. INCONCLUSIVE is plausible if the models trade wins across task types.

## What the guarantee does and does not cover

With `per_round` seeds the 2.5% bound on each directional error holds on one condition that
ARCI does not check: in every round, the suite mean over that round's scenario instances
obeys the null. Outcomes must also be independent across cells and rounds. Both models run
on one machine through one Ollama server, one session at a time; a server fault would hit
whichever arm is running and is recorded as an errored pair, not as an agent failure.

## What will be published

The verdict whatever it is, the stopping round, per-arm success, the per-cell table, fault
accounting, the run store, and the HTML report. If the run ends in ERROR it is published as
ERROR; a second run is a new campaign and is labelled as such with this one in its
`prior_runs`. No budget is enlarged after the fact.

## Command

```sh
cd plan/exec/v2/study/order-desk
export ARCI_QUICKSTART_BASELINE='ollama:gemma4:12b-mlx-ctx32k'
export ARCI_QUICKSTART_CANDIDATE='ollama:qwen3.5:4b-mlx-ctx32k'
export ARCI_QUICKSTART_TEMPERATURE=0.7
LANGSMITH_TRACING=false arci run arci.yaml --workers 1 --out ../runs
```
