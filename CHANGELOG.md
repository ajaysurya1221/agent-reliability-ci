# Changelog

## Unreleased

- `arci check-change` registers a rule before running two test commands on fresh paired rounds.
  Sealed decisions name the snapshots used for replay. ARCI checks earlier originals and
  snapshots before each launch and before reporting the verdict. Cancelling a launch stops
  its process group and records the cancellation in `verdict.txt`. The report explains the verdict
  against the registered margin and gives the number of task runs each version passed.
  See the [check-change recipe](docs/recipes/check-change.md).

- **Docs:** the readers are checked against Claude Code 2.1.326 and 2.1.330 and Codex CLI
  0.171.0. For 2.1.330 and 0.171.0 the check was one short session each; for 2.1.326 it
  was this project's own sessions of that client. `docs/LOG_FORMATS.md` names the three
  versions and says what each check was. No code change.
- **CI:** the build tool uv that every workflow installs is 0.13.4, up from 0.12.5, with the
  hashes of all 19 files PyPI lists for that version. Why: an advisory says uv below 0.13.4
  bundles a certificate store that trusts a root whose intermediate keys are compromised.
  The installed package is not affected: uv is used to build and test, not at run time.

## v2.4.1 (2026-11-18)

- **Fixed:** at the end of a command trial the boundary now waits for its MCP tool server when
  waiting can change what the grader reads, instead of always killing it at once. Why: a CI run
  showed that for an agent that never uses its tool server, `final_state` (and so
  `record_sha256`) was `{}` or the server's starting state depending on timing, because a
  server still starting when the agent exited was killed before it wrote its first state. The
  boundary waits when any of these holds at cleanup: the server has not sent one valid response
  matching a request the boundary forwarded in this trial (notifications and unmatched or
  invalid responses do not count), a forwarded request still has no response, bytes for the
  server are still queued unwritten, or a harness fault is latched. Then it stops the server in
  stages, in the order the MCP specification's stdio shutdown asks for: it closes the server's
  input, waits for the process to exit (draining its output meanwhile), sends SIGTERM if it is
  still running after half of the time left before the trial's deadline, and SIGKILL after
  three quarters. Otherwise the server is idle, and the boundary closes its input and kills it
  at once, as before. The time comes from the trial's own deadline: the parent passes its
  deadline and the seconds left to the boundary in its launch configuration, outside the spec
  and every sealed record, and the boundary never uses a deadline later than the parent's. No
  new outcome, termination, event or latch exists, and nothing about the stop (whether the
  boundary waited, or which stage ended the server) is recorded or graded. The final state can
  now differ from before (that is the fix). Limits: the idle rule trusts that a server which
  has answered has already written its state, so a server that answers before it writes its
  state, that saves only on EOF, or that writes its state in reaction to a notification (to
  which no response ever comes) can still lose that state when it is idle, as before this
  change (the project's own bridge and its fixture server write before they answer); a server
  whose start-up takes longer than half of the time left still leaves `{}`; a server that
  ignores EOF makes a trial last longer, by about half of the time left when the agent finishes
  early (three quarters if it also ignores SIGTERM), but only in trials where the idle rule
  above does not hold (for example it never answered a request, still had one open, still had
  bytes queued, or a harness fault was latched, which any server notification causes), since an
  idle server is killed at once; with decisions configured that wait is all extra time, while
  without decisions the parent already waited about as long before signalling the boundary; the
  wait is conservative, since bytes still queued for the server when the stop begins are
  discarded, not delivered; in those same trials, an agent that exits within a small fraction
  of a second of the deadline while its server ignores EOF can now end in timeout instead of
  completed, since the stop's last quarter must still fit the boundary's own exit; and a tool
  call whose request was fully written to the server when the agent left may complete during
  the wait, so its effect can reach the final state while its reply is discarded unrecorded.
- **Docs:** a third pre-registered run of the order-desk study
  (`docs/results/order-desk-study.md`, section "Run 3"): the 4B model in both arms, with and
  without a message at the injected empty lookup, on 8 cells chosen after run 2. Verdict:
  a statistical `BLOCK` at round 2 with swapped arm roles, which means the set-up without
  the message passes less often by more than 10 points on those cells. It says nothing
  about the 12B model. Its sealed store is under `docs/results/order-desk-study/run-3/`,
  and the store test re-derives its decision. A post about run 3 is at
  `docs/blog/2026-11-order-desk-run-3.md`, and a test
  (`tests/unit/docs/test_order_desk_stores.py`) holds its counts to the stores. No code
  change.
- **Docs:** every README figure and badge now uses one theme, the banner's: a neutral ground,
  blue for the reference or the good outcome (A, PASS, REPRODUCED), orange for the thing in
  question or the bad outcome (B, BLOCK, injected faults), a neutral bar for INCONCLUSIVE,
  system sans-serif and monospace type, no serif. The hero's evidence card gains one dot per
  trial (192 of 200 filled for A, 132 of 200 for B). The decision-boundary and calibration
  pictures, PNGs before, are redrawn as light and dark SVGs by the same generator
  (`docs/assets/decision-*.svg`, `docs/assets/gate-*.svg`); the gate bars are drawn to scale
  from the README table rows, and the generator's source check now also holds the table rows,
  the gate settings (alpha 0.05, delta 0.10), the two environment variables, the two decision
  faults and the four command names. The
  decision picture drops the old footer that said Jev was not run (it was run on
  2026-10-03, as the paragraph under it says). The PNGs stay in `docs/images/` because the
  2.4.0 README on PyPI links them. Tests hold the palette, the two font stacks, the same text
  in light and dark, the colour of every verdict word, the tint opacities, the hero's dot
  counts and grids, and the gate's bar widths on one shared scale. No code change.
- **Docs:** the Codex reader is checked against Codex CLI 0.169.0 (one short session;
  record types and the fields the reader uses are the same as in 0.167.0).
  `docs/LOG_FORMATS.md` names it and says that any `thread_source` other than
  `subagent` counts as main thread. No code change.
- **Fixed:** the tool server for Python toolsets (`arci.mcp_toolset_server`) wrote
  `state.json` in place, which empties the file before the new content goes in. When the
  trial ended, the 2.4.0 boundary closed the server's input and, if it was still running,
  stopped it with SIGKILL (`src/arci/mcp_boundary.py`, `_cleanup`), so a stop at that moment
  left an empty file and the trial ended `ERROR` (`grader_error`, "snapshot failed"). An idle
  server is still stopped this way (see the first entry), which is why the whole-file write
  is still needed. This was
  seen once in hosted CI, in 1 trial of 100, with an agent that finishes without using
  the tool server: one candidate trial ended `ERROR` instead of `FAIL`, which failed the
  hero acceptance test (no trial may be `ERROR`), and the gate then returned `ERROR` for
  the experiment. The server now writes `state.json.tmp` in the same folder and moves it
  into place, so the grader reads no file or a complete file; the bytes are the same as
  before. New unit tests read `state.json` at every Python call and return during a
  write: with the old code the reader finds an empty file, with the new code it finds no
  file, the old state or the new state. One behaviour changes: when a snapshot cannot be
  written (for example text that cannot be encoded), `state.json` now keeps the last
  complete state instead of being left empty; the tool call still returns -32603
  "snapshot failed". This change alone does not settle the case of an agent that never
  uses the tool server, whose graded final state was `{}` or the starting state by timing;
  the first entry of this section does, within the limits listed there.
- **Changed:** the Claude Code plugin's skill is now an instruction to Claude: run
  `uvx --python 3.14 realornoise==2.4.1` once, with nothing added, and show the output
  unchanged. If anything is typed after the command name, it tells Claude to run nothing.
  Before, the skill ran that line itself when the command was typed and
  approved it ahead of time (`allowed-tools`). Now nothing is approved ahead of time:
  whether Claude Code asks before the command runs depends on your permission mode and
  settings. In Claude Code, Claude still does not start it on its own. The command
  now exits 1 or 2 in Claude's shell tool for REAL DROP or CANNOT TELL, and the skill says
  that this is the result. A copy of plugin version 2.4.0 installed before the skill
  became an instruction keeps the earlier skill until the plugin is updated; plugin
  version 2.4.1 holds the instruction. The reason: the report of Anthropic's plugin
  directory on the first submission refused a skill with its own shell line, or with
  `allowed-tools` beyond Read, Grep, Glob and LS, from an organization that is not
  verified. The package is unchanged.
- **Fixed:** two runs with `--keep` that started together when no kept table existed yet
  could leave one run's rows out of the table. That run still succeeded and printed that
  the table could not be read, and its JSON record, when `--json` was given, has
  `kept_table: "unreadable"`. The rows were not lost for good while the logs were still
  there: the next run with `--keep` writes them. The cause: a run reads the table once
  before it holds the directory lock, with two file-system calls, and when another run
  put the table in place between the two, the reader took it for a path that exists and
  cannot be read; a run that finds an unreadable table does not write one. The reader now
  reads the path again when it was absent at one call and present at the next, four
  attempts at most and with no waiting. A dangling symlink, a path that is not a regular
  file, a file over the size limit and invalid content are unreadable as before; a
  missing path and an empty file are absent as before. Seen once, in CI, in the test that
  starts six writers together.
- **Docs:** the Claude Code plugin folder has its own README
  (`plugins/realornoise/README.md`): what the plugin reads, runs, fetches, writes, prints
  and sends, three uses, what the result means and what it cannot show. A plugin directory
  reads the README inside the plugin folder. Both skills now give the `--keep` command
  with the pinned version, so that every launcher command they show is pinned; tests hold
  both. The plugin also has a listing icon (`icon.png`, named in its manifest, drawn by
  `docs/assets/src/make_plugin_icon.py` with the standard library; a test compares its
  pixels with the generator). No behaviour changes.
- **Docs:** a privacy page for realornoise, the plugin and the skill (`docs/PRIVACY.md`):
  what the tool reads, prints, writes and sends, what a download involves and what the
  maintainer can see. The plugin manifest names it, the guide and the issue tracker
  (`privacyPolicyUrl`, `documentationUrl`, `supportUrl`), and sets a display name and
  keywords, because a plugin directory shows these; a test holds the links to files that
  exist.
- **Docs:** the Codex skill now also tells Codex not to add `--keep`, and its README
  (`integrations/codex/`) and the log threat model (`docs/THREAT_MODEL_LOGS.md`) say that
  each skill is an instruction to the assistant: run the pinned command once, with nothing
  added. The logs recipe (`docs/recipes/logs.md`) says that the plugin's skill tells Claude
  to run the pinned command and to show its output, and that neither skill asks for
  `--keep`. No code change.
- **Changed:** the pinned GitHub Actions in the workflows and in `action.yml` are updated:
  `actions/checkout` v7.0.0 to v7.0.1, `actions/setup-node` v7.0.0 to v7.1.0,
  `actions/setup-python` v7.0.0 to v7.1.0, `actions/upload-artifact` v7.0.1 to v7.0.2
  (also in `action.yml`) and `pypa/gh-action-pypi-publish` v1.14.2 to v1.14.3, each still
  pinned by commit SHA. The publish action's new pin first runs at this release's tag. No
  code change.
- **Docs:** the README's study paragraph now points to run 3. `docs/COMPATIBILITY.md` has a
  section on command trials in 2.4.1 and `docs/ROADMAP.md` lists what is done in 2.4.1.
  `docs/RELEASING.md` names the files record 0018 re-freezes and says that the maintainer
  publishes the GitHub release page by hand.
- **Known limits, not fixed in 2.4.1:**
  - `arci logs --keep`: when the read before the directory lock finds no table or a
    readable one, and the read under the lock then finds the table unreadable, the run
    writes no table and says nothing about it. It still writes the other requested outputs
    and exits with the code of its result (0, 1 or 2); the printed text has no line saying
    that the kept table could not be read, and the JSON record, when `--json` is given, has
    `kept_table` as the first read found it (`"absent"` or `"read"`). Record 0017 says that a
    run that finds the table unreadable says so; this path does not
    (`src/arci/logs/cli.py`, `_write_outputs` and `_execute`). The rows are not lost while
    the logs still exist; if the vendor has deleted those days by the next run with
    `--keep`, they cannot be recovered.
  - For a command agent with an MCP tool server, the graded final state can still depend
    on timing in the cases listed in the first entry of this section. The stop's stages are
    not recorded, so keep the version of arci beside a stored result.
  - The fixture server `tests/acceptance/mcp_fixture_server.py` still writes its state file
    in place. It is a pinned test file, not shipped code.

## v2.4.0 (2026-11-16)

- **Added:** `arci-logs/2` records, a best-case earliest test date when usable days are
  too few, and bounded client-version names after the split. `--keep` saves daily counts,
  dates and accepted settings to `realornoise-days/1`; `--keep-dir` chooses its directory
  and `--ignore-kept` skips reading it. Kept days are counted and marked in HTML.
- **Changed:** the default model and effort now come from the most responses after the
  split, falling back to the whole window only when no candidate has an after-response.
  In 2.4.0 the readers return client-version names and also return main-thread and
  sub-agent responses that lack a model or an effort. Those responses count only toward
  context counts and the version list, never toward responses or day values. The readers
  take model and effort names from the kept table so labels stay stable across runs.
  Context counts can therefore differ from those 2.3.0 printed for the same logs.
  2.4.0 follows the definition in the records.
  Both skills run `uvx --python 3.14 realornoise==2.4.0` without keeping days. Version 1
  log records remain readable. The printed limits state the largest wrong REAL DROP rate
  of the rule as built over all histories in the correlation, weekly-cycle and regime
  cells of the [self-check](docs/results/logs-selfcheck.md):
  wrong REAL DROP 362/2000 = 0.181000 [0.164743, 0.198480] (18.1%, Wilson 95% interval),
  seed 18112185, regime-switching days with log SD 0.45, 14 days after and 16 before.
  Work in phases can break the bound; other patterns can give more.
- **Fixed:** the tool never removes a directory. A failed write restores files;
  the table directory and any parents it created stay, empty, with mode 0700.
  Existing directories keep their mode. Overlapping table writes merge under an
  exclusive directory lock, held through moves and cleanup. Failure to open the
  directory is a write error; an unavailable lock module or failed lock call
  allows the write to proceed without a lock. The tool assumes no other program
  removes or replaces the directory during a run. Output names beginning with
  `.realornoise-`, after NFKC normalization and case folding, including symbolic
  links that resolve to such names, are refused before any read or write.
  Successful table writes remove regular files with that prefix while holding the
  lock. Report temporary files use `.realornoise.out-`, so table cleanup leaves
  another run's pending reports alone. A keyboard interrupt during writing ends
  with the write error and exit 3. An interrupt during the same-file check removes
  this run's new empty targets and preserves another writer's file. An interrupted
  move restores old bytes and modes and removes new targets; after the last move
  the files are already written. A second interrupt during restore can leave some
  files replaced, and an interrupt can leave a report temporary file. A process
  killed outright restores nothing and can leave replaced files, empty new targets
  and temporary files. Report leftovers may be deleted by hand.
- **Fixed:** equal numeric client-version tuples now use ascending text order in both
  the displayed list and record validation. With four equivalent spellings, the wrong
  three had been shown. A kept-table path below a regular file is now absent rather
  than unreadable: `--keep` reports a write error instead of success without a write,
  and a read-only run no longer reports an unreadable table that never existed.
  Both defects were found by the blind acceptance tests. Same-file placeholders are removed
  before staging, so interruption during staging or replacement leaves no new empty target.
  A zero-byte table is absent and can be replaced.
  Overlapping writes merge under a directory lock where available; a successful write removes
  leftover regular `.realornoise-` files. An empty `--keep-dir` is a usage error.
  Margin self-checks also gate the moved measure's own finding. Gates remain active under
  Python optimisation. Quick gates use exact binomial smoke limits and support no claim.
  Privacy tests restrict bounded names and versions to their specified JSON fields.
  Documentation corrects release metadata, reader changes and installation network use.
- **Not in this release:** an unknown split date, repeated daily looks with a stated
  error rate, a replacement streak check, two-model comparisons, a range for the change,
  other coding agents, OpenTelemetry input, a public tracker, real-machine Windows
  checks, older log formats, usage-limit or cost measures, or sending data anywhere.
- **Docs:** record 0017, the logs/2 statistics and self-check, the live example transcript,
  kept-table format and retention limits, the realornoise threat model, skill pins,
  release checks, compatibility and roadmap. The documented command requests Python
  3.14 for compressed Codex logs. Related tools are described without comparison claims.
- **CI:** CodeQL (Python and Actions) and zizmor now scan every push to `main` and
  `sprint/**` and every pull request to `main`, Dependabot opens one monthly grouped pull request for
  GitHub Actions versions, uv is installed from a hash-pinned requirements file in every
  workflow that can check out the repository first, and a new "oracle / SciPy" CI job checks
  the exact rank test against SciPy's own permutation and Mann-Whitney tests.
- **Docs:** added `CONTRIBUTING.md`, `CODE_OF_CONDUCT.md`, issue and pull request templates,
  and a test that these files exist and stay consistent with each other.
- **Docs:** the README now starts with a generated banner (`docs/assets/banner-{light,dark}.svg`,
  from `make_figures.py`) whose dots are the packaged example's day values, checked by a test.
- **Tests:** `test_slow_healthy_predecessor_has_no_gate_deadline` now uses a wait limit of
  0.3 s and tool calls of 0.8 s (before: 0.03 s and 0.08 s). On a loaded CI machine the
  gap between one tool call ending and the next starting could pass 0.03 s and fail the
  test with "tool order wait timeout". The released code uses 30 s and was not affected.
- **Tests:** added `tests/unit/logs/test_format_incidents.py`, guarding the three 2026
  `ccusage` breakages (a `null` model inside `usage.iterations[]`, a session kept twice
  once compressed, and a record cut off in the middle of its JSON) against both readers
  and against an end-to-end `arci logs` run, plus `tests/unit/packaging/test_client_versions.py`.
- **CI:** a new daily `client-versions` workflow asks npm for the latest Claude Code and
  Codex CLI versions and compares them with the versions `docs/LOG_FORMATS.md` says the
  readers were checked against; when either is newer it keeps one open issue up to date
  asking for the format tests to be run against a session of the new client.

## v2.3.0 (2026-11-15)

- **Added:** `arci logs` reads local Claude Code and Codex session logs and compares daily
  recorded measures for one model and effort setting per tool. Results are REAL DROP,
  NO DROP, CANNOT TELL or ERROR, separate from controlled-trial verdicts. The second
  distribution, `realornoise`, pins the main package's version and supports Python 3.11
  onward; compressed Codex logs need Python 3.14. New sealed record kind `arci-logs/1`,
  Markdown, JSON and self-contained HTML reports, a packaged generated example, a Claude
  Code plugin and a Codex skill. The plugin and skill put printed numbers into the
  assistant's conversation.
- **Added:** the [session-log self-check](docs/results/logs-selfcheck.md), with exact
  enumeration and simulated rates, counts, seeds and intervals. At AR(1) correlation 0.5,
  log SD 0.45 and 2000 histories per design, wrong REAL DROP with the rule as built was
  0.080500 [0.069365, 0.093243] at 5/10 after/before days,
  0.035500 [0.028240, 0.044541] at 7/21, and
  0.002500 [0.001068, 0.005839] at 14/42 (Wilson 95% intervals).
  Short correlated histories can exceed the nominal bound; passing the streak check
  does not establish the assumptions. The self-check publishes wrong NO DROP, all
  three check variants and the cost on independent days too.
- **Changed:** the README starts with logs, then imported outcomes, then controlled
  trials. The timing workflow uses a manual trigger with package and command inputs;
  CI and release workflows build both distributions, and release publishes the main
  package before `realornoise`.
- **Not in this release:** a scan over split dates; comparison of two models; a day table
  stored beyond log retention; a range for the change; other coding agents; Windows
  paths checked on a real machine; formats older than the listed clients; usage-limit
  or cost measures; sending data anywhere.
- **Docs:** finished log statistics and design record 0016, reader-format reference and
  log recipe; controlled-trial caveats and quickstart moved together; related local-log
  tools named without comparison claims; compatibility, roadmap and citation metadata
  updated. The order-desk working-record link uses commit `d46367d`. Documentation tests
  check first-screen length, links, numerical sources and the published fixed-text record.


## v2.2.0 (2026-11-15)

- **Added:** `arci verdict`, `arci verdict-rule` and `arci verdict --example`: a baseline-
  against-candidate verdict from pass/fail outcomes another tool already produced (Inspect AI
  JSON logs, JUnit XML, or CSV/JSONL), using ARCI's existing decision rule. `--previous
  DECISION.json` continues an earlier import under the same rule. The rule's required
  `fixed_before_runs` declares whether it was fixed before either arm ran; `verdict-rule`
  always writes `false`, which labels the output a descriptive verdict and withholds the error
  bound. A second console script, `agent-reliability-ci`, shares the entry point. New
  `bench/export_outcomes.py` (the store exporter) and the packaged
  `examples/outcomes/order-desk/` example files. Design record 0015.
- **Changed:** the suite decision loop was extracted into `walk_rounds`, shared by suites and
  imported outcomes, with no behaviour change to either path.
- **Not in this release:** reading an Inspect `.eval` file directly, promptfoo, the GitHub
  Action's verdict mode, and HTML output for imported outcomes.
- **Docs:** `NOTICE` now also names the four files of `examples/guardrail_agent` that
  were taken from frontier-scout and the two datasets whose label names the calibration
  results use, and carries the MIT permission notice for the portions received under that
  licence. The example's README no longer says a section was removed from `policy.json`
  (the file is unchanged). `docs/ROADMAP.md` records v2.0.0 and v2.1.0 and no longer
  presents the earlier candidate list as the plan. The README's Roadmap, Development,
  Availability and GitHub Actions passages describe 2.1.0 instead of 1.0.0, and its limits
  list no longer says an unfired fault goes unreported. `CITATION.cff` gives version 2.1.0.
  No code change.
- **Docs:** the sealed stores of both runs of the order-desk study are committed under
  `docs/results/order-desk-study/`, with a test that re-derives both decisions from the
  trials. New `docs/PROVENANCE.md`. `docs/COMPATIBILITY.md` gains a section on what 2.x
  added and what is kept stable. The README's "Related tools" names seven more projects.
  No code change.

## v2.1.0 (2026-11-13)

- **Added:** tool outcomes in suite reports (Markdown, HTML and the JSON key
  `tool_outcomes`): per arm, how many trials had a recorded tool failure without an
  injection marker and how many of those passed; per tool, trials with and without a
  recorded start. Descriptive only; the record does not show why a call failed.
- **Fixed:** the LangChain quickstart, run with two different model ids, also removed the
  candidate's retry, so a model comparison mixed two changes. Different ids now keep the
  same retry, prompt and temperature in both arms and label the arms with the model ids at
  registration. Equal ids and the offline demo are unchanged. New recipe
  `docs/recipes/model-swap.md`.
- **Corrected:** the README said nothing can PASS before about 80 paired runs. That is the
  figure when every pair is a tie (79 at the defaults); pairs in the candidate's favour
  cross sooner. Verdicts are given only at the end of complete rounds.
- **Docs:** `docs/results/order-desk-study.md` records both pre-registered runs of the
  example on two local models and the correction to run 1's first write-up. New README
  first screen and a "Related tools" section. Design record 0014.
- **Tests:** one adapter test replaced `ast.literal_eval` for the whole process and failed
  on langchain-core 1.8.0, where set-up reaches that function through `inspect`. The adapter
  now holds its own reference and the test replaces only that. No behaviour change.
- **Unchanged:** every stored record, v1 (`arci/0.5`) report output (the HTML footer shows
  the new version), the statistics.

## v2.0.0 (2026-11-11)

- **Added:** suite experiments (`arci-suite/1`). An `arci.yaml` with `tasks:` registers a
  grid of tasks by fault conditions; baseline and candidate run it in balanced rounds and
  the gate returns `PASS`, `BLOCK`, `INCONCLUSIVE` or `ERROR` at round ends. The rule is
  two one-sided betting tests in exact arithmetic; each directional error is at most
  alpha/2 under the assumptions stated in `docs/STATISTICS_SUITE.md`. `arci run`, `gate`,
  `report`, `triage`, `diff` and `plan` accept suites. Design record 0011.
- **Added:** `arci.adapters.langchain` behind the optional extra
  `agent-reliability-ci[langchain]`: runs a `create_agent` agent behind the recorded tool
  boundary with fault injection, budgets and replay. `arci init --langchain`, the example
  `examples/langchain_quickstart/` and `docs/recipes/langchain.md`. Design record 0012.
- **Added:** fault accounting in reports: for each declared fault, how many trials it fired
  in, per arm, with a fault that never fired flagged. v1 Markdown reports gain this one
  section and v1 JSON reports one key; nothing else in v1 output changes.
- **Added:** `arci report --format html`: one self-contained file, no script and no
  external request. The Action can post or update one pull-request comment (off by
  default).
- **Added:** `bench/selfcheck_suite.py`, an exact calibration bench for the suite rule.
- **Unchanged:** every v1 (`arci/0.5`) record, command and exit code. The core still
  depends only on `pydantic` and `pyyaml`; LangChain is never imported unless the adapter
  is.
- **Not built for suites yet:** `minimize`, `bundle`, `replay`, `trace-check`, JUnit. Each
  refuses with one line and exit 3.

## v1.0.0 (2026-11-06)

- **Added:** `arci triage RUN_DIR [--trial CANDIDATE_ID] [--format text|json]`
  selects up to three representative candidate failure groups and identifies the
  containing event/tool at the first recorded difference from the paired baseline.
  `arci-triage/1` JSON keeps the complete re-derived gate separate from diagnostic
  samples. The command preserves gate exits; invalid diagnosis exits 3. It neither
  executes recorded code nor writes stores, and DRIFT never changes the gate.
  The offline recipe and installed-wheel checks cover the first-use path.

- **Added:** read-only `arci trace-check BASE_RUN BASE_TRIAL CAND_RUN CAND_TRIAL`
  compares normalized tool/result events and terminal state across compatible native
  stores: `MATCH`/0, `DRIFT`/1, `INVALID`/3. Text and `arci-trace-check/1` JSON separate
  diagnostics from re-derived statistical verdicts. The offline recipe preserves
  both exits in CI; installed-wheel checks exercise all three statuses. No schema,
  statistical, replay or historical-evidence changes. First released in v1.0.0.
- **Added:** `arci run` prints `run store: <path>` on stderr after the verdict; stdout, reports and
  stores are unchanged.
- **Changed:** `arci init` reports the actual errno when a hard-link publication fails for a reason
  other than an existing file or unsupported links; the fail-closed behaviour is unchanged. The release workflow checks
  the sdist against an allowlist and the CI Action fixture checks the step summary.

## v0.8.0 (2026-10-13)

The onboarding release: install from PyPI, run the recorded retry story with one `uvx` command, scaffold
a first experiment from four references, and read the whole point on one screen. No change to the
decision rule, its calibration, the schema (`arci/0.5`) or any recorded result.

- **Added:** the PyPI package `agent-reliability-ci` and `.github/workflows/release.yml`: a version
  tag builds the wheel and sdist once, smoke-tests that wheel on Ubuntu and macOS (Python 3.11 and
  3.14) from an empty directory, and publishes the same files through PyPI trusted publishing with
  attestations. The guard refuses a tag that is not `v` + the package version. `docs/RELEASING.md`
  has the steps; `docs/design/0005-v0.8.0-packaging-and-version-bump.md` records the frozen-file
  changes (version, project URLs, classifiers, keywords, an sdist restricted by `only-include` to
  the package, README, LICENSE, NOTICE, CHANGELOG and pyproject, plus hatchling's own `PKG-INFO`
  and `.gitignore`).
- **Added:** `arci demo` (and `python -m arci`): the six-step retry story from an installed wheel with
  no checkout, through the real `run`, `diff`, `minimize` and `replay`. The seeded world and agents
  now live in `arci.demo` (`examples/retry_agent/{world,agents}.py` re-export them); the demo's
  manifests use `arci.demo` references and an `arci-demo-` experiment id, so their seals differ from
  the recorded run while the seeds, counts (192/200 vs 132/200) and verdicts are the same, and the
  demo says whether its counts matched. Run stores go to a temporary directory unless `--keep DIR`.
- **Added:** the `arci.yaml` descriptor (`src/arci/descriptor.py`, `docs/DESCRIPTOR.md`,
  `docs/design/0007-descriptor.md`): a thin, `extra="forbid"` front-end whose keys are the `Manifest`'s
  fields with the same defaults, compiled and sealed with `Manifest.create` exactly as the Python
  builders do. `arci run` accepts a `.yaml`/`.yml` descriptor or a sealed `.json` manifest, and its
  `--out` now defaults to `runs`. `arci schema` prints the JSON Schema generated from the model;
  the bytes are committed at `docs/schema/arci.schema.json` and tested for staleness. Pydantic is
  authoritative; the YAML loader resolves only `true`/`false` as booleans and decimal, `0x`, `0o`,
  `0b` as integers, so `yes` and `on` stay strings and `010` is ten, not octal eight; explicit
  `!!int`, `!!float` and `!!null` tags accept only those same forms, and alias expansion is capped.
- **Added:** `arci init EXPERIMENT_ID --baseline --candidate --toolset --oracle [...]`
  (`docs/design/0008-arci-init.md`): validates the four references in a child process with the
  runner's import rule (the toolset factory is called once; agents and the oracle are only imported),
  checks every `--fault` tool against the toolset's tools, and writes a smoke-design descriptor
  (`n_per_arm` 8, the smallest N at which a total collapse can still BLOCK under the default rule;
  two perfect arms cannot PASS below N=42). One line on stderr and exit 3 on the first problem. The
  file is published atomically (a hard link, or a rename with `--force`); without `--force` an
  existing file is never replaced.
- **Added:** a smoke-design notice on stderr from `arci run` when a gating condition has fewer than
  100 trials per arm, pointing at `arci plan`. stdout, reports, decisions and stores are unchanged.
- **Changed:** the runner appends the current directory to the import path of every child it starts
  (worker, grader, boundary, command agent, MCP server;
  `docs/design/0006-cwd-on-the-child-import-path.md`), so references into the project directory
  resolve under the `arci` console script as they already did under `python -m arci.cli`. Appended,
  never prepended; an MCP server whose `env` sets `PYTHONPATH` keeps that configured value, as
  before; records are unaffected.
- **Added:** CI jobs that build the wheel and run `arci demo` from an empty directory on Ubuntu and
  macOS, a Windows job that only installs the wheel and runs `arci --help` (execution stays
  unsupported on Windows), and an Action fixture (`examples/action_fixture/`) that runs the composite
  Action on the demo's A-vs-B manifest and asserts `BLOCK`. CI also runs on `sprint/**` branches.
- **Added:** `docs/measurement/`: the time-to-first-verdict and cold-read protocol, a receipt
  template and a receipts directory; maintainer measurements are labelled and never counted as
  cold readers.
- **Documentation:** the README opens with the question, one sentence, the two commands, the pipeline
  line, what PASS means, what a small run means and the boundary (`docs/design/0009-readme-first-screen.md`);
  the recorded result, the figure and the badges moved below the fold; "What it does not do" gains two
  items (reference validation imports your code; a fault naming a tool the agent never calls silently
  never fires). Links from the old first screen are absolute so the PyPI page renders them.
- **Documentation:** two recipes, each a runnable tree under `examples/recipes/` with a narrative in
  `docs/recipes/` and a test that runs it at smoke N from a copied directory without `PYTHONPATH`:
  `python_agent` (a blank project with `app/v1.py`, `app/v2.py` and `tests/world.py`; `arci init`,
  the smoke run, `arci plan`, the confirmatory run, then `diff`, `minimize` and `replay`, with the
  recorded output) and `mcp_agent` (a stdlib newline-JSON-RPC client against
  `arci.mcp_toolset_server`, a hand-written command-arm descriptor and an Inspector preflight). The
  Inspector step is recorded as blocked on 2026-10-13: Inspector 2.10.1 (TypeScript SDK 1.29.0)
  rejects the bridge's protocol revision `2026-07-28` at `initialize`; the recipe keeps the verbatim
  result and the ARCI steps run without it.
- Everything that was already on `main` and unreleased is in this version:
  - **Documentation:** the README presents the recorded retry result once (200 trials per arm,
  192/200 vs 132/200, BLOCK) with its boundary, links to the evidence, and the offline demo with
  lines from the committed demo log (in this release these sections sit below the new first
  screen); a "Where it has been run" summary links every campaign's records, including the
  guardrail run and the invalid and inconclusive attempts. The hero PNG is replaced by
  generated light and dark SVGs (`docs/assets/hero-*.svg`) and the how-it-works exposition by a
  generated pipeline figure (`docs/assets/where-*.svg`), both written by
  `docs/assets/src/make_figures.py` (stdlib only), whose `--check` mode runs in CI and in
  `tests/unit/docs/test_figures.py`.
  - **Added:** the technical report package `docs/reports/ci-gate-2026-10-06/` (report, plan of
  record, enumerated operating-characteristics metrics for both interval methods, the Linux
  container re-derivation log for all 18 archived decisions, the offline replay probe log for
  both committed failure bundles, and the two-stage Docker reproduction recipe) and
  `CITATION.cff`.
  - **Fixed:** platform-dependent rounding in 95% Wilson intervals by pinning the inverse-normal
  value used by the existing Linux-produced records (CPython's C accelerator on arm64 macOS
  differs by one ulp from the pure-Python fallback). Restores reproducible decision seals for
  the archived Clopper-Pearson stores without changing any verdict. Regression tests re-derive
  every committed `docs/results/jev` decision byte for byte.
  - **Fixed:** platform-dependent Clopper-Pearson bounds by comparing binomial tails with exact
  integer arithmetic, including zero-success and all-success bounds. The existing 60-step
  bisection, statistical method, confidence allocation, and gate rules are unchanged. Re-derived
  six archived Jev decisions and five guardrail decisions from unchanged sealed manifests and
  trials. Only CP bounds, their derived difference bounds, and decision seals changed; verdicts,
  exit codes, counts, stopping histories, and rendered Markdown/JUnit reports are unchanged.
  Byte-for-byte regeneration is checked on macOS and Ubuntu.
  - **Added:** `arci plan` enumerates PASS, BLOCK and INCONCLUSIVE probabilities under the
  existing Clopper-Pearson gate for independent binomial arms, one gating condition, one
  fixed-sample look and N <= 400 per arm, reporting assumptions and the smallest tested N meeting
  a target or "target not reached"; probabilities are enumerated with exact integer arithmetic
  and converted to floating point once, so the output is identical on every platform.
  - **Added:** opt-in Markdown `arci report --pass-k` estimates using C(successes,k)/C(n,k)
  separately per arm and condition, with explicit IID assumptions and unavailability for n < k,
  ERROR verdicts and multi-look designs; default report output, gate decisions and stored records
  are unchanged.
  - **Guardrail experiment:** published the pre-registered live run of
  `examples/guardrail_agent/` (2026-10-05, `run.sh` unchanged): the sealed stores of all six
  runs, the preflight receipt, per-run gate reports, and the N=200 failure diffed, minimised
  and replayed (REPRODUCED), in `docs/results/guardrail/`. The write-up and `metrics.json` are
  generated from the committed evidence by `docs/results/guardrail/summarize.py`
  (`--check` fails if they are stale), including the N=50 `decision_unavailable` run that came
  out INCONCLUSIVE rather than the pre-registered BLOCK. Added
  `tests/unit/examples/test_guardrail_results.py`, an offline test that re-derives every
  committed guardrail decision byte for byte with `arci gate`.
  - **Documentation:** the offline demo section was renamed "Try the offline demo" (this release's
  README now points it at `arci demo`); the availability note that separated `main` from the
  `v0.7.0` Action is replaced by this release's Availability line; unsupported comparison and
  reviewer-count wording removed; the calibration roadmap item now extends the published
  intent-routing audit. `CITATION.cff` pins the report URL to the `evidence-2026-10-06` tag (its
  version and date are now 0.8.0 and 2026-10-13). Added `SECURITY.md` (private reporting through
  GitHub security advisories, the trusted-code assumption, no private stores or credentials in
  reports).

## v0.7.0 (2026-10-05)

- **Calibration audit of the decision model (2026-10-03):** `bench/jev_calibration/` is a
  pre-registered audit of `jev-1.13.0` on CLINC150 (4,500 in-scope + 1,000 out-of-scope) and
  Banking77 (3,080), three passes each plus a bundling check, 26,140 requests, about USD 4.6
  at list price. `PROTOCOL.md` (hash posted on PR #2 before the first request) fixes the
  questions, passes, measures and seven expectations; `run.py` seals every answer in a
  hash-chained store; `metrics.py` (exact binomial intervals, ECE/MCE/Brier/log loss,
  tie-aware AUROC and average precision, bootstrap, agreement) is unit tested; `analyze.py`
  verifies the chains and writes `metrics.json`, `report.md`, reliability diagrams and a
  self-verifying compact store from which every number re-derives. All seven expectations
  met: zero-shot accuracy 0.921 [0.912, 0.928] on CLINC150 (a supervised TF-IDF+LR trained on
  15,000 examples: 0.925) with ECE 0.024; 0.801 on Banking77 with ECE 0.084 and mid-range
  over-confidence; 0.970 accuracy at confidence >= 0.9 on 83% coverage; out-of-scope AUROC
  0.977 (yes/no question) against 0.911 from 1 - p_max; 99.4% repeat agreement; p50 322 ms.
  Write-up: `docs/results/jev-calibration/README.md`.
- **Added:** `examples/jev_triage_agent/experiment.py` builds live manifests
  (`live_manifest`, `decisions.upstream = "http"`, pinned model, paced trial starts, prior
  runs) and writes them from the command line
  (`python -m examples.jev_triage_agent.experiment --out manifest.json`), so the day-one
  sequence in `docs/design/0004-day-one.md` runs from files. `examples/jev_triage_agent/day_one.sh`
  drives it end to end: preflight, the clean pair, the N=50 trio, the Node agent through the
  official SDK, the pre-registered N=200 run, and a minimised, replayed failure, with a gate
  report per run and a refusal to finish if the key appears in any output. Results:
  `docs/results/jev/`.
- **Run against Jev (2026-10-03):** the pre-registered day one ran end to end against
  `https://api.typesafe.ai` with `jev-1.13.0` pinned. A vs B under `decision_low_confidence` at
  N=200: 200/200 vs 0/200, bounds [-1.000, -0.957], BLOCK; A vs A and A vs C PASS at N=50; the
  Node agent through the unchanged official SDK BLOCK; the minimised failure replays REPRODUCED;
  an exploratory clean run at N=50 routed all 100 decisions correctly at confidence 1.0. 902
  recorded decisions, about USD 0.018 at list price. Sealed stores, the preflight receipt, the
  invalid first attempt and one write-up per run: `docs/results/jev/`; every `decision.json`
  re-derives from its committed `trials.jsonl`. Findings: `docs/DECISIONS.md`, "What day one
  found".
- **Added:** `arci preflight --allow-unlisted-model`. The account's `GET /v1/models` lists only
  the aliases `jev-latest` and `jev-preview`, so the pre-registered preflight exits 2 on a pinned
  versioned id. With the flag, preflight prints the listed names, sends the smoke request, and
  exits 0 only if the validated response reports exactly the pinned id (3 otherwise). Without the
  flag nothing changes except a hint after the exit-2 message. Tests:
  `tests/unit/cli/test_preflight_unlisted_model.py`.
- **Added:** `ARCI_HTTPS_PROXY=http://host:port` makes the decision upstream sender tunnel through
  an HTTP CONNECT proxy, for environments whose only egress is such a proxy; unset, the direct
  connection is unchanged, and a malformed value is a transport error. Tests:
  `tests/unit/decisions/test_upstream_proxy.py`.
- **Fixed:** the three preflight smoke questions carry `instructions`; the vendor rejects a
  question with neither `instructions` nor `criteria` (400), so the pre-registered smoke request
  could not be accepted as written.
- **Fixed:** `examples/jev_triage_agent/day_one.sh` puts the repository root on `PYTHONPATH`
  (the manifests name `examples.jev_triage_agent.*` modules, invisible to the `arci` console
  script), insists on running from the repository root, and stops with exit 4 unless both arms of
  the N=1 clean pair PASS, so a harness fault that breaks both arms equally cannot be mistaken
  for a measurement.
- **Fixed:** two reader threads, the grader's response reader and the MCP boundary's frame
  reader, could end a read on a "not ready" poll verdict computed before the child wrote and
  before the parent asked them to stop. On a loaded machine the thread was descheduled across
  the child's exit, the stale verdict dropped the whole response, and the trial ended `ERROR`
  (`grader returned invalid output`, or `boundary exited before returning` for command agents)
  at about 1 trial in 400 with 8 workers on 4 cores, which is enough to turn a 200-per-arm
  experiment into an `ERROR` verdict on a busy CI runner. The worker reader already followed
  the correct rule; both readers now snapshot the stop flag before polling, and only a poll
  made after the stop was observed may end the read. Regression tests:
  `tests/unit/runner/test_reader_stop_race.py`.

## v0.6.0 (2026-09-22)

Day-one Jev readiness. The upstream behavior below is derived from vendor and official SDK
documentation and tested against shaped fixtures; it was not run against Jev because no key was
available.

- **A1:** HTTP decision upstreams accept a path-prefixed base URL, including the Vercel AI Gateway
  TypeSafe route and its `typesafe-ai/jev` model id.
- **A2:** Response validation accepts the tested SDK response shapes: unknown metadata is tolerated and rounded
  probability sums are accepted within `1e-3`, while required keys and pinned-model checks remain.
- **A3:** Harness-owned request headers, allowlisted response headers, deterministic transport
  diagnostics, and one recorded bounded wait on an upstream 429/529 make gateway attempts auditable.
- **B4:** `arci preflight MANIFEST` checks credentials, model discovery and one tiny smoke decision,
  then emits a credential-free receipt with exit 0/2/3 semantics.
- **B5:** HTTP experiments pace trial starts through a shared parent token bucket; users divide the
  provider rate by the maximum decisions per trial.
- **B6:** Markdown reports count completed decision recordings and their available token usage,
  and show estimated input cost at the list price read on 2026-09-22 (fixtures and replays are
  free; this is an estimate, not billed spend). Incomplete admissions are excluded; before-injected
  results contribute zero tokens.
- **B7:** The Jev guide now covers the three-command day-one workflow, provider limits, privacy,
  sampled answers and live-run minimality; `docs/results/TEMPLATE-jev.md` standardises write-ups.
- **C8:** The triage example gains a Node 20+ ES-module agent using `@typesafe-ai/sdk` 0.6.0 through
  environment-only `new TypeSafeClient()`, plus CI coverage on Python 3.14 / Node 22.
- **C9:** Decision records retain an independent raw upstream snapshot before perturbation; live
  HTTP upstreams, removal trials ending in ERROR, and replay INVALID results report `reduced`, never
  `1-minimal`.
- **D10:** The offline triage fixture can inject seeded synthetic miscalibration for testing
  confidence gates; it is explicitly not evidence about Jev's calibration.

## v0.5.0 (2026-09-22)

Command agents can now test the decision logic around TypeSafe's Jev/System One API.

- `Manifest.decisions: DecisionSpec` adds a harness-owned loopback `POST /v1/systemone` boundary.
  Agents are redirected through `TYPESAFE_BASE_URL` and a per-trial token; the real upstream key
  stays in the harness (the MCP server child does not inherit it, diagnostics are scrubbed). The
  Python `typesafe-sdk` is exercised unchanged by the acceptance tests; the JavaScript SDK reads the
  same variables but is untested here.
- Admitted decisions use the existing `ToolCall`, `ToolResult` and `RecordedCall` records under
  `decision:systemone`, so budgets, events, diff, minimisation, bundles and exact replay apply.
- `decision_low_confidence` mixes choice probabilities toward uniform without changing the winner;
  `decision_unavailable` returns an injected 529 from a selected occurrence onward.
- The boundary now lives until the command agent exits when decisions are configured, including
  decisions made after the MCP session closes. Decision/MCP overlap and concurrent decisions are
  rejected as harness faults.
- Schema `arci/0.5` adds decision configuration to sealed manifests and trial specs. Records sealed
  by earlier schema versions are not readable; as with every field addition, experiments must be
  re-run.
- The official `typesafe-sdk` is a development-only dependency used by an acceptance test against
  the boundary. Runtime code and `examples/jev_triage_agent` do not import it.
- `examples/jev_triage_agent` is a six-step offline triage demo: a confidence-gating regression is
  blocked, reduced, replayed, and repaired. `docs/DECISIONS.md` documents fixture and real-Jev use.

## v0.4.0 (2026-09-22)

One thing: pre-registered looks, so an experiment can stop early without losing error control.

- `Manifest.looks = (N_1, ..., N_L)`: cumulative pairs per condition, last equal to `n_per_arm`.
  Equal Bonferroni spending, `alpha / L` per look, with either interval method. The run stops at
  the first look that is PASS or BLOCK; the final look is INCONCLUSIVE otherwise. No `looks` is
  the fixed design, unchanged.
- The gate replays every look and treats the first decisive one as a mandatory stop: a store that
  continued past it, stopped without a decision, or is not a whole-pair prefix at a declared look
  is ERROR. The plan is bound into every trial's identity; the look history is sealed into the
  decision.
- `bench/selfcheck.py --looks 50,100,200`: exact enumeration over sequential paths (a
  (x_A, x_B) state table, at most (N+1)^2 states), with the same false-PASS / false-BLOCK <= alpha
  sweep. Measured, K=1: a 0.95 -> 0.65 regression costs 302 expected trials with Clopper-Pearson
  (P(BLOCK) .985 -> .943) and 159 with Newcombe, against 400 for the fixed design; two equal 0.95
  agents cost 350 and 239. The Markdown report shows the look history and the stopping look.

## v0.3.0 (2026-09-22)

One thing: a tighter interval for the margin, opt-in.

- `Manifest.interval_method`: `clopper_pearson` (default, unchanged) or `newcombe` (Newcombe's
  hybrid score interval, method 10, no continuity correction, Wilson per arm at `1 - alpha/K`).
  Frozen with the manifest; printed in every decision and report.
- Calibration by exact enumeration in `bench/selfcheck.py --method newcombe`: a sweep of the
  boundary and the no-change line for p in [0.5, 0.99], N in {20, 50, 100, 200, 400}. Worst
  directional error 0.031 (alpha 0.05). The bench exits non-zero if any sweep fails. Head-to-head
  table in `docs/STATISTICS.md`.
- Why: the clean v0.2 confirmatory run (376/400 vs 308/400) was INCONCLUSIVE by 0.008 under the
  default rule; Clopper-Pearson with Bonferroni was spending about a tenth of its allowed alpha.
  Re-analysed under `newcombe` it blocks. Its sealed verdict stays INCONCLUSIVE.

## v0.2.0 (2026-09-21)

Command agents: test any program that speaks MCP over stdio, not only Python functions.

### Added

- **The out-of-process boundary.** A trial can be any subprocess (`CommandSpec`). Its tools are ONE
  stdio MCP server owned by the harness (`McpServerSpec`). The agent's process tree holds only a
  byte-relay shim (`arci.mcp_shim`); the recorder, fault injection, budgets and fault latches live in
  a harness-owned boundary process (`arci.mcp_boundary`). Same frame protocol, latch precedence,
  deadlines, process-group cleanup and sealed envelopes as v0.1.
- Supported MCP subset (revision 2026-07-28): `initialize`, `notifications/initialized`, `ping`,
  `tools/list`, serial `tools/call` with `resultType: "complete"`. Task results, sampling,
  elicitation and concurrent calls are a harness ERROR, never a silent pass-through.
- Replay for command agents: the recording includes `initialize` and `tools/list`, the server is
  never started, JSON-RPC ids are normalised, consumption must be exact.
- `arci.mcp_toolset_server`: serve any v0.1 python toolset as an MCP server, with a trusted
  `snapshot` for grading.
- `examples/ollama_mcp_agent`: a real tool-calling agent on a local model, with a one-sentence
  prompt regression between its arms. `docs/REAL_AGENTS.md`, `docs/design/0002-...md`.
- Schema `arci/0.2`: `ArmSpec.command`, `Manifest.mcp_server`, `McpServerSpec.snapshot`. An
  experiment is all python agents or all command agents. v0.1 run stores must be re-run.

- `CommandSpec.infra_exit_codes` (default 75, EX_TEMPFAIL): an agent can say "my infrastructure
  failed, not me". The trial is ERROR and invalidates the experiment instead of counting against the
  agent. Added after a local model server died mid-experiment and 435 trials "crashed".

### Evidence (docs/results)

A real local-LLM agent, two arms differing by one sentence of the system prompt, one injected tool
timeout. Four runs are reported, including two invalid ones that each exposed a defect (a bridge
that advertised no tool parameters; a dead model server plus a harness shutdown race). The clean
confirmatory run: 376/400 (94.0%) versus 308/400 (77.0%), bounds [-0.2445, -0.0921], verdict
INCONCLUSIVE by 0.008 under the pre-registered rule. Reported as is.

### Fixed during review

Eleven findings from an adversarial review of the boundary (false REPRODUCED at a deadline kill,
boundary crashes blamed on the agent, client mistakes invalidating experiments, malformed server
results accepted, id reuse, pipe deadlocks, recordings over 1 MiB, path leaks), a shim deadlock, and
a shutdown race that turned about 5% of trials into false ERRORs on a loaded machine.

### Trust model

For command agents the record can no longer be corrupted by accident from inside the agent's
process. This is isolation from accident, not a sandbox: the agent still holds the socket it was
given, and whatever it does outside MCP is invisible.

### Known limits

- One MCP server per trial, stdio only. No HTTP transport yet.
- Tool replay is not agent replay: a live model rarely repeats its calls, so replaying its bundle is
  usually INVALID. Deterministic replay is demonstrated only with scripted clients.
- The Claude Code recipe in `docs/REAL_AGENTS.md` is an untested sketch; no paid-agent trials were
  run for this release. The local-model results are exploratory (one machine, one small model).
- POSIX only (unix sockets, process groups).

## v0.1.0 (2026-09-21)

First release. One claim: a measured regression becomes an executable, reduced failure case.

### What is in it

- Frozen, sealed experiments (`Manifest`), a deterministic paired schedule, one fresh process per
  trial with a separate grader process, a single parent writer for `events.jsonl` and `trials.jsonl`.
- The tool boundary (`ToolBox`): budgets, seeded fault injection (`tool_timeout`, `tool_error_once`,
  `empty_result`, or your own `"module:function"`), record and replay.
- The gate: exact Clopper-Pearson at tail `alpha / (4K)`, Bonferroni bounds on the difference,
  verdicts PASS / BLOCK / INCONCLUSIVE / ERROR with exit codes 0 / 1 / 2 / 3. It never raises.
- `bench/selfcheck.py`: the gate's own operating characteristics by exact enumeration.
- Boundary-aligned trace divergence, ddmin fault minimisation with an honest 1-minimal claim,
  portable replay bundles with hash-verified embedded code.
- CLI (`arci run | gate | report | bundle | replay | diff | minimize`), Markdown and JUnit reports,
  a composite GitHub Action.
- `examples/retry_agent`: agents A, B (A minus one retry) and C (the repair), with a six-step demo.

### How it was checked

229 tests, basedpyright strict, CI on Python 3.11 and 3.14. The acceptance suite was written before
the implementation and is hash-pinned (`FROZEN.sha256`). An adversarial reviewer attacked the design and
the code in four rounds, with reproductions: about 45 findings. They were fixed, or, where out of
scope (a hostile in-process agent, detached descendants), documented as non-goals. The behavioural
fixes have frozen regression tests (`tests/acceptance/test_hardening*.py` and the gate, replay and
schema suites); documentation corrections and the protocol queue bound do not. Every published
calibration number was recomputed independently by the reviewer and matched.

### Known limits and residual risks

- Trust model: the agent is assumed buggy, not hostile. It shares a process with the tool boundary,
  so a deliberately hostile agent can forge its result. See `docs/TRUST_MODEL.md`.
- Only the tool boundary is observed. Direct file, network or subprocess use by the agent is
  invisible. Descendants that start their own session survive cleanup.
- The gate is conservative by design: mid-range success rates need large N to reach PASS, and
  N=20 decides almost nothing. `prior_runs` is author-supplied; no cross-run error budget is enforced.
- Supported statistics range: `alpha` in [1e-6, 0.5] with `alpha >= K x 1e-6`, `n_per_arm <= 10000`.
- Bundles embed only the files you include; the minimiser's output embeds none.
- The final reviewer re-check ran on Python 3.13 in a read-only sandbox, so writing bundle payloads
  to disk was exercised by the test suite and CI (3.11, 3.14) but not by that review.
- POSIX only (process groups, `ps` in tests). Windows is untested.
