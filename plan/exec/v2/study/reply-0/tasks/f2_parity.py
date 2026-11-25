"""Exercise the registered relay rule against an isolated edit of the installed JS server."""

from __future__ import annotations

import copy
import json
import re
import shutil
from pathlib import Path
from typing import Any


def relay_result(
    cell: dict[str, Any], call: dict[str, Any], result: dict[str, Any]
) -> dict[str, Any]:
    args = call["arguments"]
    pattern = args["pattern"]
    guard = cell["sentence_when"]["arg_matches"]["pattern"]
    if call["name"] != cell["tool"] or not re.fullmatch(guard, pattern):
        return result
    blocks = result["content"]
    if len(blocks) != 1 or blocks[0].get("type") != "text":
        return result
    original = blocks[0]["text"]
    if result.get("isError", False) != cell["reply_is_error"] or not re.fullmatch(
        cell["reply_pattern"], original
    ):
        return result
    delivered = copy.deepcopy(result)
    sentence = cell["sentence"].replace("{arg:pattern}", pattern)
    delivered["content"][0]["text"] = sentence
    if delivered.get("structuredContent", {}).get("content") == original:
        delivered["structuredContent"]["content"] = sentence
    return delivered


def edited_entry(env_dir: Path, work: Path, cell: dict[str, Any]) -> Path:
    modules = env_dir / "node/node_modules"
    package = work / "server-filesystem"
    shutil.copytree(modules / "@modelcontextprotocol/server-filesystem", package)
    (work / "node_modules").symlink_to(modules, target_is_directory=True)
    handler = package / "dist/server.js"
    source = handler.read_text()
    start = source.index(
        'let text = results.length > 0 ? results.join("\\n") : "No matches found";'
    )
    pos = source.index("        return {", start)
    guard = json.dumps(cell["sentence_when"]["arg_matches"]["pattern"])
    reply = json.dumps(cell["reply_pattern"])
    sentence = json.dumps(cell["sentence"])
    # After unreadable-directory diagnostics, before the server builds either content field.
    edit = (
        f"        if (new RegExp({reply}).exec(text)?.[0] === text &&\n"
        f"            new RegExp({guard}).exec(args.pattern)?.[0] === args.pattern) {{\n"
        f'            text = {sentence}.replaceAll("{{arg:pattern}}", () => args.pattern);\n'
        "        }\n"
    )
    handler.write_text(source[:pos] + edit + source[pos:])
    return package / "dist/index.js"
