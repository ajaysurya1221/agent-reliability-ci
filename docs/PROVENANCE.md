# Provenance

Factual notes on who holds this code, how it was made, and what is and is
not claimed about that. Not a sales or licensing document.

## Ownership

Copyright 2026 Ajay Surya Senthilrajan (per `NOTICE` and `LICENSE`). Apache License,
Version 2.0. One maintainer.

## How it was built

One maintainer, September to November 2026, with Claude Code and Codex as
pair-programmers, recorded in the commit messages. Through v1.0.0 the
experiment design, the decision rule and its calibration, the trust model
and the acceptance tests are the maintainer's own. For 2.0.0 and 2.1.0 the
design records were drafted by Claude as orchestrator and approved by the
maintainer, and the implementation was by Codex from written briefs
(design records 0011 to 0014).

At commit `dd2c65b` on `main` (v2.1.0 plus one documentation merge), 349 of
417 commits carry a `Co-Authored-By: Claude` trailer:

```sh
git log --grep="Co-Authored-By: Claude" --format=%H | wc -l   # 349
git rev-list --count HEAD                                     # 417
```

The maintainer states that ARCI was built independently between September
and November 2026, and that no employer or client has a claim on it.

## Third-party material

Per `NOTICE`: the canonical JSON hashing (`src/arci/hashing.py`) and
self-sealing decision pattern (`src/arci/schema.py`) are adapted from
`evalopt-graph` (MIT). `examples/guardrail_agent` (source repo only) has
four unchanged files from `frontier-scout` (MIT), each hashed in that
example's README. `docs/results/jev-calibration` (source repo only) uses
intent label names from CC BY licensed CLINC150 and Banking77; dataset
texts are not included.

## Runtime dependencies and their licences

Direct dependencies are `pydantic` and `pyyaml`; the rest are theirs.
Licences per each package's installed `METADATA`:

| Package | Licence |
|---|---|
| pydantic, pydantic-core, PyYAML, annotated-types, typing-inspection | MIT |
| typing-extensions | PSF-2.0 |

The `langchain` extra is optional and not installed by default; see its own
licence.

## What is not claimed

A sealed record's `record_sha256` is an integrity check. It shows that a
record's content matches its hash, and that a decision was derived from
exactly the trial records beside it. Anyone who can edit a file can also
recompute its hash, so it is not a signature: it says nothing about who
ran a trial, when, or on what hardware. No warranty is made beyond the
Apache-2.0 text.
