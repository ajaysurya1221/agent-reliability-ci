# Decisions log

Tie-break order: (a) the run prompt; (b) the memo; (c) the repo's rules; (d) an Astra consult seeing both positions; (e) the more reversible option. Every tie-break becomes an ADR in docs/design/.

## Decisions made at plan time (2026-10-13) (rule in brackets: a=prompt, b=memo, c=repo rules, d=Astra, e=reversibility)

1. The memo lives outside the repo; Task 00 copies it verbatim to `plan/research/forward-plan-2026-10-13.md` and `plan/exec/` is repo-relative [a].
2. Worktrees are created with `git worktree add` under `/Users/ajay/Developer/.arci-worktrees/wt-<lane>` on `sprint/<lane>` branches; coder dispatches get the absolute path; integration only on main by me [a fallback, c convention].
3. The demo is packaged as `arci.demo` (world, agents, experiment, run) and `examples/retry_agent/{world,agents}.py` become re-export shims; `experiment.py` and `hero_demo.py` stay byte-identical; distinct `arci-demo-` experiment ids; N fixed at 200; temp store [c: frozen test_hero, figure needles; b: real gate path; e].
4. `arci run` accepts YAML descriptors directly, so the memo's `arci run arci.yaml` holds; sealing stays `Manifest.create`; schema is `Descriptor.model_json_schema()` committed at `docs/schema/arci.schema.json` with a staleness test [b, c].
5. The console script puts the cwd on the children's import path (append, never prepend): ADR 0006, Astra-reviewed; without it the first-screen command cannot work [b: first-screen command; c: AGENT_SEMANTICS parent-never-imports; e: append is the least invasive].
6. `arci init` validates refs in a child process with the runner's path rule, never in the CLI process [c: AGENT_SEMANTICS].
7. The smoke notice goes to stderr of `arci run` only, threshold `n_per_arm < 100`, with the planner's numbers where its domain allows [c: pinned stdout/report bytes; b: "CLI prints that small N usually yields INCONCLUSIVE"].
8. Version bump and packaging metadata happen once, in T12, with ADR 0005 and a re-freeze commit covering `pyproject.toml`, `uv.lock` and the new ADRs; wheel version stays 0.7.0 until then and nothing is published before the bump [c; the v0.7.0 precedent re-froze without an ADR, but your rule asks for one, so a=prompt wins].
9. No `justfile` changes (frozen); release steps live in `docs/RELEASING.md` and CI scripts [c].
10. Release workflow uses `uv build` + `pypa/gh-action-pypi-publish` (SHA-pinned) because `uv publish` uploads but does not generate attestations [a: "with attestations"; docs checked today].
11. Windows gets an install/import/--help job only; any module-level POSIX reference that breaks import is guarded; execution is not advertised [b S11].
12. S8's Inspector step is run once by me with network; tests never call npx; a protocol-version rejection is recorded verbatim, not patched around in this sprint [c: no network in tests; b: honesty; e].
13. Reviewer subagent has Read/Grep/Glob only; I run all checks and hand it the diff and outputs [a: read-only tools].
14. Coder tool set is Read/Edit/Write/Bash/Grep/Glob; no Agent/web tools [a].
15. Denied `gh` commands are never bypassed through `gh api`; merges use plain git after lane CI; anything still blocked becomes HUMAN_INBOX [harness over prompt; a for the inbox].
16. Cut order under budget pressure: S8, then S9, then S7 reduced [b: TTFV path first; e].
17. No new store under `docs/results/`; measurement receipts live in `docs/measurement/receipts/` [c: pinned-store tests].
18. The `Independence` paragraph added on origin main (#14) is kept verbatim below the fold in the README rewrite [c: never loosen].

## Decisions made during execution

(appended as they happen: id, decision, positions, rule, consequence)

### D-01 (Task 01): coder dispatch mechanism
Decision: coder and reviewer dispatches run through the Workflow tool's `agent()` with
`model: 'opus'`, `effort: 'high'`, `agentType: 'general-purpose'` and the agent definition's system
prompt embedded in the dispatch text. Reason: `.claude/agents/coder.md` and `reviewer.md` were
created mid-session and the Agent tool does not register new agent types until the next session
(error: "Agent type 'coder' not found"). The probe transcript
(`subagents/workflows/wf_9cf6455a-ca5/agent-aec7c2fa636fb1c41.jsonl`) shows `message.model =
claude-opus-5-5` and `effort = high`, so the pinned model and effort hold. The agent files stay in
the repo for future sessions. Rule: (a) the prompt's intent (Opus 5.5 at high, verified in the
transcript) over its literal mechanism; (e).

