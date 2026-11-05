# v1.0.0 triage implementation and pre-merge evidence

Base: f039e1ddd07011a6018b88171cb51d5be3d63b26. Production/test implementation:
cb2ab9e. Reviewed v1 candidate: d11476945d449cceb84bb7204dccabcc14e62543.
The original approved target was v0.9.0; the operator requested a major release
before publication. No 0.9.0 version was tagged or published by this work.

## Outcome

`arci triage` selects representative native failures, resolves their baseline
partners through the schedule, reuses `check_traces`, binds its source hashes and
reports bounded containing-event context. The complete pure gate remains the
statistical result. No new dependencies, equality engine, recorder, replay path or
statistical rule was introduced. The existing comparator is unchanged apart from
an additive context helper. Both commands ship in the intended v1.0.0 release.

The [research decision](reports/release-direction.md) maps the full supplied
reference and current primary-source overlap. The [compatibility policy](../../../docs/COMPATIBILITY.md)
defines the meaning of the major version. The existing Beta classifier remains;
1.0.0 is not a production-safety, popularity or adoption claim.

## Independent review and reproducible checks

| Gate | Observed result |
|---|---|
| [Task review](reports/task-review.md) | SPEC ACCEPT / QUALITY ACCEPT for both lanes. |
| [Fresh whole-branch review](reports/final-review.md) | ACCEPT, no actionable findings; its independent checks and limits are explicit. |
| `.venv/bin/python -B -m pytest -p no:cacheprovider -ra` | 1404 passed in 423.88 seconds, exit 0. Full [log](verification/full-suite.txt). |
| Ruff format/check and basedpyright | 452 files formatted; lint clean; 0 type errors/warnings/notes. |
| Frozen/protected evidence | All 54 frozen hashes validate; only approved version metadata and new release ADR change. All 272 protected files and contracted first screen unchanged. |
| Lock | `uv lock --check --offline` passes; parsed old/new lock objects differ only in root package version. |
| Historical reproduction | `reproduce.py --check --strict`: 6/6 checks OK; 18 decisions and both planners byte-identical; 13 package and 24 indexed hashes match. |
| Prior trace rehearsal | `verify.py`: DRIFT/1, DRIFT/1, MATCH/0 receipts match and all 29 source files unchanged. |
| README figures | All four SVGs match generator with `--check`. |
| Built wheel, Python 3.13/macOS | Shared `wheel_smoke.sh` from fresh environment/outside checkout passes all six demo steps, trace statuses, triage exits/JSON/read-only checks and schema. Full [log](verification/wheel-smoke.txt). |

The exact local wheel-smoke command was:

```sh
uv build --offline --no-sources --out-dir /tmp/arci-triage-v090.ygMrHy/dist-v1-reviewed
PYTHON=.venv/bin/python bash .github/scripts/wheel_smoke.sh /tmp/arci-triage-v090.ygMrHy/dist-v1-reviewed/agent_reliability_ci-1.0.0-py3-none-any.whl
```

Local build hashes (not claims about later hosted release bytes):

- `.gitignore`: `684888c0ebb17f374298b65ee2807526c066094c701bcc7ebbe1c1095f494fc1`
- `agent_reliability_ci-1.0.0-py3-none-any.whl`: `00cf5e073c348d6ba50466b92b351b9334818fad7a513f308c145c5451c16d6b`
- `agent_reliability_ci-1.0.0.tar.gz`: `5a80ed8d4a7ff6669b641885f0a0249c02463d096fd4cd587ceed93b32540920`

[Two independent agent readers](rehearsal/REPORT.md) completed both supplied cases
under 300 seconds per diagnosis without JSONL inspection. Source hashes remain
unchanged. This measured bounded agent usability, not human adoption or retention.
The initial unpublished 0.9.0 wheel receipts are retained unchanged. From that
implementation to d114769, production/test/smoke files differ only in __version__.
The v1 wheel was separately rebuilt and smoke-tested as recorded above.

## Delivery receipts

[PR #17](https://github.com/ajaysurya1221/agent-reliability-ci/pull/17) is the durable
record for final candidate SHA, exact-candidate hosted CI, merge SHA and exact-main
CI. The version tag is allowed only after those checks pass. Its release workflow
must build/smoke/publish the same bytes, and downloaded PyPI artifacts must match
workflow SHA256SUMS and pass clean installation/demo/diagnostic checks.

The [v1.0.0 release](https://github.com/ajaysurya1221/agent-reliability-ci/releases/tag/v1.0.0)
will retain final workflow links, verified published hashes and the same artifacts.
At the time this pre-merge report is committed, those publication checks are pending;
this report does not pre-approve them. No later receipt is fabricated into an older
commit, and no old tag, distribution or historical record is replaced.
