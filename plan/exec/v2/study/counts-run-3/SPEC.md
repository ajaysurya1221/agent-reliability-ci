# Descriptive counts for run 3: definitions

Two scripts, written separately by two agents that do not see each other's code, compute
these counts from a sealed suite store (`manifest.json`, `trials.jsonl`, `events.jsonl`).
They decide nothing: the verdict comes from the tool. Both scripts are committed with the
pre-registration, before any run 3 trial, after each has been run on run 2's published
store and the two outputs compared.

## Command

    python count_X.py STORE_DIR [--audit FILE]

It prints one JSON object to standard output, keys sorted, and nothing else. It reads only
the three files of the store and, if given, the audit file. It uses the standard library
only.

## Output

    {
      "store": "<name of STORE_DIR>",
      "arms": {
        "<arm as written in the trial records>": {
          "label": "<the arm's label from the manifest>",
          "trials": int,
          "passed": int,
          "failed": int,
          "errored": int,
          "ended_on_budget_or_time": int,
          "by_termination": {"<termination as recorded>": int},
          "by_condition": {"<condition id>": {"trials": int, "passed": int}},
          "by_task": {"<task id>": {"trials": int, "passed": int}},
          "first_call_not_lookup_order": int,
          "never_called_lookup_order": int,
          "empty_result_delivered": int,
          "empty_result_delivered_ok": int,
          "after_empty_result": {
            "read_again": {"trials": int, "passed": int},
            "not_read_again": {"trials": int, "passed": int}
          },
          "uninjected_tool_error": {"trials": int, "passed": int}
        }
      },
      "audit": null or {"lines": int, "distinct_tool_call_ids": int}
    }

## Definitions

A trial's tool calls are its tool-start and tool-finish events in the order of the event
sequence number.

- `passed`, `failed`, `errored`: by the trial's recorded outcome. `trials` is their sum.
- `ended_on_budget_or_time`: trials whose recorded termination is anything other than a
  normal completion.
- `first_call_not_lookup_order`: trials whose first tool-start names a tool other than
  `lookup_order`. A trial with no tool call at all is not counted here.
- `never_called_lookup_order`: trials with no tool-start that names `lookup_order`.
- `empty_result_delivered`: trials with at least one tool-finish for `lookup_order` that
  the store marks as injected by the empty-result fault.
- `empty_result_delivered_ok`: trials with at least one tool-finish for `lookup_order` that
  the store marks as injected by the empty-result fault and that did not fail (the call is
  recorded as successful). This is the number of trials in which the model was handed the
  empty result itself; a first lookup with a wrong order id fails, is marked injected too,
  and reaches the model as an error text.
- `by_termination`: every trial of the arm, grouped by its recorded termination, whatever
  the values are.
- `after_empty_result`: only trials counted in `empty_result_delivered`. `read_again`:
  the trial has at least one tool-start for `lookup_order` later in the sequence than that
  injected tool-finish. `not_read_again`: it has none. `passed` is the number of those
  trials whose outcome is a pass.
- `uninjected_tool_error`: trials with at least one tool-finish that failed and that the
  store does not mark as injected. `passed`: those of them whose outcome is a pass.
- `by_condition`, `by_task`: every trial of the arm, grouped.
- `audit`: `null` without `--audit`. With it: the number of non-empty lines in the file and
  the number of distinct `tool_call_id` values in them.
