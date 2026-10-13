# ARCI v0.8.0 sprint: orchestration plan (plan mode, 2026-10-13)

Orchestrator: Claude Fable 5.1 (this session). Coder: Opus 5.5 subagent (`claude-opus-5-5`, effort high). Consultant: Codex `gpt-6-astra` at xhigh, read-only. Three eyes on every merge. Budget 10 h wall-clock from Task 00.

## Context

The memo (ARCI forward plan) says: ship v0.8.0 by 2026-10-20 around distribution and comprehension, not new statistics. Publish the wheel to PyPI, make `uvx --from agent-reliability-ci arci demo` work with no clone, add a thin `arci.yaml` front-end generated from the frozen Pydantic `Manifest`, ship `arci init`, rewrite the README first screen, and release the already-landed planner, pass^k and portability fixes. The sprint is pre-approved; this plan turns it into lanes, contracts and TASK blocks the coder can execute, with the repo's frozen-file, decision-rule and evidence rules preserved.

---

## A. Memo digest

**Path.** `/Users/ajay/Downloads/deep-research-report.md` (969 lines, YAML appendix at the end). It is NOT in the repo: no `research/` or `plan/` directory exists. Task 00 copies it verbatim to `plan/research/forward-plan-2026-10-13.md` and every later reference points there.

**Ordered path (memo appendix `ttfv.path`).**
1. `uv tool install agent-reliability-ci` (install from PyPI).
2. `uvx --from agent-reliability-ci arci demo` (zero-clone demo).
3. `arci init` with four refs: baseline, candidate, toolset, oracle.
4. A schema-valid `arci.yaml` that maps directly onto the existing Pydantic `Manifest`.
5. A small, explicitly labelled smoke N; an honest INCONCLUSIVE counts as a valid first verdict.
6. `arci run arci.yaml`.
7. `arci plan` before sealing a larger confirmatory CI experiment.

**Time-to-first-verdict (TTFV).** Targets: packaged demo p50 ≤ 2 min, p95 ≤ 3 min (by 2026-10-20); own fast agent p50 ≤ 10 min, 4/5 cold users ≤ 15 min (by 2026-10-27). Memo's today estimates, both UNVERIFIED: demo ~8 min, own agent ~60 min (45–90). Measured today in this session: the clone-based `hero_demo.py --n 200` runs in 38.2 s wall (user 199 s) on this 15-core Mac with 8 workers, after `uv sync`; clone, sync and reading the README are the rest of the 8 minutes.

**Sprint tasks as written (S1–S12, 51 h human estimate).**

| ID | Task | Est | Depends |
|---|---|---:|---|
| S1 | Publishable package pipeline (wheel+sdist, PyPI trusted publishing, clean install py3.11/3.14) | 4h | none |
| S2 | Packaged `arci demo` from `uvx`, no model call, real gate/diagnosis/replay, ≤2 min | 5h | S1 |
| S3 | Declarative descriptor + generated JSON Schema, thin layer over `Manifest`, no decision logic in YAML | 7h | none |
| S4 | `arci init`: one non-interactive command, four refs, schema-valid runnable descriptor | 8h | S3 |
| S5 | Honest smoke-design UX: small labelled N, CLI says INCONCLUSIVE is expected, points to `arci plan`, no outcome-dependent extension | 3h | S4 |
| S6 | README first screen ≤200 words in the prescribed order; relative PASS and not-a-sandbox above the fold | 4h | S2, S4 |
| S7 | Python-agent recipe: blank project, four refs + task data, valid verdict, no copied gate code | 3h | S4 |
| S8 | MCP command-agent recipe + Inspector preflight, responsibilities distinguished | 4h | S4 |
| S9 | TTFV and cold-read measurement harness: checklist with install/scaffold/run/verdict/interpretation milestones, five cold readers | 3h | S2, S4, S6 |
| S10 | Release-integrity merge: CHANGELOG moves planner, pass^k, portability fixes to v0.8.0; re-derivation stays valid | 4h | main clean |
| S11 | Install and Action matrix: wheel + Action on Ubuntu/macOS; Windows install/import/--help only, not advertised | 3h | S1, S10 |
| S12 | v0.8.0 release and evidence receipt: tag, PyPI files, SHA256s, exact commands, recorded fresh-machine timing, Action tag, no new claims | 3h | S1–S11 |

**Adoption plan split.**
- Yours (the user): posting and outreach. GitHub release announcement wording approval; Show HN; MCP community channels; comments in Promptfoo #5947, Inspect, Pydantic #3138 threads; r/LocalLLaMA; the upstream MCP Inspector docs PR; recruiting the first five pilot users (D8); any account creation.
- Mine (drafts, in `plan/exec/HUMAN_INBOX.md`): release notes citing recorded runs; Show HN title + body; MCP-community post; one issue-comment draft per target (Promptfoo, Inspect, Pydantic AI, agent-chaos, Chronicle); the Inspector docs PR text ("CI: protocol preflight with Inspector, stochastic resilience with ARCI"); a pilot-outreach template; the TTFV measurement protocol the pilots will follow.

---

## B. Repo audit

**Unreleased on main (CHANGELOG "Unreleased") that v0.8.0 must include.**
- `arci plan` (exact enumeration, CP only, K=1, one look, N ≤ 400).
- Opt-in `arci report --pass-k` (Markdown only; default report bytes unchanged, pinned for 19 stores × md/junit in `tests/unit/report/default_report_sha256.json`).
- Portability fixes: pinned inverse-normal for Wilson display bounds; exact-integer Clopper-Pearson tail comparison (re-derived 6 Jev + 5 guardrail decisions byte for byte on macOS and Ubuntu).
- Technical report package `docs/reports/ci-gate-2026-10-06/` + `CITATION.cff`; guardrail campaign results + `summarize.py --check`; README/figures regeneration (`docs/assets/src/make_figures.py --check`); `SECURITY.md`.
- Origin `main` is one docs commit ahead of the local checkout (`06e8744` "docs: clarify ARCI independence and bounded PASS semantics (#14)", README +17 lines). `git push --dry-run` currently fails only because local main is behind; Task 00 starts with `git pull --ff-only`.

**Merge bar today.** `just check` = ruff format --check, ruff check, basedpyright strict, pytest (883 tests, 261 acceptance, serial, offline; CI job timeout 40 min, last main run 17 min). `just frozen` = `shasum -a 256 -c FROZEN.sha256`. CI also runs `uv lock --check`, `uv sync --frozen`, the figure check, and macOS stats re-derivation. Latest run on origin main: success (2026-10-13 02:21Z). Local `just check`/`just frozen` are re-run in Task 01 after `git pull`.

