"""The Claude Code plugin and the Codex skill each name only the one command, and agree on names."""

from __future__ import annotations

import importlib.util
import json
import re
import struct
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


def test_plugin_manifest_links_point_at_files_in_this_repository() -> None:
    """A directory shows these links; a wrong one sends a reader to another project's page."""
    manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    assert manifest["displayName"] == "realornoise"
    assert manifest["supportUrl"] == manifest["repository"] + "/issues"
    blob = manifest["repository"] + "/blob/main/"
    for key in ("documentationUrl", "privacyPolicyUrl"):
        assert manifest[key].startswith(blob), key
        assert (ROOT / manifest[key].removeprefix(blob)).is_file(), key
    assert manifest["privacyPolicyUrl"] in (PLUGIN / "README.md").read_text(encoding="utf-8")
    privacy = (ROOT / "docs" / "PRIVACY.md").read_text(encoding="utf-8")
    assert "opens no network connection" in privacy
    assert "—" not in privacy


def test_claude_skill_names_only_the_fixed_command() -> None:
    meta = _frontmatter(CLAUDE_SKILL)
    # Only the user starts it, and no tool is approved ahead of time (no `allowed-tools`).
    assert set(meta) == {"name", "description", "disable-model-invocation"}
    assert meta["name"] == "realornoise"
    assert meta["disable-model-invocation"] == "true"
    body = CLAUDE_SKILL.read_text(encoding="utf-8")
    # No shell line that runs before the conversation, in any spelling, and no fenced block:
    # the skill is an instruction to Claude.
    assert "!" not in body and "```" not in body and "~~~" not in body and "\t" not in body
    # No placeholder that would paste typed text into the instruction.
    assert not re.search(r"\$(\d|ARGUMENTS|\{)", body)
    command = f"uvx --python 3.14 realornoise=={arci.__version__}"
    assert [line for line in body.splitlines() if line.startswith("    ")] == ["    " + command]
    # The command appears twice: the line to run, and the `--keep` form the user may run.
    assert re.findall(r"uvx --python[^\n`]*", body) == [command, command + " --keep"]
    assert re.findall(r"(?<![-\w])--[a-z][a-z-]*", body) == ["--python", "--keep"] * 2
    prose = " ".join(body.split())
    for sentence in (
        "made of this line and nothing else",
        "Run no other command in this turn",
        "do not pass it",
        "Do not add `--keep`.",
        "It is the result, not a failure of the command.",
    ):
        assert sentence in prose, sentence
    assert "visible to this assistant" in body
    assert "numbers only" not in body


def test_codex_skill_names_the_same_command() -> None:
    meta = _frontmatter(CODEX_SKILL)
    assert set(meta) == {"name", "description"}
    assert meta["name"] == "realornoise"
    body = CODEX_SKILL.read_text(encoding="utf-8")
    assert f"    uvx --python 3.14 realornoise=={arci.__version__}\n" in body
    assert "visible to this assistant" in body


def test_descriptions_fit_the_listing_limit() -> None:
    for path in (CLAUDE_SKILL, CODEX_SKILL):
        assert len(_frontmatter(path)["description"]) <= 1536


def test_plugin_folder_has_its_own_readme() -> None:
    """A plugin directory reads the README inside the plugin folder, not the repository's."""
    text = (PLUGIN / "README.md").read_text(encoding="utf-8")
    prose = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
    assert len(prose.split()) >= 40
    # What the plugin reads, runs, fetches, writes and sends is stated, one line each.
    for label in ("- Reads:", "- Runs:", "- Fetches:", "- Writes:", "- Prints:", "- Sends:"):
        assert label in text, label
    assert "It cannot show a cause, answer quality" in text
    assert "CANNOT TELL, which is a normal result" in text
    assert "\u2014" not in text


def test_every_launcher_command_in_the_plugin_and_skill_is_pinned() -> None:
    """An unpinned `uvx realornoise` would run another version than the one described."""
    for path in (PLUGIN / "README.md", CLAUDE_SKILL, CODEX_SKILL):
        text = path.read_text(encoding="utf-8")
        commands = re.findall(r"uvx[^\n`]*?realornoise(\S*)", text)
        assert commands, path
        for suffix in commands:
            assert suffix.rstrip(".,;:)`") == f"=={arci.__version__}", (path, suffix)


def test_listing_icon_is_a_square_png_drawn_by_the_generator() -> None:
    """A plugin directory wants a square PNG, 512 to 2048 pixels a side, under 2 MB."""
    manifest = json.loads((PLUGIN / ".claude-plugin" / "plugin.json").read_text(encoding="utf-8"))
    # The manifest names the icon; only the manifest belongs inside `.claude-plugin`.
    assert manifest["icon"] == "./icon.png"
    assert [path.name for path in (PLUGIN / ".claude-plugin").iterdir()] == ["plugin.json"]
    icon = PLUGIN / manifest["icon"]
    data = icon.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR"
    width, height = struct.unpack(">II", data[16:24])
    assert width == height and 512 <= width <= 2048
    assert len(data) < 2 * 1024 * 1024
    source = ROOT / "docs" / "assets" / "src" / "make_plugin_icon.py"
    spec = importlib.util.spec_from_file_location("make_plugin_icon", source)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # Pixels, not bytes: the compressed form may differ between zlib builds.
    expected = b"".join(b"\x00" + bytes(row) for row in module.pixels())
    assert module.decode(data) == expected
