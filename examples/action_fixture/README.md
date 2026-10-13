`manifest.json` is the sealed manifest CI's `action-fixture` job passes to the composite Action (`uses: ./`).
Regenerate it with `python examples/action_fixture/build_manifest.py`; a unit test fails if the committed file is stale.
It is the packaged demo's A-vs-B experiment (`arci.demo.*` refs, 200 trials per arm) and is expected to BLOCK.
