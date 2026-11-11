# 0012: optional framework extras

Status: accepted by the maintainer on 2026-11-11 ("Approve both", `DECISIONS.md` D-02).
History: draft v2, written by the orchestrator (Claude Fable 5.2) on 2026-11-11. Codex
Astra 6 reviewed draft v1 read-only and returned REVISE with two blocking findings; this
draft answers both (see "Review record"). Awaiting the maintainer's approval. Becomes
`docs/design/0012-optional-framework-extras.md` plus a re-freeze only when accepted.
No frozen file is changed by this draft.

## Problem

v2.0 adds a LangChain adapter (`src/arci/adapters/langchain.py`). The adapter must import
LangChain, and its tests need LangChain's fake chat models. Today `AGENTS.md` rule 4 says
runtime code uses only the standard library, `pydantic` and `pyyaml`, and `pyproject.toml`
and `uv.lock` are frozen.

The two-dependency core is worth keeping: it is why `uvx --from agent-reliability-ci arci demo`
installs in seconds and why the wheel smoke test needs nothing else.

## Decision (proposed)

1. **The core stays at two runtime dependencies.** `[project].dependencies` is unchanged.
   `import arci` and every existing command must work with LangChain absent.
2. **One optional extra per framework.** Add
   `[project.optional-dependencies] langchain = ["langchain>=1.4.9,<2"]`.
   1.4.9 is the version the phase 0 spikes ran against; nothing lower has been tested, so
   nothing lower is allowed. The upper bound follows LangChain's stated policy of no
   breaking changes before 2.0.
3. **The adapter uses public LangChain APIs only.** The S2b prototype imported a private
   formatter and an unexported exception from two packages that the `langchain` pin bounds
   only indirectly (`langchain-core`, `langgraph-prebuilt`). The product adapter does not;
   that is a phase 3 requirement (`plan/exec/v2/reviews/S2b-review.md`, requirement 5). The
   adapter may import the extra's own transitive packages (`langchain-core`, `langgraph`)
   through their public names.
4. **Adapters import their framework lazily and fail with one actionable line.** Importing
   `arci.adapters.langchain` without the extra raises an error that names the install command
   `pip install 'agent-reliability-ci[langchain]'`. No other module imports an adapter at
   import time. A capability check at import ends as a harness ERROR if a needed public name
   is missing.
5. **A separate dependency group for adapter tests, not the `dev` group.** Add
   `[dependency-groups] adapters = ["langchain>=1.4.9,<2"]`.
6. **How the core CI jobs stay green without LangChain, exactly.** The core jobs run every
   test and an unrestricted type check today (`.github/workflows/ci.yml:65-71`,
   `pyproject.toml:59`, `:76`). So:
   - Every test module under `tests/unit/adapters/` begins with a guard that skips the
     module when LangChain is absent, **unless** the environment variable
     `ARCI_REQUIRE_ADAPTERS=1` is set, in which case the guard raises. Core jobs skip those
     modules; the adapter job sets the variable, so a missing dependency there is a failure,
     not a silent skip.
   - `[tool.basedpyright]` gains an `exclude` for `src/arci/adapters` and
     `tests/unit/adapters`, so the core type check does not need LangChain's types.
   - The adapter job cannot simply pass those two paths to `basedpyright`: paths on the
     command line replace `include` but keep `exclude`, so the excluded folders would be
     skipped. It uses its own configuration file, `pyrightconfig.adapters.json` (new, not
     frozen), with the same strict settings, `include` set to the two adapter paths and no
     exclusion, run as `basedpyright --project pyrightconfig.adapters.json`. A check in the
     job fails if that run analysed zero files. Both type checks are mandatory for merge.
