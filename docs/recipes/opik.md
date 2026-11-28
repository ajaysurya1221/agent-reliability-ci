# Compare two versions with Opik and pytest

Opik 2.3.7 was tested with pytest 9.2.0 on Python 3.13.12. The test used
`@opik.llm_unit()` and a Python assertion on 20 words. Pytest wrote the JUnit
XML. The assertion determined the result. The checks used no model or account.

By default the pytest integration tries to send results to Opik's cloud address.
In the run with experiment logging on, Opik retried the connection after the
sandbox blocked it. The command below turns off experiment logging and
disables traces from `@opik.track`. ARCI reads the local pytest file.

Give each input the same id on both sides, as in the `ids=` example below.
If the ids depend on the order of the inputs, reordering them can pair two
different tasks.

Run this beside `test_agent.py`. Here `AGENT_MODE` selects the version.
Use your two settings and rerun the same tasks and assertions on each launch.

```sh
arci check-change --format junit \
  --baseline 'env AGENT_MODE=pass OPIK_PYTEST_EXPERIMENT_ENABLED=false OPIK_TRACK_DISABLE=true pytest -q -p no:cacheprovider test_agent.py --junitxml={out}' \
  --candidate 'env AGENT_MODE=fail OPIK_PYTEST_EXPERIMENT_ENABLED=false OPIK_TRACK_DISABLE=true pytest -q -p no:cacheprovider test_agent.py --junitxml={out}' \
  --out-dir opik-comparison
```

An exception in the test body counts as a failure. The error bound treats a
broken judge that raises there as a worse answer. Put this guard inside each
affected test, before calling the judge. Pytest will emit a skipped row with
that task’s ID. ARCI counts the pair as an error. Here you supply the
`judge_available` and `judge` fixtures. The judge returns true when the answer passes.

```python
@opik.llm_unit()
@pytest.mark.parametrize("word", WORDS, ids=[f"task-{w}" for w in WORDS])
def test_agent(word, judge_available, judge):
    if not judge_available:
        pytest.skip("judge model not reachable")
    assert judge(agent(word))
```

MLflow also compares paired runs, and promptfoo reports per-test pass-rate
ranges for repeats. See [check-change](check-change.md) for ARCI's verdicts.

[Fixture script](../../tests/unit/integrations/real/opik/test_agent.py.txt) · [Fixture notes](../../tests/unit/integrations/real/README.md)
