# Reproduction of the archived failure bundles on another machine

The two committed minimised bundles seal the interpreter path of the machine that produced
them (`/home/user/agent-reliability-ci/.venv/bin/python` for the Jev campaign,
`/Users/ajay/Developer/.arci-worktrees/guardrail-live/.venv/bin/python` for the guardrail
campaign) and otherwise run module commands (`-m arci.mcp_toolset_server`,
`-m examples.<campaign>.agent`). They are not resealed to make the paths convenient; instead
the paths are recreated inside a disposable Linux container and replay runs with networking
disabled, so no model key and no live endpoint can take part.

Probe of 2026-10-05 (log: `../logs/docker-replay-probe-2026-10-05.txt`), run from the arci
checkout at main `f299854`:

```bash
docker volume create arci-repro
# stage 1: install the pinned source into the sealed Linux path (network on)
docker run --rm --platform linux/amd64 -v "$PWD":/w:ro -v arci-repro:/home/user python:3.11-slim bash -lc '
  set -e; rm -rf /home/user/agent-reliability-ci; cp -r /w /home/user/agent-reliability-ci
  cd /home/user/agent-reliability-ci && rm -rf .venv && python -m venv .venv && .venv/bin/pip install -q --no-cache-dir .'
# stage 2: replay with no network; the macOS worktree path is a symlink to the same checkout
docker run --rm --platform linux/amd64 --network none -v arci-repro:/home/user python:3.11-slim bash -lc '
  mkdir -p /Users/ajay/Developer/.arci-worktrees && ln -s /home/user/agent-reliability-ci /Users/ajay/Developer/.arci-worktrees/guardrail-live
  cd /home/user/agent-reliability-ci && export PYTHONPATH=$PWD
  .venv/bin/arci replay docs/results/jev/2026-10-03/jev-live-b-low_confidence-200/min-bundle.json
  .venv/bin/arci replay docs/results/guardrail/2026-10-05/guardrail-live-b-ask-provider_down-200/min-bundle.json'
```

Observed: both replays print `REPRODUCED: failure reproduced` and exit 0 (Python 3.11.15,
glibc 2.41, linux/amd64 under emulation on an arm64 host). A scripted form of this recipe
(`reproduce.py`) is added by the planner work package; until then this file is the recipe.
