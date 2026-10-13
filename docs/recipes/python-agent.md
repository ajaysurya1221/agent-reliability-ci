# Gate a retry-policy change in ten minutes

You changed an agent: a teammate removed a "pointless" retry around a flaky tool. Every unit test
still passes, because a unit test calls the tool once and the tool works. This recipe asks the
question the unit tests cannot: when the tool fails transiently, is the new version less reliable
than the old one, by more than you are willing to accept?

The runnable tree is [examples/recipes/python_agent](../../examples/recipes/python_agent); its
[README](../../examples/recipes/python_agent/README.md) is the short version of this page. A test
(`tests/unit/recipes/test_python_agent.py`) runs the README's commands from a copy of the tree.

## What you bring

Four Python functions, referenced as `module:function`:

- the **baseline** agent, `app.v1:run`, and the **candidate**, `app.v2:run`. Both have the plain
  agent signature `run(task, tools, rng) -> dict`: they get the task, a tool box whose `call`
  goes through ARCI's boundary, and a seeded random generator. v1 confirms the order; if it is not
  held yet it calls `reserve` up to three times, then confirms again. v2 is v1 with the loop gone.
- a **toolset factory**, `tests.world:make_world(task, seed)`, which builds a fresh world per trial:
  an object with a `tools` mapping (`reserve`, `confirm`) and a `snapshot()` of its final state.
  The world is seeded: 75% of seeds start with the order already held, and 20% have a reserve
  backend that times out twice before it works. These shares are invented for the recipe.
- an **oracle**, `tests.world:passed(task, final_state)`, which decides success from the world's
  final state alone: the order in the task is confirmed. The agent's own claim is never the grade.

No gate or statistics code is copied into the tree; it is the agent, the world and the oracle.

## Step 1: scaffold and smoke-run

From a copy of the tree with the committed `arci.yaml` removed (`arci init` writes that same file
and never overwrites one without `--force`):

```bash
cp -R examples/recipes/python_agent checkout && cd checkout && rm arci.yaml
uv tool install agent-reliability-ci && arci init checkout-retry --baseline app.v1:run --candidate app.v2:run --toolset tests.world:make_world --oracle tests.world:passed --task '{"order_id": "order-7"}' --fault tool_timeout:reserve:0 && arci run arci.yaml
```

This is the README's first-screen command plus two flags for this tree: the task data and one
fault. Before any PyPI release, use the `arci` from a clone's `uv sync` environment instead of
`uv tool install`.

`arci init` validates before it writes. In one child process (the current directory on its
import path), it imports the four references, calls `make_world` once with the task and seed 0,
and checks that the fault's tool, `reserve`, is one the world offers. A typo fails here with one
line on stderr and exit 3, not after a hundred trials. It never calls the agents or the oracle.

`--fault tool_timeout:reserve:0` makes the first `reserve` call of every trial time out at the
tool boundary, in both arms. Both arms get the same seeds, so they face the same worlds.

## Step 2: read the smoke verdict

`arci init` writes 8 trials per arm, a smoke design, and `arci run` says so on stderr before the
first trial. Expect:

```text
VERDICT: INCONCLUSIVE (exit 2)
```

Why INCONCLUSIVE: the gate compares exact (Clopper-Pearson) bounds on the two success rates with
an allowed drop of delta 0.10 at alpha 0.05. At N=8 two perfect arms cannot PASS (that needs
N=42) and only a total collapse, 8/8 against 0/8, can BLOCK. v2 still confirms every order that
arrived held, so it never collapses completely, and the bounds on the difference cross the margin.
INCONCLUSIVE is a valid result: it claims neither a regression nor safety. It says that this N
cannot tell, and CI stays non-green.

## Step 3: plan the confirmatory run, then run it once

Plan from the rates you believe, not from the smoke result. If v1 is about 0.95 and v2 about
0.75 under the fault:

```bash
arci plan --baseline-rate 0.95 --candidate-rate 0.75 --target-verdict BLOCK
```

The planner enumerates every pair of success counts on its grid and reports the smallest N per arm
with P(BLOCK) >= 0.8: 400. These are probabilities under your assumptions, not observed power.

Write that design as a new experiment before running any of it:

```bash
arci init checkout-retry-n400 --baseline app.v1:run --candidate app.v2:run --toolset tests.world:make_world --oracle tests.world:passed --task '{"order_id": "order-7"}' --fault tool_timeout:reserve:0 --n 400 --out confirm.yaml
```

Append `base_seed: 1000` (fresh seeds, disjoint from the smoke run's) and
`prior_runs: ["checkout-retry"]` (the report then lists the smoke run as an earlier run on this
candidate) to `confirm.yaml`, then:

```bash
arci run confirm.yaml
```

Evaluate it once at N=400. Growing N because a verdict disappointed you is outcome-dependent
extension; the descriptor's header says never to do it, and
[docs/STATISTICS.md](../STATISTICS.md) explains why.

## Step 4: look at one failure

In the smoke run, pair 0 has v1 passing and v2 failing:

```bash
arci diff runs/checkout-retry faults:00000:baseline faults:00000:candidate
arci minimize runs/checkout-retry faults:00000:candidate --out min.json
arci bundle runs/checkout-retry faults:00000:candidate --out bundle.json --root . --include app/v2.py --include tests/world.py
arci replay bundle.json
```

- `diff` reports the first divergence: after the injected `tool_timeout`, v1 calls `reserve` again
  and v2 returns its result.
- `minimize` removes faults while the failure persists; with one fault the answer is that fault,
  1-minimal.
- `bundle` packs the trial, its recording and the named source files into one JSON file;
  `replay` re-runs it offline against the recording and exits 0 when the failure reproduces.

## Recorded run

The orchestrator's machine, one smoke run and one confirmatory run, with wall-clock times:

```text
$ arci init checkout-retry --baseline app.v1:run --candidate app.v2:run --toolset tests.world:make_world --oracle tests.world:passed --task '{"order_id": "order-7"}' --fault tool_timeout:reserve:0
arci run arci.yaml
exit 0
$ arci run arci.yaml
- None recorded.

## Reasons

- Experiment: no global errors.
- `faults`: bounds cross the margin

VERDICT: INCONCLUSIVE (exit 2)
exit 2
--- stderr ---
SMOKE DESIGN: n_per_arm=8 (alpha 0.05, delta 0.1, K=1): under the default rule two perfect arms cannot PASS below N=42 and a total collapse cannot BLOCK below N=8; expect INCONCLUSIVE. Plan a confirmatory N: arci plan --baseline-rate P --candidate-rate P --target-verdict BLOCK
INCONCLUSIVE at n_per_arm=8 is the expected smoke result; choose a confirmatory N with arci plan before re-running.
$ arci plan --baseline-rate 0.95 --candidate-rate 0.75 --target-verdict BLOCK
|---:|---:|---:|---:|---:|---|
| 20 | 40 | 0.000 | 0.000 | 1.000 | no |
| 50 | 100 | 0.000 | 0.016 | 0.984 | no |
| 100 | 200 | 0.000 | 0.093 | 0.907 | no |
| 200 | 400 | 0.000 | 0.365 | 0.635 | no |
| 400 | 800 | 0.000 | 0.828 | 0.172 | yes |

Result: smallest tested N per arm meeting P(BLOCK) >= 0.8: 400 (800 trials in total).

```

Recorded by the orchestrator on 2026-10-13 from a fresh copy of this directory, `PYTHONPATH` unset,
ARCI at the sprint's descriptor lane (the `arci run` output is cut to its last lines; the smoke run took 1.6 s
on a 15-core Apple Silicon Mac; the baseline passed 8/8 and the candidate 2/8). Counts depend on the seeds
in `arci.yaml`, so your run prints the same numbers; the verdict is INCONCLUSIVE because 8 pairs cannot decide.

## What this does not show

- **PASS is relative.** It would mean that, for this predeclared experiment, any drop from v1 to v2
  is smaller than delta. It never says either version is reliable.
- **A fault only fires on a call.** A trial whose order was already held never calls `reserve`, so
  the timeout never fires there; a fault on a tool your agent never calls silently never fires.
- **The world is a fixture.** Its shares are invented, and a verdict here is about this world, this
  task and this fault, not about your production backend.
- **Not a sandbox.** ARCI observes the calls that cross its tool boundary. `arci init` and
  `arci run` import and execute your code with your permissions.
- **Import path.** The current directory is appended to the child's import path (ADR 0006), so an
  installed top-level package called `app` or `tests` takes precedence over the tree's.