### D-02 (Task 01): dependency fixes from CONSULT 01
Astra's connectivity consult (plan/exec/consults/01.md) found three inconsistencies; adopted:
(1) T06's smoke no longer needs `arci schema` (T07 adds that step after T03 merges); (2) T04 owns a
minimal fixture tree under tests/unit/init/fixtures/ instead of borrowing T08's sample; (3) T12
depends on 02–07 and 11; a cut task (08–10) never blocks the release and is listed in CHANGELOG as
not shipped. Astra's first risk (scope vs 10 h) is accepted as is: the cut order S8 → S9 → reduced
S7 applies at the 4 h mark if lane C has not merged by then. Rule: (d) on a plan defect, (a) on scope.

### D-03 (before T09): MCP Inspector cannot talk to the ARCI bridge today
Measured 2026-10-13: `npx -y @modelcontextprotocol/inspector@latest --cli --config mcp.json --server env
--method tools/list` against `python -P -m arci.mcp_toolset_server …` returns
`{"error":{"code":"error","message":"Server's protocol version is not supported: 2026-07-28"}}`
(Inspector 2.10.1, TypeScript SDK 1.29.0, which accepts up to 2025-11-25). Decision: T09 ships with
the Inspector step recorded verbatim as blocked by the SDK version and documents the manual
alternative (the bridge answers newline-delimited JSON-RPC on stdin, so `initialize`/`tools/list`
can be driven by hand); the bridge's version handling is not changed in this sprint (plan decision
H12), and "protocol-version negotiation in the bridge" goes to the next-steps list with an ADR
sketch. T09 stays first in the cut order. Rule: (c) the frozen design record 0002 names revision
2026-07-28; (e) a doc is reversible, a protocol change is not.

### D-04 (Task 04): ADR 0006 written before dispatch
docs/design/0006-cwd-on-the-child-import-path.md is Fable-authored and will be reviewed by Astra
and the reviewer subagent together with T04's diff. Its hash is added to FROZEN.sha256 at the T12
re-freeze.

### D-05 (Task 01, corrected at 04:33Z): codex exec must have stdin closed
The first three bias-control consults stalled for 45 minutes: `codex exec` printed "Reading
additional input from stdin..." because the harness's background shell left stdin as an open pipe.
Fix: every consult runs with `< /dev/null`, and long prompts live in `plan/exec/consults/<id>-prompt.md`
("write it to a file and point Astra at the path"). The stalled runs produced no output and were
killed; nothing was read from them. Rule: (a).

### D-06 (E1, ADR 0008): the `arci init` contract
Independent proposals agreed on the signature, N=8, child-process validation, one-line errors and
`arci run --out` defaulting to `runs`. The five differences went to a tie-break consult
(plan/exec/consults/E1-tiebreak.md), which chose Astra's position on all five (single-line success
output; a five-line header without universal threshold claims; labels baseline/candidate; built-in
fault names only; no --task-id) and flagged a sixth: repeated --fault flags form ONE condition
(K=1). Adopted in full. Rule: (d). Consequence: T05's notice wording must say "two perfect arms
cannot PASS below N=42; a total collapse cannot BLOCK below N=8" (Astra's correction of the plan's
looser sentence).

### D-07 (E2, ADR 0007): the descriptor shape
Proposals agreed on nearly everything; Fable adopted Astra's positions on fixtures_sha256 exposure,
"exactly one of oracle or contract", alias-collision rejection, the versioned schema $id, the
deterministic `arci schema` output, and the error line through main(). The tie-break chose Fable's
position on the three remaining items (task_id defaults to experiment_id; bare-arm label
<module tail>.<function>; a YAML-1.2-style isolated resolver). Rule: (d).

