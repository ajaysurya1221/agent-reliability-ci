"""Execute suites in balanced rounds, with one adjacent pair per worker slot."""

from __future__ import annotations

import sys
import threading
from collections.abc import Sequence
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from arci.contracts import validate_contract
from arci.runner import run_trial
from arci.schema import Event, TrialEnvelope, TrialSpec, Verdict
from arci.suite_gate import decide_suite, evaluate_rounds
from arci.suite_schedule import arm_order, build_suite_round, suite_rule_sha256
from arci.suite_schema import SuiteManifest
from arci.suite_stats import check_suite_plan
from arci.suite_storage import SuiteStore, validate_suite_manifest


def run_suite(
    manifest: SuiteManifest,
    out_dir: Path | str,
    *,
    workers: int = 4,
    extra_pythonpath: Sequence[str] = (),
) -> tuple[TrialEnvelope, ...]:
    """Store ordinary v1 envelopes in schedule order and write the sealed suite decision.

    Normal rounds are buffered until all pairs finish. On a handled interruption, preserve
    every completed trial and observed event after draining active pairs;
    the partial store cannot produce a valid gate verdict. There is no retry or resume.
    """
    if type(workers) is not int or workers < 1:
        raise ValueError("workers must be a positive integer")
    manifest = validate_suite_manifest(manifest)
    validate_contract(manifest.contract)
    for warning in check_suite_plan(manifest):
        print(warning, file=sys.stderr)
    store = SuiteStore(out_dir, manifest)
    rule_digest = suite_rule_sha256(manifest)
    trials: list[TrialEnvelope] = []
    lock = threading.Lock()
    stopped = threading.Event()

    with ThreadPoolExecutor(max_workers=workers) as executor:
        for round_number in range(1, manifest.max_rounds + 1):
            schedule = build_suite_round(manifest, round_number)
            completed: dict[str, TrialEnvelope] = {}
            observed: dict[str, list[Event]] = {}

            def run_pair(
                index: int,
                pair: tuple[TrialSpec, TrialSpec],
                round_number: int = round_number,
                completed: dict[str, TrialEnvelope] = completed,
                observed: dict[str, list[Event]] = observed,
            ) -> None:
                if stopped.is_set():
                    return
                by_arm = {spec.arm: spec for spec in pair}
                try:
                    for arm in arm_order(rule_digest, index, round_number):
                        spec = by_arm[arm]

                        def emit(event: Event) -> None:
                            with lock:
                                observed.setdefault(event.trial_id, []).append(event)

                        trial = run_trial(
                            spec, emit, manifest.contract, extra_pythonpath=extra_pythonpath
                        )
                        with lock:
                            completed[spec.trial_id] = trial
                except BaseException:
                    # Stop queued pairs immediately, even before the parent sees this future.
                    stopped.set()
                    raise

            def append_round(
                schedule: tuple[TrialSpec, ...] = schedule,
                completed: dict[str, TrialEnvelope] = completed,
                observed: dict[str, list[Event]] = observed,
                round_number: int = round_number,
            ) -> list[TrialEnvelope]:
                results = [
                    completed[spec.trial_id] for spec in schedule if spec.trial_id in completed
                ]
                events = [event for spec in schedule for event in observed.get(spec.trial_id, ())]
                store.write_round(round_number, results, events)
                return results

            futures = []
            try:
                for i in range(0, len(schedule), 2):
                    futures.append(
                        executor.submit(run_pair, i // 2, (schedule[i], schedule[i + 1]))
                    )
                for future in as_completed(futures):
                    future.result()
                results = append_round()
            except BaseException:
                stopped.set()
                for future in futures:
                    future.cancel()
                executor.shutdown(wait=True, cancel_futures=True)
                append_round()
                raise
            trials.extend(results)
            history = evaluate_rounds(manifest, trials)
            if history[-1].verdict is not Verdict.INCONCLUSIVE:
                break
    store.write_decision(decide_suite(manifest, trials))
    return tuple(trials)
