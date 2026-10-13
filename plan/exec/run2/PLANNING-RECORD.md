# Run 2 planning record (both blind positions, inputs, tie-break, user decisions)

## Fable position (written 2026-10-13 ~13:55Z, before reading Astra's proposal)

### Principle
The memo's rule "launch channels should follow the evidence, not precede it" cuts both ways now: the
evidence that exists is enough to announce (release + recorded runs), and everything the metrics ask
for next needs strangers, not more maintainer measurement. So the next two weeks are user-driven
(posting, recruiting) with the orchestrated setup doing only small, reversible engineering that
removes known friction and the review leftovers. The importer work (D2–D6) is the memo's bet on the
"trace seam"; it is real engineering (46 h) and should start only once at least one pilot is talking
to us, because D3's acceptance needs "authentic fixtures from two independent producers".

### Weeks 1–2 (to 2026-10-27)
1. **Announce (user).** Posting order from the memo: release page is done; Show HN (draft B), MCP
   community post (draft C, with the Inspector-blocked honesty), the three issue-thread comments
   (draft D), r/LocalLLaMA last. One recorded-run claim per post. ~2 h. Acceptance: posted; links
   recorded in HUMAN_INBOX. Skip condition: none; this is the gate for every metric.
2. **Recruit five cold readers (user), D8 start.** The pilot template (draft F) to the ten target
   users in the memo's order; ask each for one TTFV receipt (demo track first). ~3 h over two weeks.
   Acceptance: five people committed; three receipts in by Oct 27. Kill: if fewer than two respond
   by Oct 27, widen the net (agent-builder communities) rather than measure ourselves again.
3. **Friction branch (orchestrated, small): `sprint/t16-friction`.** Only what the AI cohort and the
   reviews showed, all reversible, no frozen files: (a) `arci run` prints the run-store path on
   stderr at the end (stdout pinned); (b) README: shorten the path to "Gate your own agent" (a
   two-line pointer under the first screen, below the fold; first screen unchanged, ADR 0009
   holds); (c) `arci init` link-error attribution (errno-specific message) and the macOS
   `F_FULLFSYNC` note; (d) dead branches in `descriptor._int_value` (seal tests re-run); (e) sdist
   allowlist step in `release.yml`, `arci schema` added to `wheel_smoke.sh`, action-fixture job
   checks the step summary; (f) protocol: §5 q2 reading, §7/§8 repeat-attempt rule, `trials_started`
   for several stores, Track A installed-version check via `importlib.metadata`, failure taxonomy by
   milestone; (g) recipe-test nits from REVIEW 08-09 (inverse-control fixture order, "INVALID"
   wording); (h) the sample tree's `make_world` tolerates a missing task (`order_id` default) so the
   README's four-reference command succeeds on the sample as written, with the recipe docs
   re-recorded; (i) cohort builder persists `agent_execution` in the result JSON and the `sentence()`
   edge case; (j) one stale FINAL_REPORT bullet. ~8 h coder + reviews, two branches if the reviews
   get long (code vs docs). Acceptance: `just check`, two reviews, no behaviour change to pinned
   bytes or stdout's last line. Kill: anything that touches `report.py` output is dropped. Not in
   this branch: ADR 0005 `httpcore2` typo (needs a re-freeze; batch with the next frozen change),
   hatchling hash pinning, dynamic versioning (ADR 0005 "Not in v0.8.0").
