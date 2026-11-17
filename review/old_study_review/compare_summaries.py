"""Compare replayed evaluation summaries with the committed 600 seed summaries.

Usage: python3 compare_summaries.py COMMITTED_SEED_SUMMARIES REPLAY_OUT_DIR
Every field must be equal (exact float equality) except runtime_seconds and
config_digest (which hashes the worker count) and selection_sha256 (bytes embed the output path). Exit 1 on any difference or
missing run.
"""
import json
import sys
from pathlib import Path

IGNORED = {"runtime_seconds", "config_digest", "selection_sha256"}  # selection content checked separately; its bytes embed paths and the digest
committed = [json.loads(line) for line in open(sys.argv[1])]
out = Path(sys.argv[2])
replayed = {}
for path in out.glob("raw/evaluation/T-1000/*/*/seed-*/summary.json"):
    r = json.loads(path.read_text())
    replayed[(r["W"], r["method"], r["seed"])] = r

diffs, missing, equal = [], [], 0
for c in committed:
    key = (c["W"], c["method"], c["seed"])
    r = replayed.get(key)
    if r is None:
        missing.append(key)
        continue
    bad = sorted(k for k in set(c) | set(r) if k not in IGNORED and c.get(k) != r.get(k))
    if bad:
        diffs.append((key, {k: (c.get(k), r.get(k)) for k in bad}))
    else:
        equal += 1
print(f"committed {len(committed)}  replayed {len(replayed)}  identical {equal}  differing {len(diffs)}  missing {len(missing)}")
for key, d in diffs[:20]:
    print("DIFF", key, json.dumps(d)[:400])
if missing:
    print("MISSING (first 10)", missing[:10])
raise SystemExit(1 if diffs or missing or len(replayed) != len(committed) else 0)
