# Pilot S4: two local models on the LangChain quickstart (2026-11-11)

Run by a worker agent with `pilot.py` on a copy of the example (longer budgets only), one
session at a time, Ollama 0.32.14 on an Apple M5 Pro with 24 GB. Raw rows: `results.json`
(144 sessions). Temperature 0, reasoning mode off, 32k context variants. No spend.

| Model | Condition, settings | Sessions | Pass | Median s | 90th pct s | Ended |
|---|---|---|---|---|---|---|
| gemma4:12b-mlx | clean | 24 | 67% | 4.6 | 5.6 | 24 completed |
| gemma4:12b-mlx | tool_timeout, with retry | 24 | 67% | 5.8 | 7.4 | 24 completed |
| gemma4:12b-mlx | tool_timeout, no retry | 24 | 67% | 6.0 | 7.4 | 24 completed |
| qwen3.5:4b-mlx | clean | 24 | 79% | 3.6 | 4.6 | 19 completed, 5 crash |
| qwen3.5:4b-mlx | tool_timeout, with retry | 24 | 79% | 3.4 | 3.7 | 19 completed, 5 crash |
| qwen3.5:4b-mlx | tool_timeout, no retry | 24 | 71% | 4.3 | 5.6 | 19 completed, 5 crash |

## What this establishes

- The whole path works with real local models: tool calls happen, faults fire, trials are
  graded. No trial ended as a harness or infrastructure ERROR.
- A session takes 4 to 7 seconds. A 400-pair study (800 sessions) at one worker is about
  70 minutes per model pairing.
- Both models are usable but far from perfect on these tasks, which is what a study needs.

## What it shows must change before a study

1. **Temperature 0 makes every repetition identical.** Failures are the same tasks every
   time (gemma fails all 8 plain "refund" tasks; qwen crashes on the same 5 with
   `ValueError: unknown SKU`). Rounds would be copies of each other, so the study must run
   at a temperature above 0 with `scenario_seeds: per_round`, the same for both arms.
2. **The plain refund tasks need a look.** One model failing all 8 of one task type in the
   clean condition suggests the check or the prompt is stricter than the task text says.
3. **A tool that raises `ValueError` on a wrong argument crashes the run** for both
   settings; the example's retry policy does not cover it. That is realistic agent
   behaviour, but the example should say so.
4. With these models the planted "no retry" difference barely shows under `tool_timeout`
   (79% against 71% for qwen, none for gemma): the models retry on their own. The public
   study should compare the two models, not the retry setting.

Not measured: higher temperatures, more than one worker, the other two fault conditions.
