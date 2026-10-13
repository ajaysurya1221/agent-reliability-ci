# 0006: the current directory is on the child import path (v0.8.0)

Decision by the orchestrator (Claude Fable 5.1), reviewed by the read-only consultant
(gpt-6-astra, xhigh) and an independent Opus 5.5 reviewer on 2026-10-13. Part of the v0.8.0
onboarding sprint (plan/exec/PLAN.md, task 04).

## Problem

Every `module:function` reference in a manifest is resolved inside a child process (the worker for
agents and toolsets, the grader for oracles and snapshots, the boundary for decision fixtures), never
in the parent. The child starts as `sys.executable -P` with `PYTHONPATH` rebuilt from the parent's
`sys.path` (docs/AGENT_SEMANTICS.md, "children receive the parent's sys.path through PYTHONPATH").

Under `python -m arci.cli` the parent's `sys.path` begins with `""`, which `_pythonpath` maps to the
current directory, so a project's own modules resolve. Under the `arci` console script (a PyPI or
`uvx` install) the parent's `sys.path` begins with the script's `bin` directory instead, and the
current directory is absent. The same manifest therefore runs under `python -m arci.cli` and fails
every trial with `ERROR/harness_error` under `arci`. Day one against Jev hit exactly this
(docs/DECISIONS.md, "What day one found", item 4) and worked around it with `PYTHONPATH=$PWD`.

v0.8.0 puts `arci init … && arci run arci.yaml` on the README's first screen, with references into
the user's current directory (`app.v1:run`, `tests.world:make_world`). That command must work from
an installed package without an environment variable.

## Decision

`arci.runner._pythonpath` appends the current directory (`os.getcwd()`) to the child `PYTHONPATH`
when it is not already present. Appended, never prepended: installed packages and the bundle
directory that replay puts first keep precedence, so a stray `json.py` in the project cannot shadow
the standard library for the harness itself. The rule applies to every child the runner starts
(worker, grader, boundary, command agent, MCP server), so `arci init`'s reference check, which runs
in a child built the same way, accepts exactly what `arci run` will later import.

Consequences:

- `python -m arci.cli` behaviour is unchanged (the current directory was already there, first).
- Sealed records do not change: `PYTHONPATH` is never recorded, and bundle payload paths are
  unaffected.
- The trust model is unchanged: the manifest author, toolset and oracle were already trusted, and
  the agent already ran the project's code. What changes is only where that code may be found.
- A project that relied on the current directory being *absent* (none known) would now see it
  last on the path.

## Options considered

1. Leave the runner alone and tell users to set `PYTHONPATH=.` or `pip install -e .`. Rejected: it
   makes the first-screen command false as written and repeats the day-one papercut.
2. A `--pythonpath` flag on `arci run`. Rejected: the first-screen command has no flag, and the
   flag would have to be repeated on `gate`, `minimize`, `replay` and in the Action.
3. A descriptor field. Rejected: `Manifest` is frozen and a path is not part of an experiment's
   identity.
4. Prepend the current directory, matching `python -m` exactly. Rejected: shadowing risk for the
   harness's own imports in the child; appending gives the same resolution for project modules.

## Not in v0.8.0

Discovering the project root (`pyproject.toml`, `.git`) and adding that instead of the current
directory; per-manifest search paths; changing how replay orders the bundle directory.
