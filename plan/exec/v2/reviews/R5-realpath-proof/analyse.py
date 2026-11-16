import json, collections, glob
rows = [json.loads(l) for l in open("http.jsonl")]
trials = []
for r in rows:
    if len(r["body"]["messages"]) == 2:
        trials.append({"arm": r["arm"], "task": r["task"], "reqs": []})
    trials[-1]["reqs"].append(r["body"])
print("trials", len(trials), collections.Counter(t["arm"] for t in trials), "reqs/trial", collections.Counter(len(t["reqs"]) for t in trials))
first = collections.Counter()
kinds = collections.Counter()
tool_msg_keys = collections.Counter()
after = collections.Counter()
for i in range(0, len(trials), 2):
    a, b = trials[i], trials[i + 1]
    assert a["task"] == b["task"] and {a["arm"], b["arm"]} == {"baseline", "candidate"}, (a["arm"], b["arm"], a["task"], b["task"])
    first[a["arm"]] += 1
    base, cand = (a, b) if a["arm"] == "baseline" else (b, a)
    for x, y in zip(base["reqs"], cand["reqs"]):
        for key in sorted(set(x) | set(y)):
            if key != "messages":
                if x.get(key) != y.get(key):
                    kinds[("top-level", key)] += 1
                continue
            if len(x[key]) != len(y[key]):
                kinds["len"] += 1
            for j, (mx, my) in enumerate(zip(x[key], y[key])):
                if mx != my:
                    kinds[(j, mx["role"], tuple(sorted(mx)), mx["content"], my["content"])] += 1
    for t in (base, cand):
        for m in t["reqs"][-1]["messages"]:
            if m["role"] == "tool":
                tool_msg_keys[tuple(sorted(m))] += 1
        after[(t["arm"], t["reqs"][1]["messages"][3]["content"])] += 1
print("pairs first arm:", dict(first))
print("distinct arm differences (request-level counts):")
for k, v in kinds.items():
    print("  ", v, k)
print("tool message keys:", dict(tool_msg_keys))
print("message after first lookup:", dict(after))
b0 = trials[0]["reqs"][0]
print("non-message request fields:", {k: v for k, v in b0.items() if k not in ("messages", "tools")})
print("urls:", collections.Counter(r["url"] for r in rows))
aud = [json.loads(l) for l in open("audit.jsonl")]
print("audit lines", len(aud), "distinct ids", len({a["tool_call_id"] for a in aud}))
store = glob.glob("runs2/*")[0]
tr = [json.loads(l) for l in open(store + "/trials.jsonl")]
print("store trials", len(tr), collections.Counter((t["arm"], t["outcome"]) for t in tr))
print("injected first lookups:", collections.Counter((t["arm"], t["recording"][0]["tool"], t["recording"][0]["result"]["injected_by"], t["recording"][0]["result"]["ok"]) for t in tr))
blob = open(store + "/trials.jsonl").read() + open(store + "/events.jsonl").read()
print("audit ids found in store:", sum(a["tool_call_id"] in blob for a in aud))
print("EMPTY text found in store:", "returned an empty result" in blob)
