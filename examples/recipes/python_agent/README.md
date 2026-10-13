# Recipe: gate a retry-policy change in ten minutes

`app/v1.py` reserves an order with a bounded retry; `app/v2.py` is the same agent with the retry
removed. This recipe asks ARCI whether v2 is less reliable than v1 when the first `reserve` call
times out. The narrative version is [docs/recipes/python-agent.md](../../../docs/recipes/python-agent.md).

## Run it

From a clone of this repository, copy the tree out (the committed `arci.yaml` is exactly the file
the next command writes, so remove it from the copy; `arci init` never overwrites without `--force`):

```bash
cp -R examples/recipes/python_agent checkout && cd checkout && rm arci.yaml
```

Then the README's first-screen command, with this tree's task and fault added:

```bash
uv tool install agent-reliability-ci && arci init checkout-retry --baseline app.v1:run --candidate app.v2:run --toolset tests.world:make_world --oracle tests.world:passed --task '{"order_id": "order-7"}' --fault tool_timeout:reserve:0 && arci run arci.yaml
```

Until `agent-reliability-ci` is on PyPI, skip `uv tool install` and use the `arci` of the clone's
environment (`uv sync`, then `../.venv/bin/arci` from the copy if you made it inside the clone).

`arci init` imports the four references in a child process (with the current directory on its
import path), calls `make_world` once with the task and seed 0, checks that `reserve` is one of its
tools, and writes `arci.yaml`. `arci run arci.yaml` runs 8 trials per arm under the one fault
condition and stores them in `runs/checkout-retry/`.

## The files

| File | What it is |
|---|---|
| `app/v1.py` | `run(task, tools, rng)`: confirm; if the order is not held, `reserve` (up to 3 attempts), then confirm again |
| `app/v2.py` | the same with the retry removed: the first `reserve` fault ends the attempt |
| `tests/world.py` | `make_world(task, seed)`: tools `reserve` and `confirm`; 75% of seeds start with the order held, 20% have a reserve backend that times out twice; `passed(task, final_state)`: the order is confirmed |
| `arci.yaml` | what `arci init` writes for the command above (a test regenerates it and compares bytes) |

The oracle reads only the world's final state, never the agent's own claim. The fault
`tool_timeout` on `reserve` at occurrence 0 makes the first `reserve` call of every trial time out.

## What the smoke verdict means

Expect `VERDICT: INCONCLUSIVE (exit 2)` and two stderr lines that say so. Eight trials per arm is a
smoke design: under the default rule (alpha 0.05, delta 0.10, Clopper-Pearson) two perfect arms
cannot PASS below N=42, and only a total collapse can BLOCK at N=8. Here v2 still confirms every
order that arrived held (two of the eight seeds 0-7, so expect 8/8 against 2/8), so it does not
collapse to 0/8, and the interval on the difference crosses the margin. INCONCLUSIVE claims no regression and no safety; it says this N cannot tell.

## Choose a confirmatory N before running it

State the rates you expect (here: v1 about 0.95, v2 about 0.75 under the fault) and ask for the
smallest N that BLOCKs with probability at least 0.8:

```bash
arci plan --baseline-rate 0.95 --candidate-rate 0.75 --target-verdict BLOCK
```

The planner answers 400 per arm. Write that design as a new experiment before any of its trials:

```bash
arci init checkout-retry-n400 --baseline app.v1:run --candidate app.v2:run --toolset tests.world:make_world --oracle tests.world:passed --task '{"order_id": "order-7"}' --fault tool_timeout:reserve:0 --n 400 --out confirm.yaml
```

and append these two lines to `confirm.yaml`, so its seeds do not reuse the smoke run's and its
report lists the smoke run as an earlier run on this candidate:

```yaml
base_seed: 1000
prior_runs: ["checkout-retry"]
```

```bash
arci run confirm.yaml
```

Evaluate once at that N. Never grow N because a verdict disappointed you; that is the extension the
header of `arci.yaml` forbids.

## Look at a failing trial

At N=8, pair 0 has v1 passing and v2 failing:

```bash
arci diff runs/checkout-retry faults:00000:baseline faults:00000:candidate
arci minimize runs/checkout-retry faults:00000:candidate --out min.json
arci bundle runs/checkout-retry faults:00000:candidate --out bundle.json --root . --include app/v2.py --include tests/world.py
arci replay bundle.json
```

`diff` names the first divergence (v1 calls `reserve` again, v2 returns) and the injected fault
before it; `minimize` shows the one fault is needed; `replay` re-runs the bundle offline from its
recording and exits 0 when the failure reproduces.

## Recorded run

<<recorded run>>

## What this does not show

PASS would mean relative non-inferiority for this predeclared experiment (any drop from v1 to v2 is
smaller than delta), not that either version is reliable. The fault only fires when an agent calls
`reserve`: a trial whose order was already held never sees it, and a fault on a tool the agent
never calls silently never fires. The world is a seeded fixture, not your production backend, and
its 75% and 20% shares are made up. ARCI observes the calls that cross its tool boundary; it is not
a sandbox, and `arci init` and `arci run` import and run this code with your permissions. The
current directory is appended to the child's import path, so an installed top-level `tests`
package would shadow this tree's `tests`.
