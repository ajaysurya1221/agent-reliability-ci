# TASK V: verification lane — Fable, continuous
After every merge to main: `just check`, `just frozen`, `python docs/assets/src/make_figures.py --check`, `uv build --no-sources -o /tmp/arci-dist && cd $(mktemp -d) && uvx --from /tmp/arci-dist/*.whl arci demo --workers 4`, CI green on origin. `just selfcheck` and `tests/unit/selfcheck` if any statistics file is touched (none planned; any such touch is a stop-and-record event). STATUS.md gets one line per task: state, reviewers, commit.

---

---

Common to every TASK: AGENTS.md rules apply (no git state changes by the coder, no `uv`, use `.venv/bin/*`, no network, no new deps, stdlib+pydantic+pyyaml only, ruff/basedpyright strict clean, acceptance tests untouched). REPORT format: Status DONE/PARTIAL/BLOCKED | Changes | Tests (commands + results) | Deviations (with reason) | Open issues. Worktree absolute path is injected into the dispatch.
