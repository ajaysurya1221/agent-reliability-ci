# Automated non-author trace-check usability rehearsal

This is observed agent QA, not human adoption, retention, production validation, independent reproduction of the recorded executions, or a release decision. The reader agent did not author this feature. All three assigned cases were classified without requesting assistance.

## Timing and execution boundary

- Start (clock tool): **2026-11-03 14:13:47 UTC**.
- Observation/classification end (clock tool): **2026-11-03 14:16:10 UTC**.
- Measured observation wall time: **143 seconds (2 minutes 23 seconds)**, within the 30-minute cap. Report filing followed the observation period.
- Installed interpreter: `/var/folders/2k/b4x5xvk54w36pjwr4kxjgx7w0000gn/T/arci-trace-installed-5dpunht_/venv/bin/python`.
- Every CLI command used `env -u PYTHONPATH .../python -P -m arci` with cwd `/tmp`; all source paths were absolute paths under `/Users/ajay/Developer/.arci-worktrees/trace-check`.
- Only `reader-report.md` and `reader-commands.txt` were written. No source-store edits, Git mutations, installs, network requests, live model calls, agents, oracles, recorded commands, replay, or `arci gate` execution occurred.
- Read the repository `AGENTS.md`; the specific rehearsal blinding rule took precedence over its general request to read implementation source. No implementation source, fixture source, `build_fixture.py`, `PROTOCOL.md`, answer key, or other rehearsal report was read before completing this report. Immediate filenames inside the four assigned source stores were listed; only selected trial records and manifest data were inspected.
- Blinding was limited: before case execution, the allowed recipe described generic agent A/B missing-retry examples, `MATCH` despite another experiment's `BLOCK`, and a benign preserved-field pilot. This primed the task categories. It did not reveal these case-specific tool names or diagnostic-label value. A narrow memory search for `trace-check` returned no hits.
- Exact shell commands, cwd, exits, and all attempts are in `reader-commands.txt`. CLI source gates below are the freshly re-derived verdicts reported by `trace-check`; stored gate files were not consulted or executed.

## Predeclared CI rule

The assignment required an exact-path check plus a statistical gate before results were observed. Following the allowed recipe, preserve a nonzero **candidate source gate** exit first; otherwise return the trace exit. Green therefore requires candidate gate `PASS/0` and diagnostic `MATCH/0`. No experiment was repeated or enlarged to seek a passing verdict. If both sources were additionally required to have passing gates, none of these cases would become green either.

| Case | Actual diagnostic / process exit | Baseline source gate | Candidate source gate | Composed CI exit | Green? |
|---|---|---|---|---:|---|
| case-1 | `DRIFT / 1` | `PASS / 0` | `PASS / 0` | 1 | No: exact path differs |
| case-2 | `DRIFT / 1` | `INCONCLUSIVE / 2` | `INCONCLUSIVE / 2` | 2 | No: statistical exit takes precedence |
| case-3 | `MATCH / 0` | `INCONCLUSIVE / 2` | `BLOCK / 1` | 1 | No: matching this trace does not override the gate |

All six selected trial outcomes were `PASS`; these are distinct from the whole-run gate verdicts. Default text and JSON output agreed on status, process exit, first difference, and source identities in all three cases.

## Case-1: omitted decision call and changed recorded decision

Sources are the baseline and candidate trial `clean:00000` in `docs/results/guardrail/2026-10-05/guardrail-live-c-ask-clean-50`.

- First recorded difference: zero-based normalized **step 0**, JSON Pointer **`/payload/arguments/applied`**.
- CLI baseline kind/hash: `null / null` (text says `<missing>`).
- CLI candidate kind: `tool_start`; candidate differing-value SHA-256: `0ffe7d295da4ee87a69478d7de0fc2ff783d541374353ff920913ed9933873c5`.
- Targeted raw records show baseline calls **`decision:systemone`**, then calls **`record`** with `{ "applied": "tightened", "decision": "deny", "static": "ask" }`. Candidate has no `decision:systemone` tool event and calls **`record` directly**, with `{ "applied": "static-only", "decision": "ask", "static": "ask" }`.
- Practical interpretation: candidate omits the recorded decision-provider call and leaves the static `ask` decision instead of the baseline's tightened `deny`. This is an omitted tool call, not evidence of a missing retry. Both selected trials and the shared experiment gate pass; drift alone does not prove worse reliability or its cause.
- **Default output was insufficient to name the omitted call.** It accurately locates the first differing leaf, but provides neither tool name nor value. At step 0 the baseline event exists (`decision:systemone`); only the `applied` leaf is absent. Reading `<missing>` as an absent baseline event would be incorrect. Selected raw-record inspection was necessary to identify the operation-level change.

