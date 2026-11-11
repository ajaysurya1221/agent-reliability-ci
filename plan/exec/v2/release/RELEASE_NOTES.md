- **Added:** suite experiments (`arci-suite/1`). An `arci.yaml` with `tasks:` registers a grid of tasks by fault conditions; baseline and candidate run it in balanced rounds and the gate returns `PASS`, `BLOCK`, `INCONCLUSIVE` or `ERROR` at round ends. The rule is two one-sided betting tests in exact arithmetic; each directional error is at most alpha/2 under the assumptions stated in `docs/STATISTICS_SUITE.md`. `arci run`, `gate`, `report`, `triage`, `diff` and `plan` accept suites. Design record 0011.
- **Added:** `arci.adapters.langchain` behind the optional extra `agent-reliability-ci[langchain]`: runs a `create_agent` agent behind the recorded tool boundary with fault injection, budgets and replay. `arci init --langchain`, the example `examples/langchain_quickstart/` and `docs/recipes/langchain.md`. Design record 0012.
- **Added:** fault accounting in reports: for each declared fault, how many trials it fired in, per arm, with a fault that never fired flagged. v1 Markdown reports gain this one section and v1 JSON reports one key; nothing else in v1 output changes.
- **Added:** `arci report --format html`: one self-contained file, no script and no external request. The Action can post or update one pull-request comment (off by default).
- **Added:** `bench/selfcheck_suite.py`, an exact calibration bench for the suite rule.
- **Unchanged:** every v1 (`arci/0.5`) record, command and exit code. The core still depends only on `pydantic` and `pyyaml`; LangChain is never imported unless the adapter is.
- **Not built for suites yet:** `minimize`, `bundle`, `replay`, `trace-check`, JUnit. Each refuses with one line and exit 3.

**Install:** `pip install agent-reliability-ci==2.0.0`. For the LangChain adapter: `pip install 'agent-reliability-ci[langchain]==2.0.0'`.

**Read first:** [statistics and their assumptions](https://github.com/ajaysurya1221/agent-reliability-ci/blob/v2.0.0/docs/STATISTICS_SUITE.md), [LangChain recipe](https://github.com/ajaysurya1221/agent-reliability-ci/blob/v2.0.0/docs/recipes/langchain.md), design records [0011](https://github.com/ajaysurya1221/agent-reliability-ci/blob/v2.0.0/docs/design/0011-suite-gate.md), [0012](https://github.com/ajaysurya1221/agent-reliability-ci/blob/v2.0.0/docs/design/0012-optional-framework-extras.md) and [0013](https://github.com/ajaysurya1221/agent-reliability-ci/blob/v2.0.0/docs/design/0013-v2.0.0-release.md).

The files on PyPI match `SHA256SUMS` from the release workflow run.
