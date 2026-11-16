**Post with the changes below. I agree with your leaning: the result warrants an article, but this version needs tighter scope.**

1. **Correct the verdict definitions ([line 47](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/launch/post-run-3.md:47)).**

   > “It has three verdicts.”

   Replace: “It has three statistical outcomes, plus ERROR when the run cannot support a conclusion.”

   > “BLOCK: it is worse by more than that.”

   Replace: “A statistical BLOCK supports a disadvantage greater than 10 percentage points; a hard-invariant violation can also force BLOCK. This run’s BLOCK was statistical.”

   > “INCONCLUSIVE: the rounds ran out.”

   Replace: “INCONCLUSIVE: neither statistical threshold was crossed within the registered budget.”

2. **Distinguish the reader’s suggestion from your experiment ([line 21](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/launch/post-run-3.md:21)).**

   > “I tried that idea at the empty lookup, because 34 of the 4B’s 52 failures in run 2 were under that fault.”

   Replace: “The suggestion concerned the ‘unknown SKU’ error. I adapted it to the empty lookup instead: 34 of the 4B’s 52 failures in run 2 occurred under that fault.”

   > “It tests the whole system with the recovery handed to code, and it does not isolate what the model decides.”

   This is a defensible distinction, but an incomplete rationale. Replace: “A code retry would answer a useful system-design question. I chose the narrower message comparison, leaving that question unanswered; neither comparison alone establishes model capability.”

3. **Put scope beside the opening counts.**

   Replace the opening paragraph with:

   > “On eight selected stock-note cases—one task template with eight order IDs—the same 4B agent passed 15 of 16 trials with a message at an empty lookup, versus 2 of 16 with `null`. These are early-stopped counts from one wording comparison, not estimates of general reliability. Reader comments prompted this third experiment.”

   In the results paragraph, name the assumptions: independent cells and rounds, the same law each round, no arm-order effect, and the relevant condition holding for each round’s scenario instances. State that there is no guarantee averaged over seeds.

4. **Clarify registration timing and retain the checker summary.**

   > “The rule for the verdict and the message were pre-registered: pushed in a public commit before the first trial.”

   Replace: “The rule and message were publicly registered after the smoke run and before the first registered trial.”

   Replace every “trial run” with “smoke run.” “The right stock note and no refund” is a fair plain-language summary of the checker for these tasks.

5. **Numbers and likely criticism.**

   No numerical mismatches found. The quoted **32** is correctly identified as erroneous; **33 of 34** is the correction.

   A hostile but fair reader will first challenge eight ID variants being presented as eight tasks, followed by selection after run 2, smoke results seen before registration, and the unanswered code-retry comparison.

Files changed: none. Tests: not run; document review only. Live links were not checked.