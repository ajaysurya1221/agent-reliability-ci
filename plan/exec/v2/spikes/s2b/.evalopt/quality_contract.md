# S2b bounded quality contract

Owned directory: plan/exec/v2/spikes/s2b/ only. All frozen inputs remain untouched.
No network, dependency installation, git mutation, or product changes.

Required gates: all brief checks twice, Ruff formatting/lint, strict basedpyright,
frozen SHA256 verification, and no changes outside plan/exec/v2/.
A demonstrated limitation allowed by the brief may be an OK evidence check; it is
not a claim that the missing capability works. Native parity remains FAIL when
exception identity or actual body counts differ. No expected-failure conversion.

Evidence: out/run-NNNN preserves source digests, every trial spec/envelope, native
comparisons, command exits, replay bundles/results, checks, timings, and seals.
All comparisons remain offline against installed pinned LangChain sources.
The first invocation cannot establish cross-run repeatability.

Maximum iterations: 6. Stop at a demonstrated kernel/contract boundary; report it
without changing src or frozen code. No full product suite because product code is unchanged.
