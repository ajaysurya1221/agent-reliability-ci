# Astra (gpt-6-astra, effort high) on the pre-registration of run 3, 16 Nov 2026

Brief: `plan/exec/v2/tasks/R7-run3-prereg-consult.md`. Answer as returned, unedited. Every change it asks for was applied before the pre-registration was committed; the wrapper also gained a `check` mode that runs every guard and starts nothing.

---

**GO after these changes. Do not start the registered run yet.**

1. **Close the wrapper’s start and identity gaps.** In [run-3.sh:39](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/study/run-3.sh:39), checking existence before creating the log is not atomic: two invocations can pass and start together. Versions are printed, not enforced; the model tag is mutable; the ARCI executable is not checked against the inspected Python environment. Recording HEAD does not establish that the registration is committed or pushed.

   Add and implement: “Before warm-up, the wrapper atomically acquires a permanent one-start marker, verifies the registered files and digest list against the published registration commit, verifies the executable environment and model digest, and refuses any mismatch.”

   Warm-up failure is currently ignored (`|| true`); make it abort before trials. Refresh the wrapper’s registered digest after changes.

2. **Correct verdict claims.** Replace “ERROR: more than 4 errored pairs; no verdict” with: “ERROR: error tolerance exceeded, invalid records or another gate validation failure; no statistical conclusion.”

   Add: “The improvement interpretation and 2.5% directional bound apply only to statistical BLOCK, not a candidate hard-invariant override; the published result includes the decision reason.”

   Replace “Its error budget is its own” with: “The directional guarantee applies to this registered experiment under its assumptions; no error guarantee across all three campaigns is claimed.”

   The swapped-arm interpretation is otherwise sound.

3. **Strengthen the four interpretation conditions.** Digest success and the expected folder name do not establish valid execution. Replace condition 4 with: “The store’s manifest has the expected recomputed experiment identity, and independent decision recomputation validates the seals, scheduled complete-round prefix, stopping rule and stored decision; an interrupted run or ERROR supplies no statistical conclusion.”

   Add: “The audit records middleware replacement attempts, not confirmed model receipt; aggregate agreement is supporting evidence and cannot establish trial-level delivery.”

   The current audit can pass with zero deliveries, and globally distinct call IDs are not guaranteed. Neither this audit nor the four conditions establishes the statistical independence assumptions.

4. **Keep the thresholds, define their calculation.** Five percent is a defensible operational cutoff, not a statistically calibrated allowance. Zero crashes is conservative: legitimate agent failures can crash, so it may suppress an otherwise informative result; nevertheless, fixing it now is acceptable.

   Add: “At the stopping round, each arm must satisfy 20 × (timeout count + budget count) ≤ its total trials, using `by_termination`; all trials remain in the gate.”

   `ended_on_budget_or_time` includes **every non-completed termination**, including errors. Add: “These interpretation checks do not establish a 2.5% error rate conditional on passing them.”

5. **Record the missing prediction honestly.** Use: “No maintainer prediction was supplied before registration.” Silence is neither an INCONCLUSIVE prediction nor evidence of neutrality.

No files changed; no models or experiments run. `sh -n` passed; all 17 digest checks returned `OK`. These checks do not certify runtime identity.

**Next: apply the wrapper safeguards before registration.**