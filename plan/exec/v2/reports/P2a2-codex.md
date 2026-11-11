**Re-run `.venv/bin/pytest -q` outside the sandbox.** P2a2 is implemented; all **419 targeted tests pass**.

| Item | Change and regression coverage |
|---|---|
| 1 | Preserved v1 stdin input; tested manifests and bundles through pipes and redirected files. |
| 2 | Split JSONL only on newline; tested Unicode separator round-trips. |
| 3 | Parse `.json` as JSON; tested exponents, emoji, duplicate keys and non-finite values. |
| 4 | Warn and skip malformed neighbors; tested transitive history, candidate matching and missing manifests. |
| 5 | Dispatch deferred commands from parsed arguments; tested abbreviations and one-line JUnit refusal. |
| 6 | Correct descriptor diagnostics; tested conflicting keys, arm types, IDs and grid limits. |
| 7 | Drain active pairs before saving; tested multiple workers and interruptions during atomic round publication. |
| 8 | Made fixture outcomes seed-dependent; exact intended-verdict probabilities are ≥0.999. |
| 9 | Added event-order, CLI history, summary-value, guarantee, workers, contract, sealed-route and decision tests. |
| 10 | Updated [suite semantics](/Users/ajay/Developer/.arci-worktrees/wt-v2-suite/plan-notes/AGENT_SEMANTICS_suite_section.md) to match the tested behavior. |

Changed files: `src/arci/{cli,descriptor,suite_runner,suite_storage}.py`, `src/arci/demo/suite.py`, `test_cli.py` and `test_review_fixes.py` under `tests/unit/suite_cli/`, `test_runner.py` and `test_review_fixes.py` under `tests/unit/suite_runner/`, and the semantics note.

Validation tails:

```text
pytest tests/unit/{suite_runner,suite_cli,descriptor,cli} -q:
419 passed in 95.86s

pytest -q:
65 failed, 2472 passed, 2 skipped in 377.34s

ruff format --check .: 485 files already formatted
ruff check .: All checks passed!
basedpyright: 0 errors, 0 warnings, 0 notes
FROZEN.sha256: all 63 entries OK
```

All commands used `.venv/bin/`; pytest’s extra quiet setting was overridden to print summaries. **15 isolated mutations were caught** by regression tests.

Full-suite acceptance remains unverified because of socket/`ps` permission denials and downstream failures; [all 65 failing tests are named here](/private/tmp/p2a2-full-failures.txt). Root `reproduce.py` is absent, so that conditional check was skipped.

Risk: atomic publication protects each JSONL file individually; SIGKILL or persistent disk failure can still leave the two files inconsistent.

