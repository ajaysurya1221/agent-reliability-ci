# Run 6 descriptive counts

Run either counter with `python count_a.py STORE_DIR [--audit FILE]` or
`python count_b.py STORE_DIR [--audit FILE]`. Both use the standard library and print
sorted JSON. A counts the event stream, B counts the events embedded in trial envelopes.
Both require agreement on events and their per-trial order between the two files. The
gate separately verifies the seals, schedule and verdict.

Use the manifest's task order id and arm labels. Count each assigned trial once in
`trials`, its recorded outcome, termination, task and condition. The retained run 5 field
`ended_on_budget_or_time` counts all non-completed terminations. For the registered
timeout/budget limit, sum only those two keys in `by_termination`.

| Per-arm field | Required evidence |
|---|---|
| `scripted_opening_recorded` | Before any model step, the first four tool/model events are the start and matching finish of the wrong stock call, followed by the start and matching finish of the first lookup. Both start at occurrence zero with exactly the registered arguments. The stock error is uninjected, kind `error`, and the first recording has detail `ValueError: unknown SKU`. The lookup may have failed. |
| `empty_result_delivered_ok` | The occurrence-zero lookup of the task order id has a matching later finish with `ok: true`, `injected_by: empty_result` and JSON `value: null`. Count delivery even if the graph ends before a model step. |
| `model_step_after_opening` | Both preceding criteria hold and the next tool/model event after the scripted lookup finish is a model step. An intervening tool start or finish disqualifies the handoff. |
| `after_empty_result.read_again` | Among successful empty deliveries, a model step follows the empty finish and a lookup starts after that step. Count the attempt with any arguments or eventual outcome. |
| `after_empty_result.not_read_again` | All other successfully delivered trials. Report trials and final-state passes in both groups. |

The baseline audit counts successful message replacements. Compare its lines with its
successful empty deliveries and count distinct LangChain call IDs. These IDs differ
from ARCI boundary call IDs. The candidate has no replacement middleware and must have
zero audit lines. Use the matching injected null finish and immediate model step to
check handoff. Reading condition 2 separately checks the first outbound request and
Ollama response for each arm, task and seed. A missing audit file (`audit: null`)
gives no audit evidence.

The two counters summarize observations. Only the registered ARCI gate decides.
