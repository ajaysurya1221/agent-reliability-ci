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
with P(BLOCK) >= 0.8: 400, at P(BLOCK) 0.828. These are probabilities under your assumptions, not
observed power. `arci plan` assumes independent arms and does not model this recipe's shared seeds
and held-order state, so 0.828 is a planning figure under that assumption, not calibrated power for
this fixture.

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
[docs/STATISTICS.md](../STATISTICS.md) explains why. Its "Discipline" section adds the rule that
`prior_runs` serves: a new experiment id does not reset error control and does not license
retrying an unchanged candidate until it passes. Every run on this candidate stays listed.

## Step 4: look at one failure

In the smoke run, pair 0 has v1 passing and v2 failing:

```bash
arci diff runs/checkout-retry faults:00000:baseline faults:00000:candidate
arci minimize runs/checkout-retry faults:00000:candidate --out min.json
arci bundle runs/checkout-retry faults:00000:candidate --out bundle.json --root . --include app/__init__.py --include app/v2.py --include tests/__init__.py --include tests/world.py
arci replay bundle.json
```

- `diff` reports the first divergence: after the injected `tool_timeout`, v1 calls `reserve` again
  and v2 returns its result.
- `minimize` removes faults while the failure persists; with one fault the answer is that fault,
  1-minimal.
- `bundle` packs the trial, its recording and the named source files into one JSON file;
  `replay` re-runs it offline against the recording and exits 0 when the failure reproduces.
- Name both `__init__.py` files. Replay puts the bundle's directory first on the import path, and
  only as regular packages do the bundled `app` and `tests` shadow the working tree's. Without
  them the bundled directories are namespace portions, the tree's regular packages win, and replay
  runs whatever `app/v2.py` and `tests/world.py` say now, not what was bundled. The recipe's test
  edits both files after bundling: the full bundle still reproduces (exit 0); the bundle without
  the two `__init__.py` files does not (exit 1).

## Recorded run

Recorded on the maintainer's machine during the v0.8.0 sprint (2026-10-13; 15-core Apple Silicon
Mac; ARCI at the sprint's descriptor lane), from a fresh copy of the tree made as in step 1
(`arci.yaml` removed, `PYTHONPATH` unset, the clone's `.venv/bin/arci` on `PATH`, default 4
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