### D-08 (E3, ADR 0009): the README first screen
Tie-break chose Astra on all six differences plus a merged "what" sentence: question as H1; PASS
stated as the positive non-inferiority finding ("the evidence supports that any reliability drop ...
is smaller than the allowed drop") because "not shown to be worse" also describes INCONCLUSIVE;
demo first with the recorded result beneath it; no runtime promise; no link row (word count 190).
Rule: (d); (c) STATISTICS.md for the PASS sentence.

### D-09 (T11): the first-screen scaffold command stays the memo's, without `--fault`
The reviewer noted that the memo's second command writes a clean condition (no injected fault), while
the README's first sentence mentions injected tool faults and the YAML below shows one. Decision:
keep the two commands verbatim as the memo and ADR 0009 fixed them (a repeated clean comparison is a
valid first verdict and the smoke notice still fires), and say below the fold that `--fault
tool_timeout:reserve` adds a fault and that the YAML shown is hand-written. Rule: (b) the memo's
commands are fixed; (e) a sentence is reversible, a changed first-screen command is a new decision.

### D-10 (T04r1 → T04r2): the orchestrator's O_EXCL fallback contradicted ADR 0008
The T04r1 brief asked for an O_CREAT|O_EXCL fallback when hard links are unsupported. Astra showed it
breaks the ADR's atomic-publication promise (a destination visible before its bytes are complete) and
that its cleanup can delete a competitor. Decision: no fallback. Without `--force`, `os.link` is the
only publication path; any failure other than FileExistsError is reported as
`output <path>: cannot publish atomically here (hard links unsupported); choose another directory or
pass --force`, nothing is written, staging is removed. With `--force`, `os.replace` stays (atomic).
Rule: (c) the design record wins over an orchestrator brief; (d) Astra's finding.

### D-11 (run 2, T19): MCP Inspector compatibility check (2 h cap; result: still blocked, negotiation is a bridge-only design change)

Facts (2026-10-13 ~18:20Z, read-only probes of npm): `@modelcontextprotocol/sdk` latest 1.32.1
(2026-10-05) and the v2 split package `@modelcontextprotocol/core` 2.2.0 (which Inspector 2.10.1,
2026-10-08, depends on) both define `LATEST_PROTOCOL_VERSION = '2025-11-25'` and support only
2025-11-25, 2025-06-18, 2025-03-26, 2024-11-05, 2024-10-07. No released client library supports the
bridge's revision 2026-07-28, so every Inspector release rejects the bridge at `initialize`
("Server's protocol version is not supported"), as D-03 recorded. The bridge
(`src/arci/mcp_toolset_server.py`, not frozen) answers `initialize` with its constant regardless of
the client's requested version, i.e. it does not negotiate at all.

What a fix would be (corrected after Astra's review, CONSULT run2-D2/D11): ARCI's boundary forwards
the agent's `initialize` parameters to the server unchanged (`src/arci/mcp_boundary.py` ~line 1595),
so it does not itself pin 2026-07-28 in the request; a bridge that negotiated on the requested
revision would therefore change trial traffic too. The honest design is an explicit, standalone
**compatibility mode** of the bridge (a flag or environment variable that ARCI never sets in
trials): in that mode only, the bridge answers a foreign client's `initialize` with the requested
revision when it is in a small allowlist the subset can serve (2025-11-25, 2025-06-18: initialize,
initialized, ping, tools/list, serial tools/call), persists the negotiated revision for the whole
connection, omits revision-specific fields (`resultType`) in those replies, and rejects other
revisions with a defined error; each allowlisted revision's subset is verified by tests, not merely
echoed. Outside that mode, behaviour, recording and replay are unchanged and covered by tests that
pin the trial responses. Frozen touches: ADR 0002 line 36 and `schema.py:276` stay true (the
boundary contract is unchanged); AGENT_SEMANTICS gains a sentence only if it describes the bridge.
It is a design change → ADR 0011 + Astra review, scheduled with the next engineering run and only
once an MCP pilot or the MCP post commits to it (tie-break F2; rule e).

Consequence now: HUMAN_INBOX drafts C and E stay on hold; the recipe's Inspector step stays
"blocked" with today's versions added to the record.
Astra round 2 (CONSULT run2-D2 round 2): AGREE with the corrected architecture; ADR 0011 must also
ensure the compatibility mode cannot activate through inherited environment variables, because the
boundary's server environment inherits the parent's (`src/arci/mcp_boundary.py` ~line 772): the mode
must be an explicit argv flag the bridge is started with, never an environment variable.

