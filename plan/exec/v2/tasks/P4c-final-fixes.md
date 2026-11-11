# TASK P4c: last fixes before the v2.0.0 release candidate

Worktree `/Users/ajay/Developer/.arci-worktrees/wt-v2-integration` (branch `v2/integration`,
HEAD is the release candidate, version 2.0.0). No state-changing git. Frozen files
(`FROZEN.sha256`, 65 entries) untouched. You own: `action.yml`, `.github/scripts/pr_comment.py`,
`.github/scripts/prepare_report.py`, `src/arci/html_report.py`, `src/arci/storage.py` (item
2 only), `README.md` (the Action section only), `docs/results/sample-suite-report.html`,
and tests under `tests/unit/html_report/`, `tests/unit/examples/`, `tests/unit/runner/` or
a new `tests/unit/storage/`.

Two checkers confirmed every P4b fix. They found these. Record:
`/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/reviews/P4b-verification-workflow.json`.
Each fix gets a test that fails without it.

1. **Major: `action.yml` may fail to load.** An input `description` contains a `${{ }}`
   expression. Descriptions are not an expression context; remove the braces from every
   description and put the concurrency example in the README instead. Add a test that no
   `${{` appears in any `description` in `action.yml`.
2. **Major (old defect, now reachable): v1 `load_run` splits `trials.jsonl` with
   `splitlines()`**, so a v1 store whose label, condition id or failure detail contains
   U+0085, U+2028 or U+2029 cannot be loaded and gates as ERROR. Read as UTF-8 and split on
   `\n` only, as `suite_storage.py` does. Round-trip test with those characters. No other
   v1 behaviour changes; existing stores load byte-identically.
3. `render_store_html` writes the ERROR page for any load failure, including
   `RecursionError` from a deeply nested manifest.
4. Headings are fixed strings: a stored id is shown in a caption, labelled row or
   paragraph, never inside `h1` or `h2` text.
5. `overflow-wrap:anywhere` only where ids and long values appear; ordinary words in table
   cells do not break mid-word at 360 px.
6. The statistical BLOCK sentence ends with a full stop.
7. PR comment: any unexpected exception prints the fixed one line and exits 0; truncation
   treats a heading and its body as one section and keeps table header rows; the comment
   identity also includes the job id, and the README says to set `comment-id` for matrix
   jobs.
8. README: a short Action section for `pr-comment`, `comment-id`, the
   `pull-requests: write` permission and a `concurrency` example; remove the stale sentence
   that says there is no HTML report yet.

Regenerate the HTML goldens and `docs/results/sample-suite-report.html` (version footer
is `ARCI 2.0.0`). Do not touch `docs/results/order-desk-study.html`; the orchestrator
re-renders it.

Acceptance (worktree root):

```sh
.venv/bin/pytest tests/unit/html_report tests/unit/examples tests/unit/runner tests/unit/report tests/unit/cli -q
LANGSMITH_TRACING=false .venv/bin/pytest -q
.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/basedpyright
shasum -a 256 -c FROZEN.sha256
```

Report under 30 lines.
