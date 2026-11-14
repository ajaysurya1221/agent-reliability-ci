**Resolve findings 1–2 before coding.** The arithmetic checks pass; the documents leave material execution and validation rules unresolved.

References below use **0015** for [the design record](/Users/ajay/Developer/.arci-worktrees/wt-v2.2/docs/design/0015-imported-outcomes.md) and **Outcomes** for [the statistical contract](/Users/ajay/Developer/.arci-worktrees/wt-v2.2/docs/STATISTICS_OUTCOMES.md).

1. **BLOCKER — The recommended workflow contradicts preregistration.**

   **Passages:** “the rule file was fixed before the outcomes existed” (Outcomes:89); “write the rule from the baseline’s files before the candidate is run” (0015:247–249).

   The second instruction does not establish the first. Baseline results already exist, and selecting tasks or a margin from them can invalidate conditioning on the registered experiment. Moreover, `verdict-rule` excludes skipped tests (0015:113–114), so “no outcome was used” in F7 is false: skip status affects task selection.

   **Evidence:** `STATISTICS_SUITE.md:10–27` freezes both arms, oracle and grid before outcomes and prohibits outcome-dependent cell selection.

   **Replacement:** “Create the rule from a predetermined task inventory before either evaluated arm runs; historical result files may help draft that inventory, but the resulting rule applies to fresh runs of both arms.” Replace F7 with: “Task IDs were extracted; this does not establish preregistration. Freeze the rule before running either evaluated arm.”

2. **BLOCKER — Validation after the stopping round has contradictory definitions.**

   **Passages:** “Then read every input” (0015:287); “rounds beyond it are not read” (0015:293); “Round labels … above `max_rounds`” are errors (0015:131).

   Implementers can legitimately return different verdicts when round 1 crosses but a later round contains an unknown ID, malformed score, duplicate, excessive round number or unreadable file. Full-file SHA-256 also requires reading bytes beyond the stopping round. The scope of `--previous` consequently changes depending on what “read” means.

   **Proposed rule:** “Read, hash, parse and structurally validate every supplied input before inference; structural errors anywhere return ERROR, while valid outcomes after the first non-INCONCLUSIVE round do not update wealth or error tolerance.” Record all supplied-round digests, but history and inferential counts only through the stop.

   Replace F6 with: “Rounds after the stopping round were excluded from inference.” This preserves the intended statistical stopping rule while making validation deterministic.

3. **MAJOR — The unchecked conditions need an explicit experimental-protocol condition.**

   **Passages:** “the estimand is about that tool’s definition of a pass” (Outcomes:34–36); “Each task behaves the same in every round” (Outcomes:95).

   The proof remains valid for suitably independent, stationary *labels*, even when the arms use different scorers. That does not establish candidate non-inferiority under a common grading criterion. Matching IDs also does not establish matching task inputs or targets. A model grader can introduce shared randomness, drift or dependencies across cells.

   **Evidence:** `STATISTICS_SUITE.md:10–17, 92–119, 165–205` requires a registered experiment and joint independence of complete pair differences.

   **Add condition (f):** “Before execution, fix both arm identities, task inputs and targets, grading protocol and versions, numeric threshold, retry policy, and pairing/repetition schedule; use a common grading criterion for candidate-quality claims, otherwise describe the estimand as a comparison of the two complete evaluation pipelines.”

   Clarify that fixed internal transport retries are part of that protocol; replacing completed failed/errored samples with successful reruns is not. Shared seeds or caches **within one pair** are permitted by the proof; reuse across pairs needs separate justification.

4. **MAJOR — `--previous` detects changed prefixes, but its validation contract is incomplete.**

   **Passage:** “every round it read has the same `outcomes_sha256`” (0015:60–62).

   This detects normalized-label changes in the supplied predecessor’s prefix. It cannot establish execution, preregistration, an authentic predecessor, absence of other campaigns, unchanged task/scorer provenance, or that identical labels came from the same trials. A user can also supply an older predecessor or omit the option.

   The draft does not define predecessor seal/schema validation, missing predecessor rounds, malformed history, or ERROR predecessors.

   **Proposed rule:** “Require a valid, sealed `arci-outcomes/1` predecessor with a recomputed matching rule digest and contiguous round history; require every predecessor supplied round in the new input and compare its normalized digest; reject malformed predecessors and shorter or changed prefixes.”

   Define the hash payload exactly, for example:

   ```python
   hash_record({"outcomes": [[arm, task_id, outcome_or_null], ...]})
   ```

   Include every registered arm/task position, using `null` for absence; sort by arm then task ID. This distinguishes missing from explicit `error`. A single digest of the concatenated canonical prefix is a simpler alternative, but per-round hashes give better diagnostics. Neither design supplies authentication.

