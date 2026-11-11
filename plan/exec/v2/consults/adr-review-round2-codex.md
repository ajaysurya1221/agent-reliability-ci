**OPINION — Revise both records. Verdict: ADR 0011 REVISE; ADR 0012 REVISE.**

**CODE — ADR 0011: original blockers**

References: [draft v3](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/adr-0011-draft.md).

1. **RESOLVED — Stopping rules:** lines 35, 105–106 and 116–119 consistently require one-round stages and first-decisive stopping; compatible with the validation pattern in `src/arci/gate.py:328–367`.
2. **RESOLVED — Store validation:** lines 112–120 require seals, reconstructed identities, spec hashes and RECORD evidence, matching `src/arci/gate.py:41–50,275–318`. Binding through `experiment_id` at draft lines 94–102 works with `src/arci/schema.py:472` and `src/arci/schedule.py:17–19`.
3. **RESOLVED — Adjacency:** lines 107–111 define pair-level scheduling. A pool task can call synchronous `run_trial` twice sequentially (`src/arci/runner.py:1453–1476`); no frozen signature change is necessary. The scheduler-scope amendment is listed at draft lines 209–212 against `docs/AGENT_SEMANTICS.md:17–18`.
4. **RESOLVED — Infrastructure boundary:** lines 135–142 specify wrapper attribution and latch-before-propagation. A new public method can invoke existing `ToolBox.__mark_harness` (`src/arci/toolbox.py:154–156`). Its callback reaches the worker latch (`src/arci/worker.py:143–145`), which overrides caught exceptions at lines 191–196.
5. **RESOLVED — Planning model:** lines 156–161 require per-cell joint laws or an explicitly assumed homogeneous three-input model.

**KNOWN — NEW BLOCKING: seed guarantee.** Draft lines 85–89 promise an average over “seed derivation,” but deterministic hashing of registered content defines no sampling distribution. V1’s deterministic schedule (`src/arci/schedule.py:53`) supplies no justification. Specify an honestly randomized design with sufficient independence, or require the null conditionally for every derived round and remove the averaged guarantee, including line 221. Fixed mode’s conditional guarantee at lines 79–84 is sound under the stated outcome assumptions; fixed seeds alone do not guarantee stationary live-model laws as lines 66–67 suggest.

**CODE — ADR 0012: original blockers**

References: [draft v2](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/adr-0012-draft.md).

1. **PARTLY — CI isolation:** lines 44–48 fix collection under today’s `pyproject.toml:59` and `.github/workflows/ci.yml:65–71`. **NEW blocking defect:** lines 49–51 exclude the same directories the adapter command targets. Installed basedpyright’s bundled source shows positional paths replace `include`, retaining `exclude`; excluded roots are skipped. Use a separate adapter configuration clearing these exclusions.
2. **PARTLY — Supported ranges:** lines 24–33 fix the direct minimum and private imports. Lines 53–57 still do not specify both transitive-package endpoints required by `plan/exec/v2/reviews/S2b-review.md:47`; locked versions are not necessarily upper endpoints. Define concrete endpoint environments and verify installed versions.

**CODE — Verification limit:** static inspection only; no files or git state changed, no tests run.

**OPINION — Next:** replace ADR 0011 lines 85–89 with an explicit conditional guarantee.

[exited with code 0]
