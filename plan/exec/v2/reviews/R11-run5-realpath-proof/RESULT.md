# Run 5 client request proof

Across eight stock-note tasks and the first ten scheduled rounds, all 80 pairs of first
requests matched byte for byte. For all 320 pairs of later requests, replacing only the
text of the first lookup reply made the two original bodies byte-identical. **Zero
requests left the process.**

| Captured evidence | Explicit baseline | Generic candidate |
|---|---:|---:|
| Scripted cases passing the final-state check | 80/80 | 80/80 |
| Requests intercepted by HTTPX | 400 | 400 |
| First deliveries of the assigned reply (request 2) | 80 | 80 |
| Appearances of that reply in requests 2–5 | 320 | 320 |
| Tool messages containing the literal reply `null` | 0 | 0 |

The [driver](realpath_suite.py) used the run 5 descriptor, both registered agent
entry points, their LangChain adapter and the ChatOllama client. The two cases in each
pair shared a scenario seed. ARCI recorded a successful first lookup with injected
value `null` in every case. The [mock transport](realpath_proof.py) answered all 800
requests in process. Its script called lookup twice with the same input, checked stock,
added the note and finished. A socket guard blocked one internet socket creation.
It recorded zero connection attempts, DNS lookups or datagram sends.

The [analysis](analyse.py) checked each pair by round, task and request number. The
only differing JSON field was `/messages/3/content`, the reply immediately after the
first lookup. Both assigned values matched the following strings.

- Baseline
  `lookup_order returned an empty result. Call lookup_order again with the same order_id.`
- Candidate
  `The previous tool call returned an empty result. Repeat that call with the same input.`

The raw-body comparison kept every other byte, including message order, tool schemas,
model settings, whitespace and IDs. The [capture](http.jsonl.gz) has SHA-256
`511b08703e4c7ae1e1eb5d0f54dfae79209dfbba7816897cc67a8f07fa1e42dc`.
It establishes what the client serialized for these scripted responses. Live delivery,
model choices and live task outcomes remain untested for run 5.

To check the saved capture from this directory, run the second command below. The first
regenerates the capture with the same scripted policy.

```sh
proof_python=/Users/ajay/Developer/.arci-worktrees/run4-env/bin/python
env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 "$proof_python" realpath_suite.py
env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 "$proof_python" analyse.py
```
