# REVIEW: P1a suite schema, schedule and statistics

Reviewer: orchestrator (Claude Fable 5.2), 2026-11-11. Author: Codex Astra 6.
Worktree `wt-v2-suite`, branch `v2/suite`, uncommitted.

## Verdict: ACCEPT

| Check | Result |
|---|---|
| Codex's own unit tests (`tests/unit/suite`) | 159 passed |
| Blind acceptance tests (written from the contract by separate agents, never shown the code): schema, schedule, statistics | 587 passed, 0 failed, first run |
| `ruff format --check`, `ruff check`, `basedpyright` (strict), run by the orchestrator outside the sandbox | clean |
| `shasum -a 256 -c FROZEN.sha256` | 54 of 54 OK |
| Existing files changed | none |
| Orchestrator read all three modules (637 lines) | no defect found |

Codex's sandbox run of the whole suite showed 65 failures, all in existing tests that open
sockets or call `ps`. The orchestrator's run outside the sandbox showed no failure marker;
its exit code is captured on the next full run, after P1b.

## How the acceptance tests were made

`reviews/P1-acceptance-authoring-workflow.json`: 13 agents. One wrote shared builders, four
wrote one test file each from `tasks/P1-CONTRACT.md`, four independent reviewers recomputed
every literal and ran each file against their own throwaway implementation of the contract,
four fix passes applied confirmed findings. The reviewers found 2 assertions that went
beyond the contract and 9 coverage gaps; all were fixed before the first run against
Codex's code. Staged in `plan/exec/v2/acceptance-staging/`.

## Contract gaps the authors reported

Answered in `tasks/P1-CONTRACT.md` section 7. None changed Codex's code.

## Open

- `test_suite_gate.py` (96 tests) waits for P1b.
- Literal golden vectors for the digest of one fixed manifest are added at the re-freeze,
  once both implementations agree.
