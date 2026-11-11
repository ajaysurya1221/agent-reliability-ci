## New in 2.0: many tasks, and LangChain agents

**Suites.** v1 gates one task under a few fault conditions. A suite registers many tasks by
fault conditions and gates the suite average, in rounds, stopping as soon as the evidence
decides. A PASS covers the average and can hide a regression in one task, so the per-task
table sits beside every verdict. Nothing can PASS before about 80 paired runs at the
default margin. The statistics and their assumptions are in
[docs/STATISTICS_SUITE.md](docs/STATISTICS_SUITE.md).

**LangChain.** If your agent is built with `create_agent`, ARCI can run it behind its tool
boundary: you supply your tools, two settings functions and a check.

```bash
pip install 'agent-reliability-ci[langchain]>=2.0.0'
mkdir try-arci && cd try-arci && arci init --langchain && arci run arci.yaml
```

That runs a 24-task example offline with a scripted model and ends in `BLOCK`, by
construction. To compare real models, see
[examples/langchain_quickstart](examples/langchain_quickstart/README.md) and the
[recipe](docs/recipes/langchain.md).

**One recorded comparison.** A pre-registered run of that example on two local models
(12B baseline, 4B candidate, temperature 0.7) ended in `BLOCK` after one round: 96 of 96
against 70 of 96, with the prediction written beforehand being `PASS`. The report also
showed the injected fault firing in 24 of 24 baseline trials but 18 to 20 of 24 candidate
trials per faulted condition. It is one comparison on one suite and says nothing about
these models elsewhere. Report: [docs/results/order-desk-study.html](docs/results/order-desk-study.html).
