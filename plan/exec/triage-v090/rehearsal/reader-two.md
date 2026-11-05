# Independent reader two — agent usability QA

## Result

Both supplied cases were diagnosed through the installed CLI within the 300-second target. No blocking CLI usability issue was observed. This is an independent non-author agent exercise, not evidence of human adoption or retention. The recipe gives the retry example, so this is not a blinded exercise.

## Method and timing

I read `PROTOCOL.md` first, then only the permitted recipe, `cases.json`, top-level CLI help and triage CLI help. Every CLI command ran from `/tmp/arci-triage-v090.ygMrHy/empty`, using `/tmp/arci-triage-v090.ygMrHy/installed/bin/arci`, with `PYTHONPATH` removed and `PYTHONSAFEPATH=1`. Stores were supplied and available; I did not create or execute a recorded run.

| Case | Diagnosis start UTC | Diagnosis end UTC | Elapsed seconds | CLI execution seconds | Actual exit |
|---|---|---|---:|---:|---:|
| retry | 2026-11-05T18:44:54.250022+00:00 | 2026-11-05T18:45:15.772052+00:00 | 21.522030 | 0.536961 | 1 |
| repeat | 2026-11-05T18:45:15.772507+00:00 | 2026-11-05T18:46:24.218042+00:00 | 68.445535 | 0.144227 | 2 |

These are diagnosis intervals ending when the interpretations below were recorded. The retry interval includes triage-help execution and reading. The initial protocol/recipe/cases/top-level-help setup reads occurred before these intervals and were not wall-clock timestamped. Exact command timestamps, outputs, stderr and exits are retained in `reader-two-commands.txt`. No store-generation time is counted.

## Retry case

Command:

```sh
env -u PYTHONPATH PYTHONSAFEPATH=1 /tmp/arci-triage-v090.ygMrHy/installed/bin/arci triage /tmp/arci-triage-v090.ygMrHy/demo/runs/arci-demo-agent_b-reserve-timeout-200
```

The complete statistical gate is **BLOCK**, preserved by process exit **1**. The `reserve-timeout` gating condition has baseline 192/200 PASS and candidate 132/200 PASS, zero errors and zero candidate hard violations. The report shows both failure groups: 65 and 3 candidate FAIL records, with zero groups omitted.

The first representative pair is baseline `reserve-timeout:00005:baseline` PASS versus candidate `reserve-timeout:00005:candidate` FAIL. Its diagnostic label is **DRIFT**. At normalized step 4, pointer `/payload/arguments/quantity`, the baseline containing event is `tool_start`, seq 9, tool `reserve`, occurrence 1; the candidate containing event is `tool_start`, seq 10, tool `confirm`, occurrence 0. The differing value is present for the baseline and absent for the candidate. Both containing events exist; an absent argument value does not mean an absent event. The operation mismatch is the baseline's next `reserve` call against the candidate's `confirm` call.

The second representative pair, index 00063, is FAIL on both sides and **MATCH**. That selected match does not override the whole-run BLOCK verdict or establish reliability.

The CLI identifies the first recorded difference and the recipe explains this fixture's removed retry. The observed position alone does not prove a causal regression, justify benignness, prove subsequent equality, or establish the root cause of an arbitrary failure. I did not inspect argument values or execute/replay either agent.

## Repeat case

Command:

```sh
env -u PYTHONPATH PYTHONSAFEPATH=1 /tmp/arci-triage-v090.ygMrHy/installed/bin/arci triage /Users/ajay/Developer/.arci-worktrees/triage-v090/plan/exec/trace-check/rehearsal-2026-11-03/fixture-evidence/stores/arci-trace-rehearsal-2026-11-03 --trial clean:00000:candidate
```

The complete statistical gate is **INCONCLUSIVE**, preserved by process exit **2**. The `clean` gating condition has baseline 1/1 PASS and candidate 1/1 PASS, zero errors and zero candidate hard violations. There are no failure groups. The supplied explicit passing candidate ID still selects its paired baseline, with no change to the experiment or denominator.

The pair `clean:00000:baseline` versus `clean:00000:candidate` is **DRIFT**, although both individual records PASS. At normalized step 4 and pointer `/payload/result/diagnostic_label`, both contexts identify an existing `agent_result` event at seq 9. The baseline value is absent and candidate value is present. This is a field-presence mismatch within containing events that exist on both sides; it is not evidence of a missing event or a tool-operation mismatch.

The field name does not establish that the change is benign. This first difference proves neither root cause nor later trace equivalence. Two passing records and zero failure groups do not change INCONCLUSIVE into PASS and do not establish absolute reliability.

## Findings, errors and limits

- Both text reports directly exposed the containing event, original sequence, value presence, whole-run verdict and preserved process exit. The recipe and help were sufficient for these two cases without author assistance.
- No unexpected command failures, stderr, runtime help requests or answer-key access occurred. Exits 1 and 2 are valid statistical outcomes, not tool failures. Context reads and help exited 0.
- No implementation inspection, raw JSONL parsing, direct package import, network, Git, replay or recorded-agent execution occurred. Python standard-library subprocess/timing/file operations were used only to record receipts and this report. Only this reader's two owned files were written.
- CLI-provided hashes are retained in the transcript; I did not independently authenticate execution, validate replay or independently prove environment equality. Integrity seals and declared scenario equality do not provide those guarantees. The integrator's separate source-hash verification is outside this reader's observations.
- The timing excludes untimestamped context setup, and the sample is two supplied fixture cases. This is bounded agent usability QA; it does not measure human adoption, retention, production safety or general diagnostic accuracy.
