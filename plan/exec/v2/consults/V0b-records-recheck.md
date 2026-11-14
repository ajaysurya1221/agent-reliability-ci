1. **Resolve the BLOCKER items below before coding.**

   References: **D** = [design record 0015](/Users/ajay/Developer/.arci-worktrees/wt-v2.2/docs/design/0015-imported-outcomes.md); **O** = [imported-outcomes contract](/Users/ajay/Developer/.arci-worktrees/wt-v2.2/docs/STATISTICS_OUTCOMES.md).

   | Original finding | Status |
   |---|---|
   | 1. Preregistration | **PARTLY CLOSED** — workflow corrected; condition (a) names a declaration instead of actual preregistration, and descriptive outputs retain “established” claims. |
   | 2. Validation after stopping | **PARTLY CLOSED** — main rule corrected; the validation section still applies E11 to all supplied rounds before inference. |
   | 3. Experimental protocol | **CLOSED** — condition (f) covers identities, grading, thresholds, retries and scheduling. |
   | 4. Previous decisions | **PARTLY CLOSED** — digest/version/prefix rules added; nested record validity and comparison precedence remain incomplete. |
   | 5. Kernel extraction | **CLOSED** — extraction boundary and suite compatibility requirements are explicit. |
   | 6. Inspect mapping | **PARTLY CLOSED** — identity/scorer rules added; file-position assignment contradicts the general producer-label rule. |
   | 7. promptfoo mapping | **CLOSED** — identity modes, failure combinations, metadata, assertions and cardinality are covered. |
   | 8. JUnit | **PARTLY CLOSED** — structural rules added; skipped-ID exception conflicts with E1, and E19 lacks a detection predicate. |
   | 9. Neutral formats/detection | **PARTLY CLOSED** — encoding and basic syntax specified; score columns, mixed round fields and detection predicates remain undefined. |
   | 10. Record schemas | **PARTLY CLOSED** — rule model improved; null policy contradicts decision fields, and nested decision models remain sketches. |
   | 11. Whole-round continuation | **CLOSED** — F4 uses complete rounds and prints only for INCONCLUSIVE. |
   | 12. Fixed-sample comparison | **CLOSED** — unsupported superiority claim removed and hypothetical power row labelled. |
   | 13. Fixed statements | **PARTLY CLOSED** — ERROR-path validation claims, digest portability and count labels remain inaccurate. |
   | 14. CLI/output/Action | **PARTLY CLOSED** — grammar added; builder defaults, error precedence and artifact-failure behavior remain incomplete. |

2. **Contradictions remaining in the revised specification**

   | Issue | Conflicting passages |
   |---|---|
   | **BLOCKER — Declaration changes digests** | D:281–283: “the field is part of the digest, so the two cases are different registrations.” D:563: “The verdict, the exit code and every digest are identical either way.” Verdict arithmetic can remain identical; rule and decision digests cannot. |
   | **BLOCKER — Nulls** | D:261–262: “Both models … explicit nulls are refused.” D:301–302 explicitly permits “string or null” and “embedded rule or null”; D:319 requires those nulls for malformed rules. |
   | **BLOCKER — ERROR notices** | D:322: “`notices` empty.” D:366–368: “F1 and F2 appear in every terminal, Markdown, HTML and JSON output, whatever the verdict.” No alternative JSON location for these texts is defined. |
   | **BLOCKER — Error tolerance after stopping** | D:230–231: “Every one of these checks runs over all supplied inputs, before inference, including rounds after the stopping round”; the table includes E11 at D:244. D:74–75: later outcomes “update neither wealth nor the error tolerance.” |
   | **BLOCKER — Count scope** | D:308: per-task counts cover “all supplied rounds.” D:584–585: “every errored-pair count a report shows is labelled as the count through the stopping round.” A displayed per-task error count can include excluded rounds. |
   | **BLOCKER — Unregistered skips** | D:207: an unregistered skipped case “is ignored.” D:235: “A task id that is not in the rule’s `tasks`, wherever it occurs” is E1; D:572–573 repeats the unconditional rule. |
   | **BLOCKER — Inspect round assignment** | D:56–58: use producer labels and file order only “when the format supplies none.” D:179–181: multiple one-epoch logs use “file position order,” despite carrying epoch labels. |
   | **BLOCKER — Rule-error precedence** | D:275 and D:291–294 place the pair cap in `max_rounds` validation, before `score`. D:569–572 places `n * max_rounds <= 100000` after `fixed_before_runs`. An excessive budget plus invalid score selects different first failures. |
   | Digest portability | O:237–238 promises “the same digests on any machine” from the same rule and normalized outcomes. O:251 says arithmetic “does not normalise local paths, timestamps or an exporter’s own bytes”; D:304 records paths and file hashes. Only rule and normalized-round digests have the stated invariance. |

