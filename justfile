set shell := ["zsh", "-cu"]

# Everything CI runs. Must not modify files.
check:
    .venv/bin/ruff format --check .
    .venv/bin/ruff check .
    .venv/bin/basedpyright
    .venv/bin/pytest

# Immutable acceptance suite only.
acceptance:
    .venv/bin/pytest tests/acceptance

unit:
    .venv/bin/pytest tests/unit

# Fails if any orchestrator-owned frozen file changed.
frozen:
    shasum -a 256 -c FROZEN.sha256

selfcheck:
    .venv/bin/python bench/selfcheck.py

demo:
    .venv/bin/python examples/retry_agent/hero_demo.py
