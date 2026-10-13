"""The environment the MCP agent works in, served by `arci.mcp_toolset_server`.

`fetch(key)` reads a value from a seeded upstream: 30% of seeds fail the first real call
transiently. `store(key, value)` writes it. The oracle checks the stored value against the
upstream's; it never reads the agent's claim.
"""

from __future__ import annotations

import random
from collections.abc import Callable, Mapping

from pydantic import JsonValue

FLAKY_SHARE = 0.30


class World:
    def __init__(self, task: dict[str, JsonValue], seed: int) -> None:
        self._key = str(task["key"])
        self._upstream = f"v{random.Random(f'{seed}:value').randrange(1000, 10000)}"
        self._flaky = random.Random(f"{seed}:fetch").random() < FLAKY_SHARE
        self._stored: dict[str, JsonValue] = {}
        self.tools: Mapping[str, Callable[..., JsonValue]] = {
            "fetch": self.fetch,
            "store": self.store,
        }

    def fetch(self, key: str) -> JsonValue:
        """Read the upstream value for a key."""
        if self._flaky:
            self._flaky = False
            raise TimeoutError("upstream transient timeout")
        return {"key": key, "value": self._upstream if key == self._key else None}

    def store(self, key: str, value: str) -> JsonValue:
        """Write a value under a key."""
        self._stored[key] = value
        return {"key": key, "stored": True}

    def snapshot(self) -> dict[str, JsonValue]:
        return {"key": self._key, "upstream": self._upstream, "stored": dict(self._stored)}


def make_world(task: dict[str, JsonValue], seed: int) -> World:
    return World(task, seed)


def passed(task: dict[str, JsonValue], final_state: dict[str, JsonValue]) -> bool:
    stored = final_state.get("stored")
    upstream = final_state.get("upstream")
    return (
        isinstance(stored, dict) and upstream is not None and stored == {str(task["key"]): upstream}
    )
