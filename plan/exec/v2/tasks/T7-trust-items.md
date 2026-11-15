# T7: trust items for 2.4.0 (CI security checks, contributor files, an outside check of the rank test)

Read `AGENTS.md` in the worktree `/Users/ajay/Developer/.arci-worktrees/wt-v2-logs`
(branch `v2/logs2`). Work only there. Change no git state. No network, do not call `uv`.
Never open anything under `~/.claude` or `~/.codex`. Do not edit any file listed in
`FROZEN.sha256`. Plain words, short sentences, no sales wording, no em dashes.

Another agent will later change `src/arci/logs/`, `tests/unit/logs/` (existing files),
`docs/STATISTICS_LOGS.md`, `docs/recipes/logs.md`, `README.md`, the plugin and the skills.
**Do not touch those.** You own only the files named below.

## Facts you may rely on (looked up by the orchestrator on 16 Nov 2026)

- `github/codeql-action` v4.39.3 is commit `33d7b85da1a04171e211befe2c739303b9a4c066`.
- `zizmorcore/zizmor-action` v0.8.1 is commit `45d7276c9ca790aabd705e31ca99c6185c3e76dd`.
  Its quick start for a public repository: a job with `permissions: security-events: write`
  (plus `contents: read`, `actions: read`), a checkout with `persist-credentials: false`,
  then `uses: zizmorcore/zizmor-action@<sha>` with no inputs. Top-level `permissions: {}`.
- `uv` 0.12.5 wheels on PyPI (sha256):
  - `uv-0.12.5-py3-none-manylinux_2_17_x86_64.manylinux2014_x86_64.whl`
    `3e195ccf1ed60c8bb24a6447ce306441a4181d54b602407e09bc56e963911c15`
  - `uv-0.12.5-py3-none-macosx_11_0_arm64.whl`
    `d87156bc174d94fae890bb7a261e2867140abb9fe1e9de81a5295e582fb9d0f5`
  - `uv-0.12.5-py3-none-win_amd64.whl`
    `455c3e57602e2141e66e2f0bf685898c9c5e5a70377d14c9a71554a3baf3ddbf`
- For Python 3.12 on Linux x86_64:
  - `scipy==1.18.1` wheel `scipy-1.18.1-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl`
    sha256 `f55fa87b6c612ecd6b058f167c53231b1d14e412efe361d3d6e38b3631c73218`; it needs
    `numpy<2.8,>=2.0.0`.
  - `numpy==2.5.4` wheel `numpy-2.5.4-cp312-cp312-manylinux_2_27_x86_64.manylinux_2_28_x86_64.whl`
    sha256 `fbde6962867ee75b48b0ee29b2b9372ec5d617799dbaf38e82dc0596f2f7738a`.
- The existing workflows pin every action by commit with a version comment, set
  `permissions: contents: read` at the top, and install uv with
  `python -m pip install --disable-pip-version-check "uv==${UV_VERSION}"`.

## Deliverables

1. **`.github/dependabot.yml`**: `github-actions` only, monthly, one grouped pull request,
   commit-message prefix `ci`. (Python files are pinned by hash and change only at a
   re-freeze, so no Python ecosystem. Say that in a comment.)
2. **`.github/workflows/codeql.yml`**: CodeQL for the languages `python` and `actions`, on
   pushes to `main` and `sprint/**`, on pull requests, and weekly. Actions pinned to the
   commit above with the comment `# v4.39.3`. Top-level `permissions: contents: read`;
   the job adds `security-events: write`. Use the checkout pin the other workflows use,
   with `persist-credentials: false`. No build step is needed for Python.
3. **`.github/workflows/workflow-audit.yml`**: zizmor through the action above, on pushes
   to `main` and `sprint/**` and on pull requests.
4. **Hash-pinned uv.** New file `.github/requirements/uv.txt` with `uv==0.12.5` and the
   three hashes. In every workflow, replace the uv install line with
   `python -m pip install --disable-pip-version-check --require-hashes -r .github/requirements/uv.txt`.
   Check that each such step runs after a checkout in its job; if one does not, leave that
   step as it is and report it. Keep `UV_VERSION` where other steps use it.
