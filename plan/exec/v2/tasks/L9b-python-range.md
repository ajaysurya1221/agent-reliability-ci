# L9b: `realornoise` supports Python 3.11 onward

Read `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/L-CONTRACT.md` and
`L9-second-distribution.md` (same ownership as L9; nothing else). Another agent is working
under `src/arci/logs/`, `bench/` and `tests/unit/logs/`; do not touch those.

**Why.** Measured by the orchestrator with the wheels you configured: `uvx` does not choose
an interpreter from a tool's `requires-python`. With a default interpreter of 3.13, `uvx
realornoise` stops with "the current Python version (3.13.12) does not satisfy
Python>=3.14". A first run that fails is worse than a first run that cannot read compressed
Codex files, which the tool already reports in its output.

**Change.**

1. `packages/realornoise/pyproject.toml`: `requires-python = ">=3.11"` (the same range as
   the main package) and the same Python classifiers as the main package. Nothing else
   changes: same pin, same script.
2. `packages/realornoise/README.md`: it runs on Python 3.11 or newer; compressed Codex logs
   are read only on Python 3.14, the output says how many files were not read, and
   `uvx --python 3.14 realornoise` reads them (uv fetches that Python if needed).
3. Workflows and `wheel_smoke.sh`: the second wheel is built once and smoke-tested on every
   Python version of the smoke matrix, not only on 3.14. Keep the 3.14-only steps that
   exist for compressed-log tests.
4. `docs/RELEASING.md`: say the same.
5. Tests in `tests/unit/packaging/`: update the expectations; add one that the second
   distribution's `requires-python` equals the main package's.

Done when: the L9 test command passes; ruff and basedpyright clean on your Python files;
YAML parses; `shasum -a 256 -c FROZEN.sha256` passes. Final message: files changed, the
command and its last line.
