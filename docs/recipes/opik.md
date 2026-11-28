# Compare two versions with Opik and pytest

Opik 2.3.7 was tested with pytest 9.2.0 on Python 3.13.12. The test used
`@opik.llm_unit()` and a Python assertion on 20 words. Pytest wrote the JUnit
XML. The assertion determined the result. The checks used no model or account.

By default the pytest integration tries to send results to Opik's cloud address.
The fixture run with experiment logging left on retried when the sandbox
refused the connection. The command below turns off experiment logging and
disables traces from `@opik.track`. ARCI reads the local pytest file.

Give each input an explicit id with
`@pytest.mark.parametrize("word", WORDS, ids=[f"task-{w}" for w in WORDS])`.
Use the same names on both sides. Positional ids can pair different inputs
when their order changes.

Run this beside `test_agent.py`. Here `AGENT_MODE` selects the version.
Use your two settings and rerun the same tasks and assertions on each launch.

```sh
arci check-change --format junit \
  --baseline 'env AGENT_MODE=pass OPIK_PYTEST_EXPERIMENT_ENABLED=false OPIK_TRACK_DISABLE=true pytest -q -p no:cacheprovider test_agent.py --junitxml={out}' \
  --candidate 'env AGENT_MODE=fail OPIK_PYTEST_EXPERIMENT_ENABLED=false OPIK_TRACK_DISABLE=true pytest -q -p no:cacheprovider test_agent.py --junitxml={out}' \
  --out-dir opik-comparison
```

An exception in the test body counts as a failure. The error bound treats a
broken judge that raises there as a worse answer. Mark a broken setup as
skipped so it counts as an error in ARCI.

```python
if not judge_available:
    pytest.skip("judge model not reachable")
```

MLflow also compares paired runs, and promptfoo reports per-test pass-rate
ranges for repeats. See [check-change](check-change.md) for ARCI's verdicts.

[Fixture script](../../tests/unit/integrations/real/opik/test_agent.py.txt) · [Fixture notes](../../tests/unit/integrations/real/README.md)
