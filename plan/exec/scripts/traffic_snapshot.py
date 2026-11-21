"""Save GitHub's public counters and 14-day traffic window for one repository.

GitHub keeps traffic for 14 days only, so a daily run is the only way to keep a longer
series. Each run reads the whole window through the `gh` command (which must be signed in
with push access to the repository) and writes under `plan/exec/v2/signals/traffic/`:

- `daily.csv`: one row per calendar day (UTC) with views, unique visitors, clones and unique
  cloners. A day already present is replaced, because GitHub revises the last two days.
- `counts.csv`: one row per read date with stars, forks, watchers, issues opened by other
  people and discussions.
- `referrers-YYYY-MM-DD.json` and `paths-YYYY-MM-DD.json`: GitHub's top-ten lists for the
  window that ended on the read date, as returned.

Unique counts are per day; they cannot be added across days. The script sends nothing except
the `gh` requests and makes no git change.

Usage: python3 plan/exec/scripts/traffic_snapshot.py [OWNER/REPO]
"""

from __future__ import annotations

import csv
import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

DEFAULT_REPO = "ajaysurya1221/agent-reliability-ci"
OUT = Path(__file__).resolve().parents[1] / "v2" / "signals" / "traffic"
DAILY_FIELDS = ["date", "views", "view_uniques", "clones", "clone_uniques", "read_on"]
COUNT_FIELDS = ["read_on", "stars", "forks", "watchers", "outside_issues", "discussions"]
_DISCUSSIONS = (
    "query($owner:String!,$name:String!)"
    "{repository(owner:$owner,name:$name){discussions{totalCount}}}"
)


def gh(*args: str) -> Any:
    done = subprocess.run(["gh", *args], check=True, capture_output=True, text=True)
    return json.loads(done.stdout)


def series(payload: Any, key: str) -> dict[str, tuple[int, int]]:
    rows = cast(list[dict[str, Any]], payload.get(key, []))
    return {str(row["timestamp"])[:10]: (int(row["count"]), int(row["uniques"])) for row in rows}


def read_rows(path: Path, key: str) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    with path.open(newline="", encoding="utf-8") as handle:
        return {row[key]: row for row in csv.DictReader(handle)}


def write_rows(path: Path, fields: list[str], rows: dict[str, dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        for key in sorted(rows):
            writer.writerow(rows[key])


def outside_issues(repo: str, owner: str) -> int:
    issues = cast(
        list[dict[str, Any]],
        gh("api", "--paginate", f"repos/{repo}/issues?state=all&per_page=100"),
    )
    count = 0
    for issue in issues:
        user = cast(dict[str, Any], issue.get("user") or {})
        if "pull_request" in issue or user.get("type") == "Bot" or user.get("login") == owner:
            continue
        count += 1
    return count


def main(argv: list[str]) -> int:
    repo = argv[0] if argv else DEFAULT_REPO
    owner, name = repo.split("/", 1)
    today = datetime.now(UTC).date().isoformat()
    OUT.mkdir(parents=True, exist_ok=True)

    views = series(gh("api", f"repos/{repo}/traffic/views"), "views")
    clones = series(gh("api", f"repos/{repo}/traffic/clones"), "clones")
    daily = read_rows(OUT / "daily.csv", "date")
    for day in sorted(set(views) | set(clones)):
        view_count, view_uniques = views.get(day, (0, 0))
        clone_count, clone_uniques = clones.get(day, (0, 0))
        daily[day] = {
            "date": day,
            "views": str(view_count),
            "view_uniques": str(view_uniques),
            "clones": str(clone_count),
            "clone_uniques": str(clone_uniques),
            "read_on": today,
        }
    write_rows(OUT / "daily.csv", DAILY_FIELDS, daily)

    for kind in ("referrers", "paths"):
        payload = gh("api", f"repos/{repo}/traffic/popular/{kind}")
        (OUT / f"{kind}-{today}.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    info = cast(dict[str, Any], gh("api", f"repos/{repo}"))
    discussions = gh(
        "api",
        "graphql",
        "-f",
        f"query={_DISCUSSIONS}",
        "-f",
        f"owner={owner}",
        "-f",
        f"name={name}",
    )
    counts = read_rows(OUT / "counts.csv", "read_on")
    counts[today] = {
        "read_on": today,
        "stars": str(info["stargazers_count"]),
        "forks": str(info["forks_count"]),
        "watchers": str(info["subscribers_count"]),
        "outside_issues": str(outside_issues(repo, owner)),
        "discussions": str(discussions["data"]["repository"]["discussions"]["totalCount"]),
    }
    write_rows(OUT / "counts.csv", COUNT_FIELDS, counts)

    print(f"saved {len(daily)} days and counts for {today}: {counts[today]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
