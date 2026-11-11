"""Independent grading; intentionally imports no agent framework."""

from pydantic import JsonValue


def check(task: dict[str, JsonValue], final_state: dict[str, JsonValue]) -> bool:
    return final_state.get("final_output") == task.get("expected", "forty-two")
