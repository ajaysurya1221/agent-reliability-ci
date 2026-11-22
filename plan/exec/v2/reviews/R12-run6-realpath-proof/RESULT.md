# Run 6 serialized request proof

All 160 first requests contained the wrong stock call, its error, the lookup and its
assigned reply. The 80 first-request pairs differed only in the lookup reply. The same
held for the 240 subsequent pairs under the fixed recovery policy.

| Observed in process | Generic baseline | Raw-null candidate |
|---|---:|---:|
| Scheduled cases | 80 | 80 |
| First requests containing both exchanges | 80 | 80 |
| Scripted cases passing the state oracle | 80 | 80 |
| Requests intercepted by HTTPX | 320 | 320 |

The driver used the registered descriptor and entrypoints, ARCI 2.4.1, its LangChain
adapter, the seeded tools and the registered fault. Each tool boundary recorded a
failed check_stock with the order id as sku and the error ValueError: unknown SKU,
followed by a successful occurrence-zero lookup_order of that id with injected null.
Both finished before the first recorded model step. The fake HTTP transport answered
with a lookup, a stock check, a note and completion. It never contacted a model.

The analyzer checked the Cartesian product of eight tasks, ten rounds, four turns and
two arms. Each pair shared its seed. It checked the actual serialized tool arguments
and error text, model, tools, reasoning flag and temperature. Across 320 paired bodies,
the sole JSON difference was `/messages/5/content`. Substituting that one quoted value
made the original bytes identical, including every other message and field.

- Baseline supplied `The previous tool call returned an empty result. Repeat that call with the same input.`
- Candidate supplied the text `null` as the content of a tool message.

All 640 requests went to MockTransport. The audit hook blocked one internet socket
creation. There were zero connection attempts, DNS requests or datagram sends and zero
requests left the process. This checks client serialization and the scripted oracle
outcomes. Live server delivery and model decisions remain unmeasured.

The registered first-exchange observer also ran during this proof. All 160 receipts
matched the scheduled arm, task and scenario seed exactly once. Each confirmed the
six serialized messages and a completed assistant response on that same fake request.

Capture SHA-256: `c54d20bfa00718ff16569c83ebddb7c12704612d2751272ccec6ef0890bb7e45`.

From this directory the first command recreates the capture. The second checks it.

```sh
p=/Users/ajay/Developer/.arci-worktrees/run4-env/bin/python
env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 "$p" realpath_suite.py
env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 "$p" analyse.py
```

One agent wrote the interface note before writing its black-box tests and the
implementation. The note and tests are under `../../study/blind-tests-run-6/`.

## Other offline checks

From plan/exec/v2, with PYTHONDONTWRITEBYTECODE=1 and the run4-env Python:

```sh
"$p" -m pytest -p no:cacheprovider -o addopts= -q study/order-desk-compound/tests \
  study/blind-tests-run-6 study/counts-run-6/test_counts.py
```

| Check | Final output or observed result |
|---|---|
| Unit, worker, blind, receipt and counter tests | `35 passed in 17.06s` |
| Two counters on the scripted worker store | Byte-identical. Each arm had eight openings, empty deliveries, handoffs, later lookups and passes. Baseline had eight distinct audit IDs, candidate zero. |
| Two counters on the unchanged run 5 store | Byte-identical. Neither arm had a scripted opening. Named had 97 later lookups after 100 empty deliveries, with 86 passes. Generic had 103 after 103, with 92 passes. |
| R12 driver | `160 trials completed and graded; blocked socket events: {'socket.__new__': 1}` |
| First-exchange receipts | `160 assignments with a matching first request and assistant response` |
| R12 analyzer | `320/320 paired bodies byte-identical after changing only /messages/5/content.` |
| R12 network guard | `640 intercepted requests; 0 left the process. Blocked events: {'socket.__new__': 1}` |
| Ruff format and lint | `20 files already formatted` and `All checks passed!` |
| Basedpyright, strict project settings with imports resolved against run4-env | `0 errors, 0 warnings, 0 notes` |
| Planner, six candidate rates | Each finished with `exact projection`. See the six rows in the draft. |
| Descriptor, suite seal and prior runs | Validated. Re-registering a temporary copy reproduced the descriptor and task bytes. |
| Inherited study settings | Tools, oracle, tasks and configuration matched run 5 bytes. System prompt, retry arguments, error and replacement middleware matched run 5. Python and eight package versions matched. |
| Wrapper | `sh -n study/run-6.sh` exited 0 with no output. All three embedded Python blocks compiled. The wrapper itself was never invoked. |
| Registration draft | Consultant's three wording corrections verified. Consultant's BLOCK and `[[PREDICTIONS]]` present. |
| SHA-256 | All 20 study digests verified, ending `run-6.sh: OK`. All 54 frozen digests verified, ending `uv.lock: OK`. |
