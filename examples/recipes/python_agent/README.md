# Recipe: gate a retry-policy change

Ten minutes from the README to a validated first verdict is the target for this path, measured by
[the TTFV protocol](../../../docs/measurement/ttfv-protocol.md); no cold-reader receipt exists yet.

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

`agent-reliability-ci` has been on PyPI since v0.8.0. From a clone instead, use the clone's `arci`
(`uv sync`, then `../.venv/bin/arci` from the copy if you made it inside the clone).

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

Expect `VERDICT: INCONCLUSIVE (exit 2)`, two stderr lines that say so, and a third stderr line
naming the run store. Eight trials per arm is a
smoke design: under the default rule (alpha 0.05, delta 0.10, Clopper-Pearson) two perfect arms
cannot PASS below N=42, and only a total collapse can BLOCK at N=8. Here v2 still confirms every
order that arrived held (two of the eight seeds 0-7, so expect 8/8 against 2/8), so it does not
collapse to 0/8, and the interval on the difference crosses the margin. INCONCLUSIVE claims no
regression and no safety; it says this N cannot tell.

## Choose a confirmatory N before running it

State the rates you expect (here: v1 about 0.95, v2 about 0.75 under the fault) and ask for the
smallest N that BLOCKs with probability at least 0.8:

```bash
arci plan --baseline-rate 0.95 --candidate-rate 0.75 --target-verdict BLOCK
```

The planner answers 400 per arm (P(BLOCK) 0.828). `arci plan` assumes independent arms and does
not model this recipe's shared seeds and held-order state, so 0.828 is a planning figure under that
assumption, not calibrated power for this fixture. Write that design as a new experiment before
any of its trials:

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
header of `arci.yaml` forbids. As the "Discipline" section of
[docs/STATISTICS.md](../../../docs/STATISTICS.md) puts it, a new experiment id does not reset error
control and does not license retrying an unchanged candidate until it passes: `prior_runs` keeps
the smoke run in view, and every later run on this candidate belongs there too.

## Look at a failing trial

At N=8, pair 0 has v1 passing and v2 failing:

```bash
arci diff runs/checkout-retry faults:00000:baseline faults:00000:candidate
arci minimize runs/checkout-retry faults:00000:candidate --out min.json
arci bundle runs/checkout-retry faults:00000:candidate --out bundle.json --root . --include app/__init__.py --include app/v2.py --include tests/__init__.py --include tests/world.py
arci replay bundle.json
```

`diff` names the first divergence (v1 calls `reserve` again, v2 returns) and the injected fault
before it; `minimize` shows the one fault is needed; `replay` re-runs the bundle offline from its
recording and exits 0 when the failure reproduces. Name both `__init__.py` files: replay puts the
bundle's directory first on the import path, and only as regular packages do the bundled `app` and
`tests` shadow this tree's. Without them the tree's current `app/v2.py` and `tests/world.py` run
instead of the bundled ones (a test edits both after bundling to show it).

## Recorded run

Recorded on the maintainer's machine during the v0.8.0 sprint (2026-10-13; 15-core Apple Silicon
Mac; ARCI at the sprint's descriptor lane), from a fresh copy of this directory made as in "Run
it" (`arci.yaml` removed, `PYTHONPATH` unset, the clone's `.venv/bin/arci` on `PATH`, default 4
workers). `[...]` marks output left out. The blocks, in order: `arci init` and its one line of
output; the smoke run's stderr (the two smoke notices), its condition table, its verdict line and
its wall time; the planner's table, its result and its "No pairing" assumption; the confirmatory
descriptor, its two appended lines, and that run's condition table, its "Earlier runs" section,
its verdict line and its wall time.

```text
$ arci init checkout-retry --baseline app.v1:run --candidate app.v2:run --toolset tests.world:make_world --oracle tests.world:passed --task '{"order_id": "order-7"}' --fault tool_timeout:reserve:0
arci run arci.yaml
```

