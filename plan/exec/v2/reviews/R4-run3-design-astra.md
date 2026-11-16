# Astra (gpt-6-astra, effort high) on the design of run 3, 16 Nov 2026

Brief: `plan/exec/v2/tasks/R4-run3-design-consult.md`. Answer as returned, unedited.

---

**Go with changes: register the text comparison only; demonstrate code retry with scripted, model-free tests.** Keep the eight cells, 10-point margin and 40-round cap, plus the proposed delivery audit and sealed code digest.

**Strongest argument against your leaning:** the second live run adds little information while increasing implementation, environment-restoration and reporting work. The uncertainty worth testing is whether this particular message improves outcomes; automatically fetching the missing result largely removes the decision you wanted to investigate.

1. **Swapped roles:** Sound: with Δ = unchanged − changed, statistical BLOCK establishes an improvement exceeding 10 points; PASS establishes that the improvement is below 10 points, allowing zero benefit or harm. The [suite contract](/Users/ajay/Developer/.arci-worktrees/wt-v2-logs/docs/STATISTICS_SUITE.md:204) requires, for `per_round`, the relevant null in every round’s scenario instances plus conditional independence; neither pooled seed averages nor shared-server execution establishes this, and there is no cleaner released positive-improvement verdict.

2. **Eight selected cells:** Defensible as a prospectively registered follow-up using fresh trials in both arms, explicitly selected from run 2; these are eight order instances of one task template, not eight independent demonstrations of generalization. The larger grids answer different questions and dilute this effect; they are necessary for broader reliability claims, not inherently more honest.

3. **Margin and cap:** Register 10 points as the smallest worthwhile improvement on this selected grid, and 40 rounds as the resource limit: 320 pairs, 640 trials. Fifty rounds permits 25% more trials without an additional sequential error penalty, but cannot guarantee resolution near the margin; the supplied power projections remain conditional scenarios, especially because 7/40 is uncertain and selected for poor performance.

4. **Code retry:** Omit the live comparison: a scripted end-to-end test can establish that an empty lookup triggers exactly one recorded retry and delivers its result, while admitting that it does not measure downstream model success. A live comparison would measure the complete retry intervention’s effect, not capability or an isolated psychological mechanism; it is defensible, but not my priority for this half day.

5. **Message and control:** Keep the exact proposed two-sentence message, omit `Error:`, and preserve successful tool-message status so an error label/status does not become another intervention. Against `null`, BLOCK supports “this replacement message helped”; attributing the benefit specifically to naming the next step requires a status-only message control, so narrow the claim instead of adding another arm.

6. **12B arm:** Leave it out because the question is whether this intervention helps the 4B setup. Measuring the remaining model gap needs a contemporaneous 12B comparison under specified middleware; determining differential benefit needs both models with and without the change, and historical 480/480 cannot substitute.

7. **Maintainer’s choice:** I would spend one bounded half day on the text follow-up because it answers an actual reader question, then publish every outcome and stop this study line. If restoring the environment and validating delivery consumes that allocation, reply with the existing evidence and proposed test instead of extending the work; another experiment is not evidence of adoption.

**Additional publication safeguards:** Keep all registered trials in the gate, including those that never trigger the fault; delivery-conditioned rates are descriptive. Freeze infrastructure-error handling, budgets, software/model digests and the rule against trying revised wording until BLOCK. Verify code hashes at execution: sealing a claimed digest does not verify loaded code, and an unsealed delivery log is supporting evidence. Report early-stopped success rates descriptively, without ordinary fixed-sample confidence claims.

No files changed; no tests, models, planner or experiments run. Assessment used local contracts, harness and study records.

**Next:** record “text only; code retry demonstrated offline; no model-gap or mechanism claim” as the design decision.