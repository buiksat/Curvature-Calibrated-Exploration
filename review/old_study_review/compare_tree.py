"""Field-by-field diff of two artifact directories (JSON and JSONL files with the same names).

Usage: python3 compare_tree.py COMMITTED_DIR REPLAY_DIR [extra ignored key substrings...]
Values must be exactly equal. Volatile keys (paths, hashes, digests, timings, worker
count, git/host details, run error text) are skipped and listed. Exit 1 on any difference.
"""
import json
import sys
from pathlib import Path

# Filesystem locations are listed by name: "factor_path" is a scientific recipe, not a location.
EXACT = {"path", "summary_path", "selection_path", "protocol_path", "output", "outputs", "runtime_seconds",
         "elapsed_seconds", "timestamp_utc", "started_at", "completed_at", "workers", "python", "signature",
         "git_revision", "git_dirty", "git_dirty_at_start", "error"}
EXTRA = sys.argv[3:]


def volatile(k):
    k = k.lower()
    return k in EXACT or "sha256" in k or "digest" in k or any(e in k for e in EXTRA)
skipped, diffs = set(), []


def walk(a, b, where):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if volatile(k):
                skipped.add(k)
                continue
            if k not in a or k not in b:
                diffs.append((where + "/" + k, "missing on one side"))
                continue
            walk(a[k], b[k], where + "/" + k)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            diffs.append((where, f"list length {len(a)} vs {len(b)}"))
        for i, (x, y) in enumerate(zip(a, b)):
            walk(x, y, f"{where}[{i}]")
    elif isinstance(a, str) and isinstance(b, str) and a.startswith("/") and b.startswith("/") and a.rsplit("/", 1)[-1] == b.rsplit("/", 1)[-1]:
        skipped.add(where.rsplit("/", 1)[-1] + " (path-like string)")
    elif a != b:
        diffs.append((where, f"{a!r:.120} vs {b!r:.120}"))


def load(p):
    if p.suffix == ".jsonl":
        return [json.loads(line) for line in p.open()]
    return json.loads(p.read_text())


committed, replay = Path(sys.argv[1]), Path(sys.argv[2])
for p in sorted(committed.iterdir()):
    q = replay / p.name
    if p.suffix not in (".json", ".jsonl"):
        continue
    if not q.exists():
        print(f"{p.name}: MISSING in replay")
        diffs.append((p.name, "missing"))
        continue
    before = len(diffs)
    walk(load(p), load(q), p.name)
    print(f"{p.name}: {'identical' if len(diffs) == before else f'{len(diffs) - before} differences'}")
for where, what in diffs:
    print("  DIFF", where, what)
print("skipped keys:", ", ".join(sorted(skipped)))
raise SystemExit(1 if diffs else 0)
