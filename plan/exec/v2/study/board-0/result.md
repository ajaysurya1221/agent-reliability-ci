# Board-0

## M1 · day 1 · qwen3.5:4b-mlx-ctx32k

Clean tasks passing at least once: orders 8/8, calendar 8/8. Status: rated.
BLOCK at round 1. Clean plus measured elapsed time 98.65 seconds.

| Arm | Passes | Orders | Calendar | Retrieved | Exact |
|---|---:|---:|---:|---:|---:|
| stock-sentence | 16/16 | 8/8 | 8/8 | 16 | 0 |
| empty-as-given | 1/16 | 1/8 | 0/8 | 1 | 0 |

Pair signs minus 15, zero 1, plus 0, errored 0.

## M1 · day 2 · qwen3.5:4b-mlx-ctx32k

Clean tasks passing at least once: orders 8/8, calendar 8/8. Status: rated.
BLOCK at round 1. Clean plus measured elapsed time 95.12 seconds.

| Arm | Passes | Orders | Calendar | Retrieved | Exact |
|---|---:|---:|---:|---:|---:|
| stock-sentence | 16/16 | 8/8 | 8/8 | 16 | 0 |
| empty-as-given | 2/16 | 2/8 | 0/8 | 2 | 0 |

Pair signs minus 14, zero 2, plus 0, errored 0.

## M2 · day 1 · gemma4:12b-mlx-ctx32k

Clean tasks passing at least once: orders 8/8, calendar 7/8. Status: rated.
BLOCK at round 2. Clean plus measured elapsed time 145.65 seconds.

| Arm | Passes | Orders | Calendar | Retrieved | Exact |
|---|---:|---:|---:|---:|---:|
| stock-sentence | 27/32 | 16/16 | 11/16 | 30 | 0 |
| empty-as-given | 1/32 | 0/16 | 1/16 | 1 | 0 |

Pair signs minus 26, zero 6, plus 0, errored 0.

## M2 · day 2 · gemma4:12b-mlx-ctx32k

Clean tasks passing at least once: orders 8/8, calendar 7/8. Status: rated.
BLOCK at round 1. Clean plus measured elapsed time 109.86 seconds.

| Arm | Passes | Orders | Calendar | Retrieved | Exact |
|---|---:|---:|---:|---:|---:|
| stock-sentence | 14/16 | 8/8 | 6/8 | 15 | 0 |
| empty-as-given | 0/16 | 0/8 | 0/8 | 0 | 0 |

Pair signs minus 14, zero 2, plus 0, errored 0.

## M3 · day 1 · llama3.1:8b-ctx32k

Clean tasks passing at least once: orders 8/8, calendar 8/8. Status: rated.
BLOCK at round 1. Clean plus measured elapsed time 90.80 seconds.

| Arm | Passes | Orders | Calendar | Retrieved | Exact |
|---|---:|---:|---:|---:|---:|
| stock-sentence | 16/16 | 8/8 | 8/8 | 16 | 0 |
| empty-as-given | 0/16 | 0/8 | 0/8 | 0 | 0 |

Pair signs minus 16, zero 0, plus 0, errored 0.

## M3 · day 2 · llama3.1:8b-ctx32k

Clean tasks passing at least once: orders 8/8, calendar 8/8. Status: rated.
BLOCK at round 1. Clean plus measured elapsed time 90.73 seconds.

| Arm | Passes | Orders | Calendar | Retrieved | Exact |
|---|---:|---:|---:|---:|---:|
| stock-sentence | 15/16 | 7/8 | 8/8 | 16 | 0 |
| empty-as-given | 1/16 | 0/8 | 1/8 | 0 | 0 |

Pair signs minus 14, zero 2, plus 0, errored 0.

## M4 · day 1 · mistral-nemo:12b-ctx32k

Clean tasks passing at least once: orders 8/8, calendar 6/8. Status: rated.
PASS at round 5. Clean plus measured elapsed time 317.51 seconds.

| Arm | Passes | Orders | Calendar | Retrieved | Exact |
|---|---:|---:|---:|---:|---:|
| stock-sentence | 0/80 | 0/40 | 0/40 | 0 | 0 |
| empty-as-given | 0/80 | 0/40 | 0/40 | 0 | 0 |

Pair signs minus 0, zero 80, plus 0, errored 0.

## M4 · day 2 · mistral-nemo:12b-ctx32k

Clean tasks passing at least once: orders 8/8, calendar 4/8. Status: not rated.
PASS at round 5. Clean plus measured elapsed time 319.29 seconds.

| Arm | Passes | Orders | Calendar | Retrieved | Exact |
|---|---:|---:|---:|---:|---:|
| stock-sentence | 0/80 | 0/40 | 0/40 | 0 | 0 |
| empty-as-given | 0/80 | 0/40 | 0/40 | 0 | 0 |

Pair signs minus 0, zero 80, plus 0, errored 0.

## M5 · day 1 · qwen2.5:7b-ctx32k

Clean tasks passing at least once: orders 8/8, calendar 8/8. Status: rated.
PASS at round 2. Clean plus measured elapsed time 158.06 seconds.

| Arm | Passes | Orders | Calendar | Retrieved | Exact |
|---|---:|---:|---:|---:|---:|
| stock-sentence | 11/32 | 2/16 | 9/16 | 11 | 0 |
| empty-as-given | 30/32 | 16/16 | 14/16 | 30 | 0 |

Pair signs minus 2, zero 9, plus 21, errored 0.

## M5 · day 2 · qwen2.5:7b-ctx32k

Clean tasks passing at least once: orders 8/8, calendar 8/8. Status: rated.
PASS at round 2. Clean plus measured elapsed time 160.42 seconds.

| Arm | Passes | Orders | Calendar | Retrieved | Exact |
|---|---:|---:|---:|---:|---:|
| stock-sentence | 11/32 | 1/16 | 10/16 | 12 | 0 |
| empty-as-given | 29/32 | 16/16 | 13/16 | 30 | 0 |

Pair signs minus 3, zero 8, plus 21, errored 0.

## Criteria

| Slot | Day | BLOCK | PASS | INCONCLUSIVE | Orders stock | Orders empty | Calendar stock | Calendar empty |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| M1 | 1 | 1 | 0 | 0 | 8/8 | 1/8 | 8/8 | 0/8 |
| M1 | 2 | 1 | 0 | 0 | 8/8 | 2/8 | 8/8 | 0/8 |
| M2 | 1 | 1 | 0 | 0 | 16/16 | 0/16 | 11/16 | 1/16 |
| M2 | 2 | 1 | 0 | 0 | 8/8 | 0/8 | 6/8 | 0/8 |
| M3 | 1 | 1 | 0 | 0 | 8/8 | 0/8 | 8/8 | 0/8 |
| M3 | 2 | 1 | 0 | 0 | 7/8 | 0/8 | 8/8 | 1/8 |
| M4 | 1 | 0 | 1 | 0 | 0/40 | 0/40 | 0/40 | 0/40 |
| M4 | 2 | 0 | 1 | 0 | 0/40 | 0/40 | 0/40 | 0/40 |
| M5 | 1 | 0 | 1 | 0 | 2/16 | 16/16 | 9/16 | 14/16 |
| M5 | 2 | 0 | 1 | 0 | 1/16 | 16/16 | 10/16 | 13/16 |
