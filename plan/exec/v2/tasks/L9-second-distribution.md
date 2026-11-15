# L9: the `realornoise` distribution, the release workflow, CI and the wheel smoke

Read `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/L-CONTRACT.md` and follow
its rules. Record 0016, decision 8, and `docs/RELEASING.md` describe what is wanted. Read
`pyproject.toml` (frozen: do not edit), `.github/workflows/release.yml`,
`.github/workflows/ci.yml`, `.github/workflows/ttfv-reference.yml`,
`.github/scripts/wheel_smoke.sh` and the tests under `tests/unit/` that check workflows and
packaging before changing anything. Other agents are working under `src/arci/logs/`,
`bench/`, `docs/` and `tests/unit/logs/`; do not touch those.

## You own

- `packages/realornoise/` (new): `pyproject.toml`, `README.md`, `LICENSE` (a copy of the
  repository's), `src/realornoise/__init__.py`, `src/realornoise/py.typed`
- `.github/workflows/release.yml`, `.github/workflows/ci.yml`,
  `.github/workflows/ttfv-reference.yml`, `.github/scripts/wheel_smoke.sh`
- `docs/RELEASING.md`
- `tests/unit/packaging/test_realornoise_distribution.py` (new; put it beside the existing
  packaging or workflow tests if they live elsewhere and say where)

## Build

1. `packages/realornoise/pyproject.toml`: project `realornoise`; the same build backend and
   licence fields as the main package; `version` equal to the main package's version (today
   `2.2.0`; the orchestrator bumps both at the re-freeze); `requires-python = ">=3.14"`;
   `dependencies = ["agent-reliability-ci==<that version>"]`; console script
   `realornoise = "arci.logs.cli:main"`; a description in plain words ("Did your coding agent
   get worse? Reads the Claude Code and Codex session logs on your disk and answers real
   drop, no drop or cannot tell. Sends nothing."); project URLs pointing at the repository;
   classifiers for Python 3.14 only. It is not a uv workspace member and `uv.lock` must not
   change. `src/realornoise/__init__.py` holds a docstring and `__version__`, nothing else.
   The README is short: what it is, `uvx realornoise`, `uvx realornoise --example`, what it
   cannot show, a pointer to the main repository, and that the code lives in
   `agent-reliability-ci`.
2. The main wheel must contain the packaged example data
   (`arci/logs/example/**`). Check how the main wheel is built; if the files are already
   included, add a test that proves it; if they are not and the only fix is in the frozen
   `pyproject.toml`, stop and report the exact line needed.
3. `release.yml`: keep everything it does today for the main package. Add: the tag guard
   also checks the second distribution's version and its pin; build the second wheel and
   sdist into their own directory; the smoke job installs both wheels into a Python 3.14
   environment and runs `realornoise --example` (expects exit status 1 and the line
   `RESULT: REAL DROP`) and `arci logs --example`; checksums cover the new files in the way
   the existing files are covered; a second publish job for `realornoise` that runs only
   after the main package is published, uses PyPI trusted publishing with the same
   environment name as the existing publish job, and uploads only the second
   distribution's files. Follow the existing job's permissions and attestations exactly.
4. `ci.yml`: the unit tests for `src/arci/logs` run on Python 3.14 as well as 3.11 if they do
   not already; the wheel-smoke job also builds and installs the second wheel on 3.14 and
   runs the two example commands. Keep every existing job.
5. `wheel_smoke.sh`: extend in the script's own style; an expected exit status of 1 for the
   example must not fail the script, any other status must.
6. `ttfv-reference.yml`: remove the dead `sprint/t18-**` push trigger; keep
   `workflow_dispatch` with an input for the package and command to time (default
   `agent-reliability-ci`, `arci demo`), so it can time `uvx realornoise --example` later.
   Keep its behaviour otherwise.
7. `docs/RELEASING.md`: the release steps for two distributions, including the one-time
   step for the maintainer on PyPI (a pending trusted publisher for `realornoise`: owner
   `ajaysurya1221`, repository `agent-reliability-ci`, workflow `release.yml`, and the
   environment name the workflow uses), the order of publishing, and what to check after.

## Tests

- The second distribution's version equals the main package's version and its pin; its
  `requires-python`, script and dependency are as specified; it has no other dependency.
- If `uv` or the build backend is available offline, build both wheels in a temporary
  directory and check their file lists (the main wheel has the example data; the second
  wheel has only its own package and metadata, and its entry point). If a build is not
  possible in your sandbox, write the test so it skips with a clear reason when the backend
  is missing, and say so.
- Workflow checks in the style of the existing workflow tests: both publish jobs exist, the
  second needs the first, the dead trigger is gone.

## Done when

`.venv/bin/pytest tests/unit -q -k "packag or workflow or release or realornoise"` passes
(name the exact command you used); ruff format, ruff check and basedpyright are clean on
your Python files; `shasum -a 256 -c FROZEN.sha256` still passes; YAML files parse
(`python -c "import yaml, sys; [yaml.safe_load(open(f)) for f in sys.argv[1:]]" <files>`).
Final message: files changed, commands and last lines, what could not be verified (hosted
CI cannot run in your sandbox), risks.
