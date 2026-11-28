# Compare two versions with DeepEval

DeepEval 4.3.6 was tested with pytest 9.2.0 on Python 3.13.12.
The test ran 20 word checks with a Python metric called `ContainsWord`.
DeepEval passed the JUnit option to pytest. The saved XML also covers a failed
metric, a skipped test and an exception. The checks used no model or account.

Give each task an id based on its input, as in the `ids=` example below.
DeepEval's saved report names one such case `test_agent::test_agent[task-w01]`.
A positional id such as `golden0` can pair different tasks if you reorder the inputs.

Run this from the directory containing `test_agent.py`. In the fixture,
`AGENT_MODE` selects the version. For your own tests, use your two settings
and keep the inputs and metric fixed. Each launch should run the tests afresh.

```sh
arci check-change --format junit \
  --baseline 'env AGENT_MODE=pass deepeval test run test_agent.py --junitxml={out}' \
  --candidate 'env AGENT_MODE=fail deepeval test run test_agent.py --junitxml={out}' \
  --out-dir deepeval-comparison
```

An exception in the test body counts as a failure, just like a wrong answer.
If the judge is down, the error bound cannot distinguish that fault from a worse
answer. Put this guard inside each affected test, before calling the judge.
Pytest will emit a skipped row with that task’s ID. ARCI counts the pair as an
error. Here you supply the `judge_available` and `judge` fixtures. The judge
returns true when the answer passes.

```python
@pytest.mark.parametrize("word", WORDS, ids=[f"task-{w}" for w in WORDS])
def test_agent(word, judge_available, judge):
    if not judge_available:
        pytest.skip("judge model not reachable")
    assert judge(agent(word))
```

Other tools also report statistics. MLflow compares paired runs and promptfoo
reports per-test pass-rate ranges for repeats. For ARCI's margin and stopping
rule, see [check-change](check-change.md).

[Fixture script](../../tests/unit/integrations/real/deepeval/test_agent.py.txt) · [Fixture notes](../../tests/unit/integrations/real/README.md)