**What FROZEN pins (48 lines).** `AGENTS.md`, `docs/AGENT_SEMANTICS.md`, `docs/STATISTICS.md`, `docs/TRUST_MODEL.md`, the four existing `docs/design/*` files, `justfile`, `pyproject.toml`, `uv.lock`, `src/arci/{contracts,fingerprint,hashing,interfaces,schedule,schema}.py`, `tests/__init__.py`, `tests/acceptance/**` (31 files). Consequences: the version bump (pyproject `version = "0.7.0"`, uv.lock root version) needs ADR + re-freeze commit; no new `just` recipes; new CLI subcommands must be additive to the frozen `test_cli.py` contract (exit code = verdict, last stdout line `VERDICT: …`, `arci gate --markdown` byte-equal to `GITHUB_STEP_SUMMARY`); schema `arci/0.5` unchanged.

**Release workflow today.** None. `.github/workflows/ci.yml` is the only workflow (SHA-pinned actions, `permissions: contents: read`). No GitHub environments exist (`gh api …/environments` → 0). `gh` is logged in (scopes repo, workflow); tags `v0.1.0`…`v0.7.0`, `evidence-2026-10-06`.

**PyPI path.** Package name from pyproject: `agent-reliability-ci` (console script `arci`, hatchling, wheel `packages = ["src/arci"]`, deps pydantic + pyyaml, `readme = README.md`). PyPI JSON API and simple index both returned HTTP 404 for `agent-reliability-ci` on 2026-10-13 → the name appears unregistered (the project page itself served a bot challenge, so this is the best available evidence; a pending publisher reserves nothing until first publish). Needs: a pending trusted publisher (owner `ajaysurya1221`, repo `agent-reliability-ci`, workflow `release.yml`, environment `pypi`), the `pypi` environment in the repo, `pypa/gh-action-pypi-publish` (SHA-pinned; generates PEP 740 attestations by default under trusted publishing; Linux runner only), `uv build --no-sources` in a separate build job, and an sdist restricted with `[tool.hatch.build.targets.sdist] only-include` (docs/results alone is 17 MB; examples/jev_triage_agent has node tooling). `uv publish` uploads attestations but does not create them, so the pypa action is the publisher.

**Pins that must move to the new tag / new route.** `README.md:14-15` ("no PyPI package"), `:31` (release badge → v0.7.0), `:39-44` (`git clone` + `uv sync` demo route), `:297-305` (Action example `@v0.7.0`, "not in that tag" sentence), `:364`, `:367`; `docs/ROADMAP.md:42-46` ("On main, not yet released"); `CHANGELOG.md:3` Unreleased → `## v0.8.0 (date)`; `CITATION.cff:10-11` version/date; `src/arci/__init__.py:3` `__version__`; `pyproject.toml:3` + `uv.lock:11` (frozen). Not to touch: `docs/reports/ci-gate-2026-10-06/**` (SHA256SUMS + evidence index, tested), `docs/results/retry-demo-n200.md` rows and the hero log (figure-generator needles), `docs/results/guardrail/README.md` (generated).

**Facts that shape the design (from the read-only repo map).**
- The wheel ships only `src/arci`; `examples.*` is unimportable from the console script. Trial seeds are `base_seed + j·n + i`, independent of module paths; agent/world code is stdlib + pydantic + `arci.interfaces`. A packaged copy under `arci.demo` reproduces 192/200 vs 132/200 exactly but with different manifest seals; frozen `test_hero.py` imports `examples.retry_agent.experiment`, and the figure generator needs the literal `tool="reserve",\n                at_occurrence=0,` in `examples/retry_agent/experiment.py`.
- Refs resolve only in child processes (`sys.executable -P -m arci.worker/arci.grade`) with PYTHONPATH built from the parent's `sys.path`; the parent never imports refs (AGENT_SEMANTICS). Under the console script the cwd is NOT on that path, so `arci init … && arci run arci.yaml` with cwd refs would fail today (the same papercut day one found; DECISIONS.md #4).
- `ExperimentStore` refuses a non-empty run dir; the demo must use a temp dir.
- A smoke notice may only go to stderr of `arci run`/`arci gate`: stdout's last line is pinned, report bytes are pinned for stores with N=1 and N=50, and `arci report` must keep stderr empty.
- At defaults (α 0.05, δ 0.10, K=1) PASS is impossible below N=42 and BLOCK below N=8; the planner refuses K≠1, looks, newcombe, N>400.
- POSIX-only runtime (`os.killpg`, `select` on pipes, AF_UNIX, `/tmp`); Windows can only do install/import/--help.
- MCP bridge answers protocol `2026-07-28` and never negotiates; the TS SDK cached locally (1.29.0) rejects it → the Inspector preflight must be run for real before S8 commits to it.
- Measured: ~0.23 s per trial, 12 s per 400-trial run at 8 workers, 38 s for the whole six-step demo on this machine.
- `contracts.load_contract` (frozen) already does `yaml.safe_load` + pydantic validation: the precedent for the descriptor loader (new module, same pattern). YAML 1.1 coercion (`yes`/`no` → bool, leading-zero ints → octal) inside `task` would silently change a seal; the docs must say so and `arci init` quotes strings.
- PyPI versions are immutable: nothing may be published while pyproject still says 0.7.0; the release workflow refuses a tag that does not equal `v` + pyproject version.
- PyPI's readme renderer strips `<source>` (keeps `<picture>`/`<img>`) and relative links break: the first screen uses absolute URLs and only the light SVG shows on PyPI.
- Root `.gitignore` lacks `node_modules/` (only the nested one has it), so a local sdist would leak `examples/jev_triage_agent/node_modules`; the build happens on a clean CI checkout and the root ignore gets the line. hatchling is unpinned (>=1.27,<2; 1.32.x emits Metadata-Version 2.5): the pypa publish action's bundled twine validates it; the version used is recorded in the release notes.
- `python -m arci` does not exist (no `__main__.py`); recipes use the `arci` script or `python -m arci.cli`.
- Precedent: the v0.7.0 bump (commit `e304e81`) re-froze pyproject/uv.lock without a design record; this run adds ADR 0005 because the user's rule requires one.

---

## C. Lanes and contracts

Worktrees: `git worktree add /Users/ajay/Developer/.arci-worktrees/wt-<lane> -b sprint/<lane>` (existing convention dir), each with its own `.venv` (`uv sync --frozen`, run by the orchestrator once). Lanes own disjoint files; the only shared file is `src/arci/cli.py`, where each lane adds exactly one import line and one `add_parser`/dispatch block inside a marked `# --- <lane> ---` region; the orchestrator resolves those conflicts at integration. At most two coders run at once (user rule).

