# P3a quality contract

Source: `/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/P3a-langchain-adapter-core.md`. All requirements in that brief apply without narrowing. Python strict checks; no network or dependencies; no git mutation; frozen hashes unchanged.

Runtime owner: adapter_core (the two adapter source files). Test owner: adapter_tests (adapter fixtures and behavioral tests). Parent owns toolbox method and carrier, toolbox tests, lazy-import tests, adapter type configuration, verification evidence and final review. No preexisting changes.

Acceptance: runner faults/budgets/snapshot/replay; every rejection live and replay; typed retries and preserved error identity; 1,000 stress repetitions each at first and middle failure; all infrastructure classifications and negative controls; byte-native parity including transforms and non-JSON parsed arguments; lazy imports; seven specified commands; median of at least twelve graded trials.

Limits to state: trusted middleware bypasses; validators run twice; replay reconstructs only scrubbed text, not attributes; seed-zero replay factory; provider binding/output errors share infrastructure wrapper. No recipe/CLI/CI/dependency/frozen changes.

Verify combined candidate and frozen hashes after all edits. Record actual failures, including sandbox-only socket failures; never skip or alter existing tests.