```text
$ /usr/bin/time -p arci run arci.yaml
--- stderr ---
SMOKE DESIGN: n_per_arm=8 (alpha 0.05, delta 0.1, K=1): under this design's fixed-sample Clopper–Pearson rule two perfect arms cannot PASS below N=42 and a total collapse cannot BLOCK below N=8; expect INCONCLUSIVE. Plan a confirmatory N: arci plan --baseline-rate P --candidate-rate P --target-verdict BLOCK
INCONCLUSIVE at n_per_arm=8 is the expected smoke result; choose a confirmatory N with arci plan before re-running.
--- stdout, from its condition table ---
## Condition: faults

| Measure | Baseline | Candidate / condition |
|---|---:|---:|
| Role | — | Gating |
| n | 8 | 8 |
| Successes | 8 | 2 |
| Success rate | 100.0% | 25.0% |
| Wilson 95% (display only) | [0.6756, 1.0000] | [0.0715, 0.5907] |
| Clopper-Pearson (97.5000%) | [0.5782, 1.0000] | [0.0221, 0.6942] |
| Bounds on difference, clopper_pearson (candidate - baseline) | — | [-0.9779, 0.1160] |
| Candidate hard violations | — | 0 |
| Condition verdict | — | **INCONCLUSIVE** |
[...]
VERDICT: INCONCLUSIVE (exit 2)
--- /usr/bin/time -p ---
real 1.60
user 4.85
sys 0.44
```

```text
$ arci plan --baseline-rate 0.95 --candidate-rate 0.75 --target-verdict BLOCK
[...]
| N per arm | Total trials | P(PASS) | P(BLOCK) | P(INCONCLUSIVE) | Meets target |
|---:|---:|---:|---:|---:|---|
| 20 | 40 | 0.000 | 0.000 | 1.000 | no |
| 50 | 100 | 0.000 | 0.016 | 0.984 | no |
| 100 | 200 | 0.000 | 0.093 | 0.907 | no |
| 200 | 400 | 0.000 | 0.365 | 0.635 | no |
| 400 | 800 | 0.000 | 0.828 | 0.172 | yes |

Result: smallest tested N per arm meeting P(BLOCK) >= 0.8: 400 (800 trials in total).
[...]
Assumptions: [...] No pairing: shared seeds or any other dependence between the arms is not modelled. [...]
```

```text
$ arci init checkout-retry-n400 --baseline app.v1:run --candidate app.v2:run --toolset tests.world:make_world --oracle tests.world:passed --task '{"order_id": "order-7"}' --fault tool_timeout:reserve:0 --n 400 --out confirm.yaml
arci run confirm.yaml
$ printf 'base_seed: 1000\nprior_runs: ["checkout-retry"]\n' >> confirm.yaml
$ /usr/bin/time -p arci run confirm.yaml
--- stderr: empty (no smoke notice at N=400) ---
--- stdout, from its condition table ---
## Condition: faults

| Measure | Baseline | Candidate / condition |
|---|---:|---:|
| Role | — | Gating |
| n | 400 | 400 |
| Successes | 390 | 296 |
| Success rate | 97.5% | 74.0% |
| Wilson 95% (display only) | [0.9546, 0.9864] | [0.6949, 0.7806] |
| Clopper-Pearson (97.5000%) | [0.9513, 0.9892] | [0.6875, 0.7880] |
| Bounds on difference, clopper_pearson (candidate - baseline) | — | [-0.3018, -0.1633] |
| Candidate hard violations | — | 0 |
| Condition verdict | — | **BLOCK** |
[...]
## Earlier runs on this candidate are never hidden

- `checkout-retry`
[...]
VERDICT: BLOCK (exit 1)
--- /usr/bin/time -p ---
real 96.65
user 288.65
sys 32.55
```

The smoke run passed 8/8 against 2/8 and is INCONCLUSIVE, because 8 pairs cannot decide anything
short of a total collapse. The confirmatory run passed 390/400 against 296/400; the bounds on the
difference, [-0.3018, -0.1633], lie wholly below -delta (-0.10), so it BLOCKs, and its report lists
the smoke run `checkout-retry` as an earlier run on this candidate. The trials are seeded by the
descriptors, so the same files give the same counts on your machine; wall times differ.

## What this does not show

PASS would mean relative non-inferiority for this predeclared experiment (any drop from v1 to v2 is
smaller than delta), not that either version is reliable. The fault only fires when an agent calls
`reserve`: a trial whose order was already held never sees it, and a fault on a tool the agent
never calls silently never fires. The world is a seeded fixture, not your production backend, and
its 75% and 20% shares are made up. ARCI observes the calls that cross its tool boundary; it is not
a sandbox, and `arci init` and `arci run` import and run this code with your permissions. The
current directory is appended to the child's import path, so an installed top-level `tests`
package would shadow this tree's `tests`.