4. **D1 parent-IPC per-request pacing: design record first, code second.** The memo marks it HIGH
   PRIORITY, but it touches the decision boundary and could change outcome classification; the
   acceptance criterion needs a concurrency test harness. Week 1: ADR 0010 (scope, invariants,
   the test that proves "admitted requests obey the declared rate without changing outcome
   classification"), Astra mandatory. Week 2: implementation only if the ADR survives review.
   ~10 h. Kill: if the ADR cannot state a test that distinguishes the new pacing from the
   divide-by-k approximation on recorded runs, defer D1 to the 90-day plan.
5. **Measurement hygiene (orchestrated, 1 h):** fix the stopwatch wrapper (`PIPESTATUS` under zsh),
   add the protocol 2.3 version check to the scripts, and record the `uv tool install` route once
   the harness allows it. No new maintainer receipts: they do not move any metric.

### Weeks 3–4 (to 2026-11-12)
6. **D8 completion + first external run (user + orchestrated support).** Score incoming receipts
   (scorer ≠ reader), answer blockers within a day, and get one external recorded run (memo: by
   Oct 31; realistic: by Nov 12). Each receipt is a PR the user merges; the orchestrated setup only
   checks the file parses and follows the template.
7. **D7 third recipe (orchestrated, 6 h)** only if a pilot uses LangGraph or Pydantic AI; otherwise
   the recipe is guesswork. Framework-native tests stay; ARCI only gates.
8. **D2 import-record provenance model (orchestrated, 6 h; design record, Astra mandatory):** the
   schema that lets imported traces diff without ever becoming gate evidence. Start when a pilot
   has a real trace to import; otherwise defer to the 90-day plan with D3–D6.
9. **Kill-criteria checkpoint on Nov 12 (user + me, 1 h):** `arci init` (7/10 cold users produce a
   runnable descriptor without syntax surgery?), YAML round-trip, recipe time budgets; write the
   result as a decision in `plan/exec/DECISIONS.md`.

### What I would not do before Nov 12
- D3–D6 importers before a pilot produces an authentic fixture (memo: "authentic versioned fixtures
  from two independent producers"; none exist).
- Any change to the decision rule, calibration or STATISTICS; any HTML/PR-comment reporting (R8:
  only after ≥3 external users ask); native Windows (R5); a scheduler beyond D1 (kill criterion).
- More maintainer or AI measurements presented as progress on the TTFV metrics.
- MCP Inspector negotiation in the bridge: wait for the upstream Inspector SDK or an external MCP
  pilot (R4), and send the docs PR text (draft E) instead.

### Highest-risk assumptions in the memo's metrics
- That strangers will try it at all without a channel push: test by posting (step 1) and counting
  clicks on the release page within a week.
- That ten minutes to a first verdict is achievable for a person writing their own references: test
  with the first two cold readers on their own agent, not the sample tree.
- That INCONCLUSIVE as the first verdict is accepted as "valid" by users: ask each pilot one
  question after their first run.

## Inputs gathered (read-only)

- **Memo (plan/research/forward-plan-2026-10-13.md).** Thirty-day plan D1–D8 due 2026-11-12 (lines
  96–108; YAML 754–818): D1 parent-IPC per-request pacing "HIGH PRIORITY immediately after v0.8.0",
  D2 import-record provenance model, D3 OTLP JSON importer (needs "authentic versioned fixtures from
  two independent producers"), D4 OTLP protobuf, D5 Claude importer, D6 Codex importer, D7 third
  recipe (LangGraph/Pydantic), D8 external pilot round (five target users; one complete run or a
  written blocker each; no hidden maintainer help). Ninety-day R1–R8 (lines 111–122), all
  conditional on external evidence. Adoption metrics with dates (lines 285–294): demo TTFV by Oct 20;
  own-agent TTFV by Oct 27; ≥80 % cold readers all-correct by Nov 12; first external run by Oct 31;
  ≥5 runs across ≥3 repos by Nov 30; ≥5 Action references by Dec 15; 10 onboardings and ≥5 stranger
  issues by Jan 11. Kill criteria (lines 298–314): `arci init` replaced if <7/10 cold users get a
  runnable descriptor by Nov 12; a recipe that misses its time budget is fixed or removed before any
  new recipe; no HTML/PR-comment UX until ≥3 external users ask; no broader scheduler without need;
  importers stay experimental without useful fixtures by Nov 12. Posting order (273–281): release
  page → Show HN → MCP community (after the Inspector recipe) → issue threads → r/LocalLLaMA; "launch
  channels should follow the evidence". Open questions (339–342): Windows native vs WSL; Claude vs
  Codex as the first coding-agent pilot.
- **Recorded follow-ups (30 items, de-duplicated by the Explore agent).** Code: Inspector protocol
  negotiation (needs an ADR; ADR 0002 names revision 2026-07-28; constant in
  `src/arci/mcp_toolset_server.py`), `mcp_boundary.py` `sys.stdout.buffer` at import, `init.py`
  link-error attribution and macOS `F_FULLFSYNC`, `descriptor._int_value` dead branches, `arci run`
  store path, the sample tree's missing-`--task` failure. CI/release: sdist allowlist, hatchling hash
  pin [frozen], `arci schema` missing from `wheel_smoke.sh`, action-fixture job checks the local
  report not the step summary, `pypi` environment reviewer (user setting). Docs: ADR 0005 `httpcore2`
  [frozen, next re-freeze], long README lines, README length before "Gate your own agent", recipe
  test nits. Protocol: `trials_started` across stores, Track A version check, repeat-attempt rule
  (§7.1/§8), q2 key reading, failure taxonomy. Process: cohort builder persistence, human cold
  readers, announcements, `dist-v0.8.0/` cleanup. None touches schema/interfaces/hashing/
  fingerprint/schedule/contracts, tests/acceptance, the decision rule or STATISTICS.
- **Plan agent (sequencing and risk).** The evidence chain is serial and user-only: announce →
  outreach → cold readers and D8 → first external run → R2. Protocol edits must land *before* any
  human receipt or receipts become incomparable. The MCP chain is negotiation ADR → implementation →
  MCP post → Inspector docs PR → Inspector-maintainer pilot → R4. D1 is not small: it rewrites
  frozen semantics (`docs/AGENT_SEMANTICS.md` pacing section, `tests/acceptance/test_decisions_v06.py`)
  → ADR + re-freeze + selfcheck; schedule the ADR in week 3, implementation in week 4 only if budget
  remains. D7 is blocked by the cookbook kill rule until a cold reader finishes recipe one within
  budget. D3 needs a fixture ask to LangSmith/Phoenix users now. D5 vs D6: pick one after the first
  pilot (memo open question 4). Checkpoints on 10-27 (§8 report vs the Oct 27 target) and 11-12
  (kill rules applied in writing). A v0.8.1 only for a stranger-found blocker (re-freeze cost).

## Astra position (blind proposal, read 2026-10-13 ~18:05Z, after "Fable position" was written)

1. **Start D1 now (Oct 13–20, team, 12–16 h incl. reviews)**: the memo's explicit immediate priority;
   accept concurrent tests showing aggregate admission-rate compliance with unchanged outcome
   classification and replay; cut broader scheduling; unresolved correctness blocks shipping.
2. **Leftovers branch before human measurement (Oct 13–19, team, 8–12 h)**: protocol clarifications
   (repeat-attempt denominators, Track A version check, multi-store `trials_started`, q2 scoring);
   receipt reconstruction inputs saved separately; link-error attribution, macOS durability
   documented, store path on stderr; sdist allowlist, schema smoke, Action summary assertion, replay
   inverse-control precondition. Defer dead-code cleanup, `F_FULLFSYNC`, hash pinning, Inspector
   negotiation; `httpcore2` only at the next justified re-freeze.
3. **D8 recruitment and measurement (Oct 13–27, user 8–10 h; team scoring 2–3 h)**: five humans
   with real agents; ask two producers for versioned trace exports; Show HN with the recorded-demo
   claim; measure demo p50/p95 by Oct 20 and own-agent by Oct 27; keep failures and interventions;
   a 2 h capped Inspector compatibility check, MCP promotion stays blocked until a preflight passes.
4. **D2 → D3 (Oct 28–Nov 12, team, 24–30 h)** after inspecting authentic fixtures; insufficient
   semantics by Nov 12 → experimental, analysis-only, no replay promise. D4–D7 deferred (D7 until the
   existing recipes meet human time budgets).
5. **Finish D8 (Oct 28–Nov 12)**: one independent recorded run by Oct 31; by Nov 12 each pilot a run
   or a blocker; ≥80 % all five unaided; extend descriptor testing towards ten cold users (<7/10
   runnable without syntax surgery → replace the interface); insufficient recruitment = "unmeasured".
6. **Risky assumptions**: speed transfers (a macOS CI runner took 206 s for the demo, above the
   3-minute p95); comprehension transfers (AI 5/5 says nothing about humans); interest becomes
   adoption (track replies → attempts → runs → Action references; the Nov 30/Dec 15/Jan 11 targets
   are hypotheses).
7. **Excluded for 30 days**: new statistics, counterfactual engine, permission calibration,
   server-version gating, native Windows, resumability, dashboards, generic adapters/evaluators/
   chaos/observability, telemetry; no Inspector docs PR before a successful preflight; no imported
   trace promoted into PASS.

## Reconciliation

Agreed without consult: announce now with the recorded-demo claim; recruit five humans with real
agents and ask two producers for trace exports in week 1; land the protocol clarifications and the
evidence/UX fixes before any human receipt; defer D4–D7, all of R1–R8, new statistics, HTML/PR
reporting, Windows, resumability, Inspector docs PR until a preflight passes; `httpcore2` and hash
pinning wait for a justified re-freeze; nothing imported ever becomes gate evidence; D2/D3 are gated
on authentic fixtures (Astra: "after inspecting authentic fixtures"; Fable: "when a pilot has a real
trace"; Plan agent: "only if ≥1 authentic OTLP fixture arrived").

Forks sent to the tie-break consult (CONSULT NEXT-2):
- **F1 D1 timing.** Astra: implement Oct 13–20. Fable: ADR 0010 in week 1, implementation in week 2
  only if the ADR states a test that distinguishes the new pacing from divide-by-k on recorded runs.
  Plan agent: ADR week 3, code week 4. D1 touches frozen `docs/AGENT_SEMANTICS.md` and
  `tests/acceptance/test_decisions_v06.py`, so an ADR + re-freeze + selfcheck is required either way.
- **F2 Inspector.** Astra: 2 h capped compatibility check, negotiation deferred. Plan agent: ADR
  (design only) in weeks 1–2, implementation weeks 3–4. Fable: wait for upstream or an MCP pilot.
- **F3 leftovers scope.** Fable adds: the sample tree's `make_world` tolerating a missing task so the
  README's four-reference command works on the sample as written; dead-branch removal in
  `descriptor._int_value`. Astra defers dead-code cleanup and `F_FULLFSYNC`; silent on the sample
  default.

Tie-break result (CONSULT NEXT-2, Astra, fresh context, both positions shown):
- **F1 → B** (ADR 0010 week 1, code week 2 after review). Superseded by the user's decision to
  defer D1 past Nov 12; recorded so the ADR-first shape is used when D1 is picked up.
- **F2 → A**: a 2 h capped compatibility check now (newer Inspector/SDK support for revision
  2026-07-28; what negotiation would require); implementation deferred. Changing the constant alone
  would contradict ADR 0002's pinned revision; a check is reversible and does not conflate bridge
  compatibility with R4.
- **F3 → exclude both**: a world-only task default would still leave both sample agents and the
  oracle indexing `order_id`, so it fixes nothing real; instead the README's own-agent command
  (below the fold, not the first screen) should carry `--task '{"order_id": "order-7"}'` for the
  sample. Dead-branch removal in the sealing parser fixes no demonstrated behaviour and waits for a
  separately scoped change.

## Reconciliation
<<pending>>

## User decisions (AskUserQuestion, 2026-10-13 ~18:05Z)
- Engineering runs as another autonomous orchestrated run (same setup: Opus coder/reviewer
  subagents, Astra reviews, two reviews per merge, wall-clock budget, HUMAN_INBOX).
- No posting and no recruiting for now: no external evidence this month; every dated adoption
  metric is reported as unmeasured, honestly; the launch and outreach drafts stay in HUMAN_INBOX.
- D1 (parent-IPC pacing) is deferred past 2026-11-12 (fork F1 closed by the user).

