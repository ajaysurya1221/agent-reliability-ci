# TASK P3b: LangChain quickstart example, recipe and `arci init --langchain`

Worktree `/Users/ajay/Developer/.arci-worktrees/wt-v2-integration` (branch `v2/integration`:
the suite lane and the adapter lane merged, LangChain installed in `.venv` through the new
`adapters` dependency group). Work only there. No state-changing git, no network, no new
dependency. Frozen files are listed in `FROZEN.sha256` (64 entries); do not touch them.

Read: `AGENTS.md`; `src/arci/adapters/langchain.py` (its docstring lists the limits);
`src/arci/init.py` and `docs/design/0008-arci-init.md`; `src/arci/descriptor.py` (suite
descriptors); `src/arci/demo/suite.py`; `examples/recipes/`, `docs/recipes/` and
`tests/unit/recipes/`, `tests/unit/examples/`, `tests/unit/init/` for house style; decisions
D-06 and D-08 in `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/DECISIONS.md`.

## Build

1. **`examples/langchain_quickstart/`**: what a real user would write, and nothing more.
   - `tools.py`: three or four realistic tools over a small seeded in-memory store (for
     example an order desk: look up an order, check stock, issue a refund, add a note),
     returned as a `ToolEnv` whose `snapshot` is the store's final state. The seed varies
     the data so that tasks are not memorisable.
   - `tasks.jsonl`: 24 tasks with ids, a string `input` and the facts the check needs.
     Tasks must need one to four tool calls and have one checkable right end state.
   - `agent.py`: `make_adapter(...)` with a baseline and a candidate settings function. The
     model comes from the environment: `ARCI_QUICKSTART_BASELINE` and
     `ARCI_QUICKSTART_CANDIDATE`, each `provider:model` as `langchain.chat_models.init_chat_model`
     accepts (for example `ollama:qwen3.5:4b-mlx-ctx32k`), with temperature and any
     reasoning mode set identically for both arms in code. When the variables are unset the
     example uses a scripted offline model defined in `offline_model.py` (a fake chat model
     that solves most tasks and, for the candidate, mishandles tool errors) so that the
     example and CI run with no model and no network. The baseline uses
     `ToolRetryMiddleware`; say in a comment why.
   - `check.py`: `check(task, final_state) -> bool` over the snapshot; imports no agent
     framework.
   - `arci.yaml`: a suite descriptor: the 24 tasks, four conditions (clean,
     `tool_timeout`, `tool_error_once`, `empty_result` on sensible tools), default rule.
     With the offline models the run must end in a verdict the README states in advance,
     with probability at least 0.999 (compute it in a test with
     `suite_stats.operating_characteristics`, or make the offline models seed-deterministic
     by construction and say so).
   - `README.md`: the five steps from an empty virtual environment to a verdict; what each
     file is; how to switch to a real model; every limit the adapter's docstring lists, in
     plain words; that provider retries belong in the model client's settings; that
     `fault_exceptions` is keyed by fault kind; the `langsmith` tracing note of ADR 0012.
2. **`docs/recipes/langchain.md`**: the recipe: when to use the adapter, the adapter file
   line by line, the snapshot contract, what is rejected and why, FAIL versus ERROR for
   every failure source (table), replay limits, cost per trial. Link it from the recipes
   index if one exists (not from frozen files).
3. **`arci init --langchain`** (`src/arci/init.py`): scaffolds the same five files into the
   current directory, adapted to placeholders, with the offline model so that
   `arci run arci.yaml` works immediately after `pip install 'agent-reliability-ci[langchain]'`.
   Follow ADR 0008's rules for `arci init` (no overwrite, exact messages, exit codes).
   Without LangChain installed it prints the one-line install hint and exits 3; plain
   `arci init` is unchanged.
4. **First five minutes, scripted**: `tests/unit/examples/test_langchain_quickstart.py`
   (guarded like the adapter tests) runs the example end to end through `subprocess`:
   `arci run`, `arci gate`, the stated verdict and exit code; and
   `tests/unit/init/test_init_langchain.py` scaffolds into a temp directory and runs it.
   Record wall-clock time of the example run in your report. Keep each under two minutes
   (fewer workers, small `max_rounds` in the test copy if needed, stated).
5. Type checking: add the new LangChain-importing paths to `pyrightconfig.adapters.json`
   and, if they must be excluded from the core check, say exactly which `pyproject.toml`
   exclusion the orchestrator must add (you cannot edit it; it is frozen). Prefer placing
   LangChain-importing test code under `tests/unit/adapters/` so no frozen change is needed.

## Acceptance (worktree root; LangChain is installed)

```sh
LANGSMITH_TRACING=false ARCI_REQUIRE_ADAPTERS=1 .venv/bin/pytest tests/unit/adapters tests/unit/examples tests/unit/init tests/unit/recipes -q
LANGSMITH_TRACING=false .venv/bin/pytest -q
.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/basedpyright
.venv/bin/basedpyright --project pyrightconfig.adapters.json
shasum -a 256 -c FROZEN.sha256
```

The core environment has no LangChain: nothing outside the guarded tests may import it, and
the core type check must stay clean without it (the orchestrator re-runs both
environments). Sandbox note as before. Stop and report if a frozen file blocks you.

Report under 60 lines: files; command tails; the example's verdict, rounds and wall time;
lines of user-written code in the example by file; anything a frozen file prevented.
