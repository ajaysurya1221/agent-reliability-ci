# Execution ledger: plan/exec/v2/tasks/S1c-balanced-rounds.md

1. Contracts and brief read. Memory registry search returned no relevant hits.
2. Reference procedure and exact enumeration: six tests green after missing-module red.
3. Full tables and proof: in progress.
4. Independent review and required verification: pending.

Ruling: all writes, including caches and this ledger, stay in the owned s1c directory; no skill workspace or git mutations, per the task's explicit boundary.
Ruling: Table C lists four scenario types times two couplings (8), not 12; its fourth type is impossible because a 1.0 success-probability drop from any of 0.99, 0.80, 0.30 is negative. Asked the user; absent a correction, report six feasible cases and two infeasible cases, without inventing four more.
Ruling: boundary half-improvement and mixed laws use no-zero paired differences. These are valid trinomial laws; half cells have mean +0.3 and compensating cells exactly restore suite mean -0.1. Odd N uses floor(N/2) improving cells.
Ruling: adversarial random-restart search evaluates 2,000 distinct configurations per N, 1,000 loss/zero laws and 1,000 loss/win laws. Optimize both directions over the same candidates. This is a declared restricted search, not global optimization or a proof over all laws.
Ruling: applying the per-round convolution's linear cell factors without intermediate absorption is exactly the round-level DP. A separate round_kernel exposes the explicit increment convolution for exhaustive checks.

Independent review: no mathematical or DP defect found; reviewer independently checked 20 exhaustive heterogeneous seven-pair distributions and expected costs. Reviewer found one important issue: test_s1c.py imports run_all ambiguously under the required PYTHONPATH, causing basedpyright to select S1b's module. Reproduced exactly (two reportAttributeAccessIssue errors). Fix queued after the active initial computation, followed by fresh full regeneration and byte-repeat verification.
Review limits to resolve: final tables, run timing, and repeatability were not yet available.
Performance observation: summing packed coefficients by `% (2**width-1)` is exact but slow for large widths. A benchmark of exact binary-fold digit summation (same no-carry bound) ran 100 operations in 0.0128s versus 1.3441s for modulus. Any optimization must retain exact probabilities and be checked against the original output.

Final fix: moved the study implementation to uniquely named s1c_study.py and kept run_all.py as the entry point; test import now resolves correctly. Required basedpyright command changed from 2 errors to 0 errors. No ignore directives.
Performance fix: binary digit folding replaces long modulus division under the same strict no-carry bound. New regression test observed failing before implementation, then 12 tests green. S1 independent-enumerator and exhaustive-path tests still pass. Full 400-pair 0.50 equal-arm benchmark retains PASS=0.5198436308683786 and expected pairs=306.31906492966203; time improved from 5.0s to 1.5s despite concurrent work. Proof updated with the folding invariant.
Initial slow run remains active because the environment rejected process termination. Its source-hash check will fail before artifact writes after these source changes; it cannot overwrite final outputs. No acceptance is claimed for that exploratory run. Final computation uses the corrected sources and separate final-run.log.

Generation 1: all required checks pass (12 tests; format/check clean; strict basedpyright 0 errors; 54 frozen hashes intact).
Artifact audit after generation 1: 23 A rows, 6,000 search rows, 11,500 B rows, 108 homogeneous C rows, six feasible heterogeneous rows. All 17,751 probability/cost records conserve probability, have zero ERROR mass and expected cost in [1,400]. All homogeneous N=10 records match sampled exactly; balanced costs are never below sampled costs on that grid. Three position-dependent conditional rows match S1b binary_enumeration exactly; the full 400-pair independent 0.50-equal-arms row matches S1 characteristics exactly. Final numerical conclusions inspected in RESULTS.md. Repeat verification remains in progress.

Task complete for all mathematically feasible specified cases. Final --verify-repeat exited 0: two fully recomputed generations, byte-identical results.json and RESULTS.md, total 282.187 seconds with up to 15 workers. Both generations passed 12 tests, Ruff format/check, strict basedpyright, and all 54 frozen checks. No pyright suppressions. Table C's impossible drop and 8-versus-12 count defect remain explicitly documented, not silently repaired.
Final review dispositions: the sole important import issue is fixed and verified; no deferred minor findings. The review's pending artifact/timing/repeat checks are resolved by the artifact audit and successful two-generation run. The initial slow pre-optimization process was not acceptance evidence and cannot overwrite these outputs because its input/source hash guard will reject the changed sources; sandbox process termination was unavailable.