## Case-2: preserved diagnostic content changes

Sources are `clean:00000:baseline` and `clean:00000:candidate` in `plan/exec/trace-check/rehearsal-2026-11-03/fixture-evidence/stores/arci-trace-rehearsal-2026-11-03`.

- First recorded difference: zero-based normalized **step 4**, JSON Pointer **`/payload/result/diagnostic_label`**.
- CLI baseline kind/hash: `null / null`; candidate kind: `agent_result`.
- Candidate differing-value SHA-256: `b5a0272cdbec8dc10e680e2c08b7e10c3e722aa5713f7702844beff4b1072571`.
- Baseline result is `{ "success": true }`; candidate result is `{ "diagnostic_label": "rehearsal-v2", "success": true }`.
- Both selected traces call `get_reservation` then `confirm`. A focused stdlib comparison of the documented selected view found both tool starts and finishes equal after removing top-level call IDs, with identical documented terminal fields and final state. The selected normalized difference is the added result label.
- Practical interpretation: this is benign diagnostic content drift relative to the observed tool behavior, terminal contract result, and final state. The label is retained payload content, not excluded wrapper timing. It is still a valid exact-path failure. Neither the unchanged observed operational result nor `DRIFT` establishes a broader reliability claim; the experiment remains `INCONCLUSIVE`.
- **Default output was enough to locate and name the new field, but not its value or establish the surrounding behavior remained equal.** Targeted raw-record inspection was necessary for the `rehearsal-v2` value and the benign-content interpretation. JSON output also supplies hashes rather than payload values.

## Case-3: same selected baseline trace, different experiment gates

Sources are `provider_down:00000:baseline` from `guardrail-live-b-ask-provider_down-50` and `guardrail-live-b-ask-provider_down-200`, both under `docs/results/guardrail/2026-10-05`.

- Actual status is `MATCH / 0`; JSON `first_difference` is **`null`**. There is no first differing normalized step or field.
- Both selected records are **baseline-arm** trials, even though the second positional source is labeled `Candidate` in the diagnostic. The second source's gate is a whole-experiment verdict, not a verdict about this selected baseline trial.
- Raw inspection confirms both selected traces record `decision:systemone` failing with injected `http_529`, then `record` with `applied=unavailable`, `decision=ask`, and `static=ask`, ending in the same successful terminal state.
- Practical interpretation: the selected normalized baseline behavior matches across the two stores. This does not compare or certify every candidate trial in the second experiment, establish safety, authenticate execution, or verify replay.
- **Default output was sufficient for the match and non-green CI conclusion.** It clearly prints baseline source `INCONCLUSIVE/2` and candidate source `BLOCK/1`; no raw inspection was necessary for that conclusion. Raw inspection was performed as part of the shared selected-record inspection and only added behavioral context.

## Source identity receipts

The `manifest_sha256` and `trial_sha256` values below are the full record identities printed by the CLI, not raw-file byte hashes. The inspected JSON self-hash fields agree with these identities.

| Case / source | Manifest record SHA-256 | Selected trial record SHA-256 | Re-derived decision SHA-256 |
|---|---|---|---|
| 1 baseline | `9b9600226b434635e959932ca450e40dc2782093845c307303f5fd9d5514d2d3` | `7798cd83d7385c5b72c1f2b69367ac98d2e2edc9c6d8421ed676f7b787d91ef6` | `fe2e793037e2e26aaeea7a210cc13aa1abf6e621b7edeb0a5fb646c8ed0dab14` |
| 1 candidate | `9b9600226b434635e959932ca450e40dc2782093845c307303f5fd9d5514d2d3` | `10e4f5b48159bac6c72c3e2672ecec765aac24df7cbb745aba620f48efb6c8ac` | `fe2e793037e2e26aaeea7a210cc13aa1abf6e621b7edeb0a5fb646c8ed0dab14` |
| 2 baseline | `1dfcd7f8a34eefacc53af85f5a2379d58f37b8dd4cbcea7366f2b1b23f5536b0` | `7807443e7a1da6275e49ca86c8e879f87c9ac4bba9981a96ad1cddeac6881c83` | `63c8378fcb0ee28e038edb31005bf0e239742340685c5e683fcc6f9c76acdb23` |
| 2 candidate | `1dfcd7f8a34eefacc53af85f5a2379d58f37b8dd4cbcea7366f2b1b23f5536b0` | `aa31798050446704816e99f7852ab8d2104db0892d0303961ddc20314089d25d` | `63c8378fcb0ee28e038edb31005bf0e239742340685c5e683fcc6f9c76acdb23` |
| 3 baseline | `423b6719ac42281a2951aa30a8fda54c4848c4dc252964cd9b245784056f5585` | `0a6e12f68bab19ddf5cd48046fbb03afa143e6b07f283b0f6d41eb82578fe17d` | `f5180309d92b49385bb38e4d9eac9b88af8619d9ef4b37676fe0af0cd28c92e9` |
| 3 candidate | `4046a23989ec8dbd6abf8ae02e1b8622a6b811a55eec58ef1cac7ac9bf20139f` | `4670075778d0b741dcd2cd325cc373cf40058a36587751c89ebf4d938086261d` | `13fa8a91fe7b98d059be460bb04f21399b064ff99d5a150fa5f5b102e7f4e3dc` |

