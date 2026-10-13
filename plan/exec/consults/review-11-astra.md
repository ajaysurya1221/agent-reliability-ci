REVIEW 11 — Reviewer Astra | Verdict REVISE

Findings by severity:

- **MAJOR — [README.md:285](/Users/ajay/Developer/.arci-worktrees/wt-readme/README.md:285): PyPI documentation links remain broken.** The latest checked revision, `1740188`, still contains **34 relative Markdown destinations**, including the descriptor reference, statistics contract, command-agent instructions and trust model. PyPI readers cannot follow these essential onboarding and interpretation links. The two PNG URLs have been fixed. **Verify:** inspect the rendered package description and resolve its links from the PyPI project page.

- **MINOR — [README.md:284](/Users/ajay/Developer/.arci-worktrees/wt-readme/README.md:284): “with the manifest’s default” remains inaccurate.** A descriptor supplies omitted `task_id` from `experiment_id`; `Manifest` requires `task_id`. Descriptor faults default `bucket` to `falsify`; `FaultSpec` requires it. The revision correctly acknowledges aliases but still overstates default equivalence. **Verify:** compare the descriptor models and `to_manifest()` at `76523e5` with the frozen schema.

Required changes (for REVISE/REJECT):

1. Make the PyPI-facing documentation destinations absolute. Preserve the required verbatim Independence paragraph; coordinate package-description URL normalization for its relative `NOTICE` link.
2. Replace the default-equivalence sentence with: “The descriptor expands documented shorthands into a sealed manifest; the key reference lists its defaults.”

Follow-ups:

- **Scope:** reviewed requested `9864488`, then checked concurrent README fixes through `1740188`. Line numbers above refer to `1740188`; both findings persist.
- **Cold-read assessment:** the first screen matches the ADR verbatim, measures **191 words**, and provides purpose, Python-agent audience, positive relative-PASS meaning, limitations and install/init/run commands. No prohibited prose jargon remains. Developer, builder, CI engineer and researcher routes are understandable. An MCP server author still needs a below-fold clarification that the server is the shared environment, rather than a separately versioned comparison target.
- **Verification passed:** the exact YAML example compiles and seals using `76523e5`, including bare-string arms, singular `fault`, `occurrence: 0` and `n_per_arm: 8`. Thresholds **42/8**, the probability table and **18 byte-identical archived decisions** independently recomputed. Init behavior, `--out runs`, CI coverage and Windows limitations match inspected code. Demo wording distinguishes fresh reproduction from recorded evidence; Independence and both tables remain unchanged; limitations were not loosened.
- **Checks and limits:** `.venv/bin/pytest -p no:cacheprovider --capture=sys tests/unit/examples/test_retry_example.py::test_fixed_seed_scenario_mix_is_environment_driven` ended **“1 passed in 0.05s”**; figure verification and diff whitespace checks passed. No files changed. No network, installation, full demo or rendered desktop/mobile PyPI check was performed; hosted rendering remains unverified.