| Lane | Branch | Owns | Frozen interface contract |
|---|---|---|---|
| **B demo** | `sprint/demo` | `src/arci/demo/**`, `examples/retry_agent/{world,agents}.py` (become re-export shims), `tests/unit/demo/**`, cli.py demo block | `arci demo [--workers N] [--keep DIR]` → exit 0 all six steps held, 1 a step failed, 3 CLI error; stdout mirrors hero_demo's step format; `arci.demo.experiment.build_manifest(n_per_arm=200, candidate="agent_b")`, `clean_manifest(candidate)`; refs `arci.demo.world:make_world`, `arci.demo.world:oracle`, `arci.demo.agents:agent_{a,b,c}`; `experiment_id = f"arci-demo-{candidate}-{condition_id}-{n}"`; base_seed 12000; N fixed at 200 |
| **C descriptor** | `sprint/descriptor` | `src/arci/descriptor.py`, `src/arci/init.py` (scaffold), `src/arci/runner.py` (`_pythonpath` cwd rule only), `docs/schema/arci.schema.json`, `docs/DESCRIPTOR.md`, `tests/unit/{descriptor,init}/**`, cli.py descriptor/init/schema blocks, `_cmd_run` YAML branch + stderr smoke notice | `Descriptor` pydantic model (`extra="forbid"`, frozen) → `to_manifest() -> Manifest` (sealed via `Manifest.create`); `load_descriptor(path) -> Manifest`; `descriptor_json_schema() -> dict` = `Descriptor.model_json_schema()`; `arci run PATH` accepts `.json` (sealed) or `.yaml/.yml` (compiled + sealed, store unchanged); `arci schema [--out PATH]`; `arci init …` per decision E1; stderr-only notice per T05 |
| **A package/CI** | `sprint/package` | `.github/workflows/release.yml`, `.github/workflows/ci.yml` (new jobs + `sprint/**` push trigger), `examples/action_fixture/**`, `docs/RELEASING.md` | release on `v*` tag: build (ubuntu, `uv build --no-sources`), smoke (ubuntu+macos × 3.11/3.14 from the built wheel in an empty dir), publish (env `pypi`, `id-token: write`, pypa action SHA-pinned, attestations on); CI `wheel-smoke`, `windows-smoke` (install + `arci --help` only), `action-fixture` (`uses: ./`, demo manifest, expects BLOCK via `continue-on-error` + output assert) |
| **D recipes** | `sprint/recipes` | `examples/recipes/python_agent/**`, `examples/recipes/mcp_agent/**`, `docs/recipes/*.md`, `tests/unit/recipes/**` | each recipe = runnable sample tree + doc; tests run `arci init` + `arci run` at smoke N expecting exit 2 (INCONCLUSIVE) and a valid sealed store, < 60 s each, no network |
| **E measure** | `sprint/measure` | `docs/measurement/**` | `ttfv-protocol.md` (stopwatch milestones, five cold-read questions, scoring sheet), `receipt.template.json`, `receipts/` (recorded runs); nothing under `docs/results/` |
| **F release** (Fable) | `sprint/release` | `CHANGELOG.md`, `docs/ROADMAP.md`, `CITATION.cff`, `src/arci/__init__.py`, `pyproject.toml` + `uv.lock` + `FROZEN.sha256` (re-freeze), `docs/design/0005-*.md`, README pins | per T12/T13 |
| **README** (Fable) | `sprint/readme` | `README.md` first screen only | decision E3 |
| **V verify** (Fable, continuous) | main | nothing | after every merge: `just check`, `just frozen`, `python docs/assets/src/make_figures.py --check`, wheel build + `uvx --from dist/*.whl arci demo` from an empty temp dir, CI green on origin; `just selfcheck` only if statistics are touched (none planned) |

