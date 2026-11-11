"""Independent grader: only serialized JSON state, no optional framework imports."""

from pydantic import JsonValue


def oracle(task: dict[str, JsonValue], state: dict[str, JsonValue]) -> bool:
    return (
        not task.get("reject_oracle", False)
        and set(state) == {"final_output", "structured_response", "state"}
        and state["final_output"] == "done"
    )
