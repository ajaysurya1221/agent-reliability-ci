Read-only review of two task briefs before any code is written. Do not edit anything.

Briefs:
- /Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/R1-tool-outcomes.md
- /Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/R2-model-swap.md

They will be carried out in this worktree (ARCI 2.0.0, read AGENTS.md first). Check each brief against the actual code and say, with file:line evidence:

1. Any statement in a brief that is false about the code (function names, line positions, payload fields, what tests exist, what register.py / configuration.py / init.py actually do).
2. Any requirement that cannot be met without editing a file in FROZEN.sha256, or that conflicts with a frozen document or an acceptance test.
3. R1: is the "own failure" definition sound given how src/arci/toolbox.py, src/arci/perturb.py, src/arci/runner.py and src/arci/adapters/langchain.py record tool_finish (ok, error_kind, injected_by)? Name cases where it would miscount: retries by middleware, harness failures, budget stops, incomplete calls, decision tools, a fault that makes a later uninjected call fail. Is there any JSON report schema, versioned contract or test that a new JSON key would break? Would v1 output change anywhere?
4. R2: is the three-row rule implementable with the registration check as it exists? What exactly do the arm labels in arci.yaml feed into (experiment id, digest, reports)? What is the smallest honest fix for requirement 3? Does a user middleware with wrap_tool_call returning a ToolMessage for ValueError work with the adapter as written, or is it rejected ("tools that handle their own errors" or similar)? Quote the code.
5. Files the two briefs both need to touch (they will run one after the other, R1 first).
6. Anything ambiguous enough that two implementers would build different things.

Answer under 80 lines: numbered findings, each BLOCKING / SHOULD FIX / NOTE, with the correction you propose.
