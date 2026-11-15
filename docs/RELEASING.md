# Releasing

How matching versions of `agent-reliability-ci` and `realornoise` reach PyPI. PyPI versions
are immutable: a version number, once uploaded, can never be uploaded again, even after a
deletion.

## 0. One-time PyPI setup

Before the first `realornoise` release, the maintainer registers a **pending trusted
publisher** on PyPI for project `realornoise`:

- Owner: `ajaysurya1221`
- Repository: `agent-reliability-ci`
- Workflow: `release.yml`
- Environment: `pypi`

The existing `agent-reliability-ci` publisher uses the same owner, repository, workflow and
environment. Check that the GitHub `pypi` environment has the intended reviewer protection.
Both jobs use OIDC with attestations; no PyPI API token is needed. Creating the pending
publisher is a maintainer action, not something this repository's tests establish.

## 1. Bump the version (one commit)

`pyproject.toml` and `uv.lock` are frozen, so the bump is a re-freeze:

1. Add a design record under `docs/design/` that names the new version and why it is cut.
2. Set the version in `pyproject.toml` (`[project].version`) and in `src/arci/__init__.py`
   (`__version__`) to the same `X.Y.Z`. Set `packages/realornoise/pyproject.toml`'s version,
   its sole dependency `agent-reliability-ci==X.Y.Z`, and
   `packages/realornoise/src/realornoise/__init__.py`'s `__version__` to match.
   Also set `plugins/realornoise/.claude-plugin/plugin.json` (`version`) and
   `CITATION.cff` (`version`) to `X.Y.Z`. These are the package metadata and dependency-pin
   locations. Set the `uvx --python 3.14 realornoise==X.Y.Z` pins in
   `plugins/realornoise/skills/realornoise/SKILL.md` (including `allowed-tools`) and
   `integrations/codex/skills/realornoise/SKILL.md`; keep their documented command in
   `integrations/codex/README.md`, `docs/recipes/logs.md` and `docs/THREAT_MODEL_LOGS.md`
   in agreement. `uv.lock` also contains the main package version and is regenerated below.
   `tests/unit/packaging/test_review_fixes.py::test_every_release_version_matches` checks
   every location against `arci.__version__`. Log snapshots normalize the header version;
   a version bump does not regenerate them. The five HTML goldens under
   `tests/unit/html_report/golden/` (`pass.html`, `block.html`, `inconclusive.html`,
   `error.html` and `v1.html`) hold the version in their footer and are regenerated at a
   bump with `.venv/bin/python -m tests.unit.html_report.generate`. That command also
   regenerates `docs/results/sample-suite-report.html`. Historical release notes, design records,
   compatibility tables, recipes and archived reports keep their historical versions, with
   one exception: the captured banner line in `docs/recipes/logs.md` (`realornoise X.Y.Z`)
   is a current-version location and is set at the bump.
   Search the old version before each bump to catch newly added locations.
   Both distributions support Python 3.11 onward.
   It is not a uv workspace member and does not add an entry to the root lockfile.
   Regenerate the main package's `uv.lock` with `uv lock`. `uv lock` may also
   rewrite equivalent dependency markers (it did at `e304e81` and again for v0.8.0); resolved
   versions must not change, `uv lock --check` must pass, and the design record says what moved.
3. Move the CHANGELOG `Unreleased` entries under `vX.Y.Z (YYYY-MM-DD)`.
4. Recompute `FROZEN.sha256` for the files the bump touched (`pyproject.toml`, `uv.lock`, the new
   design record) and check that every other hash is unchanged. For 2.4.0,
   record 0017 re-freezes exactly `docs/STATISTICS_LOGS.md`, `src/arci/logs/schema.py`,
   `tests/acceptance/test_logs.py`, `pyproject.toml` and `uv.lock`, and newly pins
   `docs/design/0017-logs-2.md`. Record 0016 stays pinned and unchanged; every other
   hash stays as it is.
   Only the release orchestrator may change these frozen files or their hashes:
   `shasum -a 256 -c FROZEN.sha256`.
5. Commit on `main` (for example `release: vX.Y.Z`) and wait for CI to be green, including the
   `wheel-smoke` jobs and `oracle / SciPy` on that commit. In `.github/workflows/ci.yml`,
   the oracle job installs `constraints/oracle.txt` with hashes on top of the locked
   environment, runs `tests/unit/logs/test_oracle_scipy.py`, and fails on a skipped module.
   SciPy is a test oracle, not a runtime dependency.

Check locations added for 2.4.0: `.github/workflows/codeql.yml` scans Python and Actions;
`.github/workflows/workflow-audit.yml` runs zizmor; `.github/workflows/client-versions.yml`
compares npm client versions daily with the checked versions in `docs/LOG_FORMATS.md` and
maintains one open issue when a newer version appears. That issue is a request to check
formats, not evidence of compatibility. `.github/dependabot.yml` groups monthly Actions
updates. Workflows install uv from `.github/requirements/uv.txt` with required hashes
where checkout is available first. Inspect these checks along with CI and release smoke
results; a successful local check does not establish a successful hosted run.

