REVIEW 08-09 — Reviewer Astra | Verdict REVISE

Findings by severity:

- **BLOCKER:** None.
- **MAJOR — [examples/recipes/python_agent/README.md:87](/Users/ajay/Developer/.arci-worktrees/wt-recipes/examples/recipes/python_agent/README.md:87)**, also `docs/recipes/python-agent.md:104` and `tests/unit/recipes/test_python_agent.py:194`: the bundle omits `app/__init__.py` and `tests/__init__.py`. Its embedded directories therefore become namespace packages; the original recipe’s regular packages override them even when the bundle directory comes first. An import-resolution probe confirmed this precedence. The existing test replays beside the originals, so its success does not establish that bundled source executed. **Verify:** bundle, alter the original agent/oracle, and replay; the sealed sources must still determine the result.
- **MINOR — [docs/recipes/python-agent.md:76](/Users/ajay/Developer/.arci-worktrees/wt-recipes/docs/recipes/python-agent.md:76)**, also `examples/recipes/python_agent/README.md:52`: N=400 and P(BLOCK)=0.828 are correct under the planner’s **independent-arm** model. This recipe shares seeds and held-order state between arms. The prose omits that mismatch, and the recorded excerpt drops the planner’s explicit “No pairing” qualification. Readers can mistake the recommendation for calibrated power for this fixture. **Verify:** compare the complete planner output with the recipe’s shared-state construction. Gate validity under pairing remains unchanged.
- **NIT:** None.

Required changes (for REVISE/REJECT):

1. Include both package initializers in the Python bundle commands and pinned test commands. Add a replay check that proves modified original files cannot override bundled sources.
2. State beside N=400 that the planner assumes independent arms and does not model this recipe’s pairing; retain that qualification in the recorded excerpt.

Follow-ups:

- **Scope:** reviewed the supplied `f7eaad5` diff and subsequent recording/test corrections through clean HEAD `1d55eb9`. The placeholder assertions and broken Inspector fencing observed initially were fixed during review and are not outstanding findings.
- **Verified:** both descriptors compile with valid seals; the planner returns 400. In-process Python checks reproduce 8/8 versus 2/8 → INCONCLUSIVE and 390/400 versus 296/400 → BLOCK. New experiment identity, fresh seeds, `prior_runs`, relative-PASS wording, and once-only confirmatory guidance are present.
- **MCP:** one session and serial calls are implemented; framing and bridge environment match the documented setup. Inspector incompatibility is recorded honestly. Consider explicit `resultType` validation in `Session.call`: a mocked task result currently passes through as completed content, although ARCI’s boundary independently marks unsupported results as harness ERROR.
- **Checks and limits:** no files changed or network used. All 48 frozen hashes match; Ruff checks/format checks and scoped basedpyright pass. `PYTHONDONTWRITEBYTECODE=1 .venv/bin/pytest -s -p no:cacheprovider -o addopts= tests/unit/recipes --tb=short` ended **`2 passed, 7 errors in 0.26s`**; all seven errors were temporary-directory setup failures under the read-only sandbox. End-to-end preflight/run/replay remains independently unverified here. After the fixes, rerun that command with writable temporary storage.