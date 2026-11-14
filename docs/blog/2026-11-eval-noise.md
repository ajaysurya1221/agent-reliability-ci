# Your eval dropped 6 points. An agent compared with itself does that, or worse, a quarter of the time.

*A calculation, one real study, and what to do about it.*

You change a prompt, re-run your 50-task eval, and the pass rate goes from 80% to 74%. Is the
new version worse?

## Compare an agent with itself

Take one agent that passes each of 50 tasks 80% of the time, each task independent of the
others. Run the suite twice. Call the first run "baseline" and the second "candidate". Nothing
changed between them.

How often does the "candidate" look worse? This is arithmetic, not a measurement:

| The second run is worse by | How often |
|---|---:|
| 4 points or more (2 tasks) | 35.3% |
| 6 points or more (3 tasks) | 26.5% |
| 10 points or more (5 tasks) | 13.0% |

So a drop of 6 points or more on one run of 50 tasks is what an unchanged agent shows about
one time in four. The same holds in the other direction: an unchanged agent looks 6 points
or more *better* just as often.

More tasks help, slowly. With 200 tasks at the same pass rate, a drop of 6 points or more
still appears 7.5% of the time with nothing changed.

## One real study

In the second of two registered experiments in a [study of two local models](https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/docs/results/order-desk-study.md)
on 96 task-and-fault combinations, the first round had the smaller model 11.5 points behind
(85 of 96 against 96 of 96). The rule fixed before the run asked whether it was within 10
points. One round could not answer that. After five rounds the gap was 10.8 points and the
verdict was still INCONCLUSIVE: the data could not separate "just inside 10 points" from "just
outside".

## What repetition buys

Repeat the whole suite, and decide with a rule you wrote down first. With the same 50 tasks
and the rule ARCI uses (is the candidate within 10 points of the baseline; each kind of wrong
verdict held to 2.5% under stated assumptions), these are model projections for independent
tasks:

| | One run | 8 runs |
|---|---:|---:|
| Unchanged agent (80% and 80%): verdict PASS | 4.0% | 75.9% |
| Unchanged agent: wrong verdict BLOCK | 0.0004% | 0.0006% |
| Real drop (80% to 60%): verdict BLOCK | 2.4% | 63.3% |

One run almost never decides anything. Eight runs usually do, and when they do not, the
verdict says INCONCLUSIVE instead of guessing.

PASS here means "not worse by 10 points or more". It never means the new version is better.

## Try it on results you already have

ARCI 2.2 has a command that reads pass/fail results another tool wrote (Inspect AI logs,
pytest JUnit XML, or a CSV) and gives PASS, BLOCK or INCONCLUSIVE. It does not run your agent.

```sh
uvx agent-reliability-ci verdict --example
```

On results that already exist, the output starts with "Descriptive verdict" and claims no
error bound, because the rule was written after the data. To get the bound, write the rule
first, then run both versions, then run the command. The
[recipe](https://github.com/ajaysurya1221/agent-reliability-ci/blob/main/docs/recipes/verdict.md)
shows both, and a table of how many repetitions different suite sizes need.

Other tools compare two eval runs statistically too, for example
[evalsig](https://pypi.org/project/evalsig/) and the comparison in
[inspect-mlflow](https://inspect-mlflow.readthedocs.io/en/latest/comparison.html). Use whichever
fits; the point of this post holds for all of them.

## Limits

The tables assume tasks that are independent and behave the same in every run. Real suites
have related tasks and models that drift, and both make single runs less trustworthy, not
more. The percentages are calculations from that model, not measurements of any agent. The
study is one suite, one prompt, two models, one machine.

Every figure in this post is recomputed by a test in the repository
(`tests/unit/docs/test_blog_figures.py`).