## 2. Tag

```sh
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

The tag must be exactly `v` + the version in `pyproject.toml`.

## 3. What `.github/workflows/release.yml` does

- **build** (Ubuntu, Python 3.12): the guard requires a tag equal to `v` plus the main
  package's version, matching project and module versions in both distributions, and the
  exact main-package dependency pin in `realornoise`. `uv build --no-sources` writes the main
  wheel and sdist to `dist/`. A separate build writes the second wheel and sdist to
  `dist-realornoise/`. Each directory has its own `SHA256SUMS`, printed in the job summary,
  and is uploaded as its own artifact (`dist` and `dist-realornoise`). The main sdist
  allowlist check stays in place.
- **smoke** (Ubuntu and macOS, Python 3.11 and 3.14): installs both exact wheels into a
  fresh venv and runs the existing help, demo, trace-check, triage and schema checks from
  an empty directory. Every matrix entry runs `arci logs --example` and
  `realornoise --example`. Each example must exit **1** and print
  the line `RESULT: REAL DROP`; any other status or a missing line fails the smoke.
  `.github/scripts/wheel_smoke.sh` verifies the main wheel's packaged examples and the
  second wheel's file allowlist, version, dependency pin, Python range and entry point
  before installation. It is shared with CI. CI runs the full unit suite, including
  the log tests, on both Python 3.11 and 3.14. In each workflow, the second distribution
  is built once and its artifact is smoke-tested on every Python version in the smoke
  matrix. Python 3.14-only compressed-log test steps remain in place.
- **publish** (environment `pypi`): after build and every smoke job pass, re-checks the main
  `SHA256SUMS`, removes it, and uploads only the main wheel and sdist through trusted
  publishing with attestations.
- **publish-realornoise** (also `pypi`): runs only after the main publish job succeeds,
  verifies the second artifact's checksums, and uploads only the second wheel and sdist
  with the same publishing action, permissions and attestations. This order makes the
  exact dependency available before `realornoise` is published.

`workflow_dispatch` exists for re-runs; started from a branch, the guard stops it at build.

## 4. Verify

Download each distribution's wheel and sdist from PyPI into separate directories. Put the
matching `SHA256SUMS` from the workflow artifacts into each directory. Run
`shasum -a 256 -c SHA256SUMS` inside each, and check both PyPI pages show the intended version
and attestations. Check `realornoise`'s metadata requires Python 3.11 or newer and pins the
same main version. Compressed Codex logs are read only on Python 3.14; the output reports
how many files were not read. `uvx --python 3.14 realornoise` reads compressed logs
(uv fetches that Python if needed). With Python 3.11 or newer available, run:

```sh
uvx --from agent-reliability-ci==X.Y.Z arci demo
uvx --from agent-reliability-ci==X.Y.Z arci logs --example
uvx --python 3.14 realornoise==X.Y.Z --example
```

The demo must exit 0 and print `All six steps held.` Both example commands must exit 1 and
print `RESULT: REAL DROP` plus the generated-example label. Exit 1 is expected, so capture
it explicitly if verifying from a shell with `set -e`. Use `--example` for release checks;
it uses packaged synthetic data.

For later timing measurements, dispatch `ttfv-reference.yml` with package `realornoise`
(or `realornoise==X.Y.Z`) and command `realornoise --example`. Defaults remain
`agent-reliability-ci` and `arci demo`. The demo keeps Python 3.12; the log examples use
Python 3.14. The workflow preserves five cold and two warm samples and their deadlines,
and checks the selected command's expected exit and success line. These are hosted-machine timings, not user-adoption evidence.

## When the publish job fails

- **Trusted publisher missing** (the job fails at the OIDC token exchange): on PyPI, register the
  publisher for the failing project (`agent-reliability-ci` or `realornoise`): owner
  `ajaysurya1221`, repository `agent-reliability-ci`, workflow `release.yml`, environment
  `pypi`. Then re-run only the
  failed publish job from the same workflow run, using its already-built artifact. If the
  main package succeeded and `realornoise` failed before any upload, re-run only
  `publish-realornoise`; do not re-upload the main package. The unused version is free only
  for the distribution that has uploaded nothing.
- **Any failure after an upload started:** check both PyPI projects for which files of
  `X.Y.Z` exist. Never re-upload or rebuild a version that PyPI already has; fix forward with `X.Y.(Z+1)` through
  the steps above.
- **Guard or smoke failure:** nothing was published. Fix on `main`; if the tag points at the
  wrong commit and nothing was uploaded, delete the tag and tag again.