5. **MAJOR — Kernel extraction needs explicit ownership of validation and aggregation.**

   **Passage:** “`evaluate_rounds` … attaches … each round’s `trials_sha256` and the per-cell totals” (0015:202–204).

   `evaluate_rounds` does not currently attach per-cell totals: `_cells` is called separately by `decide_suite`, covering **all supplied trials**, including those after a stop (`suite_gate.py:145–164, 312–326`). Moving it into the walked prefix changes existing ERROR records.

   **Required rule:** “Extract only cumulative count accumulation, incremental wealth, crossing flags, verdict priority and stopping; preserve suite validation, digests, cell aggregation and ERROR construction in their existing callers.”

   Exact signatures I recommend:

   ```python
   def walk_rounds(
       rule: SuiteRule,
       per_round_counts: Iterable[RoundIncrement],
   ) -> tuple[RoundLook, ...]: ...

   def check_rule_plan(rule: SuiteRule) -> tuple[str, ...]: ...
   ```

   `RoundIncrement` contains the five integer increments named in 0015. `RoundLook` contains the existing round-result fields except `trials_sha256`. Keep candidate violations cumulative, including violations on errored trials, and preserve crossing flags even when overridden.

   Preserve these existing behaviours: incomplete trailing rounds produce no look; no complete round returns `()`; supplied trials after a stop remain suite ERROR; an early inconclusive suite stop remains ERROR; every ERROR has `stopped_at_round=0`. `check_suite_plan` must retain its exception type, E9-before-E10 ordering and warning tuple.

6. **MAJOR — Inspect mapping is incomplete even for the supported identity types.**

   **Passages:** “sample `id`, string or integer”; “several logs of one epoch each in file order” (0015:105–106).

   The real fixture contains integer ID `7001` and two scorers. The rule stores string IDs, but conversion is undefined: integer `7001` and string `"7001"` can collide. Multiple one-epoch logs also conflict with the instruction to use their explicit `epoch`, normally 1.

   **Evidence:** `inspect/candidate.json:167–168` contains integer `7001`, epoch 1. Fixture inspection found 27 samples per arm, two scorers, and an errored candidate sample with empty scores.

   **Add rules:** Canonicalize integer IDs to decimal strings and reject collisions or inconsistent source ID types; require one selected scorer across the whole import, never choose the first score present; treat an absent selected score as an errored outcome, while malformed present values are validation errors.

   Define one explicit round-assignment mode per arm: one multi-epoch log uses epochs; multiple single-epoch logs use file position; reject other mixtures. Check header/sample consistency, reject duplicate sample/epoch records rather than choosing a retry, and treat registered samples omitted by a limit as missing errors. Missing whole epochs require an explicit header-derived round policy, not silent disappearance.

7. **MAJOR — promptfoo has unstable IDs and an unsafe failure fallback.**

   **Passages:** “`repeatGroupId` when present, else `test-<testIdx>`”; “otherwise the `success` flag decides” (0015:117–118).

   Real fixtures identify the same first test as `test-0` in the single export and `test-0-vars-0` in the repeated export. These cannot be transparently mixed. The fallback also turns unknown `failureReason` values into ordinary failures, potentially violating condition (e).

   **Evidence:** `promptfoo/baseline-single.json:116` versus `promptfoo/baseline.json:94–95`. Description is under `testCase.description`, not a top-level row field.

   **Proposed rule:** “Require consistent repeated/non-repeated identity mode throughout both arms; reject mixed modes rather than guessing correspondence; accept only `(success=true, reason=0)`, `(false,1)` and `(false,2)`, mapping them to pass, fail and error respectively.”

   Compare canonical `vars` and `testCase.description` across **all rounds and both arms**. Validate prompt/provider cardinality across the arm’s whole input set, not just each file. Register and check grading assertions where available; equal description and variables alone do not establish equal grading.

