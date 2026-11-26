"""Count A uses the audit's independently replayed observations."""

from collections import defaultdict

from common import SIDES, Row


def count(observations: list[Row]) -> Row:
    arms: Row = {}
    pairs: dict[str, dict[str, str]] = defaultdict(dict)
    for side in SIDES:
        groups = arms[side] = {}
        for group in ("all", "orders", "calendar"):
            rows = [
                o
                for o in observations
                if o["side"] == side and (o["family"] == group or group == "all")
            ]
            groups[group] = {
                "trials": len(rows),
                "passed": sum(o["outcome"] == "PASS" for o in rows),
                "errored": sum(o["outcome"] == "ERROR" for o in rows),
                "exact": sum(o["exact"] for o in rows),
                "retrieved": sum(o["retrieved"] for o in rows),
            }
    for o in observations:
        pairs[o["pair"]][o["side"]] = o["outcome"]
    signs = dict.fromkeys(("minus", "zero", "plus", "errored"), 0)
    for pair in pairs.values():
        diff = int(pair["candidate"] == "PASS") - int(pair["baseline"] == "PASS")
        signs["errored" if "ERROR" in pair.values() else ("minus", "zero", "plus")[diff + 1]] += 1
    return {"arms": arms, "signs": signs}
