# Order-desk imported outcomes

These CSV files export the recorded outcomes of the two order-desk study stores.
Each task id is `<task_id>/<condition_id>`; rows carry the original round number.
Only complete rounds evaluated by the suite decision are included.

Regenerate from the repository root:

```sh
.venv/bin/python -m bench.export_outcomes docs/results/order-desk-study/run-1/order-desk-gemma4-12b-vs-qwen3.5-4b@533c6d1a78ccc1a201eb7e265a61873244d48c2ac0e26cde5a50bc7dfd5f83bb examples/outcomes/order-desk/run-1
.venv/bin/python -m bench.export_outcomes docs/results/order-desk-study/run-2/order-desk-gemma4-12b-vs-qwen3.5-4b-recoverable@eaa438b195f418b66878a57422ab6229b2171c74dd8d6eb7ba097ec4a09b96fb examples/outcomes/order-desk/run-2
cp examples/outcomes/order-desk/run-1/{rule.yaml,baseline.csv,candidate.csv} src/arci/demo/outcomes/order-desk-run-1/
.venv/bin/arci verdict examples/outcomes/order-desk/run-1/rule.yaml --baseline examples/outcomes/order-desk/run-1/baseline.csv --candidate examples/outcomes/order-desk/run-1/candidate.csv
.venv/bin/arci verdict examples/outcomes/order-desk/run-2/rule.yaml --baseline examples/outcomes/order-desk/run-2/baseline.csv --candidate examples/outcomes/order-desk/run-2/candidate.csv
```

Run 1 begins (exit 1; also available as `arci verdict --example`):
```text
Descriptive verdict: the rule file declares it was written after outcomes existed. The error bound is not claimed.
VERDICT: BLOCK (exit 1)
```

Run 2 begins (exit 2):
```text
Descriptive verdict: the rule file declares it was written after outcomes existed. The error bound is not claimed.
VERDICT: INCONCLUSIVE (exit 2)
```

These verdicts are descriptive because the outcomes rule was written afterwards, while the [study's own suite rule](../../../docs/results/order-desk-study.md) was registered before each run.
