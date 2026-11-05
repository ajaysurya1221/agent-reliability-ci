# Reader one: independent agent first-use QA

**Result:** Both supplied cases were diagnosed through the installed CLI within the 300-second target. No usability blocker or operational error was observed. This is agent usability QA, not human adoption or retention evidence. The recipe exposes the generic retry example, so this was not blinded.

The protocol identifies product commit `cb2ab9e`; I did not independently inspect Git or implementation. I read `PROTOCOL.md` first, then only the recipe, `cases.json`, CLI help and CLI reports. Every CLI call used `/tmp/arci-triage-v090.ygMrHy/empty`, removed `PYTHONPATH`, and set `PYTHONSAFEPATH=1`. I did not inspect source code, read/parse JSONL, import the package, execute recorded agents, access the network, or use Git. No files other than the two owned reader-one receipts were written by this reader.

## Timing

Times below are exact UTC timestamps observed through the system clock. Diagnosis duration begins immediately before the case's CLI invocation and ends when the interpretation is recorded; it includes reading, reasoning, and preparing the recorded diagnosis. Initial recipe/help reading occurred before timing.

| Case | Diagnosis start UTC | Diagnosis end UTC | Elapsed seconds | CLI seconds | CLI exit |
|---|---|---|---:|---:|---:|
| retry | 2026-11-05T18:44:49.007764+00:00 | 2026-11-05T18:45:08.172095+00:00 | 19.164331 | 0.542558 | 1 |
| repeat | 2026-11-05T18:45:08.172425+00:00 | 2026-11-05T18:46:19.257688+00:00 | 71.085263 | 0.091727 | 2 |

The retained `reader-one-commands.txt` contains exact read/help and diagnostic commands, process exits, full diagnostic stdout/stderr, command start/end timestamps and diagnosis timestamps. A Python standard-library subprocess wrapper captured process output and timing; it did not import ARCI or read the stores directly.

## Retry diagnosis

Command:

```sh
env -u PYTHONPATH PYTHONSAFEPATH=1 /tmp/arci-triage-v090.ygMrHy/installed/bin/arci triage /tmp/arci-triage-v090.ygMrHy/demo/runs/arci-demo-agent_b-reserve-timeout-200
```

The complete experiment is **BLOCK**, with valid triage and process exit **1**. At its single 200-pair look, the gating `reserve-timeout` condition reports baseline 192/200 PASS and candidate 132/200 PASS, with zero ERROR records and zero candidate hard violations.

Automatic selection shows both failure groups: 65 FAIL and 3 FAIL; zero groups omitted. The first representative is baseline `reserve-timeout:00005:baseline` PASS against candidate `reserve-timeout:00005:candidate` FAIL. Its normalized traces **DRIFT** at step 4, pointer `/payload/arguments/quantity`:

- Baseline: `tool_start`, sequence 9, tool `reserve`, occurrence 1, differing value present.
- Candidate: `tool_start`, sequence 10, tool `confirm`, occurrence 0, differing value absent.

The containing operation changes from a repeated `reserve` to `confirm`; both sides have a containing event. The missing candidate quantity is an absent field value, not an absent event. This aligns with the recipe's constructed retry example, but the position alone does not establish an arbitrary failure's root cause.

The other selected pair (`reserve-timeout:00063`) is FAIL on both sides and **MATCH**. That selected trace match does not override the full experiment's BLOCK.

## Repeat diagnosis

Command:

```sh
env -u PYTHONPATH PYTHONSAFEPATH=1 /tmp/arci-triage-v090.ygMrHy/installed/bin/arci triage /Users/ajay/Developer/.arci-worktrees/triage-v090/plan/exec/trace-check/rehearsal-2026-11-03/fixture-evidence/stores/arci-trace-rehearsal-2026-11-03 --trial clean:00000:candidate
```

The explicit candidate ID compares with its scheduled baseline partner. Both selected trials PASS, and the clean condition has baseline 1/1 PASS and candidate 1/1 PASS, zero ERROR records and zero candidate hard violations. The complete statistical gate is nevertheless **INCONCLUSIVE**, with valid triage and process exit **2**. There are zero failure groups; explicit passing selection still produces one comparison without changing the statistical experiment.

The pair **DRIFT** is at normalized step 4, pointer `/payload/result/diagnostic_label`. Both containing contexts are `agent_result` at sequence 9. The baseline field is absent and the candidate field is present. This is a result-field difference within an existing event on both sides; the CLI does not identify a tool-operation change at this first difference.

Both per-trial PASS outcomes do not establish a whole-run PASS, and the DRIFT does not change the INCONCLUSIVE verdict. Neither the field name nor the passing records proves that the difference is benign.

## Findings and limits

The default text report was sufficient for both diagnoses without JSONL access, a JSON report, or author assistance. It states the statistical exit, containing-event context and limits directly. The explicit trial argument was discoverable in the recipe and help. Both nonzero exits were expected statistical results rather than operational failures; stderr was empty. No command retries, mistakes, or runtime help occurred.

Only the first difference is shown. These observations cannot establish later equivalence, benignness, root cause, or that drift caused the observed reliability difference. The selected examples are descriptive rather than causal or significance rankings. The selected normalized observed tool/result traces and terminal states do not authenticate execution, verify replay, or establish actual environment equality; the report warns that fixture identities are empty and environment equality is declaration-only. No fresh agent execution occurred. Source immutability and seal verification beyond the CLI's emitted evidence remain for the integrator's independent pre/post checks.

Assistance was limited to supplied protocol/recipe/case paths and installed CLI help. No answer key or additional author assistance was used. Two agent cases cannot establish human usability, adoption, or retention.
