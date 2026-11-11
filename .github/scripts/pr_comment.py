"""Opt-in sticky GITHUB_TOKEN comment. Needs pull-requests: write; fails soft.

The caller should serialize runs for a PR with workflow concurrency. GitHub's
issue-comment API has no atomic create-if-absent operation.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast
from urllib.parse import urlsplit

MARKER_PREFIX = "<!-- arci-reliability-report:"
Api = Callable[[str, str, dict[str, str] | None], object]


def gh_api(method: str, endpoint: str, payload: dict[str, str] | None = None) -> object:
    command = ["gh", "api", "--method", method, endpoint]
    if payload is not None:
        command += ["--input", "-"]
    result = subprocess.run(
        command,
        input=json.dumps(payload) if payload is not None else None,
        text=True,
        capture_output=True,
        check=True,
        timeout=30,
    )
    return cast(object, json.loads(result.stdout))


def marker(env: Mapping[str, str]) -> str:
    identity = (
        ["explicit", env["ARCI_COMMENT_ID"]]
        if env.get("ARCI_COMMENT_ID")
        else [
            env.get("GITHUB_WORKFLOW", ""),
            env.get("GITHUB_JOB", ""),
            env.get("ARCI_MANIFEST", ""),
        ]
    )
    digest = hashlib.sha256(json.dumps(identity, ensure_ascii=True).encode()).hexdigest()
    return f"{MARKER_PREFIX}{digest} -->"


def _provenance(env: Mapping[str, str]) -> str:
    # These values are runner metadata, not experiment strings. Restrict their syntax.
    head = env.get("ARCI_HEAD_SHA", env.get("GITHUB_SHA", ""))
    head = head if re.fullmatch(r"[a-fA-F0-9]{7,64}", head) else "unavailable"
    run = env.get("GITHUB_RUN_ID", "")
    run = run if re.fullmatch(r"[0-9]{1,30}", run) else "unavailable"
    return f"Head SHA: `{head}`; run id: `{run}`."


def _body(env: Mapping[str, str], repository: str) -> str:
    prefix = f"{marker(env)}\n## ARCI reliability gate\n\n{_provenance(env)}\n\n"
    verdict = env.get("ARCI_VERDICT", "")
    fallback = (
        f"VERDICT: {verdict}\n\n" if verdict in {"PASS", "BLOCK", "INCONCLUSIVE", "ERROR"} else ""
    )
    artifact_url = env.get("ARCI_ARTIFACT_URL", "")
    try:
        parsed = urlsplit(artifact_url)
        server = urlsplit(env.get("GITHUB_SERVER_URL", "https://github.com"))
        valid_url = (
            parsed.scheme == "https"
            and parsed.netloc == server.netloc
            and re.fullmatch(
                r"/" + re.escape(repository) + r"/actions/runs/[0-9]+/artifacts/[0-9]+", parsed.path
            )
            and not parsed.query
            and not parsed.fragment
        )
    except ValueError:
        valid_url = False
    try:
        summary = Path(env["ARCI_SUMMARY"]).read_text(encoding="utf-8") if valid_url else ""
    except (OSError, ValueError, KeyError):
        summary = ""
    if not summary.strip():
        return prefix + fallback + "Report unavailable.\n"
    suffix = f"\n\n[Download HTML report]({artifact_url})\n"
    notice = "\n\nSummary truncated at a section boundary; see HTML report."
    budget = 65000 - len(prefix.encode()) - len(suffix.encode()) - len(notice.encode())
    kept: list[str] = []
    size = 0
    # Only generated sections are admitted; never cut a table row or a code span.
    for section in summary.strip().split("\n\n"):
        added = len(section.encode()) + (2 if kept else 0)
        if size + added > budget:
            return (
                prefix + ("\n\n".join(kept) or fallback + "Report unavailable.") + notice + suffix
            )
        kept.append(section)
        size += added
    return prefix + "\n\n".join(kept) + suffix


def post_comment(env: Mapping[str, str], api: Api = gh_api) -> str:
    """Return one log line; never turn a publication failure into a gate failure."""
    if not env.get("GH_TOKEN"):
        return "ARCI comment skipped: no token."
    if env.get("GITHUB_EVENT_NAME") not in {"pull_request", "pull_request_target"}:
        return "ARCI comment skipped: outside a pull request."
    try:
        raw_event: object = json.loads(Path(env["GITHUB_EVENT_PATH"]).read_text())
        if not isinstance(raw_event, dict):
            raise ValueError("invalid event")
        event = cast(dict[str, object], raw_event)
        number = event.get("number")
        repository = env["GITHUB_REPOSITORY"]
        if type(number) is not int or number <= 0 or len(repository.split("/")) != 2:
            raise ValueError("invalid pull request")
        body = _body(env, repository)
        current_marker = marker(env)
        root = f"repos/{repository}/issues/{number}/comments"
        page = 1
        found: list[int] = []
        while True:
            response = api("GET", f"{root}?per_page=100&page={page}", None)
            if not isinstance(response, list):
                raise ValueError("invalid comment list")
            comments = cast(list[object], response)
            for item in comments:
                if not isinstance(item, dict):
                    raise ValueError("invalid comment")
                comment = cast(dict[str, object], item)
                user = comment.get("user")
                if not isinstance(user, dict):
                    continue
                author = cast(dict[str, object], user)
                text = comment.get("body")
                identifier = comment.get("id")
                if (
                    author.get("login") == "github-actions[bot]"
                    and author.get("type") == "Bot"
                    and isinstance(text, str)
                    and text.startswith(current_marker + "\n")
                    and type(identifier) is int
                ):
                    found.append(identifier)
            if len(comments) < 100:
                break
            page += 1
        if found:
            # Update the oldest canonical comment first, then reconcile racing duplicates.
            # Delete none: all surviving copies must show the current head and verdict.
            for identifier in sorted(set(found)):
                api("PATCH", f"repos/{repository}/issues/comments/{identifier}", {"body": body})
            return "ARCI comment updated."
        api("POST", root, {"body": body})
        return "ARCI comment created."
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError):
        return "ARCI comment skipped: API or report unavailable; gate result unchanged."


if __name__ == "__main__":
    print(post_comment(os.environ))
