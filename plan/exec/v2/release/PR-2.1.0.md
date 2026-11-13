TITLE: v2.1.0: tool outcomes in suite reports, a clean model swap, corrected study record

## What

- Suite reports gain a descriptive "Tool outcomes" section (Markdown, HTML, JSON key `tool_outcomes`): per arm, trials with a recorded tool failure that has no injection marker and how many of those passed; per tool, trials with and without a recorded start.
- LangChain quickstart: two different model ids now compare the model only (same retry, prompt, temperature; arms labelled with the ids). Equal ids and the offline demo keep the retry-removal comparison. New `docs/recipes/model-swap.md`.
- `docs/results/order-desk-study.md`: both pre-registered runs and the correction to run 1; run 2's report added; run 1's re-rendered.
- README: new first screen (supersedes design record 0009, recorded in 0014), "Related tools", and the "80 paired runs" sentence corrected.
- Version 2.1.0. Frozen list: `pyproject.toml` and `uv.lock` re-hashed, record 0014 added (66 entries).

## Why

Two readers of the public study asked what each arm did with its tools; one showed run 1 could not separate a weaker model from a tool contract that hides errors. The answers took hand-written scripts and a hand-patched example.

## Checked

- The new section reproduces the hand counts from both stored study runs (run 2 candidate: 2 never looked up, 124 with an uninjected failure, 77 passed, 47 not).
- Blind tests written from the contract by a separate agent (51); two adversarial reviews with a skeptic per finding; 17 confirmed minor findings fixed, none blocking.
- Full suite in the core environment; adapter tests on the locked LangChain set and on the latest release; strict type check in both configurations; lint; frozen hashes; calibration bench.
- One live round of the 2.1.0 quickstart in model-swap mode on two local Ollama models (192 trials): arms labelled with the model ids, the same retry in both arms, tool outcomes rendered, verdict re-derived by `arci gate`. A release check, not evidence.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
