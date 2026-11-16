# Astra (gpt-6-astra, effort high) on the result of run 3 and what is published, 16 Nov 2026

Brief: `plan/exec/v2/tasks/R9-run3-writeup-consult.md`. Answer as returned, unedited. Its sentence changes were applied to the result file and to both replies, in plainer words where the reply is for a blog comment; its list for the public section is the brief for the pull request.

---

**Verdict: yes after these changes.** The corrected result is publishable; the replies need clearer scope and direction.

1. **Result write-up.** Replace the audit qualification with:

   “The audit records middleware replacements, not what the model received; its lines cannot be tied to individual trials, so matching counts are supporting evidence only.”

   Replace “the message is worth more than 10 points” with:

   “Under its stated assumptions, the registered test supports a mean pass-rate advantage exceeding 10 percentage points on these eight selected cells; this is a threshold decision, not an effect-size estimate.”

2. **Replies: exact replacements and additions.**

   **Both:** replace the sentence beginning “The test stopped…” with:

   “The test stopped at round 2 with a statistical BLOCK: the message arm was deliberately labelled baseline, so BLOCK favors it over the concurrently tested run-2 setup. Under the test’s stated assumptions, this supports an advantage exceeding 10 percentage points on these eight cells, not an estimated gain or a conclusion about the full suite.”

   Add:

   “Both arms already had ‘Retry an empty lookup once.’ in the system prompt. A disclosed smoke run preceded registration; its trials are excluded.”

   **dev.to:** replace the opening agreement with:

   “The records show different actions under the same instruction; they do not establish a capability gap.”

   Replace the “outcome is nearly fixed” explanation with:

   “A code retry would test the combined system with recovery delegated to code; it would not isolate the model’s retry decision or guarantee task success.”

   **Hashnode:** replace “so there is no text at all” with:

   “The successful tool response contains the literal text `null`, with no explanation or next-step instruction.”

   The run-2 counts are descriptive; retain that qualification. Its 106 immediate lookups are supported by the stored traces.

3. **Public section: include these in order.**

   - Explain before the table: runs 1–2 compare 12B versus 4B across 96 cells; run 3 compares two 4B setups across eight cells selected after run 2. Label both arms explicitly.
   - Give the exact message, shared retry instruction, registration, disclosed smoke results, budgets and stopping rule; note no run-3 prediction was supplied.
   - Show statistical BLOCK, reason, round 2, 32 trials, 15/16 versus 2/16, pair counts, per-task counts and fault delivery 16/16 versus 15/16. Label stopped-sample counts.
   - State unchecked assumptions, the per-round null condition, no guarantee averaged over seeds or across campaigns, no pooling, and no conclusion about the 12B gap or mechanism.
   - Link registration, erratum, digests, logs, sealed store and decision-recomputation tests; distinguish recomputation from rerunning the model.

4. **Erratum:** honestly handled. It weakens smoke-to-registration provenance, not the recorded statistical decision: the executed wrapper matched its registered digest. File times cannot prove unchanged study code. Preserve the original registration alongside the correction.

5. **Do not** merely append run 3 beneath the existing 4B-versus-12B framing; revise the introduction before publishing.

Files changed: none. Tests/model runs: none; R8’s verification was reviewed, not repeated.