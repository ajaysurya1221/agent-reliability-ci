# Run 4 client request proof

The unmodified run 4 baseline and candidate ran in one process through the registered LangChain adapter and ChatOllama client. An HTTPX mock transport captured the serialized bodies of all 800 POSTs to `/api/chat` in [http.jsonl.gz](http.jsonl.gz).

The proof used the 8 registered stock-note tasks, the first 10 scheduled rounds, and the same scenario seed within each pair. Both arms received the same scripted sequence of responses: look up the order, repeat the lookup, check stock, add the note, finish. ARCI recorded a successful injected empty first lookup in all 160 trials. All 160 passed the study's state oracle.

| Measurement | Baseline | Candidate |
| --- | ---: | ---: |
| Trials × requests per trial | 80 × 5 | 80 × 5 |
| Captured request bodies | 400 | 400 |
| First deliveries of the arm's replacement text | 80 | 80 |
| Appearances of that reply across requests 2–5 | 320 | 320 |
| Appearances with literal content `null` | 0 | 0 |

Paired by round, task and request number, all 80 first-request pairs were byte-identical. Each of the remaining 320 pairs differed in exactly one JSON field, `/messages/3/content`, the tool reply immediately after the first `lookup_order` call. Its two values were:

- Baseline (`agent.EXPLICIT_TEXT`): “lookup_order returned an empty result. Call lookup_order again with the same order_id.”
- Candidate (`agent.NEUTRAL_TEXT`): “lookup_order returned an empty result. This lookup_order result is for the supplied order_id.”

Substituting that single string made all 320 serialized pairs byte-identical. No IDs or other fields were normalized. System prompt, tool schemas, message order, model ID, temperature (0.7), reasoning (`think: false`) and streaming (`true`) matched.

**0 requests left the process.** The mock answered all 800. A Python audit hook refused internet sockets, connection attempts, DNS lookups and datagram sends. It blocked one import-time urllib3 IPv6 capability probe at socket creation. There were zero connect, DNS or send events.

This verifies what the client sends on this scripted path. The transport supplied every response, so the capture provides no evidence about a real model's retry decisions or task success.

To reproduce from this folder:

```sh
proof_python=/Users/ajay/Developer/.arci-worktrees/run4-env/bin/python
env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 "$proof_python" realpath_suite.py
env -i PATH=/usr/bin:/bin PYTHONDONTWRITEBYTECODE=1 "$proof_python" analyse.py
```
