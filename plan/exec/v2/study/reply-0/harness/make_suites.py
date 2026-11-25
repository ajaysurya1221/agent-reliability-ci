"""Build one registered descriptor at a time. No server or model is started."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from harness.wiring_check import registered_node  # noqa: E402

TASK_LIST = HERE.parent / "tasks/tasks.json"
FX = Path("/Users/Shared/arci-reply0/fx")
MODELS = {"4B": "qwen3.5:4b-mlx-ctx32k", "12B": "gemma4:12b-mlx-ctx32k"}
ROUNDS = {8: 15, 7: 18, 6: 20, 5: 24}
PHASES = ("main", "clean", "unscripted", "confirmation", "generic")
Row = dict[str, Any]


def register(fx: Path = FX) -> Row:
    raw = TASK_LIST.read_bytes()
    if hashlib.sha256(raw).hexdigest() != (
        "76ee13ca3c4eaa54514ae4c08cef1cc75e93e81c8b43ac4073dee5e267b922a1"
    ):
        raise ValueError("unregistered task list")
    return json.loads(raw.decode().replace("{FX}", str(fx)))


def write_json(path: Path, value: object) -> None:
    data = json.dumps(value, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        if path.read_text() != data:
            raise ValueError(f"conflicting existing file {path}")
    else:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(data)


def write_inputs(doc: Row, directory: Path = HERE) -> None:
    keys: Row = {}
    for cell_id, cell in doc["cells"].items():
        for task in cell["main"] + cell["held_out"]:
            key = task["key_id"]
            if key in keys:
                raise ValueError("duplicate key_id")
            keys[key] = {
                "expect": task["expect"],
                "decoys": task["decoys"],
                "world_key": "order.total_cents" if cell_id == "C0" else None,
            }
        if cell_id == "C0":
            continue
        for mode, sentence in (("naming", cell["sentence"]), ("generic", doc["generic_sentence"])):
            write_json(
                directory / "rules" / f"{cell_id}-{mode}.json",
                [
                    {
                        "tool": cell["tool"],
                        "is_error": cell["reply_is_error"],
                        "text_matches": cell["reply_pattern"],
                        "when": cell.get("sentence_when", {}),
                        "replace_text": sentence,
                    }
                ],
            )
    write_json(directory / "answer_key.json", keys)


def public_task(cell_id: str, task: Row) -> Row:
    public = {k: task[k] for k in ("key_id", "ask", "bad")}
    public.update(cell=cell_id, clean=task["good"][0])
    if cell_id == "C0":
        public["order_id"] = task["order_id"]
    return public


def study_path(path: Path, portable: bool) -> str:
    if portable and path.is_relative_to(HERE.parent):
        return str(path.relative_to(HERE.parent))
    return str(path)


def relay_argv(
    env: Path,
    fx: Path,
    cell: str,
    server: str,
    modes: list[str],
    edited: Path | None,
    inputs: Path = HERE,
    *,
    portable: bool = False,
) -> list[str]:
    py = str(env / "py/bin/python")
    entry = ["-m", "relay"] if portable else [str(HERE / "relay.py")]
    argv = [py, "-P", *entry, "--ledger"]
    small_env = {
        "HOME": str(env / "home"),
        "LC_ALL": "C",
        "TZ": "UTC",
        "PATH": "/opt/homebrew/bin:/usr/bin:/bin",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if server == "filesystem":
        node = str(registered_node(env))
        relative = "dist/index.js"
        package = env / "node/node_modules/@modelcontextprotocol/server-filesystem"
        command = [node, str(package / relative), str(fx / "files")]
        variant = (
            [node, study_path(edited / cell / "package" / relative, portable), str(fx / "files")]
            if edited
            else None
        )
    elif server == "git":
        small_env.update(
            GIT_CONFIG_GLOBAL="/dev/null", GIT_CONFIG_NOSYSTEM="1", GIT_OPTIONAL_LOCKS="0"
        )
        command = [py, "-P", "-m", "mcp_server_git", "--repository", str(fx / "repo")]
        variant = command if edited else None
        if edited:
            argv += ["--module-root", f"edited={study_path(edited / cell, portable)}"]
    elif server == "orderdesk":
        if edited:
            raise ValueError("orderdesk has no edited package")
        variant = None
        small_env["PYTHONPATH"] = study_path(HERE.parent / "orderdesk", portable)
        argv += ["--allow-tool", "lookup_order", "--allow-tool", "check_stock"]
        command = [
            py,
            "-P",
            "-m",
            "arci.mcp_toolset_server",
            "--toolset",
            "orderdesk_world:make_tools",
            "--workdir",
            "{workdir}",
            "--task-file",
            "{task_file}",
            "--seed",
            "{seed}",
            "--tools",
            "lookup_order,check_stock",
        ]
    else:
        raise ValueError("unknown server")
    for k, v in small_env.items():
        argv += ["--env", f"{k}={v}"]
    for mode in modes:
        argv += [
            "--rules",
            f"{mode}={study_path(inputs / 'rules' / f'{cell}-{mode}.json', portable)}",
        ]
    if variant:
        return [
            *argv,
            "--server",
            "shipped=" + json.dumps(command),
            "--server",
            "edited=" + json.dumps(variant),
        ]
    return [*argv, "--", *command]


def descriptor(
    doc: Row,
    env: Path,
    fx: Path,
    cell_id: str,
    phase: str,
    model: str,
    rows: list[Row],
    *,
    run: str,
    plain: bool,
    edited: Path | None = None,
    plans: tuple[Path | None, Path | None] = (None, None),
    prior_runs: tuple[str, ...] = (),
    fallback: bool = False,
) -> Row:
    cell = doc["cells"][cell_id]
    if model == "12B" and cell_id in ("G2", "F0"):
        raise ValueError("cell not registered on 12B")
    labels = ("naming-sentence", "reply-as-given")
    opening = "bad"
    modes = [] if cell_id == "C0" else ["naming"]
    if phase in ("clean", "unscripted"):
        if not plain or (phase == "unscripted" and cell_id not in ("G1", "F2", "F1")):
            raise ValueError("ineligible plain pair")
        labels = ("clean", "clean")
        opening = "clean" if phase == "clean" else "none"
        modes = []
    elif phase == "confirmation":
        if cell_id != "F1" or edited is None:
            raise ValueError("confirmation requires the F1 edited package")
        labels = ("edited-server", "server-as-shipped")
        modes = []
    elif phase == "generic":
        if cell_id == "C0":
            raise ValueError("C0 has no generic relay rewrite")
        labels = ("naming-sentence", "generic-sentence")
        modes = ["naming", "generic"]
    elif phase != "main":
        raise ValueError("unknown phase")
    if edited is not None and phase != "confirmation":
        raise ValueError("edited package requires confirmation")
    condition: Row = {"id": cell_id}
    if cell_id == "C0" and opening == "bad":
        condition["fault"] = cell["fault"]
    portable = all(plans)
    result: Row = {
        "oracle": "reply0_oracle:passed",
        "conditions": [condition],
        "prior_runs": list(prior_runs),
        "budgets": {"max_tool_calls": 12, "max_seconds": 120, "grader_seconds": 20},
        "mcp_server": {
            "name": "env",
            "argv": relay_argv(env, fx, cell_id, cell["server"], modes, edited, portable=portable),
            "snapshot": "reply0_oracle:snapshot",
        },
    }
    if plain:
        (one,) = rows
        result.update(
            experiment_id=run, task_id=one["id"], task=public_task(cell_id, one), n_per_arm=1
        )
    else:
        result.update(
            suite_id=run,
            tasks=[{"id": t["id"], **public_task(cell_id, t)} for t in rows],
            rule={
                "alpha": "1/20",
                "delta": "1/10",
                "stakes": ["1/4", "1/2"],
                "max_rounds": ROUNDS[len(rows)],
                "scenario_seeds": "per_round",
                "max_errored_pairs": 4,
            },
        )
    for side, label, plan in zip(("baseline", "candidate"), labels, plans, strict=True):
        argv = [
            str(env / "py/bin/python"),
            "-P",
            *(["-m", "agent"] if portable else [str(HERE / "agent.py")]),
            "--mcp-config",
            "{mcp_config}",
            "--task-file",
            "{task_file}",
            "--arm",
            label,
            "--opening",
            opening,
            "--model",
            MODELS[model],
            "--prompt",
            doc["system_prompt"],
            "--run-id",
            run,
        ]
        if cell_id == "C0" and opening == "bad":
            argv += ["--replace-empty-opening", cell["sentence"]]
            if fallback:
                argv.append("--empty-fallback-null")
        if plan:
            argv += ["--offline", study_path(plan, portable)]
        result[side] = {
            "label": label,
            "command": {
                "argv": argv,
                "infra_exit_codes": [70, 75],
                "env": {"REPLY0_ARCI_ARM": side},
            },
        }
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("env", type=Path)
    parser.add_argument("--fx", type=Path, default=FX)
    parser.add_argument("--inputs-only", action="store_true")
    parser.add_argument("--cell")
    parser.add_argument("--model", choices=MODELS)
    parser.add_argument("--phase", choices=PHASES)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--kept", type=Path)
    parser.add_argument("--task-id")
    parser.add_argument("--edited", type=Path)
    parser.add_argument("--prior-run", action="append", default=[])
    parser.add_argument("--offline-baseline", type=Path)
    parser.add_argument("--offline-candidate", type=Path)
    parser.add_argument("--empty-fallback-null", action="store_true")
    args = parser.parse_args()
    doc = register(args.fx.resolve(strict=True))
    write_inputs(doc)
    if args.inputs_only:
        return
    if not (args.phase and args.model and args.cell in doc["cells"] and args.out):
        parser.error("provide phase, model, cell and output descriptor")
    cell = doc["cells"][args.cell]
    part = "held_out" if args.phase == "confirmation" else "main"
    rows = cell[part]
    plain = args.phase in ("clean", "unscripted")
    if plain:
        if args.phase == "clean":
            rows = rows + cell["held_out"]
        rows = [row for row in rows if row["id"] == args.task_id]
        if len(rows) != 1:
            parser.error("plain pair requires one eligible --task-id")
    else:
        if not args.kept or args.task_id:
            parser.error("suite requires --kept")
        ids = json.loads(args.kept.read_bytes())[args.model][args.cell][part]["kept"]
        if not isinstance(ids, list) or len(set(ids)) != len(ids):
            parser.error("expected unique kept task ids")
        rows = [row for row in rows if row["id"] in ids]
        if len(rows) != len(ids) or len(rows) not in ROUNDS:
            parser.error("ineligible retained set")
    run = "-".join(
        ["reply0", args.phase, args.model, args.cell] + ([args.task_id] if plain else [])
    )
    plans = (args.offline_baseline, args.offline_candidate)
    if any(plans) and not all(plans):
        parser.error("an offline descriptor needs both plans")
    if all(plans):
        run += "-offline"
    config = descriptor(
        doc,
        args.env.resolve(),
        args.fx.resolve(),
        args.cell,
        args.phase,
        args.model,
        rows,
        run=run,
        plain=plain,
        edited=(args.edited or args.env / "edited").resolve()
        if args.phase == "confirmation"
        else None,
        plans=(plans[0].resolve() if plans[0] else None, plans[1].resolve() if plans[1] else None),
        prior_runs=tuple(args.prior_run),
        fallback=args.empty_fallback_null,
    )
    write_json(args.out, config)


if __name__ == "__main__":
    main()
