"""The Claude Code plugin and the Codex skill only run the command, and agree on names."""

from __future__ import annotations

import json
from pathlib import Path

import arci

ROOT = Path(__file__).resolve().parents[3]
MARKETPLACE = ROOT / ".claude-plugin" / "marketplace.json"
PLUGIN = ROOT / "plugins" / "realornoise"
CLAUDE_SKILL = PLUGIN / "skills" / "realornoise" / "SKILL.md"
CODEX_SKILL = ROOT / "integrations" / "codex" / "skills" / "realornoise" / "SKILL.md"


def _frontmatter(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "---"
    end = lines.index("---", 1)
    pairs = (line.split(":", 1) for line in lines[1:end])
    return {key.strip(): value.strip() for key, value in pairs}


def test_marketplace_points_at_the_plugin_folder() -> None:
    market = json.loads(MARKETPLACE.read_text(encoding="utf-8"))
    assert market["name"] == "agent-reliability-ci"
    assert market["owner"]["name"]
    (entry,) = market["plugins"]
    assert entry["name"] == "realornoise"
    assert entry["source"] == "./plugins/realornoise"
    assert (ROOT / entry["source"]).is_dir()


def test_plugin_manifest_matches_the_package() -> None:
    manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["name"] == "realornoise"
    assert manifest["version"] == arci.__version__
    assert manifest["license"] == "Apache-2.0"
    for key in ("description", "author", "repository"):
        assert manifest[key]


def test_claude_skill_runs_only_the_fixed_command() -> None:
    meta = _frontmatter(CLAUDE_SKILL)
    assert meta["name"] == "realornoise"
    assert meta["disable-model-invocation"] == "true"
    assert meta["allowed-tools"] == "Bash(uvx realornoise), Bash(uvx realornoise *)"
    body = CLAUDE_SKILL.read_text(encoding="utf-8")
    commands = [line for line in body.splitlines() if line.startswith("!`")]
    assert commands == ["!`uvx realornoise 2>&1 || true`"]
    assert "$ARGUMENTS" not in body
    assert "visible to this assistant" in body


def test_codex_skill_names_the_same_command() -> None:
    meta = _frontmatter(CODEX_SKILL)
    assert set(meta) == {"name", "description"}
    assert meta["name"] == "realornoise"
    body = CODEX_SKILL.read_text(encoding="utf-8")
    assert "    uvx realornoise\n" in body
    assert "visible to this assistant" in body


def test_descriptions_fit_the_listing_limit() -> None:
    for path in (CLAUDE_SKILL, CODEX_SKILL):
        assert len(_frontmatter(path)["description"]) <= 1536
