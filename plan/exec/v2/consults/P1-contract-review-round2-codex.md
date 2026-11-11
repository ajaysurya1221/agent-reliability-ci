P1 CONTRACT: REVISE

**Previous findings**

1. **CODE — RESOLVED:** normalization uses rebuilt instances for validation and scoring ([Contract:334](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/P1-CONTRACT.md:334)).
2. **CODE — PARTLY RESOLVED:** metadata, check ordering, history and outcome rules are explicit; unhashable strings still defeat ERROR serialization ([Contract:374](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/P1-CONTRACT.md:374)).
3. **CODE — RESOLVED:** cell counts include errored pairs and independently count each arm’s successes ([Contract:119](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/P1-CONTRACT.md:119)).
4. **CODE — RESOLVED:** the float restriction now permits existing JSON values and TrialSpec mirrors ([P1a:66](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/P1a-suite-schema-schedule-stats.md:66)).
5. **CODE — RESOLVED:** ambiguity requires stopping; digest tests explicitly exclude the three omitted fields ([P1a:29](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/P1a-suite-schema-schedule-stats.md:29)).
6. **CODE — RESOLVED:** exact assertions reference matching Table C records in `results.json` ([Contract:295](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/P1-CONTRACT.md:295)).
7. **OPINION — RESOLVED:** seed bounds, pair-ID parsing, rule/count/law domains and exceptions are pinned ([Contract:179](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/P1-CONTRACT.md:179), [245](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/P1-CONTRACT.md:245)).
8. **CODE — RESOLVED:** digest construction remains non-circular, with gate-side recomputation ([Contract:165](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/P1-CONTRACT.md:165), [348](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/P1-CONTRACT.md:348)).

**New blocking counterexample**

1. **CODE — The “never raises” guarantee remains impossible for accepted Python strings** ([Contract:330](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/P1-CONTRACT.md:330), [375–383](/Users/ajay/Developer/agent-reliability-ci/plan/exec/v2/tasks/P1-CONTRACT.md:375)). A trial with `record_sha256="\ud800"` rebuilds successfully and satisfies the prescribed `str` condition, but its mandatory digest raises `UnicodeEncodeError`. Likewise, `prior_runs=("\ud800",)` passes the existing string-field validation; mirroring it prevents even the fallback ERROR decision from being sealed. Catching the exception does not resolve the conflicting field requirements.
   **Fix:** specify `trials_sha256=""` whenever its digest cannot be computed; define a safe metadata fallback when required mirrored strings cannot be UTF-8 encoded, including deterministic reason precedence.

Read-only `.venv/bin/python` probes exited 0 and reproduced both encoding failures. No files or git state changed; no test suite ran. Next: amend §5’s serialization fallback.
---
Recorded by the orchestrator on 2026-11-11. Answer written into contract section 5 the same
day: checks 1 and 5 also require canonical JSON encoding to succeed; `trials_sha256` is ""
whenever it cannot be computed; a last-resort fixed template always seals.