8. **MAJOR — JUnit support needs structural rules; the promised pytest-repeat rejection is not unconditional.**

   **Passages:** “The id is `classname::name`”; “such a file fails on unknown ids” (0015:110–115).

   `verdict-rule` can discover pytest-repeat’s suffixed IDs itself, after which those IDs are registered and no unknown-ID error occurs. Repetitions then become separate cells. The real promptfoo JUnit fixture also embeds the candidate label in `classname` and numbers repeated rows.

   **Evidence:** XML inspection found six cases in `pytest/single.xml`, 18 suffixed cases in `pytest/repeat.xml`, and classnames `[candidate] prompt 1` in `promptfoo/candidate.junit.xml`.

   **Add rules:** Accept `<testsuite>` or `<testsuites>` roots and recursively visit each testcase once; require nonempty `classname` and `name`; reject duplicate composite IDs, including delimiter collisions; use error/skipped before failure before pass when status children coexist.

   Replace the repeat claim with: “Repeat suffixes remain literal task IDs; pairing fails against an unsuffixed inventory, but suffixes discovered into the rule become distinct cells.” Explicitly refuse promptfoo’s repeated JUnit export for repetition import and direct users to its JSON.

   Specify UTF-8-only XML, or perform declaration rejection after safe decoding; a raw ASCII byte search for `<!DOCTYPE` does not cover UTF-16 XML.

9. **MAJOR — Neutral formats and auto-detection lack a deterministic parsing contract.**

   **Passages:** “Columns `task_id`, `outcome`, and `round` when the file carries it”; “sniffs by extension and top-level shape” (0015:109, 119).

   No real CSV/JSONL fixture accompanies this contract. Encoding, dialect, duplicate keys/headers, blanks, ID coercion, mixed round labels, score-column precedence and ambiguous detection are unspecified.

   **Proposed rules:** Use UTF-8 with optional BOM; CSV uses comma delimiters and standard double-quote escaping; JSONL has one object per nonblank newline-delimited record. Reject duplicate keys/headers, malformed rows, non-finite numbers and conflicting outcome/score values. Require string IDs, exact lowercase outcome labels and positive integer rounds.

   Apply auto-detection independently per file; require a unique supported shape consistent with its extension, otherwise E6. Explicit `--format` selects one parser for every file. Do not guess between Inspect and promptfoo JSON.

10. **MAJOR — Rule and decision schemas remain too incomplete to implement consistently.**

    **Passages:** “Keys: …” (0015:42–45); “The decision record … holds” (0015:70–75); “no absent optional key written” (0015:261–262).

    Missing choices include unknown/duplicate YAML keys, explicit nulls, empty task lists/IDs, integer coercion, score-threshold range, canonical defaults, record field names, ERROR templates, per-task count scope and predecessor linkage.

    **Evidence:** `SuiteRule` validates arithmetic parameters but does **not** impose the 100,000-pair cap; that lives in frozen `SuiteManifest` (`suite_schema.py:123–128`). Extracting `check_rule_plan` does not inherit it.

    **Required rule:** “Publish exact rule and decision models before implementation; reject unknown/duplicate keys and invalid types, expand all semantic defaults before hashing, impose `N * max_rounds <= 100000`, and define threshold parsing separately from positive-only suite rationals.”

    Explicitly decide whether imported single-round rules require acknowledgement or only W1. Define zero-input rejection, how empty files declare rounds, which round set establishes arm balance, and whether unknown IDs remain errors after a stop. For malformed rules, define an ERROR record with an unavailable rule digest rather than promising a valid digest in every output.

11. **MAJOR — F4 can report a PASS at a forbidden mid-round look.**

    **Passage:** “PASS is reached after `<m>` more pairs (`<r>` more rounds)” (0015:161).

    **Executed check:** With 50 tasks, eight registered rounds and 50 observed ties, the arithmetic threshold needs **29 additional ties**, but the next allowed decision requires **50 additional pairs: one complete round**.

    **Replacement:** “If every further pair is a non-errored tie, PASS is reached after `<r>` more complete rounds (`<r*N>` more pairs).”

    Compute the smallest allowed round count from current cumulative counts. Print F4/F5 only for INCONCLUSIVE; do not suggest continuing after a decisive or ERROR stop.

12. **MAJOR — The fixed-sample superiority claim compares different hypotheses.**

    **Passage:** “a classical exact paired test has more power at the same alpha: McNemar’s exact test” (Outcomes:166–169).

    McNemar tests equality of paired marginal probabilities, not the registered non-inferiority margin. The text also fails to distinguish total alpha from the directional `alpha/2` budget. No comparison establishes uniform power superiority over this heterogeneous-cell estimand.

    **Replacement:** “A fixed-sample procedure designed for the same non-inferiority estimand and directional error budget may offer greater power; this document does not establish such a comparison.”

    Also replace “a one-round import is a formality, not a test” (Outcomes:135–137): the displayed 50×1 rule is rejected, while valid one-round rules are statistical tests. Describe that row as a hypothetical 50-pair look, also obtainable as the first look of a longer valid registration.

