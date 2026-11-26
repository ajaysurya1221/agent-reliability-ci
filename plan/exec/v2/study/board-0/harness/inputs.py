"""Exact registration and publication inventory."""

from pathlib import Path

from common import EXPORTS, LIST, NOTE, REG, ROOT, Row, need, schedule, sha

SOURCE_NAMES = (
    "agent.py",
    "admission.py",
    "audit.py",
    "board_oracle.py",
    "board_relay.py",
    "common.py",
    "check_evidence.py",
    "count_a.py",
    "count_b.py",
    "fifo.py",
    "grade.py",
    "inputs.py",
    "launcher.py",
    "offline_model.py",
    "pin.py",
    "privacy.py",
    "publication.py",
    "suite_process.py",
    "worlds.py",
    "run-board0.sh",
    "check-offline.sh",
    "INTERFACE.md",
    "DEVIATIONS.md",
    "tests/test_board.py",
    "tests/test_grade.py",
    "tests/planted.py",
    "tests/rehearsal.py",
    "tests/fake_ollama.py",
    "tests/native_rehearsal.py",
    "tests/native-rehearsal.sh",
    "tests/test_fake_ollama.py",
)


def sources() -> list[str]:
    return sorted(
        [
            REG,
            "models.json",
            "scenario-collisions.json",
            *(
                "projections/" + n
                for n in (
                    "project.py",
                    "board0_plan_stub.py",
                    "plan-16x20.yaml",
                    "plan-16x26.yaml",
                    "registered-rows.json",
                )
            ),
            "tasks/tasks.json",
            "tasks/make_tasks.py",
            "orderdesk/orderdesk_world.py",
            "orderdesk/task.json",
            "calendardesk/calendar_world.py",
            "calendardesk/key.py",
            "calendardesk/tasks.json",
            *("harness/" + n for n in SOURCE_NAMES),
        ]
    )


def file(root: Path, name: str) -> Path:
    path = root / name
    need(
        not Path(name).is_absolute()
        and ".." not in Path(name).parts
        and path.resolve() == path
        and path.is_file(),
        f"missing or linked {name}",
    )
    return path


def digests(names: list[str], root: Path = ROOT) -> str:
    return "".join(f"{sha(file(root, n).read_bytes())}  {n}\n" for n in sorted(names))


def descriptors(slots: list[Row]) -> list[str]:
    from worlds import rows

    return [
        name
        for r in schedule(slots)
        if "-pin-" not in r
        for name in (
            [f"clean/{r}/{task}/descriptor.yaml" for task in rows()]
            if r.endswith("-clean")
            else [f"runs/{r}/descriptor.yaml"]
        )
    ]


def outputs(run: str) -> list[str]:
    if "-pin-" in run:
        return [f"pins/{run}.json"]
    if run.endswith("-clean"):
        from worlds import rows

        return [
            f"clean/{run}.json",
            *(f"clean/{run}/{tid}/{name}" for tid in rows() for name in EXPORTS),
        ]
    return [f"runs/{run}/{name}" for name in EXPORTS]


def inventory(slots: list[Row]) -> list[str]:
    return sorted(
        [*sources(), LIST, NOTE, "result.md", *(p for run in schedule(slots) for p in outputs(run))]
    )