**Integration order.** 00 → 01 → B ‖ C (C's two bias-control consults run while B is being coded) → A (after B) ‖ C → D ‖ E (after C) → README (after B, C) → F release (last) → measurements → FINAL_REPORT/HUMAN_INBOX.

**Cut order if the budget runs short.** S8 (Inspector dependence), then S9 (keep a minimal checklist), then S7 reduced to the `arci init`-generated tree only. S1–S6, S10–S12 are not cut.

---

## D. Tasks

Common to every TASK: AGENTS.md rules apply (no git state changes by the coder, no `uv`, use `.venv/bin/*`, no network, no new deps, stdlib+pydantic+pyyaml only, ruff/basedpyright strict clean, acceptance tests untouched). REPORT format: Status DONE/PARTIAL/BLOCKED | Changes | Tests (commands + results) | Deviations (with reason) | Open issues. Worktree absolute path is injected into the dispatch.

### TASK 00: persist the plan — Lane F | Owner Fable | 10 min
Goal: `git pull --ff-only`, then commit this plan verbatim to `plan/exec/PLAN.md`, one file per task in `plan/exec/tasks/<id>.md`, `plan/exec/DECISIONS.md` (section H), `plan/exec/STATUS.md` (empty table), and the memo copied verbatim to `plan/research/forward-plan-2026-10-13.md`. One commit on main (`docs(plan): persist the v0.8.0 sprint plan`). Done when: `git log -1` shows it and `git push` succeeds. Reviewers: none (no product change).

### TASK 01: team setup and preflight — Lane F | Owner Fable | 30 min | Depends 00
Goal: the three parties exist and are verified; the merge bar passes on main.
- Create `plan/exec/CONTRACT.md` (REPORT format, merge bar, file ownership, FROZEN/recorded-results rule, no git, no uv, no network).
- Create `.claude/agents/coder.md`: `model: claude-opus-5-5`, `effort: high`, `tools: Read, Edit, Write, Bash, Grep, Glob`; system prompt embeds CONTRACT.md.
- Create `.claude/agents/reviewer.md`: `model: claude-opus-5-5`, `effort: high`, `tools: Read, Grep, Glob` (no Bash: the orchestrator runs checks and hands the reviewer the diff and the check output); prompt = REVIEW format, verdicts ACCEPT/REVISE/REJECT, findings by severity.
- Consultant: `codex exec -m gpt-6-astra -c model_reasoning_effort="xhigh" -c approval_policy="never" -s read-only --skip-git-repo-check -C <path> -o plan/exec/consults/<id>.md "<prompt>"`; test with CONSULT 01 (a one-paragraph question about the plan); confirm the output file; record whether `--ignore-user-config` is needed to suppress the `notify` hook in `~/.codex/config.toml`.
- Probe: dispatch the coder on a trivial read-only task; open `~/.claude/projects/-Users-ajay-Developer-agent-reliability-ci/<session>/subagents/agent-*.jsonl`; confirm `message.model` = `claude-opus-5-5` and the effort key = high. If effort cannot be set per subagent, set session effort high and record it in DECISIONS.
- Confirm `gh auth status`, `git push --dry-run` (after pull), `uv sync --frozen`, `just check`, `just frozen`, `python docs/assets/src/make_figures.py --check`.
- Create worktrees for lanes B, C, A, D, E; `uv sync --frozen` in each.
Done when: `plan/exec/consults/01.md` exists, the probe transcript shows the model and effort, all five checks pass; any failure is the first HUMAN_INBOX item. Reviewers: none.

### TASK 02 (S2): packaged `arci demo` — Lane B | Owner Opus high | est 60–90 min coder + 20 min review | Depends 01
Goal: `uvx --from <wheel> arci demo` runs the six-step retry story from an empty directory, no clone, no model call, real `run`/`diff`/`minimize`/`replay`, exit 0.
Context: `examples/retry_agent/{hero_demo,experiment,world,agents}.py`, `src/arci/cli.py`, `src/arci/{runner,replay,minimize,diff}.py`, plan §B facts, memo S2.
Interface contract: Lane B row in §C. Steps and expectations identical to hero_demo (1 clean pair; 2 A vs B BLOCK and A vs A PASS at N=200; 3 diff after `tool_timeout`; 4 minimise 3→1 faults, 1-minimal; 5 replay REPRODUCED; 6 C passes the reproducer and its own experiment). CLI calls go through `arci.cli.main([...])` in-process or `sys.executable -m arci.cli`; no `PYTHONPATH`, no `__file__`, no repo root. Default workers `min(8, os.cpu_count() or 4)`. Run stores in a `tempfile.mkdtemp(prefix="arci-demo-")` unless `--keep DIR`; `--keep` into a non-empty dir is a clean exit-3 error. Final line names the store dir and says the counts are expected to match the recorded run (192/200, 132/200) but are computed fresh, not replayed from evidence.
Files: create `src/arci/demo/{__init__,world,agents,experiment,run}.py`, `src/arci/__main__.py` (three lines: `python -m arci` = `arci`), `tests/unit/demo/{__init__,test_demo}.py`; modify `examples/retry_agent/world.py` and `agents.py` into re-export shims (`from arci.demo.world import *` plus explicit names incl. the constants and `scenario_for_seed`), `src/arci/cli.py` (demo block only). NOT to touch: `examples/retry_agent/experiment.py` (figure needle, frozen test import), `examples/retry_agent/hero_demo.py`, anything frozen, `docs/results/**`.
Acceptance: fresh venv + `pip install dist/*.whl` in an empty temp dir → `arci demo` exits 0 with "All six steps held"; `tests/acceptance/test_hero.py`, `tests/unit/examples/test_retry_example.py`, figure check still pass; `arci demo --help` exits 0 with empty stderr.
Tests to add: in-process test of `arci.demo.experiment` seals and refs; a parity test that `examples.retry_agent.world.make_world is arci.demo.world.make_world`; an import-isolation test that `arci.demo` loads no `examples.*`/`bench.*`/`tests.*` module (same shape as `test_the_cli_never_imports_bench`); an N-independent test of step logic with `--n` unexposed (use the clean manifest and a 12-trial noisy run to keep it < 30 s); a CLI test that `--keep` on a non-empty dir exits 3.
Constraints: no change to default report bytes; no new store under `docs/results`.
Done when: `.venv/bin/pytest tests/unit/demo tests/unit/examples tests/acceptance/test_hero.py -q`; `.venv/bin/ruff format --check . && .venv/bin/ruff check . && .venv/bin/basedpyright`; `uv build --no-sources -o /tmp/arci-dist && cd $(mktemp -d) && uvx --from /tmp/arci-dist/*.whl arci demo` (orchestrator runs the last one).
Reuses: hero_demo step logic, `run_experiment`, `decide`, `first_divergence`, `minimize_faults`, `replay`. Integrates with: T06/T07 smoke jobs, T11 README. Mandatory reviewers: Fable + reviewer subagent. REPORT → `plan/exec/reports/02.md`.

### TASK 03 (S3): declarative descriptor + generated JSON Schema — Lane C | Owner Opus high | est 90–120 min + 30 min review | Depends 01, decision E2
Goal: `arci.yaml` is a thin deserialisation layer into the existing `Manifest`; sealing is unchanged; the schema is generated from code; the Python builder stays.
Context: `src/arci/schema.py` (frozen, read only), `src/arci/cli.py`, `tests/acceptance/test_schema.py` (frozen), memo S3 and the YAML sketch, ADR 0007 (decision E2 outcome).
Interface contract: Lane C row in §C. Invariants regardless of E2's exact shape: (i) no decision logic in the YAML layer; (ii) every descriptor key maps 1:1 onto a `Manifest` field or is a documented alias (`oracle` → `contract.oracle`; an arm given as a bare string is a python `ArmSpec(label=<function name>, agent=<ref>)`); (iii) unknown keys rejected (pydantic `extra="forbid"`); (iv) `arci run` accepts `.yaml`/`.yml`, compiles, seals with `Manifest.create`, runs; the run store is unchanged (`manifest.json` is the sealed JSON); (v) `arci schema` prints `Descriptor.model_json_schema()`; `docs/schema/arci.schema.json` is committed and a test fails when stale; (vi) placeholders `{workdir}` etc. stay unexpanded strings; (vii) `created_at` is set by the loader like the builder does; (viii) the loader uses `yaml.safe_load` like `contracts.load_contract` and the docs state the YAML 1.1 coercion pitfall; (ix) fault names are checked against `perturb.REGISTRY` or the `module:function` form at load time, with one-line errors; (x) the docs say Pydantic is authoritative and the committed schema bytes are pinned under the locked pydantic.
Files: create `src/arci/descriptor.py`, `docs/schema/arci.schema.json`, `docs/DESCRIPTOR.md`, `tests/unit/descriptor/**`; modify `src/arci/cli.py` (`_cmd_run` load branch, `schema` subcommand). NOT to touch: frozen files, report.py output, `examples/**`.
Acceptance: the descriptor for the retry demo compiles to a `Manifest` whose `record_sha256` equals `arci.demo.experiment.build_manifest(200, "agent_b").record_sha256` (same semantic manifest, byte-equal seal); a command-agent descriptor (mcp_server + command arms) round-trips; unknown key → exit 3 with one line naming the key and path; `arci run x.yaml` on the acceptance fixture world gives the same verdict as the JSON path.
Tests to add: round-trip and seal-equality tests; schema staleness test; error-message tests; `arci run` yaml path test at small N (exit 2) using `tests.acceptance.fixture_agents` refs with `PYTHONPATH`.
Constraints: no `bench` import at `arci.cli` import time; help output `usage: arci schema`, empty stderr.
Done when: `.venv/bin/pytest tests/unit/descriptor tests/unit/cli tests/acceptance/test_cli.py tests/acceptance/test_schema.py -q` + ruff/basedpyright + `.venv/bin/python -m arci.cli schema | diff - docs/schema/arci.schema.json`.
Reuses: `Manifest.create`, pydantic JSON Schema. Integrates with: T04, T05, T08, T09. Mandatory reviewers: Fable + reviewer subagent + Astra (schema-adjacent). REPORT → `plan/exec/reports/03.md`.

### TASK 04 (S4): `arci init` — Lane C | Owner Opus high | est 90 min + 30 min review | Depends 03, decision E1, ADR 0006
Goal: one non-interactive command writes a schema-valid, runnable `arci.yaml` from experiment name + baseline/candidate/toolset/oracle refs, validating the refs immediately and failing with one actionable error.
Context: T03's `Descriptor`, `src/arci/runner.py` `_pythonpath`, AGENT_SEMANTICS "the parent never imports refs", `docs/DECISIONS.md` #4, memo S4 + first-screen command, ADR 0006 (cwd on the child import path), ADR 0008 (E1 outcome).
Interface contract (bounds; exact flags from E1): `arci init EXPERIMENT_ID --baseline REF --candidate REF --toolset REF --oracle REF [--task JSON | --task-file PATH] [--fault NAME[:TOOL[:OCC]]] [--n N] [--out PATH (default arci.yaml)] [--force]`; exit 0 and prints the next command (`arci run arci.yaml`); exit 3 with ONE line on the first bad ref (module not importable / attribute missing / not callable / fault tool not in the toolset's tools) or on an existing output file without `--force`; ref validation runs in a child `sys.executable -P` with the same PYTHONPATH rule the runner uses (never in the CLI process); the written file carries a header comment marking the smoke design and the `arci plan` pointer; the written file re-validates through T03's loader before exit.
ADR 0006 (Lane C, part of this task): `runner._pythonpath` appends `os.getcwd()` when absent, so refs in the cwd resolve under the console script exactly as under `python -m arci.cli`; documented in `docs/DESCRIPTOR.md` and CHANGELOG; Astra review mandatory.
Files: create `src/arci/init.py`, `tests/unit/init/**`; modify `src/arci/cli.py` (init block), `src/arci/runner.py` (`_pythonpath` only). NOT to touch: frozen files, `examples/**`.
Acceptance: from an empty dir containing `app/v1.py`, `app/v2.py`, `tests/world.py` (the T08 sample copied in a tmp dir), `arci init checkout-retry --baseline app.v1:run --candidate app.v2:run --toolset tests.world:make_world --oracle tests.world:passed` writes `arci.yaml`; `arci run arci.yaml` (console-script semantics, no PYTHONPATH) exits 2 with a valid store; a typo'd ref exits 3 with the one-line error; `tests/acceptance/**` still pass (PYTHONPATH behaviour for existing callers unchanged: cwd is appended, never prepended).
Tests to add: subprocess tests for the four error classes, `--force`, smoke header, the cwd rule (a console-script-like invocation with `-P` and sys.path without cwd).
Done when: `.venv/bin/pytest tests/unit/init tests/unit/runner tests/acceptance/test_cli.py tests/acceptance/test_runner_replay.py -q` + ruff/basedpyright.
Reuses: T03 loader, `contracts.resolve` (in the child), `interfaces` signatures. Integrates with: T05, T08, T09, T11. Mandatory reviewers: Fable + reviewer subagent + Astra (ADR 0006). REPORT → `plan/exec/reports/04.md`.

### TASK 05 (S5): honest smoke-design UX — Lane C | Owner Opus high | est 45 min + 15 min review | Depends 04
Goal: the first run is fast and never pretends to be confirmatory.
Contract: `arci init` default `n_per_arm` per E1 (memo says 5; the floor at which a total collapse can still BLOCK is 8; E1 decides), written with a comment `# smoke design: expect INCONCLUSIVE; run arci plan before a confirmatory N`. `arci run` prints, to **stderr only**, one line before the run when any gating condition has `n_per_arm < 100`: `SMOKE DESIGN: n_per_arm=<N> (<alpha>, <delta>, K=<k>): PASS is impossible below N=42 and BLOCK below N=8 at the default rule; expect INCONCLUSIVE. Plan a confirmatory N with: arci plan --baseline-rate P --candidate-rate P --target-verdict BLOCK` (numbers computed from `arci.planning` when the design is in the planner's domain, otherwise the fixed sentence). After an INCONCLUSIVE verdict at such N, one more stderr line repeats the `arci plan` pointer. Nothing on stdout, nothing in reports, decisions or stores; no outcome-dependent extension anywhere.
Files: modify `src/arci/cli.py` (`_cmd_run`), `src/arci/init.py` (header), tests under `tests/unit/cli/test_smoke_notice.py`. NOT to touch: `report.py` default output, `gate.py`, `schema.py`.
Acceptance: `tests/acceptance/test_cli.py` (last stdout line) and `tests/unit/report/test_report_pass_k_cli.py` (stderr empty for `report`) still pass; the notice appears on stderr for N=6 and not for N=200; the Action job summary is unchanged.
Done when: `.venv/bin/pytest tests/unit/cli tests/unit/report tests/acceptance/test_cli.py -q` + ruff/basedpyright.
Reuses: `arci.planning.verdict_table`. Mandatory reviewers: Fable + reviewer subagent + Astra (statistics wording). REPORT → `plan/exec/reports/05.md`.

### TASK 06 (S1): publishable package pipeline — Lane A | Owner Opus high | est 60 min + 30 min review | Depends 02 (for the smoke), E-none
Goal: a tag push builds wheel+sdist, smoke-tests the built wheel on Ubuntu and macOS (py3.11, 3.14) from an empty directory, and publishes to PyPI via trusted publishing with attestations.
Context: `.github/workflows/ci.yml` (pin style), pyproject (frozen until T12), §B PyPI path, pypa/gh-action-pypi-publish README, uv docs.
Contract: `.github/workflows/release.yml` on `push: tags: ['v*']` and `workflow_dispatch`; jobs: `build` (ubuntu, `uv build --no-sources`, `twine check`-equivalent via `uv`/`python -m zipfile -l`, upload `dist/` artifact, print SHA256SUMS to the job summary); `smoke` (matrix ubuntu/macos × 3.11/3.14: download artifact, `python -m venv`, `pip install dist/*.whl`, `cd $(mktemp -d)`, `arci --help`, `arci demo --workers 4`, `arci schema`); `publish` (needs build+smoke, `environment: pypi`, `permissions: id-token: write`, `pypa/gh-action-pypi-publish@<sha>` with attestations default on, `skip-existing: false`). A `guard` step refuses to build unless the tag equals `v` + the pyproject version and `src/arci/__init__.__version__` matches (PyPI versions are immutable). All actions SHA-pinned with version comments; `permissions: contents: read` at top. Root `.gitignore` gains `node_modules/`. Also: create the GitHub `pypi` environment via `gh api -X PUT repos/ajaysurya1221/agent-reliability-ci/environments/pypi` (orchestrator) and `docs/RELEASING.md` (exact release steps, verification with `shasum`, what to do if the pending publisher is missing).
Files: create `.github/workflows/release.yml`, `.github/scripts/wheel_smoke.sh`, `docs/RELEASING.md`; modify `.gitignore`. NOT to touch: `pyproject.toml`, `uv.lock`, `action.yml`, `ci.yml` (T07 owns), frozen files.
Acceptance: `actionlint` clean; a dry run of the build+smoke jobs on the lane branch via `workflow_dispatch` is NOT possible without a tag → the smoke steps are exercised locally by the orchestrator (`uv build` + fresh venv + `arci demo`) and on CI through T07's `wheel-smoke` job, which reuses the same shell steps (one composite script `.github/scripts/wheel_smoke.sh` shared by both).
Done when: `actionlint .github/workflows/release.yml`; `shellcheck .github/scripts/wheel_smoke.sh`; local `bash .github/scripts/wheel_smoke.sh dist/*.whl` passes.
Mandatory reviewers: Fable + reviewer subagent + Astra (release workflow). REPORT → `plan/exec/reports/06.md`.

### TASK 07 (S11): install and Action matrix in CI — Lane A | Owner Opus high | est 45 min + 20 min review | Depends 02, 06
Goal: distribution did not break CI use; Windows is install/import/--help only and not advertised.
Contract: `ci.yml` gains `on.push.branches: [main, 'sprint/**']` (lane branches get CI without PRs), job `wheel-smoke` (ubuntu/macos × 3.11/3.14; `uv build --no-sources`; `.github/scripts/wheel_smoke.sh`), job `windows-smoke` (windows-latest, py3.12: `pip install dist/*.whl`, `python -c "import arci, arci.cli"`, `arci --help`; nothing else; job name says "install/--help only, execution unsupported"), job `action-fixture` (ubuntu: `uses: ./` with `manifest: examples/action_fixture/manifest.json` (sealed JSON built from `arci.demo` refs, N=200, A vs B), `continue-on-error: true`, then `test "${{ steps.gate.outputs.verdict }}" = BLOCK` and that the Markdown report reached `$GITHUB_STEP_SUMMARY`). `examples/action_fixture/build_manifest.py` regenerates the fixture and a unit test checks it is current. If `import arci.cli` fails on Windows because of a module-level POSIX reference, guard that reference (allowed: it is not frozen) and record it in CHANGELOG.
Files: modify `.github/workflows/ci.yml`; create `.github/scripts/wheel_smoke.sh`, `examples/action_fixture/**`, `tests/unit/examples/test_action_fixture.py`. NOT to touch: `action.yml` unless the fixture reveals a defect (then ADR + Astra), frozen files.
Done when: `actionlint`, `shellcheck`, the unit test, and a green CI run on `sprint/package` showing all new jobs.
Mandatory reviewers: Fable + reviewer subagent + Astra (CI/action). REPORT → `plan/exec/reports/07.md`.

### TASK 08 (S7): Python-agent recipe — Lane D | Owner Opus high | est 60 min + 20 min review | Depends 04, 05
Goal: "Gate a retry-policy change in ten minutes": from a blank sample project, four refs + task data reach a valid verdict; no gate/statistics code copied.
Contract: `examples/recipes/python_agent/` = `app/__init__.py`, `app/v1.py` (`run(task, tools, rng)` with a retry), `app/v2.py` (retry removed), `tests/__init__.py`, `tests/world.py` (`make_world(task, seed)`, `passed(task, final_state)`), `README.md` (the memo's exact second first-screen command, then `arci plan`, then the confirmatory re-run, then `diff`/`minimize`/`replay`), `arci.yaml` as `arci init` writes it (checked current by a test). Refs exactly as the memo: `app.v1:run`, `app.v2:run`, `tests.world:make_world`, `tests.world:passed`. `docs/recipes/python-agent.md` is the narrative with the recorded output of one run (INCONCLUSIVE at smoke N, BLOCK at the planned N) and the time taken on this machine. The world is a smaller cousin of the retry world (one tool with a transient fault), not a copy.
Files: create the tree above, `docs/recipes/python-agent.md`, `tests/unit/recipes/test_python_agent.py`. NOT to touch: `src/arci/**`, frozen files.
Acceptance: test copies the tree to tmp, runs `arci init …` and `arci run arci.yaml` with console-script semantics (no PYTHONPATH), expects exit 2 and a sealed store, < 60 s; `basedpyright` strict passes on the sample code; the recipe README's commands are the ones the test runs (test greps them).
Mandatory reviewers: Fable + reviewer subagent. REPORT → `plan/exec/reports/08.md`.

### TASK 09 (S8): MCP command-agent recipe + Inspector preflight — Lane D | Owner Opus high | est 75 min + 20 min review | Depends 04
Goal: an MCP route using what exists: Inspector for protocol/tool discovery, ARCI for recorded/faulted repeated trials; responsibilities explicitly distinguished.
Contract: `examples/recipes/mcp_agent/` = `world.py` (python toolset served by `arci.mcp_toolset_server`), `agent.py` (~40-line stdlib newline-JSON-RPC client: one session, initialize → tools/list → calls → exit 0/1; v1 retries a transient tool fault, v2 does not), `mcp.inspector.json` (the `{"mcpServers": …}` config pointing at the bridge with `-e PYTHONPATH` and `--task-file`), `arci.yaml` (command arms + `mcp_server`, written by hand because `arci init` scaffolds python arms; documented), `README.md`. `docs/recipes/mcp-inspector.md`: step 1 Inspector CLI (`npx @modelcontextprotocol/inspector --cli --config mcp.inspector.json --server env --method tools/list`), step 2 `arci run arci.yaml`, step 3 `diff`/`minimize`/`replay`; a boxed "what each one checks" table; the honest list of what a raw-server preflight does not cover (faults, budgets, one-connection rule, reserved names, 1 MiB line limit). The coder does NOT run npx (no network); the orchestrator runs the Inspector step once locally and pastes the verbatim result into the doc. If Inspector rejects protocol `2026-07-28`, the doc records that verbatim and the recipe ships with the Inspector step marked "blocked by SDK version <x> on <date>"; changing the bridge's version handling is out of scope for this task (ADR + Astra if ever).
Files: the tree above, `docs/recipes/mcp-inspector.md`, `tests/unit/recipes/test_mcp_agent.py`. NOT to touch: `src/arci/**`, frozen files.
Acceptance: test runs `arci run arci.yaml` at N=3 for the recipe (exit 2, sealed store, both arms exercised; < 60 s), and a standalone smoke of `agent.py` against the bridge over a pipe.
Mandatory reviewers: Fable + reviewer subagent. REPORT → `plan/exec/reports/09.md`.

### TASK 10 (S9): TTFV and cold-read measurement harness — Lane E | Owner Opus high (worker-lite scope) | est 40 min + 15 min review | Depends 02, 04
Goal: replace estimates with repeatable measurements that five cold readers can be scored on without coaching.
Contract: `docs/measurement/ttfv-protocol.md`: preconditions (machine with Python 3.11+ and uv, no checkout), the stopwatch milestones from the memo (README opened → install start → demo verdict; scaffold complete → run start → verdict printed → store validates → interpretation answered), what stops the clock, how agent execution time is reported separately, the five comprehension questions (what is it, for whom, what does PASS mean, what does it not do, the first three own-agent commands) with the scoring key, and the receipt format; `receipt.template.json` (ISO timestamps per milestone, machine, python, uv, package version/wheel sha, verdict, answers, score); `receipts/README.md` (how receipts are contributed; failures kept; no telemetry). No code.
Files: the three files above. NOT to touch: `docs/results/**`.
Acceptance: the orchestrator fills one receipt end to end in T13 without needing to ask anything.
Mandatory reviewers: Fable + reviewer subagent. REPORT → `plan/exec/reports/10.md`.

### TASK 11 (S6): README first screen — Lane README | Owner Fable | est 45 min + 20 min review | Depends 02, 04, decision E3
Goal: value proposition and two commands before any statistics jargon; ≤200 words before deeper docs; relative PASS and "not a sandbox" above the fold.
Contract: order exactly as the memo (question headline → one-sentence what → `uvx … arci demo` → `uv tool install … && arci init … && arci run arci.yaml` → pipeline line → PASS-means-only-this → small-run INCONCLUSIVE + `arci plan` → boundary sentence), final text per E3. Below the fold, unchanged in substance: recorded result + evidence links, hero figure (figure `<source>`/`<img>` URLs and every first-screen link made absolute to `https://github.com/ajaysurya1221/agent-reliability-ci/...` / `raw.githubusercontent.com/.../main/docs/assets/…`, because PyPI strips `<source>` and breaks relative links; only the light SVG shows there), verdict table, how it works, where it has been run, the gate measured against itself, gate your own agent (now: descriptor first, builder as the advanced path), GitHub Actions (pin updated in T12), **"What it does not do" kept and tightened** (add: `arci init` validates refs by importing them; a fault on a tool the toolset never calls silently never fires), roadmap, development. Jargon per the memo's table on the first screen only. No new claims; the new demo wording says the counts are computed fresh and match the recorded run.
Files: `README.md` only. Figure check must pass unchanged (`make_figures.py` never reads README).
Done when: `python docs/assets/src/make_figures.py --check`; word count of the first screen ≤ 200 (`plan/exec/scripts/first_screen_words.py`); reviewer cold-read ≥ 4/5 (see F).
Mandatory reviewers: reviewer subagent + Astra. REPORT → `plan/exec/reports/11.md`.

### TASK 12 (S10): release-integrity merge — Lane F | Owner Fable | est 45 min + 20 min review | Depends 02–11 merged
Goal: v0.8.0 is identified in CHANGELOG with everything unreleased plus the sprint; recorded decisions and default report bytes stay pinned; the version bump is lawful.
Contract: `docs/design/0005-v0.8.0-packaging-and-version-bump.md` (ADR: why `pyproject.toml` and `uv.lock` change — version 0.8.0, `[project.urls]`, classifiers, keywords, `[tool.hatch.build.targets.sdist] only-include = ["src/arci", "README.md", "LICENSE", "NOTICE", "CHANGELOG.md", "pyproject.toml"]` — and that nothing else in them changes); `uv lock` (no dependency change expected; `uv lock --check` must pass); `FROZEN.sha256` re-freeze commit titled `re-freeze: pyproject.toml, uv.lock and design records for v0.8.0 (ADR 0005)` that also adds the new ADRs 0005–0008 (keeps AGENTS.md's "docs/design/** frozen" coherent); `CHANGELOG.md` `## v0.8.0 (2026-10-1x)` listing: planner, pass^k, portability fixes, evidence package, guardrail results, docs; then the sprint: PyPI/uvx, `arci demo`, descriptor + schema + `arci schema`, `arci init`, smoke notice, cwd import rule (ADR 0006), recipes, measurement protocol, CI matrix + release workflow, README; `docs/ROADMAP.md` "Done in v0.8.0" + removal of "On main, not yet released"; `CITATION.cff` version/date; `src/arci/__init__.py`; README availability line and Action example `@v0.8.0`; the `v0.7.0` release badge link → `v0.8.0`.
Done when: `just check`, `just frozen` (after re-freeze), `uv lock --check`, figure check, `.venv/bin/pytest tests/unit/report tests/unit/examples tests/unit/stats -q` (pins unchanged), `.venv/bin/python docs/reports/ci-gate-2026-10-06/reproduce.py --check` (package untouched).
Mandatory reviewers: reviewer subagent + Astra (FROZEN/pyproject). REPORT → `plan/exec/reports/12.md`.

### TASK 13 (S12): v0.8.0 release and evidence receipt — Lane F | Owner Fable | est 60 min | Depends 12, CI green on main
Protocol: (1) merge `sprint/release` to main, wait for CI green; (2) `git tag -a v0.8.0 -m …` + `git push origin v0.8.0` → `release.yml` builds, smokes, publishes (if the pending publisher exists; otherwise the publish job fails on OIDC and becomes HUMAN_INBOX item one with the exact command `uv publish --trusted-publishing always` from a re-run, or a manual `uv publish --token` the user runs); (3) GitHub release via `gh release create v0.8.0 --notes-file plan/exec/release-notes.md dist/*` with SHA256SUMS; notes cite recorded runs only (if `gh release create` stays denied → HUMAN_INBOX with the exact command and the notes file); (4) installed-package smoke from a clean environment: `cd $(mktemp -d) && uvx --from agent-reliability-ci==0.8.0 arci demo` if published, else `uvx --from dist/*.whl …`; timing recorded as a receipt; (5) README and Action re-pinned (done in T12; verified live); (6) cold-read by the reviewer subagent with no context (F); (7) `plan/exec/STATUS.md`, `FINAL_REPORT.md`, `HUMAN_INBOX.md`; push.
Mandatory reviewers: reviewer subagent + Astra (release). REPORT → `plan/exec/reports/13.md`.

### TASK V: verification lane — Fable, continuous
After every merge to main: `just check`, `just frozen`, `python docs/assets/src/make_figures.py --check`, `uv build --no-sources -o /tmp/arci-dist && cd $(mktemp -d) && uvx --from /tmp/arci-dist/*.whl arci demo --workers 4`, CI green on origin. `just selfcheck` and `tests/unit/selfcheck` if any statistics file is touched (none planned; any such touch is a stop-and-record event). STATUS.md gets one line per task: state, reviewers, commit.

---

## E. Bias-control decisions (step 5, at most three)

For each: Astra proposes from the spec alone (CONSULT E<n>-astra, written before mine); I write mine without reading it (committed as `plan/exec/decisions/E<n>-fable.md` with a timestamp before I open Astra's); compare; adopt where we agree; on differences a fresh consult (CONSULT E<n>-tiebreak) sees both and answers with one choice and one paragraph; then rule (d). Each produces an ADR.

1. **E1 — the `arci init` contract (ADR 0008).** Flag names and shapes (`--fault` syntax, `--task` vs `--task-file`, `--n`, `--out`, `--force`), the default smoke N (memo's 5 vs the "collapse can still BLOCK" floor of 8), what the scaffold validates (ref importability, callability, fault tool ∈ toolset tools, output file collision), the exact one-line error format, what it prints on success, and whether it also writes a tiny `README`/next-steps text. Spec input: memo S4/S5 + first-screen command, AGENT_SEMANTICS ref rules, §B facts. Runs during T02 coding, before T03/T04 dispatch.
2. **E2 — the declarative descriptor shape (ADR 0007).** Top-level keys and aliases (memo sketch: `experiment_id, task, toolset, oracle, baseline, candidate, conditions[].{id, fault{name,tool,occurrence}}, alpha, delta, n_per_arm`), how a command-agent experiment is expressed, whether `task_id` is derived or explicit, how buckets default (`falsify`) and `budgets`/`looks`/`interval_method`/`prior_runs` are exposed, the file name `arci.yaml`, and the JSON Schema `$id`/title. Bounded by the T03 invariants. Runs with E1.
3. **E3 — the README first screen text (ADR 0009, documentation decision).** The memo's ≤200-word text is the baseline; the decision is the final wording (jargon table applied, the two commands verbatim, whether the pipeline line and the "not a sandbox" sentence stay as written), what moves below the fold, and the absolute figure URLs. Runs after T02 and T04 merge, before T11.

Everything else is decided by the tie-break order without the step-5 protocol; Astra still reviews mandatory areas.

---

## F. Definition of done, budget, wrap-up, metrics

**Done for the run.** Main green on origin CI; every lane merged or on a pushed `sprint/*` branch with a REPORT; v0.8.0 tagged and GitHub release published (or an inbox item with the exact command); PyPI published through `release.yml` if the pending publisher exists, else inbox item one; README first screen live and cold-read tested; `plan/exec/{STATUS,FINAL_REPORT,HUMAN_INBOX}.md` pushed; zero merged changes with fewer than two non-author reviews; nothing half-applied; no frozen file changed outside the ADR'd re-freeze; no recorded result edited.

**Budget.** 10 h wall-clock from the Task 00 commit timestamp (recorded in STATUS.md). At 9 h 15 min: stop starting tasks, finish or abort in-flight ones, merge only what is green, write the reports, push. Rough timeline: 00+01 by 0:40; B merged ~2:15; C merged ~4:00; A merged ~3:45; D+E merged ~5:30; README ~6:00; T12 ~6:45; tag + release + smoke ~7:30; measurements, reports, inbox by 8:45.

**Wrap-up protocol.** (1) `git status` clean in every worktree; (2) each unmerged branch pushed with its REPORT and a STATUS line "on branch, not merged, why"; (3) FINAL_REPORT sections exactly as the prompt lists (shipped vs sprint, deviations with rule, review coverage incl. the count of changes Astra reviewed, metrics vs targets, cuts, Opus/Fable/Astra usage from the subagent transcripts and consult files, known issues, next three steps); (4) HUMAN_INBOX ordered by impact with exact text/clicks and the launch/outreach drafts attached; (5) final push; (6) last verification-lane run on main.

**Metrics measured before finishing (memo targets in brackets).**
- Packaged demo TTFV [p50 ≤ 2 min]: from an empty temp dir, wall time of `uvx --from <PyPI or wheel> arci demo` including resolve/install, three runs, receipt recorded.
- Own-agent TTFV on a fresh, clone-free directory [≤ 10 min]: copy the T08 sample tree, run the first-screen second command verbatim, stop at the printed verdict and a validated store; scaffold, run and interpretation timed separately.
- Cold read of the new first screen by the reviewer subagent with no context: the five questions, scored with the T10 key [target ≥ 4/5 correct].
- Installed-package smoke from CI on Ubuntu and macOS (release workflow) and the Windows install/--help job.
- `just check`, `just frozen`, figure check, `uv lock --check` on the released commit; `reproduce.py --check` unchanged.

---

## G. Pre-flight for you (in order)

1. Approve this plan.
2. Set the permission mode that runs without prompts (the app's mode selector; `defaultMode` in your settings is `auto`). Your global `~/.claude/settings.json` deny list blocks `gh pr create`, `gh pr merge`, `gh release create`, `gh workflow run`, `uv tool install`, `curl`: allow the first three for this run. If you leave them denied I merge with plain git, run lane CI on `sprint/**` pushes, and put PR/release creation in HUMAN_INBOX with exact commands (I will not route around a deny via `gh api`).
3. Register a PyPI pending publisher at https://pypi.org/manage/account/publishing/: project `agent-reliability-ci`, owner `ajaysurya1221`, repository `agent-reliability-ci`, workflow `release.yml`, environment `pypi`. (PyPI's JSON API and simple index returned 404 for that name on 2026-10-13; if the form says the name is taken, tell me the alternative name and only the distribution name changes.)
4. Env vars: none. No sprint task makes a live call; `JEV_API_KEY` is not needed.
5. Confirm `codex login status` succeeds (Astra) and that this session is `claude` 2.1.281 (verified); `gh auth status` is already logged in as `ajaysurya1221`.

---

## H. Decisions made now (rule in brackets: a=prompt, b=memo, c=repo rules, d=Astra, e=reversibility)

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
