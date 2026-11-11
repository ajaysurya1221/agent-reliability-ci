_at"})
327:    def _looks_are_a_plan(self) -> Manifest:
328:        if self.looks:
329:            if any(b <= a for a, b in zip(self.looks, self.looks[1:], strict=False)):
330:                raise ValueError("looks must be strictly increasing")
331:            if self.looks[0] < 1 or self.looks[-1] != self.n_per_arm:
332:                raise ValueError("looks must start above 0 and end at n_per_arm")
367:    looks: tuple[int, ...] = ()
393:    schema_version: Literal["arci/0.2"] = SCHEMA_VERSION
451:    schema_version: Literal["arci/0.2"] = SCHEMA_VERSION
461:    looks: tuple[int, ...] = ()  # the plan, (n_per_arm,) when the manifest declared none
475:    schema_version: Literal["arci/0.2"] = SCHEMA_VERSION

hook: PostToolUse
hook: PostToolUse
hook: PostToolUse Completed
hook: PostToolUse Completed
codex
1. **OPINION — Statistics: specify the randomness model before choosing the confidence sequence.**

   **KNOWN —** Waudby-Smith–Ramdas betting, applied to \(X=(d+1)/2\), guarantees simultaneous coverage \(P(\forall n:\mu\in C_n)\ge1-\alpha\) under constant conditional mean and predictable, admissible bets. Thus optional stopping is valid; PASS requires \(L>-\delta\), BLOCK \(U<-\delta\). Allocate error across conditions and directions. This controls statistical errors, excluding invariant-triggered BLOCKs. [Source](https://arxiv.org/html/2010.09686).

   **KNOWN —** Uniform independent task draws and fresh stationary trial randomness suffice. A fixed PRNG seed alone establishes neither independence nor conditional validity. Seed shopping, reused outcomes, provider drift, outcome-dependent omissions, or bets informed by the current task can invalidate that argument. Completed balanced-round means are safe under the conditional-mean assumption **at round endpoints**; pair-level stratified sampling needs another proof.

   **KNOWN —** Ordinary exact McNemar tests equality, not a nonzero risk-difference margin. Exact unconditional trinomial tests with nuisance maximization and Bonferroni looks are alternatives; comparable efficiency needs measurement. [Hsueh–Liu–Chen](https://pubmed.ncbi.nlm.nih.gov/11414572/).

   **OPINION —** A simpler spike tests only the threshold using betting wealth, avoiding full interval inversion. Illustratively, \(W^\pm_n=\prod_i[1\pm0.5(d_i+0.1)]\), crossing 40, gives two directional tests at 0.025 by Ville’s inequality. Fixed stakes are illustrative, potentially inefficient near the boundary.

   **OPINION — Planning estimates:** for independent Bernoulli arms, one condition, 20,000 freshly simulated runs, seeds 20261110/11 and a 2,000-pair cap: approximately **104 pairs** for 0.95→0.95 and **183 pairs** for 0.95→0.75; Monte Carlo 95% half-widths ≈0.6/2.2 pairs. Neither scenario had capped runs. Marginals alone cannot determine these expectations.

   **OPINION —** Compute operating characteristics by absorbing-state enumeration when counts suffice; otherwise seeded simulation with Monte Carlo intervals. Publish all verdict probabilities, stopping quantiles and censoring across joint-outcome distributions. Simulation is not a validity proof. Avoid platform `log`/`sqrt`, reduction-order and boundary-rounding differences: use rational bets, integer threshold comparisons, canonical serialization and cross-platform golden vectors.

2. **KNOWN — Pairing helps through covariance:**  
   \(\operatorname{Var}(B-A)=\operatorname{Var}(B)+\operatorname{Var}(A)-2\operatorname{Cov}(A,B)\).

   Shared task difficulty or effective common randomness can reduce variance. Independent stochastic arms on one task have zero covariance; negative covariance hurts. Balanced allocation can additionally remove task-composition noise.

   **CODE —** Today’s gate separates arm counts before forming intervals ([gate.py:199](/Users/ajay/Developer/agent-reliability-ci/src/arci/gate.py:199)).

   **OPINION —** Release claims must exclude universal sample savings, guaranteed first-run decisions, per-task non-inferiority, unseen-task reliability, deterministic live inference, and error-budget resets through repeated campaigns. Suite-average PASS can hide individual regressions.

3. **OPINION — Choose option 1**, with separate versioned suite records and explicit command dispatch.

   **CODE — The historical hash premise is false.** The v0.4 tag added `looks` while retaining `arci/0.2`; hashing included every nonvolatile field. Current hashing likewise includes empty/default fields ([schema.py:49](/Users/ajay/Developer/agent-reliability-ci/src/arci/schema.py:49)). v0.5 explicitly made earlier records unreadable ([CHANGELOG.md:256](/Users/ajay/Developer/agent-reliability-ci/CHANGELOG.md:256)). Therefore optional `tasks[]` is not hash-compatible.

   **CODE → OPINION —** Under option 1, existing v1 commands retain their paths. Suite **gate/report/triage/trace-check** need suite decisions and schedule validation; **diff** chiefly needs loading/selection; **bundle/minimize** need suite spec resolution and provenance; **replay** can reuse native per-trial payload execution but needs dispatch for a new wrapper. Dependencies: [storage.py:27](/Users/ajay/Developer/agent-reliability-ci/src/arci/storage.py:27), [triage.py:97](/Users/ajay/Developer/agent-reliability-ci/src/arci/triage.py:97), [trace_check.py:89](/Users/ajay/Developer/agent-reliability-ci/src/arci/trace_check.py:89), [cli.py:519](/Users/ajay/Developer/agent-reliability-ci/src/arci/cli.py:519). Option 2 requires these adaptations plus version-aware legacy hashing/parsing.

   **CODE → OPINION —** Bind a canonical suite-plan digest into every `TrialSpec.experiment_id`; it already enters `spec_sha256` ([schedule.py:17](/Users/ajay/Developer/agent-reliability-ci/src/arci/schedule.py:17)). The suite gate must reconstruct and verify that commitment, pair completeness and mandatory stopping.

4. **OPINION — Start with synchronous, explicitly serial, JSON-only tools.**

   **CODE —** ToolBox has mutable counters/recording without locks ([toolbox.py:95](/Users/ajay/Developer/agent-reliability-ci/src/arci/toolbox.py:95)); replay consumes calls in order ([toolbox.py:258](/Users/ajay/Developer/agent-reliability-ci/src/arci/toolbox.py:258)). A lock prevents overlap but does not establish deterministic ordering.

   **KNOWN → OPINION —** LangChain supports parallel tools, async hooks, and `ToolMessage`/`Command` responses. Require explicit serialization/codecs; preserve IDs, artifacts and state updates or reject unsupported types. Execute tools exactly once; avoid handler recursion, bypass and nested retries. [LangChain documentation](https://docs.langchain.com/oss/python/langchain/middleware/custom).

   **CODE —** Every admitted call, including injected failure, consumes budget; model steps require separate instrumentation ([toolbox.py:164](/Users/ajay/Developer/agent-reliability-ci/src/arci/toolbox.py:164)). Each trial launches worker and grader processes; startup consumes timeout ([runner.py:481](/Users/ajay/Developer/agent-reliability-ci/src/arci/runner.py:481), [runner.py:374](/Users/ajay/Developer/agent-reliability-ci/src/arci/runner.py:374)).

   **CODE → OPINION —** Agent returns are **not** final state. Arrange shared trial-local output capture in `toolset.snapshot()`; JSON travels worker→parent→grader ([worker.py:149](/Users/ajay/Developer/agent-reliability-ci/src/arci/worker.py:149), [worker.py:179](/Users/ajay/Developer/agent-reliability-ci/src/arci/worker.py:179), [runner.py:357](/Users/ajay/Developer/agent-reliability-ci/src/arci/runner.py:357)). Fake-model tests cannot establish live-model replay.

5. **OPINION —** Cut async/concurrent adapters, arbitrary Commands, adaptive task allocation and multiple statistical methods. The riskiest item is matching the sampling implementation to the theorem. Before product code, prove that contract, benchmark power, and demonstrate adapter recording→snapshot→grading→replay with budgets and injected failures.

   **CODE —** All 54 frozen hashes match. No files or git state changed; no tests ran.

**Top 3 changes to the proposal**

1. **OPINION:** Define randomness, weighting and multiplicity precisely.
2. **OPINION:** Preserve v1 through separate suite records.
3. **OPINION:** Require statistics and serial-adapter spikes first.


hook: Stop
hook: Stop
hook: Stop
hook: Stop Completed
hook: Stop Completed
hook: Stop Completed
tokens used
1,30,487
1. **OPINION — Statistics: specify the randomness model before choosing the confidence sequence.**

   **KNOWN —** Waudby-Smith–Ramdas betting, applied to \(X=(d+1)/2\), guarantees simultaneous coverage \(P(\forall n:\mu\in C_n)\ge1-\alpha\) under constant conditional mean and predictable, admissible bets. Thus optional stopping is valid; PASS requires \(L>-\delta\), BLOCK \(U<-\delta\). Allocate error across conditions and directions. This controls statistical errors, excluding invariant-triggered BLOCKs. [Source](https://arxiv.org/html/2010.09686).

   **KNOWN —** Uniform independent task draws and fresh stationary trial randomness suffice. A fixed PRNG seed alone establishes neither independence nor conditional validity. Seed shopping, reused outcomes, provider drift, outcome-dependent omissions, or bets informed by the current task can invalidate that argument. Completed balanced-round means are safe under the conditional-mean assumption **at round endpoints**; pair-level stratified sampling needs another proof.

   **KNOWN —** Ordinary exact McNemar tests equality, not a nonzero risk-difference margin. Exact unconditional trinomial tests with nuisance maximization and Bonferroni looks are alternatives; comparable efficiency needs measurement. [Hsueh–Liu–Chen](https://pubmed.ncbi.nlm.nih.gov/11414572/).

   **OPINION —** A simpler spike tests only the threshold using betting wealth, avoiding full interval inversion. Illustratively, \(W^\pm_n=\prod_i[1\pm0.5(d_i+0.1)]\), crossing 40, gives two directional tests at 0.025 by Ville’s inequality. Fixed stakes are illustrative, potentially inefficient near the boundary.

   **OPINION — Planning estimates:** for independent Bernoulli arms, one condition, 20,000 freshly simulated runs, seeds 20261110/11 and a 2,000-pair cap: approximately **104 pairs** for 0.95→0.95 and **183 pairs** for 0.95→0.75; Monte Carlo 95% half-widths ≈0.6/2.2 pairs. Neither scenario had capped runs. Marginals alone cannot determine these expectations.

   **OPINION —** Compute operating characteristics by absorbing-state enumeration when counts suffice; otherwise seeded simulation with Monte Carlo intervals. Publish all verdict probabilities, stopping quantiles and censoring across joint-outcome distributions. Simulation is not a validity proof. Avoid platform `log`/`sqrt`, reduction-order and boundary-rounding differences: use rational bets, integer threshold comparisons, canonical serialization and cross-platform golden vectors.

2. **KNOWN — Pairing helps through covariance:**  
   \(\operatorname{Var}(B-A)=\operatorname{Var}(B)+\operatorname{Var}(A)-2\operatorname{Cov}(A,B)\).

   Shared task difficulty or effective common randomness can reduce variance. Independent stochastic arms on one task have zero covariance; negative covariance hurts. Balanced allocation can additionally remove task-composition noise.

   **CODE —** Today’s gate separates arm counts before forming intervals ([gate.py:199](/Users/ajay/Developer/agent-reliability-ci/src/arci/gate.py:199)).

   **OPINION —** Release claims must exclude universal sample savings, guaranteed first-run decisions, per-task non-inferiority, unseen-task reliability, deterministic live inference, and error-budget resets through repeated campaigns. Suite-average PASS can hide individual regressions.

3. **OPINION — Choose option 1**, with separate versioned suite records and explicit command dispatch.

   **CODE — The historical hash premise is false.** The v0.4 tag added `looks` while retaining `arci/0.2`; hashing included every nonvolatile field. Current hashing likewise includes empty/default fields ([schema.py:49](/Users/ajay/Developer/agent-reliability-ci/src/arci/schema.py:49)). v0.5 explicitly made earlier records unreadable ([CHANGELOG.md:256](/Users/ajay/Developer/agent-reliability-ci/CHANGELOG.md:256)). Therefore optional `tasks[]` is not hash-compatible.

   **CODE → OPINION —** Under option 1, existing v1 commands retain their paths. Suite **gate/report/triage/trace-check** need suite decisions and schedule validation; **diff** chiefly needs loading/selection; **bundle/minimize** need suite spec resolution and provenance; **replay** can reuse native per-trial payload execution but needs dispatch for a new wrapper. Dependencies: [storage.py:27](/Users/ajay/Developer/agent-reliability-ci/src/arci/storage.py:27), [triage.py:97](/Users/ajay/Developer/agent-reliability-ci/src/arci/triage.py:97), [trace_check.py:89](/Users/ajay/Developer/agent-reliability-ci/src/arci/trace_check.py:89), [cli.py:519](/Users/ajay/Developer/agent-reliability-ci/src/arci/cli.py:519). Option 2 requires these adaptations plus version-aware legacy hashing/parsing.

   **CODE → OPINION —** Bind a canonical suite-plan digest into every `TrialSpec.experiment_id`; it already enters `spec_sha256` ([schedule.py:17](/Users/ajay/Developer/agent-reliability-ci/src/arci/schedule.py:17)). The suite gate must reconstruct and verify that commitment, pair completeness and mandatory stopping.

4. **OPINION — Start with synchronous, explicitly serial, JSON-only tools.**

   **CODE —** ToolBox has mutable counters/recording without locks ([toolbox.py:95](/Users/ajay/Developer/agent-reliability-ci/src/arci/toolbox.py:95)); replay consumes calls in order ([toolbox.py:258](/Users/ajay/Developer/agent-reliability-ci/src/arci/toolbox.py:258)). A lock prevents overlap but does not establish deterministic ordering.

   **KNOWN → OPINION —** LangChain supports parallel tools, async hooks, and `ToolMessage`/`Command` responses. Require explicit serialization/codecs; preserve IDs, artifacts and state updates or reject unsupported types. Execute tools exactly once; avoid handler recursion, bypass and nested retries. [LangChain documentation](https://docs.langchain.com/oss/python/langchain/middleware/custom).

   **CODE —** Every admitted call, including injected failure, consumes budget; model steps require separate instrumentation ([toolbox.py:164](/Users/ajay/Developer/agent-reliability-ci/src/arci/toolbox.py:164)). Each trial launches worker and grader processes; startup consumes timeout ([runner.py:481](/Users/ajay/Developer/agent-reliability-ci/src/arci/runner.py:481), [runner.py:374](/Users/ajay/Developer/agent-reliability-ci/src/arci/runner.py:374)).

   **CODE → OPINION —** Agent returns are **not** final state. Arrange shared trial-local output capture in `toolset.snapshot()`; JSON travels worker→parent→grader ([worker.py:149](/Users/ajay/Developer/agent-reliability-ci/src/arci/worker.py:149), [worker.py:179](/Users/ajay/Developer/agent-reliability-ci/src/arci/worker.py:179), [runner.py:357](/Users/ajay/Developer/agent-reliability-ci/src/arci/runner.py:357)). Fake-model tests cannot establish live-model replay.

5. **OPINION —** Cut async/concurrent adapters, arbitrary Commands, adaptive task allocation and multiple statistical methods. The riskiest item is matching the sampling implementation to the theorem. Before product code, prove that contract, benchmark power, and demonstrate adapter recording→snapshot→grading→replay with budgets and injected failures.

   **CODE —** All 54 frozen hashes match. No files or git state changed; no tests ran.

**Top 3 changes to the proposal**

1. **OPINION:** Define randomness, weighting and multiplicity precisely.
2. **OPINION:** Preserve v1 through separate suite records.
3. **OPINION:** Require statistics and serial-adapter spikes first.



[exited with code 0]