3. **Remaining deterministic-build gaps and rules to add**

   - **BLOCKER — Decision records and predecessors (D:296–324).** Nested fields, ordering, count definitions and inference-time ERROR construction are incomplete.  
     **Add:** “Specify exact nested models and canonical ordering for inputs, history, task counts and notices, retain the final evaluated round separately from ERROR’s zero `stopped_at_round`, and validate predecessor cross-field consistency before accepting its seal.”

   - **BLOCKER — Neutral parsing and detection (D:213–224).** Score-only rows, missing selected scores, empty values, mixed labelled/unlabelled rounds and format predicates are unresolved.  
     **Add:** “Accept an exact outcome or the rule-selected score, reject disagreement and mixed round-field presence within a file, treat an absent selected score as missing, and define an explicit extension-and-shape table for auto-detection.”

   - **BLOCKER — `verdict-rule` construction (D:333–345).** `--suite-id` is optional although the model has no default; repeated task discovery and partial round inventories lack rules.  
     **Add:** “Default `suite_id` to `imported-outcomes`, deduplicate IDs across discovery files and repetitions after rejecting duplicate observations, and build the inventory without applying an already-registered round budget.”

   - **BLOCKER — Validation and output failures (D:338–349).** File order does not order errors within a file, cross-file failures or predecessor-prefix comparisons; earlier artifacts may already contain PASS when a later write fails.  
     **Add:** “Publish one ordered validation table covering CLI/path checks, rule fields, predecessor structure, file records, cross-file coverage and predecessor comparisons, then specify artifact-write order and the exact ERROR output retained on E29.”

   - **Exporter identification (D:170–211).** Inspect header consistency and promptfoo-JUnit recognition still require implementer guesses.  
     **Add:** “Define accepted Inspect header/sample field types and consistency checks, and define E19 by a fixture-backed structural predicate rather than repetition suffixes alone.”

4. **`fixed_before_runs`: defensible design, but the printed contract is not yet fully honest.**

   **BLOCKER:** Change condition (a) to **“The rule and task list actually were fixed before either evaluated arm ran; the author declares this and ARCI does not verify it.”** D:375–384 currently conditions the bound on a declaration. The referenced suite contract requires actual preregistration.

   **BLOCKER:** With `false`, unchanged reasons still print “non-inferiority established” or “regression established” (D:435–438). Replace these in descriptive output with “PASS threshold crossed” and “BLOCK threshold crossed.” Require F11 to be the first displayed text, not merely somewhere ahead of F2.

   F2’s “ARCI checked input structure and registered task and round coverage” is false when rule validation prevents reading any inputs. ERROR output must state which checks completed. F12 must distinguish the evaluated prefix from all-supplied descriptive counts.

   Two further corrections: E3 incorrectly says fewer rounds were registered even for round `0`; and O:65–67 wrongly implies that truncating at a genuinely preregistered cap inherently breaks the proof. Refusing excess rounds is a valid policy, but that rationale is unnecessary. D:85 should prescribe fresh runs under any revised registration, or descriptive analysis—not imply that rewriting the rule restores the bound.

5. **Three implementation costs to defer**

   | Part | First-release cut |
   |---|---|
   | Exporter compatibility matrix | Defer native `.eval`, mixed-format auto-detection and complicated multi-file exporter modes; retain explicit neutral formats and narrowly supported JSON/JUnit inputs. |
   | GitHub Action verdict mode and PR integration | Defer; terminal exit codes and JSON artifacts already support CI invocation. |
   | HTML output and cross-renderer parity | Defer HTML; ship terminal, JSON and Markdown with identical statistical qualifications. |

   Keep exact arithmetic, complete-round stopping, missing-pair treatment, declaration labels and `--previous` checks.

   No files changed; no tests run for this document-only re-check. Next: resolve the digest contradiction at [D:563](/Users/ajay/Developer/.arci-worktrees/wt-v2.2/docs/design/0015-imported-outcomes.md:563).