7. **Three adapter environments, each with stated versions that the job asserts.**
   - **Low:** a constraints file `constraints/adapters-low.txt` (new, not frozen) pins the
     lowest supported set: `langchain==1.4.9` and the lowest `langchain-core`, `langgraph`
     and `langgraph-prebuilt` that it allows (for 1.4.9: `langchain-core==1.7.5`,
     `langgraph-prebuilt==1.1.0`; to be confirmed from the package metadata in phase 3).
   - **Locked:** the versions in `uv.lock` (`uv sync --frozen --group adapters`). This is
     what the release is tested against. It is not an upper endpoint.
   - **Latest:** a scheduled weekly job installs the newest releases inside the allowed
     range (`--upgrade`, not frozen) and reports, without blocking merges, so a breaking
     upstream release is seen within a week.
   - Every job prints the installed versions of those four packages and fails if they are
     not the ones its environment names. All three run the adapter tests and the adapter
     type check. Python 3.13; 3.14 is added when LangChain installs on it (checked in
     phase 3, not assumed).
8. **Adapter tests are offline.** They use `langchain_core.language_models.fake_chat_models`
   only. The adapter jobs set `LANGSMITH_TRACING=false` and must make no network call.
9. **A guard test protects the core.** A unit test starts a fresh interpreter, imports `arci`
   and runs `arci --help`, and fails if `langchain`, `langgraph` or `langsmith` appears in
   `sys.modules`.

## Exact frozen changes (to be made in the release re-freeze, phase 5)

- `pyproject.toml`: add the `[project.optional-dependencies]` table with the one `langchain`
  entry; add the `adapters` dependency group; add the two `exclude` paths under
  `[tool.basedpyright]`. Version bump is ADR 0011's business.
- `uv.lock`: regenerated with `uv lock`. New packages are LangChain and its transitive
  dependencies only. Resolved versions of every existing package must not change; the record
  will list what moved.
- `AGENTS.md` rule 4: replace "Runtime code uses only the stdlib, `pydantic`, `pyyaml`." with
  "Runtime code uses only the stdlib, `pydantic`, `pyyaml`; a module under
  `src/arci/adapters/` may also import the one optional extra it is named for, and that
  extra's own packages, lazily." The rule "No new dependencies" stays as it is for coding
  agents: only a design record adds one.
- `FROZEN.sha256`: new hashes for those three files and for this record. Every other entry
  unchanged.

Not frozen, added or changed in the same release: `.github/workflows/ci.yml` (the adapter
jobs), `pyrightconfig.adapters.json`, `constraints/adapters-low.txt`.

## Consequences

- A user who never installs an extra sees no change in install size or import time.
- The lock file grows by roughly 25 packages (measured in the spike environment:
  `langchain-core`, `langgraph`, `langsmith`, `requests`, `orjson` and others).
- A second adapter repeats the pattern: one extra, one lazy module, tests in the same group.
- Core type checking no longer covers the adapter paths; the adapter jobs do.

## Open points

1. Does LangChain 1.4.9 install on Python 3.14? Checked in phase 3.
2. `langsmith` arrives transitively and can send traces when its environment variables are
   set. The recipe must tell users that ARCI does not enable it and that run stores may hold
   sensitive task data either way.

## Review record

Codex Astra 6, read-only, on draft v1: REVISE. Blocking finding 1: a separate dependency
group does not by itself keep core test collection and type checking away from LangChain
(answered by item 6). Blocking finding 2: `>=1.4` was not the verified lower bound, and the
transitive packages were unaddressed (answered by items 2, 3 and 7). Codex judged the
dependency-group approach appropriate and the `AGENTS.md` change minimal, and asked for the
transitive-import permission to be explicit (now in the rule text).

## Amendments made before this record was frozen (2026-11-11)

- The lowest supported set was resolved from the package index and tested: `langchain 1.4.9`,
  `langchain-core 1.7.5`, `langgraph 1.2.12`, `langgraph-prebuilt 1.1.0`
  (`constraints/adapters-low.txt`). The adapter tests pass there and on the locked set.
- The frozen changes were made when the two lanes were integrated, before the release
  re-freeze, so that hosted CI could check the adapter. The version stays 1.0.0 until the
  release record.
- The "Latest" environment runs from its own workflow file, `adapters-latest.yml`, weekly.
- The locked job asserts its four package versions against `constraints/adapters-locked.txt`,
  which is written from `uv.lock`.
- The adapter test guard also covers `tests/unit/toolbox/test_fail_harness.py`'s neighbours
  only where they import LangChain; tests that do not need it run in the core jobs.
