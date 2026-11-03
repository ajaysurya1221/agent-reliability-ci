# Trace-check implementation and delivery evidence

The approved feature is implemented at
`84878c143dcb564c598746e1df87f70dfbcb9cf9`, based on
`68cc861c222c180d1e2b2f103e141fc9047c4e9f`. Subsequent evidence-only commits
do not change its source. **Availability is main / unreleased after merge.**
The temporary verification wheel still carries frozen package version 0.8.0;
it is not the released v0.8.0 distribution and must not be published as one.

The authoritative final delivery receipt is the body of
[PR #15](https://github.com/ajaysurya1221/agent-reliability-ci/pull/15). It records
the final candidate SHA, complete local-suite result, exact-revision hosted CI,
merge SHA and post-merge main CI. Those outcomes cannot be embedded in the same
commit they attest to. This record does not assert that a pending check passed
or that creating a PR is a merge/release decision.

## Delivered behavior

- `arci trace-check` reads two native stores and selected trial IDs, re-derives
  both gates, validates the selected traces and declared scenarios, and returns
  MATCH/0, DRIFT/1 or INVALID/3 with bounded diagnostics and source seals.
- Canonical-byte equality and difference location preserve typed/nested values;
  only approved wrappers and top-level tool call IDs are normalized away.
- Existing statistical, runner, oracle, storage, replay and same-run diff
  behavior is unchanged. No frozen-contract amendment or dependency was needed.
- The recipe keeps statistical exits independent and provides an unfilled
  non-author adoption/retention worksheet. **Adoption remains unmeasured.**

## Independently rerun local checks

Environment: isolated worktree on macOS, installed project Python 3.13 tools.
Existing environment and Node SDK fixture dependencies were copied from the
project without resolving new project dependencies. Fresh wheel verification
uses a separate venv with only the wheel and its declared runtime dependencies.

| Check | Command or procedure | Result |
|---|---|---|
| Frozen contracts | `shasum -a 256 -c FROZEN.sha256` | 53/53 OK |
| Historical/protected bytes | Recompute every SHA-256 in `baseline.json` | 228/228 identical; README first screen identical to base |
| Formatting | `.venv/bin/ruff format --check .` | 427 files already formatted at implementation commit |
| Lint and types | `.venv/bin/ruff check .`; `.venv/bin/basedpyright` | Clean; 0 errors/warnings/notes |
| Figures | `.venv/bin/python -B docs/assets/src/make_figures.py --check` | All four current |
| Archived reproduction | `.venv/bin/python -B docs/reports/ci-gate-2026-10-06/reproduce.py --check --strict` | Six checks OK: 18 decisions and both planner outputs byte-identical; evidence hashes match |
| Actual recipe | Extract and run the first three Bash blocks in `docs/recipes/trace-check.md` under `bash` with `set -euo pipefail`, outside checkout | Exit 0; all six demo steps held, A/A MATCH with candidate-run BLOCK; A/B DRIFT at step 4 |
| Build | Existing cached Hatchling 1.32.4, `python -m hatchling build -t wheel` and `-t sdist`, temporary output directory | Both built; wheel comparator equals source bytes; sdist allowlist 42 entries |
| Installed comparator | Fresh `python -m venv`; install built wheel; clear PYTHONPATH, set PYTHONSAFEPATH=1; installed `python -P .github/scripts/trace_check_smoke.py DEMO_DIR`, outside checkout | MATCH/0, DRIFT/1, INVALID/3; exact JSON/source identities; unchanged source hashes; no summary writes |
| Full suite | `.venv/bin/python -m pytest -p no:cacheprovider -ra` | Final result retained in PR receipt |

The local package probe reused the actual recipe's complete demo stores. Hosted
CI runs the whole shared `wheel_smoke.sh` in fresh environments on Ubuntu/macOS
with Python 3.11/3.14; its final result must be checked at the final candidate.
Local Python 3.13 is additional evidence, not a substitute for that matrix.

Temporary build artifact hashes (implementation commit only; not releases):

```text
2a10770dea974ec38981d6a941262041b035fac1ec48272f84cbda2b10cf4b5e  agent_reliability_ci-0.8.0-py3-none-any.whl
7c365551227f669e998697dd7a6df576a2d820efc8d98ce5b305a2be6b6ebd04  agent_reliability_ci-0.8.0.tar.gz
```

## Review and delivery gates

[Independent review receipts](reports/reviews.md) record ACCEPT for CLI/package,
core, and whole-branch reviews. Reviewers are non-author agents, not external
customers. No deferred or parked findings remain. Lane reports retain red/green
implementation evidence; the integrator and reviewers reran their own checks.

PR #15 remains draft/unmerged until full-suite, package matrix, frozen/history,
format/lint/types and review gates pass on the final candidate. Any changed
candidate or base requires new acceptance; no stale green run approves it.
The orchestrator must enforce these gates because main has no required-check
enforcement. Use a merge commit, then verify CI on the resulting main commit.
No repository settings, old tags, release assets or distributions may change.

The day-one status cut was met before feature freeze: all three CLI statuses
worked in the integration tests; the subsequent installed probe confirmed them.
Features froze at implementation commit
`84878c1`; later work is evidence, review fixes if required, and verification.
The 16-working-hour hard stop remains binding if delivery checks stay unresolved.

## Integration rulings and limits

- Native app worktree creation/attachment could not manage the nested repository.
  Use the manual isolated Git worktree with explicit workdir. Cost if wrong:
  desktop app bookkeeping may not reflect the checkout; Git isolation was verified.
- Reuse and repoint the copied installed project environment instead of resolving
  the lock again locally. Cost if wrong: hidden environment dependence; separate
  fresh-wheel probes and hosted matrices are mandatory to expose it.
- Retain this approved execution record and worktree rather than deleting the
  skill workspace at finish. Cost: disk usage; historical evidence stays available.
- Agent command argv/env is variable agent identity; equal declared environment
  means toolset/full MCP-server configuration, not ambient execution bytes. Cost:
  MATCH must never be described as environment authentication.

Original checkout's untracked research PDF and `dist-v0.8.0/` are outside this
work and remain preserved. No outreach or human pilot took place. A consenting
non-author's 30-minute pilot and seven-day independent repeat remain future
adoption evidence, not engineering acceptance substitutes.