5. **An outside check of the exact rank test.** New `tests/unit/logs/test_oracle_scipy.py`
   (a new file; it must not import or change any other test file). It skips as a whole
   when SciPy cannot be imported (`pytest.importorskip`). Read `src/arci/logs/rank_test.py`
   and the method in `docs/STATISTICS_LOGS.md` first. For at least 200 seeded small cases
   with ties (group sizes from 2 to 6 each, values drawn from a few integers so that ties
   are common) and 100 without ties, the tool's exact one-sided p-value must equal, as an
   exact fraction, the count that `scipy.stats.permutation_test` gives with the same
   midrank statistic, `permutation_type="independent"`, full enumeration and the matching
   `alternative`. Compare counts, not floats: SciPy's p-value times the number of
   arrangements must round to an integer within 1e-9 and equal the tool's numerator over
   the same denominator. Also compare the tie-free cases with
   `scipy.stats.mannwhitneyu(method="exact")`. State in the module docstring which SciPy
   functions are the oracle and that the test is skipped without SciPy. SciPy is not
   installed here: write the test with care; the orchestrator runs it.
   New `constraints/oracle.txt` with the two pins and hashes above. New CI job in
   `.github/workflows/ci.yml`, named `oracle / SciPy`, Python 3.12 on `ubuntu-latest`:
   sync the locked environment the way the `check` job does, then
   `uv pip install --python .venv/bin/python --require-hashes -r constraints/oracle.txt`,
   then `.venv/bin/pytest -p no:cacheprovider -o addopts='' tests/unit/logs/test_oracle_scipy.py -rs`
   and fail the job if the output shows the module was skipped.
6. **Contributor files** (all true to this repository; read `README.md`, `AGENTS.md`,
   `SECURITY.md`, `docs/RELEASING.md`, `docs/COMPATIBILITY.md` first):
   - `CONTRIBUTING.md`: one maintainer working with AI coding agents; no promised response
     time; how to run the checks locally; pinned files (`FROZEN.sha256`) change only with a
     design record; the privacy rule for reports (never attach session logs or log lines;
     attach only the tool's own output, which holds counts, rates, dates and the names of
     the model and effort); how to report a changed log format.
   - `CODE_OF_CONDUCT.md`: short and original (about ten lines): be civil, stay on the
     subject, no personal data of others, how to report a problem (the security advisory
     link in `SECURITY.md` for private matters), what the maintainer may do.
   - `.github/ISSUE_TEMPLATE/config.yml` (blank issues allowed; a contact link to the
     security advisory page for vulnerabilities),
     `.github/ISSUE_TEMPLATE/log-format-changed.yml` (tool, client version, `realornoise`
     version, the pasted output of the run, a required checkbox "I pasted no log line and
     no file path"), `.github/ISSUE_TEMPLATE/bug.yml` (command, version, Python version,
     what happened, what was expected; the same checkbox).
   - `.github/PULL_REQUEST_TEMPLATE.md`: what changed, how it was checked, pinned files
     touched (should be none), no session logs attached.
7. **A test of these files**: `tests/unit/packaging/test_trust_files.py`: the files exist;
   every YAML file parses with `yaml.safe_load`; every `uses:` in every workflow is pinned
   to 40 hex characters (a local `./` action is allowed); no workflow installs uv without
   `--require-hashes`; the version in `.github/requirements/uv.txt` equals every
   `UV_VERSION`; `dependabot.yml` lists `github-actions`; both issue forms carry the
   required checkbox.
8. `CHANGELOG.md`, under `## Unreleased`: one `- **CI:**` bullet and one `- **Docs:**` bullet.

## Done when

- `.venv/bin/pytest -o addopts='' -q tests/unit/packaging tests/unit/docs tests/unit/logs/test_oracle_scipy.py`
  passes (the oracle module is reported as skipped here).
- `.venv/bin/ruff format --check .`, `.venv/bin/ruff check .`, `.venv/bin/basedpyright` are clean.
- `shasum -a 256 -c FROZEN.sha256` passes.

Final message, concise: files added or changed, each command with its last line, every
workflow step you left unchanged and why, anything you could not check here (the
workflows cannot run locally), risks.