Supplemental raw-file SHA-256 values measured with stdlib `hashlib` after the CLI reads:

| Assigned source store | `manifest.json` bytes | `trials.jsonl` bytes |
|---|---|---|
| case-1 shared store | `b3ceb3d339ff8a11757c4d17aec61b40342a969eecf13d9ebfd0cb3208a01608` | `e6beb36380f6d550a11cb4b911533421002e411fe4f2c1a28685d06c41923ea7` |
| case-2 shared store | `0b1051695276c97cd8e2ae4fb8b5b672a94387d87b56b7e2a101832aabddd07d` | `7b2ce26067b521fc01c1bfaded8c61dde8c82dd18d6e74730e27f979282290ae` |
| case-3 baseline store | `3bd3aaaafa4065217e3ff1f2927297cf0b29e194ed493ff036560d10cfd80652` | `6c0b76eaf80b0d89d1b8169ced213f82cd7336c69c086b8181b495410927629d` |
| case-3 candidate store | `92d2abca37dfec8ba2bc1cded716bb54f05827dca08b54bbfbf6b777eefea059` | `810735253f743c585a90bb3529f7d64790afd985e12d5692673d7a7320095f0e` |

## Assistance, errors, and friction

- Assistance requests: **none**. No root answer hints received. The root was sent classifications only after the observations were complete.
- Completed attempts: help, default text and JSON for each of three cases, selected-record inspection, manifest/trial identity capture, and a focused case-2 comparison. No command invocation failed unexpectedly; `DRIFT/1` and no-match `rg/1` were expected statuses.
- An initial dump of all six selected raw records exceeded the tool display budget and was truncated. This was a reader command-design error, not a CLI error. A compact event/terminal selection recovered the required evidence, followed by a focused case-2 read. No unobserved truncated text was used to support a conclusion.
- No incorrect behavioral or CI conclusion was adopted. The main interpretation hazard was the case-1 `<missing>` label: it describes a leaf absent from an existing baseline event, not an absent event. The reader resolved this through raw inspection before naming the omitted candidate call.
- Usability finding: the default first-difference locator is useful but is not by itself sufficient to identify a missing tool call when unlike events are aligned at the same normalized step. Showing the containing tool names, or explaining that `<missing>` applies to the pointed value, could reduce this inspection step while retaining hash-only payload handling.
- Source gates and limits were readily visible. The text explicitly warns that diagnostic status does not replace either gate, integrity is not execution authenticity or replay verification, and fixture identity is declaration-only because all four manifests have empty `fixtures_sha256` values.
- These observations cover three assigned recorded cases and one automated reader. Human consent, human time-to-understanding, adoption, seven-day reuse/retention, and production performance remain **unmeasured**. This report does not establish a source-store before/after immutability proof; the commands were read-only and post-read file hashes were recorded.

## Filing receipt after initial report

Both owned files were read back successfully; the report's required fields were present. The clock tool returned **2026-11-03 14:18:05 UTC**, or **258 seconds (4 minutes 18 seconds)** after the start, including report preparation and this readback. After initial classification, the root reported adding a targeted-inspection paragraph to the recipe. The reader did not reopen the recipe or re-score the completed observations; that later documentation change was not assistance during initial classification. Initial results, friction, and command attempts above are preserved.

