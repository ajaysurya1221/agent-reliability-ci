REVIEW 04r1 — Reviewer Astra | Verdict REVISE

**Findings by severity**

1. **MAJOR — [src/arci/init.py:624](/Users/ajay/Developer/.arci-worktrees/wt-descriptor/src/arci/init.py:624): cleanup can delete a competing file.** The inode check and `unlink` are separate operations. A replacement between them is deleted. Additionally, when `fstat` fails, `created is None` permits deleting any destination. Both paths reproduced with the pinned module and mocked filesystem operations. The report acknowledges the first race; existing tests do not cover either.

2. **MAJOR — [src/arci/init.py:611](/Users/ajay/Developer/.arci-worktrees/wt-descriptor/src/arci/init.py:611): exclusive creation still permits partial publication.** The destination becomes visible before its bytes are written. Process termination can leave it truncated; a write failure followed by a suppressed cleanup failure also leaves partial output. In-memory probes confirmed partial visibility and retained truncated bytes. This contradicts frozen [ADR 0008:39](/Users/ajay/Developer/agent-reliability-ci/docs/design/0008-arci-init.md:39), which still promises atomic publication, and the implementation’s “nothing written” guarantee. Ordinary fsync-failure cleanup coverage does not establish those guarantees.

**Required changes**

1. Fail closed when hard-link publication fails without `--force`; remove the copy-into-destination fallback. Preserve the actionable error and staging cleanup. The task brief’s exclusive-create fallback conflicts with the frozen atomic-publication contract; the orchestrator must reconcile that instruction.
2. Add regression coverage proving unsupported-link failures preserve competing destinations and create no partial destination.

**Follow-ups**

The other requested corrections passed independent checks: leading-dash commands parse with `--`; argparse errors retain the amended generic format; repeated `<<` keys reject while merge lists and explicit overrides work; statistical wording is exact, with verified default **42/8** and nondefault **17/8** thresholds.

ADR 0006’s amendment honestly discloses namespace-package precedence and configured MCP `PYTHONPATH` exceptions; probes confirmed both. Its earlier categorical wording and the runner docstring should be qualified consistently.

No files changed. The supplied diff matches `b45cdda`; the candidate changes no frozen paths. Exact-commit `.venv/bin/python -I -B -c …` probes passed **26 checks** and reproduced **six publication scenarios**. Filesystem/process suites and reported lint/type checks were not independently rerun under the read-only sandbox.

Next: open `src/arci/init.py:605` to remove the unsafe fallback.
