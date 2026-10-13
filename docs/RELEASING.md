# Releasing

How a version of `agent-reliability-ci` reaches PyPI. PyPI versions are immutable: a version
number, once uploaded, can never be uploaded again, even after a deletion.

## 1. Bump the version (one commit)

`pyproject.toml` and `uv.lock` are frozen, so the bump is a re-freeze:

1. Add a design record under `docs/design/` that names the new version and why it is cut.
2. Set the version in `pyproject.toml` (`[project].version`) and in `src/arci/__init__.py`
   (`__version__`) to the same `X.Y.Z`; regenerate `uv.lock` with `uv lock`. `uv lock` may also
   rewrite equivalent dependency markers (it did at `e304e81` and again for v0.8.0); resolved
   versions must not change, `uv lock --check` must pass, and the design record says what moved.
3. Move the CHANGELOG `Unreleased` entries under `vX.Y.Z (YYYY-MM-DD)`.
4. Recompute `FROZEN.sha256` for the files the bump touched (`pyproject.toml`, `uv.lock`, the new
   design record) and check that every other hash is unchanged:
   `shasum -a 256 -c FROZEN.sha256`.
5. Commit on `main` (for example `release: vX.Y.Z`) and wait for CI to be green, including the
   `wheel-smoke` jobs.

## 2. Tag

```sh
git tag -a vX.Y.Z -m "vX.Y.Z"
git push origin vX.Y.Z
```

The tag must be exactly `v` + the version in `pyproject.toml`.

## 3. What `.github/workflows/release.yml` does

- **build** (Ubuntu, Python 3.12): the guard fails the job unless the ref is a tag equal to
  `v` + `[project].version` and `arci.__version__` equals that version. Then
  `uv build --no-sources` writes the wheel and the sdist to `dist/`, the wheel contents are
  listed, and `dist/SHA256SUMS` is written and copied into the job summary. `dist/` is uploaded
  as the artifact `dist`.
- **smoke** (Ubuntu and macOS, Python 3.11 and 3.14): installs that exact wheel into a fresh
  venv and runs `arci --help`, `python -m arci --help` and `arci demo --workers 4` from an
  empty directory (`.github/scripts/wheel_smoke.sh`, the same script CI runs).
- **publish** (environment `pypi`): re-checks `SHA256SUMS`, removes it from `dist/`, and uploads
  the wheel and the sdist with `pypa/gh-action-pypi-publish` through trusted publishing (OIDC,
  no token) with attestations. It runs only if build and every smoke job passed.

`workflow_dispatch` exists for re-runs; started from a branch, the guard stops it at build.

## 4. Verify

Download the wheel and the sdist from PyPI into one directory with `SHA256SUMS` (in the run's
`dist` artifact, and printed in the build job's summary), then:

```sh
shasum -a 256 -c SHA256SUMS
uvx --from agent-reliability-ci==X.Y.Z arci demo
```

The demo must print `All six steps held.`

## When the publish job fails

- **Trusted publisher missing** (the job fails at the OIDC token exchange): on PyPI, register the
  publisher for project `agent-reliability-ci`: owner `ajaysurya1221`, repository
  `agent-reliability-ci`, workflow `release.yml`, environment `pypi`. Then re-run only the
  failed publish job from the same workflow run. Nothing was uploaded, so the version is free.
- **Any failure after an upload started:** check PyPI for which files of `X.Y.Z` exist. Never
  re-upload or rebuild a version that PyPI already has; fix forward with `X.Y.(Z+1)` through
  the steps above.
- **Guard or smoke failure:** nothing was published. Fix on `main`; if the tag points at the
  wrong commit and nothing was uploaded, delete the tag and tag again.
