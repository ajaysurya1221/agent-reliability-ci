"""`arci preflight --allow-unlisted-model`.

The vendor's `GET /v1/models` lists aliases (`jev-latest`, `jev-preview`) while versioned ids such
as `jev-1.13.0` stay accepted. Without the flag a pin missing from the list is still exit 2 with no
smoke request (the pre-registered rule, pinned by the acceptance tests). With the flag the smoke
request decides: exit 0 only if its validated response reports exactly the pinned id.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import JsonValue

from arci import cli
from arci.mcp_boundary import UpstreamResult
from arci.schema import DecisionSpec
from examples.jev_triage_agent.experiment import live_manifest
from tests.acceptance.test_decisions_v06 import (
    _generic_answers,  # pyright: ignore[reportPrivateUsage]
)

ALIASES = ("jev-latest", "jev-preview")


def _fake_upstream(listed: tuple[str, ...], smoke_model: str) -> Any:
    posts: list[dict[str, JsonValue]] = []

    def upstream(
        method: str,
        endpoint: str,
        body: dict[str, JsonValue] | None,
        spec: DecisionSpec,
        *,
        api_key: str | None = None,
    ) -> UpstreamResult:
        if endpoint == "/v1/models":
            cards: list[JsonValue] = [
                {"name": name, "description": "x", "release_date": "2026-09-15"} for name in listed
            ]
            return UpstreamResult(status=200, headers={}, body={"models": cards, "object": "list"})
        assert body is not None
        posts.append(body)
        answers = _generic_answers(cast(dict[str, Any], body["questions"]))
        return UpstreamResult(
            status=200,
            headers={"x-typesafe-request-id": "req-unit"},
            body={
                "model": smoke_model,
                "answers": answers,
                "usage": {"input_tokens": 31, "output_tokens": 3},
            },
        )

    upstream.posts = posts  # type: ignore[attr-defined]
    return upstream


@pytest.fixture
def manifest_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("TYPESAFE_API_KEY", "unit-test-key")
    path = tmp_path / "manifest.json"
    path.write_text(live_manifest("b").model_dump_json(indent=2) + "\n", encoding="utf-8")
    return path


def test_without_the_flag_an_unlisted_pin_is_still_exit_2_and_no_smoke_request(
    manifest_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = _fake_upstream(ALIASES, "jev-1.13.0")
    assert cli._cmd_preflight(str(manifest_path), upstream=fake) == 2  # pyright: ignore[reportPrivateUsage]
    out = capsys.readouterr().out
    assert "jev-latest, jev-preview" in out and "--allow-unlisted-model" in out
    assert fake.posts == []


def test_with_the_flag_the_smoke_request_verifies_the_pin(
    manifest_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = _fake_upstream(ALIASES, "jev-1.13.0")
    code = cli._cmd_preflight(  # pyright: ignore[reportPrivateUsage]
        str(manifest_path), allow_unlisted_model=True, upstream=fake
    )
    out = capsys.readouterr().out
    assert code == 0, out
    assert len(fake.posts) == 1 and fake.posts[0]["model"] == "jev-1.13.0"
    assert "pinned model not listed" in out and "model: jev-1.13.0" in out
    assert '{"preflight":' in out and "unit-test-key" not in out


def test_with_the_flag_a_smoke_response_for_another_model_is_exit_3(
    manifest_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    fake = _fake_upstream(ALIASES, "jev-1.14.0")
    code = cli._cmd_preflight(  # pyright: ignore[reportPrivateUsage]
        str(manifest_path), allow_unlisted_model=True, upstream=fake
    )
    assert code == 3
    assert "smoke" in capsys.readouterr().out
    assert len(fake.posts) == 1


def test_a_listed_pin_is_unchanged_with_or_without_the_flag(manifest_path: Path) -> None:
    for flag in (False, True):
        fake = _fake_upstream(("jev-1.13.0", *ALIASES), "jev-1.13.0")
        code = cli._cmd_preflight(  # pyright: ignore[reportPrivateUsage]
            str(manifest_path), allow_unlisted_model=flag, upstream=fake
        )
        assert code == 0 and len(fake.posts) == 1


def test_parser_accepts_the_flag() -> None:
    values = vars(cli._parser().parse_args(["preflight", "m.json", "--allow-unlisted-model"]))  # pyright: ignore[reportPrivateUsage]
    assert values["allow_unlisted_model"] is True
    values = vars(cli._parser().parse_args(["preflight", "m.json"]))  # pyright: ignore[reportPrivateUsage]
    assert values["allow_unlisted_model"] is False
