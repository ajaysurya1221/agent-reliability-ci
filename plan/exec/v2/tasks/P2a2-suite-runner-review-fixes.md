# TASK P2a2: fixes after the independent review of the suite runner, store and CLI

Lane A. Worktree `/Users/ajay/Developer/.arci-worktrees/wt-v2-suite`. Your P2a work is in
the working tree, uncommitted. Same ownership and rules as P2a. No state-changing git.

The orchestrator's run outside the sandbox: 2,481 passed, lint and types clean, 63 frozen
hashes OK. Four reviewers with a skeptic per finding found no defect in the runner's
statistics (one look per round, pair scheduling, no re-runs, exact stop, determinism across
1, 2 and 8 workers all held). They confirmed 22 other findings. Record with reproductions:
`/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/reviews/P2a-review-workflow.json`.
Every fix gets a test that fails without it.

## Fix

1. **Blocking: v1 behaviour changed.** `arci replay /dev/stdin < bundle.json` and
   `arci run /dev/stdin` now fail because the suite sniff reads the input before the v1
   reader. Never pre-read an input the v1 path reads again: read once and dispatch on the
   parsed `schema_version`, or restrict the sniff to directories and regular files that are
   not stdin aliases. Regression tests through stdin for a v1 bundle and a v1 manifest.
2. **Line splitting.** `load_suite_run` and the JSONL task reader split on `\n` only.
   U+2028, U+2029 and U+0085 inside a recorded string must round-trip (a valid run with
   such output currently gates as ERROR). Do not change v1's `storage.py`.
3. **`.json` task files are parsed as JSON**, not YAML.
4. **Prior-run discovery**: check `schema_version` before anything else; skip directories
   that are not suite runs; an unreadable or malformed neighbour is skipped with a warning
   that names the file, never an abort; fix the four under-reporting cases in the review;
   make the semantics text say what the code does.
5. **Deferred commands**: decide from the parsed arguments, so abbreviated options cannot
   bypass the one-line message. `arci gate <suite store> --junit` exits 3 with one line
   saying JUnit export for suites is not built yet, not "Run store validation failed".
6. **Descriptor errors**: a v1 descriptor with a stray `tasks:` or `suite_id:` key, and the
   wrong-key messages listed in the review, each name the right key and the fix.
7. **Interrupted round**: on any interruption, cancel queued work, wait for the running
   pairs, then store every trial that finished, and write a round's lines so that a
   completed round cannot be left half written. The gate still gives ERROR for a partial
   round.
8. **The fixture is really stochastic.** Each fixture agent's success depends on the trial
   seed with a known per-cell probability, so `per_round` means something, the planted
   regression is a known size, the control equals the baseline in law, and test verdicts
   have slack: compute each fixture's PASS/BLOCK probability with
   `suite_stats.operating_characteristics` in a test and require the intended verdict to
   have probability at least 0.999, or fix the seeds' outcome by construction and say so.
9. **Tests the mutation run showed missing**: `events.jsonl` content and order; that
   `arci run` discovers prior runs (drive the CLI); every value printed by `arci gate` and
   `arci run` (counts, both wealths, threshold, errored against tolerance) and the
   guarantee sentence for both seed modes, compared with the text of
   `docs/STATISTICS_SUITE.md`; `--workers` honoured; contract validation in the runner; the
   sealed-manifest route; stored-decision edge cases; interruption with several workers.
10. Update `plan-notes/AGENT_SEMANTICS_suite_section.md`: fix the false sentence and the
    omissions the review lists.

Acceptance: the commands of P2a. Report under 50 lines: per item the change and its test;
command tails; anything you could not do.