13. **MINOR — Several fixed statements overstate or misdescribe the contract.**

    **Passages:** “ARCI checked only the task list and balance” (0015:157); “nothing on the command line can [change the verdict]” (0015:41–42); “rounds are in the order they were run” (Outcomes:97).

    The command also validates scores, schemas, budgets and optionally prior hashes. File order explicitly changes round assignment. Concurrent Inspect epochs need not have a unique wall-clock round order; predetermined logical ordering is sufficient under the stated joint-independence assumptions.

    **Replacements:** “ARCI checked input structure and registered task/round coverage; it did not verify execution or the statistical assumptions.” “Statistical parameters come only from the rule; CLI file order determines rounds when specified by the format.” “Pairing and logical round order were fixed before outcomes were observed; no registered round was omitted or replaced.”

    F2’s **`alpha/2` expression is correct for nondefault alpha**. Render the actual alpha and directional bound for clarity. Correct Outcomes:100–102 too: misclassifying a candidate infrastructure failure can favour BLOCK; misclassifying a baseline failure can favour PASS. Errors can end ERROR, not merely delay a verdict. Different calendar days alone do not establish nonstationarity.

14. **MAJOR — CLI, output and Action behaviour are not yet acceptance-testable.**

    **Passages:** “The GitHub Action gains a verdict mode” (0015:84); “Each row is exit 3 with fixed reason text” (0015:124).

    Missing rules cover Action inputs and incompatible modes, repeated-option accumulation, `--example` conflicts, `verdict-rule` format/scorer selection, output-path collisions, report-write failures, malformed `--previous`, invalid rule values and multiple-error precedence.

    **Proposed rule:** “Specify the CLI grammar and Action input table, reject incompatible modes and input/output aliases before writing, define one deterministic validation-error order and fixed text for every failure class, and return exit 3 if a requested artifact cannot be written.”

    Scope “same … digests on any machine” (Outcomes:179) to identical canonical evidence and rule inputs. Exact arithmetic alone does not normalize local paths, timestamps or independently generated exporter bytes.

### Checked and found correct

- **Statistical bound:** Fewer supplied rounds, repeated calls over an unchanged registered prefix, stopping at the first decisive round, worst-case scoring of missing outcomes, and tolerance based on the full registered budget preserve the directional bound under the stated latent-outcome assumptions. Missingness may depend on outcomes. Within-pair dependence is unrestricted.

- **Power recomputation:** `.venv/bin/python -B -c …` calling `operating_characteristics` returned:

  | Tasks × rounds | PASS, 0.9→0.9 | BLOCK, 0.9→0.7 |
  |---|---:|---:|
  | 50 × 1 | 0.040323914 | 0.021884646 |
  | 50 × 3 | 0.504390593 | 0.292153249 |
  | 50 × 8 | 0.961563696 | 0.799641260 |
  | 100 × 1 | 0.262699663 | 0.138003544 |
  | 200 × 2 | 0.953653544 | 0.767404334 |

  All printed rounding matches. Separate direct multinomial enumeration, using independently multiplied factors, matched the 50×1 and 100×1 rows.

- **Wealth arithmetic:** Factors `1/2, 19/18, 29/18`; products `29/36, 361/324, 841/324`; ratio `261/361`; tie floor **79 pairs**. The example gives `max_rounds=5`, tolerance `5`, PASS wealth `1.92124e-03`, BLOCK wealth `1.56229e+02`, hence BLOCK.

- **Extraction and frozen boundary:** Extraction is feasible without editing frozen suite schemas or acceptance tests. No additional existing frozen-file edit is inherently required beyond 0015’s listed release changes. `pyproject.toml` changes must precede testing the new installed console alias; that is an orchestrator-owned release-stage operation. Hash verification ended: **`FROZEN 66 mismatches []`**.

- **Review limits:** No files changed; no implementation or acceptance suite was run. Python 3.13.12 refused both `.eval` archives with `NotImplementedError: That compression method is not supported`, confirming the documented fallback requirement; their decompressed contents and Python 3.14 behaviour were not verified. JSON fixtures and all XML fixtures were inspected.

