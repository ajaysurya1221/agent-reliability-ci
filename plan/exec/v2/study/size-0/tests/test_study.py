"""Acceptance checks with the repository pytest and the pinned Run 6 interpreter."""

import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from check_evidence import (  # noqa: E402
    PYTHON,
    inspect_claims,
    observation,
    receipt_map,
    validated_round,
)
from claims import board_idle, calendar, locks, prior_claims  # noqa: E402
from count_a import count as count_a  # noqa: E402
from count_b import count as count_b  # noqa: E402
from descriptors import REG, RUNS, Row, encoded, models, read  # noqa: E402
from report import interval, qualified_ids, render  # noqa: E402


def pinned(script: str, *args: Path | str, ok: bool = True) -> subprocess.CompletedProcess[str]:
    child = subprocess.run(
        [
            str(PYTHON),
            "-IB",
            "-c",
            "import sys; sys.path.insert(0,sys.argv.pop(1));" + script,
            str(ROOT),
            *map(str, args),
        ],
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    if ok:
        assert child.returncode == 0, child.stderr
    return child


def test_wire_identity(tmp_path: Path, frozen: Path) -> None:
    tmp_path = tmp_path / "wire"
    tmp_path.mkdir()
    child = subprocess.run(
        [str(PYTHON), "-IB", str(ROOT / "tests/request_probe.py"), str(tmp_path)],
        capture_output=True,
        stdin=subprocess.DEVNULL,
        text=True,
    )
    assert child.returncode == 0, child.stderr
    # Compare original serialized bytes, including object order, whitespace and text escaping.
    assert (tmp_path / "reference").read_bytes() == (tmp_path / "study").read_bytes()
    assert (tmp_path / "baseline").read_bytes() == (tmp_path / "reference").read_bytes()
    tags = {r["slot"]: r["tag"].encode() for r in read(ROOT / "models.example.json")["slots"]}
    assert (tmp_path / "anchor").read_bytes() == (tmp_path / "reference").read_bytes().replace(
        tags["q4"], tags["g12"], 1
    )
    expected = read(frozen / "prepared/size0-d1-q4-null.assignments.json")
    assert all(
        a["body_sha256"] == hashlib.sha256((tmp_path / "reference").read_bytes()).hexdigest()
        for a in expected
        if a["order_id"] == "ORD-103"
    )
    body = read(tmp_path / "study")
    assert len(body["messages"]) == 6 and body["messages"][-1]["content"] == "null"
    assert len(body["tools"]) == 4 and body["options"] == {"temperature": 0.7}
    assert body["think"] is False and body["stream"] is True


def test_unexposed_boundary_retry(tmp_path: Path) -> None:
    manifest = {"suite_id": RUNS[1], "tasks": [{"task_id": "id", "task": {"order_id": "A"}}]}
    (tmp_path / "manifest.json").write_bytes(encoded(manifest))
    audit = tmp_path / "audit"
    audit.touch()
    trials: list[Row] = []
    for i, scenario in enumerate(("right", "none", "wrong", "undelivered", "errored", "dropped")):
        start = {
            "tool": "lookup_order",
            "call_id": "b",
            "arguments": {"order_id": "A"},
            "occurrence": 0,
        }
        sequence: list[tuple[str, Row]] = [
            (
                "tool_start",
                {"tool": "check_stock", "call_id": "a", "arguments": {"sku": "A"}, "occurrence": 0},
            ),
            (
                "tool_finish",
                {
                    "tool": "check_stock",
                    "call_id": "a",
                    "ok": False,
                    "injected_by": None,
                    "error_kind": "error",
                },
            ),
            ("tool_start", start),
            (
                "tool_finish",
                {
                    "tool": "lookup_order",
                    "call_id": "b",
                    "ok": scenario != "undelivered",
                    "injected_by": "empty_result",
                    "value": None,
                },
            ),
            ("model_step", {}),
        ]
        if scenario != "none":
            sequence.append(
                (
                    "tool_start",
                    start
                    | {
                        "call_id": "c",
                        "occurrence": 1,
                        "arguments": {"order_id": "B" if scenario == "wrong" else "A"},
                    },
                )
            )
        if scenario == "errored":
            sequence = []
        tid = str(i)
        trials.append(
            {
                "trial_id": tid,
                "pair_id": "r000001:id:null",
                "seed": i,
                "final_state": None,
                "arm": ("candidate" if i % 2 else "baseline"),
                "task_id": "id",
                "condition_id": "empty_result",
                "contract": {"success": scenario in ("right", "wrong"), "grader_error": None},
                "events": [
                    {"kind": kind, "payload": p, "seq": seq, "trial_id": tid}
                    for seq, (kind, p) in enumerate(sequence)
                ],
                "recording": [
                    {"result": {"error_detail": "ValueError: unknown SKU", "injected_by": None}}
                ],
                "termination": "harness_error" if scenario == "errored" else "completed",
                "outcome": {"right": "PASS", "errored": "ERROR"}.get(scenario, "FAIL"),
            }
        )
    for filename, data in (
        ("trials", trials),
        ("events", [e for t in trials for e in t["events"]]),
    ):
        (tmp_path / (filename + ".jsonl")).write_text("".join(json.dumps(r) + "\n" for r in data))
    (tmp_path / "exchanges.jsonl").write_text(
        "".join(
            json.dumps(
                {
                    "run": RUNS[1],
                    "round": 1,
                    "order_id": "A",
                    "seed": i,
                    "arm": t["arm"],
                    "stream_completed": i != 5,
                    "incomplete_reason": None if i != 5 else "missing_terminal",
                }
            )
            + "\n"
            for i, t in enumerate(trials)
        )
    )
    a = count_a(tmp_path, audit)
    assert a == count_b(tmp_path, audit)
    p = a["pooled"]
    assert [
        p[k]
        for k in (
            "trials",
            "scripted_opening_recorded",
            "model_step_after_opening",
            "delivered",
            "read_again",
            "read_again_right_id",
            "passed",
            "errored",
        )
    ] == [6, 5, 4, 4, 2, 1, 1, 1]
    assert p["final_state_passes"] == 2
    assert p["terminations"] == {"harness_error": 1, "completed": 5}
    assert a["baseline"]["read_again"] == 2 and a["candidate"]["read_again"] == 0
    assert (p["exposed"], p["unexposed"], p["boundary_read_again"], p["unexposed_trials"]) == (
        3,
        1,
        3,
        ["5"],
    )
    trials[-1]["recording"].append(
        {"tool": "lookup_order", "occurrence": 0, "result": trials[-1]["events"][3]["payload"]}
    )
    assert observation(trials[-1], "A", False)["read_again"] == 0
    assert observation(trials[-1], "A", True)["read_again"] == 1
    audit.write_text("{}\n")
    for counter in (count_a, count_b):
        with pytest.raises(ValueError):
            counter(tmp_path, audit)


@pytest.fixture
def frozen(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("SIZE0_CLAIMS", str(tmp_path.resolve() / "claims"))
    copy = tmp_path.resolve() / "study"
    shutil.copytree(
        ROOT,
        copy,
        ignore=shutil.ignore_patterns("prepared", "claims", "__pycache__", "models.json"),
    )
    shutil.copyfile(copy / "models.example.json", copy / "models.json")
    pinned("from pathlib import Path; from freeze import prepare; prepare(Path(sys.argv[1]))", copy)
    return copy


@pytest.mark.parametrize(
    "name", [REG, "agent/tools.py", "models.json", "prepared/" + RUNS[-1] + ".yaml"]
)
def test_changed_inputs(frozen: Path, name: str) -> None:
    p = frozen / name
    p.write_bytes(p.read_bytes() + b" ")
    result = pinned(
        "from freeze import verify; from pathlib import Path; verify(Path(sys.argv[1]))",
        frozen,
        ok=False,
    )
    assert result.returncode and "digest" in result.stderr


def test_host_locks_and_claim_gap(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    board = tmp_path / "board"
    board.mkdir()
    monkeypatch.setattr("claims.BOARD", board)
    claims = tmp_path.resolve() / "claims"
    with locks(claims, real=True), pytest.raises(BlockingIOError), locks(claims, real=True):
        pass
    assert not list(board.iterdir())
    lock = board / "suite.lock"
    lock.write_bytes(b"retained")
    with lock.open("rb") as owner:
        fcntl.flock(owner, fcntl.LOCK_EX)
        with pytest.raises(BlockingIOError), locks(claims, real=True):
            pass
    assert lock.read_bytes() == b"retained"
    from processes import start_time

    (board / "active-suite.json").write_bytes(
        encoded(
            {"launcher": os.getpid(), "launcher_start_time": start_time(os.getpid()), "groups": []}
        )
    )
    with pytest.raises(ValueError, match="alive"):
        board_idle(board)
    (claims / RUNS[1]).mkdir()
    with pytest.raises(ValueError, match="missing earlier"):
        prior_claims(claims, RUNS)


def test_day_bindings() -> None:
    def start(run: str, day: int) -> Row:
        d = f"2020-01-{day:02d}"
        return dict(run=run, date=d, timezone="+0530", started_at=d + "T00:00:00+05:30")

    first = start(RUNS[0], 1)
    calendar([first, start(RUNS[1], 1), start(RUNS[8], 2)])
    for second in (start(RUNS[1], 2), start(RUNS[8], 1), start(RUNS[1], 1) | {"timezone": "+0000"}):
        with pytest.raises(ValueError):
            calendar([first, second])


def test_bound_receipts() -> None:
    a = dict(
        run=RUNS[1],
        round=1,
        order_id="ORD-103",
        arm="baseline",
        seed=42,
        body_sha256="a" * 64,
        trial_id="a",
    )
    b = a | dict(arm="candidate", trial_id="b")
    observed = dict(
        host="127.0.0.1",
        port=11434,
        path="/api/chat",
        method="POST",
        response_model="test",
        stream_completed=True,
        incomplete_reason=None,
        model_mismatch=False,
    )
    assert receipt_map([a | observed, b | observed], [a, b], "test") == {"a": True, "b": True}
    for changes in (
        {"arm": "baseline"},
        {"run": RUNS[0]},
        {"round": 2},
        {"order_id": "wrong"},
        {"host": "192.0.2.1"},
        {"port": 1234},
        {"body_sha256": "0" * 64},
        {"response_model": "wrong"},
        {"model_mismatch": True},
        {"stream_completed": 1},
    ):
        with pytest.raises(ValueError):
            receipt_map([a | observed, b | observed | changes], [a, b], "test")
    with pytest.raises(ValueError, match="missing"):
        receipt_map([a | observed], [a, b], "test")


def test_validated_round_prefix(frozen: Path) -> None:
    assignments = read(frozen / "prepared" / (RUNS[0] + ".assignments.json"))
    decision = dict(
        verdict="ERROR",
        history=[dict(round=1, verdict="ERROR", counts={"errored": 5})],
        stopped_at_round=0,
        reasons=["errored pairs exceed max_errored_pairs"],
    )
    assert validated_round(assignments[:16], assignments, decision) == 1
    for cut in (0, 1, 15, 17, 159):
        with pytest.raises(ValueError, match="incomplete rounds"):
            validated_round(assignments[:cut], assignments, decision)
    with pytest.raises(ValueError, match="prefix"):
        validated_round([assignments[1], *assignments[1:16]], assignments, decision)
    with pytest.raises(ValueError, match="stopping"):
        validated_round(
            assignments[:16], assignments, decision | {"reasons": ["stopped without a decision"]}
        )


def test_stale_counts_and_mode(frozen: Path) -> None:
    claims = frozen / "claims"
    work = claims / RUNS[0]
    work.mkdir(parents=True)
    (work / "counts.json").write_text('{"pooled": {}}')
    status, verified = inspect_claims(frozen, claims, True)
    assert len(status) == 14 and status[RUNS[0]] == "interrupted" and len(verified) == 0
    assert render(status, verified, True).splitlines()[:2] == ["rehearsal", "partial"]
    (work / "started.json").write_bytes(encoded({"mode": "real", "run": RUNS[0]}))
    with pytest.raises(ValueError, match="mode"):
        inspect_claims(frozen, claims, True)


def test_duplicate_digest_and_identity_change(frozen: Path) -> None:
    from identity import inspect_model, validate

    model = models(frozen)["q4"]
    expected = inspect_model(frozen, model, True)
    validate(frozen, model, expected)
    for k in (
        "digest",
        "loaded_digest",
        "size",
        "quantization",
        "context",
        "loaded_context",
        "family",
        "format",
        "ollama",
    ):
        with pytest.raises(ValueError, match=k):
            validate(frozen, model, expected | {k: "wrong"})
    config = read(frozen / "models.json")
    config["slots"][0]["digest"] = config["slots"][1]["digest"]
    (frozen / "models.json").write_bytes(encoded(config))
    with pytest.raises(ValueError, match="distinct"):
        models(frozen)


def test_report_numbers() -> None:
    run = RUNS[1]
    by = {
        str(i): dict(
            trials=20,
            final_state_passes=10 if i < 6 else 9,
            delivered=11,
            exposed=10,
            read_again=2,
            read_again_right_id=1,
        )
        for i in range(8)
    }
    data = {k: sum(r[k] for r in by.values()) for k in by["0"]} | {
        "by_order": by,
        "unexposed": 8,
        "unexposed_trials": [],
        "unexposed_details": {},
    }
    assert qualified_ids(data) == 6
    data.update(passes_read_again=7, passes_no_read_again=6, passes_unexposed=0)
    verified = {
        run: dict(counts={"pooled": data}, model={"tag": "fixture"}, round=10, verdict="PASS")
    }
    row = render(dict.fromkeys(RUNS, "not started") | {run: "finished"}, verified, False)
    assert "88\t80\t8\t16/80\t20.0" in row
    assert interval(0, 0) is None
    assert interval(5, 10) == pytest.approx((0.1870860284, 0.8129139716))
    assert interval(0, 10) == pytest.approx((0, 1 - 0.025**0.1))
    assert interval(10, 10) == pytest.approx((0.025**0.1, 1))


def test_compiler_and_seeds(frozen: Path) -> None:
    script = """
from pathlib import Path
import json
from arci.descriptor import compile_run_descriptor, loads_suite_descriptor, DescriptorError
from arci.suite_schedule import build_suite_round
root=Path(sys.argv[1])/"prepared"
schedules=[]
for run in ("size0-d1-q2-null","size0-d1-q4-null","size0-d2-q2-null"):
    path=root/(run+".yaml")
    manifest=compile_run_descriptor(path)
    assert manifest.max_rounds == 10
    specs=build_suite_round(manifest,1)
    assert all(a.seed==b.seed for a,b in zip(specs[::2],specs[1::2],strict=True))
    schedules.append({s.task_id:s.seed for s in specs})
assert schedules[0].keys()==schedules[1].keys()==schedules[2].keys()
assert len(set.union(*(set(s.values()) for s in schedules)))==24
data=json.loads(path.read_bytes())
data["rule"]["max_rounds"]=9
try:
    loads_suite_descriptor(json.dumps(data))
except DescriptorError as exc:
    assert "budget cannot establish PASS for a candidate that never differs" in str(exc)
else:
    raise AssertionError("9 rounds admitted")
"""
    pinned(script, frozen)


def test_registration_and_regeneration(frozen: Path) -> None:
    script = """
from pathlib import Path
from unittest.mock import patch
from descriptors import REG,RUNS,read,encoded
from freeze import published,verify,sha
from claims import claims_dir
root=Path(sys.argv[1])
claims=claims_dir()
claims.mkdir()
ref="a"*40
def git(argv,**kwargs):
    if argv[-1]=="--git-common-dir": return str(root/".git").encode()
    if argv[-1]=="--show-toplevel": return str(root).encode()
    if "merge-base" in argv: return ref.encode()
    assert argv[-1].startswith(ref+":")
    return (root/argv[-1].split(":",1)[1]).read_bytes()
registration=(root/REG).read_bytes()
(root/REG).write_text("PLACEHOLDER, not a registration")
with patch("freeze.subprocess.check_output",git):
    for receipt,error in [("","invalid push"),(ref+" refs/heads/main","invalid push"),
                           (ref+" refs/heads/v2/phase0","placeholder")]:
        (claims/"push-receipt.txt").write_text(receipt)
        try: published(root)
        except ValueError as e: assert error in str(e)
        else: raise AssertionError("bad registration accepted")
    (root/REG).write_bytes(registration)
    assert published(root)==ref
    (root/"agent/__pycache__").mkdir()
    try: published(root)
    except ValueError as e: assert "bytecode" in str(e)
    else: raise AssertionError("stale bytecode accepted")
path=root/"prepared"/(RUNS[0]+".yaml")
path.write_bytes(path.read_bytes()+b" ")
pins=root/"prepared/descriptors.json"
data=read(pins)
data[path.name]["sha256"]=sha(path.read_bytes())
pins.write_bytes(encoded(data))
try: verify(root)
except ValueError as e: assert "regenerated descriptor" in str(e)
else: raise AssertionError("stale descriptor accepted")
"""
    pinned(script, frozen)


def test_injection_and_snapshot() -> None:
    path = next((ROOT.parent / "runs-run-6").glob("*/trials.jsonl"))
    t = json.loads(path.read_text().splitlines()[0])
    oid = t["final_state"]["state"]["order_id"]
    assert observation(t, oid, True)["passes_read_again"] == 1
    t["final_state"]["state"]["order"]["notes"] = []
    with pytest.raises(ValueError, match="snapshot"):
        observation(t, oid, True)
    injection = next(e for e in t["events"] if e["payload"].get("injected_by"))
    t["events"].append(injection)
    with pytest.raises(ValueError, match="injection"):
        observation(t, oid, True)
    t["condition_id"] = "clean"
    with pytest.raises(ValueError, match="injection"):
        observation(t, oid, True)


def test_exclusive_stream_log(tmp_path: Path) -> None:
    from execution import execute

    arg = [
        sys.executable,
        "-IB",
        "-c",
        "import sys;print('partial output',file=sys.stderr);sys.exit(3)",
    ]
    assert execute(tmp_path, arg, ()) == 3
    record = read(tmp_path / "execution.json")
    assert record["exit_code"] == 3 and record["started_at"] <= record["ended_at"]
    assert (tmp_path / "arci.log").read_bytes() == b"partial output\n"
    with pytest.raises(FileExistsError):
        execute(tmp_path, arg, ())


def test_first_response_cold_timing(frozen: Path) -> None:
    preflight_client(frozen, "missing")


def test_preflight_native_client_without_socket(frozen: Path) -> None:
    preflight_client(frozen, "reported")


def preflight_client(frozen: Path, timing: str) -> None:
    # The actual pinned serializer and tool-call parser run on a mock HTTPX transport.
    script = """
from pathlib import Path
from unittest.mock import patch
import httpx,json,re
from langchain.chat_models import init_chat_model
from preflight import preflight,validate_pin
from descriptors import read,models
from identity import inspect_model
root=Path(sys.argv[1])
model=models(root)["q2"]
ident=inspect_model(root,model,True)
clock=[0.]
counter=0
def respond(req):
    global counter
    body=json.loads(req.content)
    assert body["model"]==model["tag"] and body["options"]=={"temperature":0.7}
    assert body["stream"] is True and body["think"] is False
    msg=body["messages"][-1]
    assistant={"role":"assistant","content":""}
    if msg["role"]=="user":
        counter+=1
        if counter!=2:
            pebble=msg["content"].rstrip("?").split()[-1]
            assistant["tool_calls"]=[{"function":{"name":"read_pebble","arguments":{"pebble":pebble}}}]
        else: assistant["tool_calls"]=[{"function":{"name":"read_pebble","arguments":7}}]
    else:
        token=msg["content"]
        assert re.fullmatch("[0-9a-f]{24}",token)
        assert token not in json.dumps(body["messages"][:-1])
        assistant["content"]=token
    assistant["thinking"]="test-only"
    frame=dict(model=model["tag"],done=True,message=assistant,load_duration=100000000)
    if sys.argv[2]=="missing" and counter==1 and msg["role"]=="user":
        del frame["load_duration"]
        clock[0]+=7
    else:
        clock[0]+=41
    return httpx.Response(200,json=frame)
def build(*args,**kwargs):
    assert kwargs["sync_client_kwargs"]["follow_redirects"] is False
    kwargs["sync_client_kwargs"]["transport"]=httpx.MockTransport(respond)
    return init_chat_model(*args,**kwargs)
initial=ident|dict(loaded_context=None,loaded_digest=None)
with (patch("langchain.chat_models.init_chat_model",build),
      patch("agent_hooks.monotonic",lambda:clock[0],create=True),
      patch("preflight.inspect_model",side_effect=[initial]+[ident]*5)):
    preflight(root,root,model,"rehearsal","rehearsal")
from preflight import latest_pin,history_dir
record=latest_pin(root,"q2","rehearsal")
with (patch("langchain.chat_models.init_chat_model",build),
      patch("preflight.inspect_model",return_value=ident)):
    preflight(root,root,model,"rehearsal","rehearsal")
attempts=[read(p) for p in sorted(history_dir(root,"q2","rehearsal").glob("*.json"))]
assert len(attempts)==2 and attempts[0]==record
assert attempts[0]["cold"] and not attempts[1]["cold"] and attempts[1]["cold_load_seconds"] is None
assert validate_pin(root,model,record,"rehearsal","rehearsal")==ident
if sys.argv[2]=="missing":
    assert record["cold_load_seconds"]==7, record["cold_load_seconds"]
    assert record["load_duration_missing"] is record["probes"][0]["load_duration_missing"] is True
else:
    assert record["cold_load_seconds"]==0.1
assert [r["parser_error"] for r in record["probes"]]==[False,True,False,False,False]
assert [r["native_call"] for r in record["probes"]]==[True,False,True,True,True]
assert all(r["token_repeated"]==r["native_call"] and r["thinking"] for r in record["probes"])
record["probes"][-1]["identity"]["template_sha256"]="a"*64
try: validate_pin(root,model,record,"rehearsal","rehearsal")
except ValueError as e: assert "identity" in str(e)
else: raise AssertionError("changed template accepted")
"""
    pinned(script, frozen, timing)


def test_durable_incomplete_stream(tmp_path: Path) -> None:
    script = """
from pathlib import Path
import sys,json,os,httpx
root=Path(sys.path[0])
sys.path.insert(0,str(root/"agent"))
from exposure import FirstExchange
work=Path(sys.argv[1])
binding=dict(run="r",round=1,seed=1,order_id="o",arm="baseline")
path=work/"assignments"
path.write_text(json.dumps([binding]))
os.environ.update(SIZE0_RUN="r",SIZE0_ASSIGNMENTS=str(path),SIZE0_TAG="fixture")
observer=FirstExchange(str(work),{"order_id":"o"},1,"baseline")
req=httpx.Request("POST","http://127.0.0.1:11434/api/chat",content=b"body")
observer.on_request(req)
# No handler return or clean shutdown is required to preserve the first request.
saved=lambda:json.loads(next(work.glob("*.json")).read_bytes())
assert saved()["stream_completed"] is False and saved()["body_sha256"]
frame={"model":"wrong","message":{"role":"assistant"},"done":False}
response=httpx.Response(200,request=req,json=frame)
observer.on_response(response)
list(response.iter_lines())
assert saved()["response_model"]=="wrong" and saved()["model_mismatch"]
assert saved()["stream_completed"] is False
"""
    pinned(script, tmp_path)


def test_exact_published_fields() -> None:
    from check_evidence import compare_counts

    good = {
        "pooled": {
            "by_order": {"ORD-103": {"read_again": 1, "passes_read_again": 1}},
            "terminations": {"completed": 1},
        }
    }
    for changed in (
        {"pooled": {}},
        {"pooled": good["pooled"] | {"extra": 1}},
        {"pooled": good["pooled"] | {"by_order": {}}},
        {"pooled": good["pooled"] | {"terminations": {"completed": True}}},
    ):
        with pytest.raises(ValueError, match="counts/pooled"):
            compare_counts(good, changed)


def test_guard_real_predecessor_and_calendar(tmp_path: Path) -> None:
    script = """
from datetime import date
from pathlib import Path
from unittest.mock import patch
from launcher import guard
from descriptors import RUNS,encoded
claims=Path(sys.argv[1])
first=dict(run=RUNS[0],started_at="2020-01-01T12:00:00+05:30",date="2020-01-01",timezone="+0530",
           mode="real",registration="a"*40,inputs_sha256="freeze",descriptors_sha256="schedule")
guard(claims,RUNS[0],RUNS,first)
(claims/RUNS[0]).mkdir()
prior=claims/RUNS[0]/"started.json"
(claims/RUNS[0]/"finished.json").write_text("{}")
second=first|dict(run=RUNS[1])
with patch("launcher.finish_record",return_value={}):
    for saved, proposed, error in [
        (first|dict(mode="rehearsal"),second,"mode"),
        (first,second|dict(date="2020-01-02",started_at="2020-01-02T12:00:00+05:30"),"spans"),
        (first,first,"permanent claim")]:
        prior.write_bytes(encoded(saved))
        try: guard(claims,proposed["run"],RUNS,proposed)
        except ValueError as e: assert error in str(e)
        else: raise AssertionError("invalid admission")
    prior.write_bytes(encoded(first))
    guard(claims,RUNS[1],RUNS,second)
assert not (claims/RUNS[1]).exists()
"""
    pinned(script, tmp_path)


@pytest.mark.parametrize("scenario", ["multi", "malformed", "server_error", "transport_error"])
def test_wire_before_parsing(tmp_path: Path, scenario: str) -> None:
    pinned(
        """
from pathlib import Path
import os,json,httpx
from ollama import Client
sys.path.insert(0,str(Path(sys.path[0])/"agent"))
from exposure import FirstExchange
from check_evidence import receipt_map
work=Path(sys.argv[1])
case=sys.argv[2]
binding=dict(run="r",round=1,seed=17,order_id="o",arm="baseline")
(work/"assignments").write_text(json.dumps([binding]))
os.environ.update(SIZE0_RUN="r",SIZE0_ASSIGNMENTS=str(work/"assignments"),SIZE0_TAG="fixture")
observer=FirstExchange(str(work),{"order_id":"o"},17,"baseline")
class Frames(httpx.SyncByteStream):
    def __iter__(self):
        frame={"model":"fixture","message":{"role":"assistant","content":""}}
        if case=="malformed":
            frame["message"]["tool_calls"]=[{"function":{"name":"bad","arguments":7}}]
        if case=="multi": frame.pop("model")
        yield json.dumps(frame).encode()+b"\\n"
        if case=="transport_error": raise httpx.ReadError("fixture disconnect")
        final={"error":"backend stopped"} if case=="server_error" else {
            "model":"fixture","message":{"role":"assistant","content":"end"},"done":True}
        yield json.dumps(final).encode()+b"\\n"
client=Client(host="http://127.0.0.1:11434",transport=httpx.MockTransport(
    lambda request:httpx.Response(200,stream=Frames())),event_hooks={
    "request":[observer.on_request],"response":[observer.on_response]})
try:
    answer=list(client.chat(model="fixture",messages=[],stream=True))
except Exception as e:
    assert case!="multi"
    if case=="malformed": assert "arguments" in str(e)
else:
    assert case=="multi" and answer[-1].done
r=json.loads(next(work.glob("*.json")).read_bytes())
done=case in ("multi","malformed")
assert r["stream_completed"] is done and r["incomplete_reason"]==(None if done else case)
assert r["response_model"]=="fixture" and not r["model_mismatch"]
assignment=binding|{"body_sha256":r["body_sha256"],"trial_id":"trial"}
assert receipt_map([r],[assignment],"fixture")=={"trial":done}
""",
        tmp_path,
        scenario,
    )


def test_unreadable_claim_and_partial_table(frozen: Path) -> None:
    claims = frozen / "claims"
    work = claims / RUNS[0]
    work.mkdir(parents=True)
    (work / "started.json").write_text("{")
    (claims / RUNS[1]).mkdir()
    status, verified = inspect_claims(frozen, claims, True)
    assert status[RUNS[0]] == "unreadable" and status[RUNS[1]] == "interrupted"
    table = render(status, verified, True)
    assert "starts accounted for: 2/14" in table and "verified rows: 0/14" in table
    table = render(dict.fromkeys(RUNS, "interrupted"), {}, False)
    assert "partial" in table and "starts accounted for: 14/14" in table


def test_registered_slot_ranges(frozen: Path) -> None:
    from descriptors import validate_slot
    from identity import validate

    path = frozen / "models.json"
    roster = read(path)
    q2, q4, q9, _ = roster["slots"]
    q2["slot"], q9["slot"] = q9["slot"], q2["slot"]
    path.write_bytes(encoded(roster))
    with pytest.raises(ValueError, match="size"):
        models(frozen)
    q2["slot"], q9["slot"] = q9["slot"], q2["slot"]
    q4["quantization"] = "different"
    path.write_bytes(encoded(roster))
    with pytest.raises(ValueError, match="quantization"):
        models(frozen)
    for size in ("3.0B", "6B", "4.7B"):
        validate_slot(frozen, "q4", {"family": "Qwen3", "size": size})
    with pytest.raises(ValueError, match="family"):
        validate_slot(frozen, "q4", {"family": "other", "size": "4.7B"})
    # This time swap only the tags: the roster's claimed sizes remain plausible.
    sys.path.insert(0, str(ROOT / "tests"))
    from fake_ollama import installed
    from identity import expected

    wrong = q2 | {"tag": q9["tag"]}
    actual = expected(frozen, wrong) | installed()[wrong["tag"]] | {"template_sha256": "a" * 64}
    with pytest.raises(ValueError, match=r"digest|size"):
        validate(frozen, wrong, actual)
    assert "slots.json" in read(frozen / "prepared/inputs.json")


def test_recycled_pid_and_legacy_command(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from processes import group_alive

    pid = os.getpid()
    claim = "board0-example"
    path = tmp_path / "active-suite.json"
    path.write_bytes(encoded(dict(launcher=pid, claim=claim, groups=[], launcher_start_time="old")))
    board_idle(tmp_path)
    assert not group_alive(pid, "old")
    path.write_bytes(encoded(dict(launcher=pid, claim=claim, groups=[])))

    def command(line: str) -> None:
        def ps(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(["ps"], 0, line)

        monkeypatch.setattr("claims.subprocess.run", ps)

    command("python unrelated.py")
    board_idle(tmp_path)
    command(f"python -PB harness/launcher.py real {claim}")
    with pytest.raises(ValueError, match="alive"):
        board_idle(tmp_path)


@pytest.mark.parametrize(("term", "done"), [("timeout", False), ("crash", True)])
def test_honest_worker_loss(term: str, done: bool) -> None:
    t = json.loads(
        next((ROOT.parent / "runs-run-6").glob("*/trials.jsonl")).read_text().splitlines()[0]
    )
    oid = t["final_state"]["state"]["order_id"]
    t.update(termination=term, outcome="FAIL", contract={"success": False, "grader_error": None})
    if term == "timeout":
        t.update(recording=[], final_state=None, events=t["events"][:6])
    obs = observation(t, oid, done)
    assert (obs["delivered"], obs["exposed"], obs["unexposed"], obs["final_state_passes"]) == (
        1,
        int(done),
        int(not done),
        0,
    )
    if term == "timeout":
        t["events"][3]["payload"]["occurrence"] = 1
        with pytest.raises(ValueError, match="injection"):
            observation(t, oid, done)


@pytest.mark.parametrize("module", ["count_a", "count_b"])
@pytest.mark.parametrize("n", [0, 2])
def test_standalone_receipt_cardinality(tmp_path: Path, module: str, n: int) -> None:
    t = json.loads(
        next((ROOT.parent / "runs-run-6").glob("*/trials.jsonl")).read_text().splitlines()[0]
    )
    oid = t["final_state"]["state"]["order_id"]
    (tmp_path / "trials.jsonl").write_text(json.dumps(t) + "\n")
    (tmp_path / "events.jsonl").write_text("".join(json.dumps(e) + "\n" for e in t["events"]))
    (tmp_path / "manifest.json").write_bytes(
        encoded(
            dict(suite_id="fixture", tasks=[dict(task_id=t["task_id"], task={"order_id": oid})])
        )
    )
    receipt = dict(
        run="fixture", round=1, order_id=oid, arm=t["arm"], seed=t["seed"], stream_completed=False
    )
    (tmp_path / "exchanges.jsonl").write_text((json.dumps(receipt) + "\n") * n)
    audit = tmp_path / "audit"
    audit.touch()
    result = subprocess.run(
        [sys.executable, "-B", str(ROOT / (module + ".py")), str(tmp_path), "--audit", str(audit)],
        capture_output=True,
        text=True,
    )
    assert (
        result.returncode
        and ("duplicate" if n else "missing") + " receipt for " + t["trial_id"] in result.stderr
    )


def test_worker_parent_death_retains_locks(frozen: Path, tmp_path: Path) -> None:
    import signal
    import time

    from processes import group_alive

    # A blocking in-process transport gives us a known live worker without a socket.
    (frozen / "agent/standin.py").write_text("""
import os,time,httpx
from pathlib import Path
def transport():
    def hold(req):
        Path(os.environ['HOLD_MARK']).touch()
        time.sleep(75)
        raise RuntimeError('hold expired')
    return httpx.MockTransport(hold)
""")
    work = tmp_path / "interrupted"
    work.mkdir()
    (work / "receipts").mkdir()
    run = RUNS[0]
    locks_paths = [tmp_path / "size.lock", tmp_path / "board.lock"]
    handles = [p.open("ab") for p in locks_paths]
    for handle in handles:
        fcntl.flock(handle, fcntl.LOCK_EX)
    fds = tuple(h.fileno() for h in handles)
    mark = work / "in-chat"
    env = os.environ | dict(
        SIZE0_LOCKS=",".join(map(str, fds)),
        HOLD_MARK=str(mark),
        SIZE0_RUN=run,
        SIZE0_CONDITION="clean",
        SIZE0_TAG=models(frozen)["q2"]["tag"],
        SIZE0_TRANSPORT="offline",
        PYTHONDONTWRITEBYTECODE="1",
        LANGSMITH_TRACING="false",
        LANGCHAIN_TRACING_V2="false",
        SIZE0_ASSIGNMENTS=str(frozen / "prepared" / (run + ".assignments.json")),
        ORDER_DESK_FIRST_EXCHANGE_AUDIT=str(work / "receipts"),
    )
    with subprocess.Popen(
        [
            str(PYTHON),
            "-IB",
            str(ROOT / "execution.py"),
            str(work),
            "run",
            str(frozen / "prepared" / (run + ".yaml")),
            "--out",
            str(work / "store"),
            "--workers",
            "1",
        ],
        env=env,
        cwd=frozen / "agent",
        pass_fds=fds,
    ) as supervisor:
        for handle in handles:
            handle.close()
        try:
            end = time.monotonic() + 35
            while not mark.exists() and supervisor.poll() is None and time.monotonic() < end:
                time.sleep(0.05)
            assert mark.exists(), (work / "arci.log").read_text()
            assert (work / "arci.log").stat().st_size
            (group,) = [read(p) for p in (work / "groups").glob("*.json")]
            assert group_alive(group["pid"], group["start_time"])
            for p in locks_paths:
                with p.open("rb") as handle, pytest.raises(BlockingIOError):
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
            os.kill(read(work / "execution.json")["pid"], signal.SIGKILL)
            assert supervisor.wait(timeout=20) != 0
            assert read(work / "execution.json")["status"] == "interrupted, worker survived"
            assert not group_alive(group["pid"], group["start_time"])
            for p in locks_paths:
                with p.open("rb") as handle:
                    fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        finally:
            if supervisor.poll() is None and (work / "execution.json").exists():
                execution = read(work / "execution.json")
                from processes import start_time

                if execution["pid"] and start_time(execution["pid"]) == execution["start_time"]:
                    os.kill(execution["pid"], signal.SIGKILL)


def test_list_midnight_estimate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SIZE0_CLAIMS", str(tmp_path))
    (tmp_path / RUNS[0]).mkdir()
    result = pinned("import launcher; sys.argv=['launcher','list']; launcher.main()")
    assert "d1: 7 starts remaining" in result.stdout and "local midnight" in result.stdout


def test_atomic_claim_write(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from records import atomic_json

    path = tmp_path / "started.json"
    atomic_json(path, {"version": 1})

    def fail_flush(fd: int) -> None:
        assert os.fstat(fd).st_size > 0
        assert read(path) == {"version": 1}
        raise OSError("simulated fsync failure")

    monkeypatch.setattr(os, "fsync", fail_flush)
    with pytest.raises(OSError, match="fsync failure"):
        atomic_json(path, {"version": 2})
    assert read(path) == {"version": 1} and list(tmp_path.iterdir()) == [path]


def test_sealed_crash_counts(frozen: Path, tmp_path: Path) -> None:
    result = subprocess.run(
        [
            str(PYTHON),
            "-IB",
            str(ROOT / "tests/crash_probe.py"),
            str(frozen),
            str(tmp_path / "crashes"),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def test_group_probe_permission_keeps_lock(monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import Mock

    from processes import group_alive

    monkeypatch.setattr("processes.start_time", Mock(return_value=None))
    probe = Mock(side_effect=[PermissionError(), ProcessLookupError()])
    monkeypatch.setattr("processes.os.killpg", probe)
    assert group_alive(1234, "registered")
    assert not group_alive(1234, "registered")


def receipt_trial(frozen: Path, work: Path, case: str) -> tuple[Row, Row]:
    child = subprocess.run(
        [str(PYTHON), "-IB", str(ROOT / "tests/receipt_probe.py"), str(frozen), str(work), case],
        capture_output=True,
        text=True,
    )
    assert child.returncode == 0, child.stderr
    return read(work / "trials.jsonl"), read(work / "exchanges.jsonl")


def test_lost_completion(frozen: Path, tmp_path: Path) -> None:
    trial, receipt = receipt_trial(frozen, tmp_path, "lost")
    assert "SIZE_ZERO_RECEIPT_LOST" in trial["failure_detail"]
    assert receipt["response_model"] == models(frozen)["q2"]["tag"]
    assert receipt["incomplete_reason"] == "incomplete_stream"
    audit = tmp_path / "replacement.jsonl"
    audit.touch()
    for counter in (count_a, count_b):
        with pytest.raises(ValueError, match="receipt lost.*" + trial["trial_id"]):
            counter(tmp_path, audit)
    with pytest.raises(ValueError, match="receipt lost") as error:
        observation(trial, "A", False)
    claims = frozen / "claims"
    for run in RUNS[:2]:
        work = claims / run
        work.mkdir(parents=True)
        (work / "started.json").write_bytes(
            encoded(
                dict(
                    run=run,
                    mode="rehearsal",
                    started_at="2000-01-01T00:00:00+00:00",
                    date="2000-01-01",
                    timezone="+0000",
                )
            )
        )
    (claims / RUNS[1] / "refused.json").write_bytes(encoded({"reason": str(error.value)}))
    status, counts = inspect_claims(frozen, claims, True)
    report = render(status, counts, True)
    assert any(RUNS[1] in line and "receipt lost" in line for line in report.splitlines())
    assert "\tnull\t" not in report


def test_preheader_timeout(frozen: Path, tmp_path: Path) -> None:
    _, receipt = receipt_trial(frozen, tmp_path, "timeout")
    assert receipt["incomplete_reason"] == "no_response_headers"


def test_board_worker_after_exec(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import Mock

    record = {"launcher": 777, "groups": [888], "claim": "board0-test"}
    (tmp_path / "active-suite.json").write_bytes(encoded(record))
    monkeypatch.setattr("claims.start_time", Mock(return_value=None))
    ps = Mock(
        return_value=subprocess.CompletedProcess(["ps"], 0, "888 S python -P -m arci.worker\n")
    )
    monkeypatch.setattr("claims.subprocess.run", ps)
    with pytest.raises(ValueError, match="Board-0 suite process alive"):
        board_idle(tmp_path)
    ps.return_value.stdout = "888 S unrelated\n889 S python -P -m arci.worker\n888 Z arci\n"
    board_idle(tmp_path)


def test_grader_error_after_worker_loss() -> None:
    t = json.loads(
        next((ROOT.parent / "runs-run-6").glob("*/trials.jsonl")).read_text().splitlines()[0]
    )
    oid = t["final_state"]["state"]["order_id"]
    t.update(
        termination="grader_error",
        outcome="ERROR",
        final_state=None,
        recording=[],
        agent_claimed_success=None,
        events=t["events"][:6],
        contract={"success": False, "grader_error": "grader exited"},
    )
    counts = observation(t, oid, False)
    assert counts["delivered"] == counts["unexposed"] == counts["errored"] == 1
    t["events"][3]["payload"]["occurrence"] = 1
    with pytest.raises(ValueError, match="wrong injection"):
        observation(t, oid, False)


def test_date_unverified_after_torn_start(frozen: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from unittest.mock import Mock

    claims = frozen / "claims"
    first, second = [claims / run for run in RUNS[:2]]
    for folder in (first, second):
        folder.mkdir(parents=True)
        (folder / "finished.json").write_text("{}")
    (first / "started.json").write_text("{")
    (second / "started.json").write_bytes(
        encoded(
            dict(
                run=second.name,
                mode="rehearsal",
                started_at="2000-01-01T00:00:00+00:00",
                date="2000-01-01",
                timezone="+0000",
            )
        )
    )
    pooled = dict.fromkeys(
        (
            "trials",
            "final_state_passes",
            "delivered",
            "exposed",
            "unexposed",
            "read_again",
            "passes_read_again",
            "passes_no_read_again",
            "passes_unexposed",
            "read_again_right_id",
        ),
        0,
    )
    data = dict(
        counts={
            "pooled": pooled
            | dict(trials=16, exposed=12, read_again=3, by_order={}, unexposed_details={})
        },
        model={"tag": "fixture"},
        round=1,
        verdict="ERROR",
    )
    monkeypatch.setattr("check_evidence.finish_record", Mock(return_value={}))
    monkeypatch.setattr("check_evidence.check_run", Mock(return_value=data))
    statuses, counts = inspect_claims(frozen, claims, True)
    assert statuses[first.name] == "unreadable" and statuses[second.name] == "date unverified"
    report = render(statuses, counts, True)
    assert (
        first.name + "\tunreadable" in report
        and "partial" in report
        and "verified rows: 0/14" in report
    )
    line = next(line for line in report.splitlines() if "\tfixture\tnull\t" in line)
    assert "3/12" in line and "date unverified" in line
