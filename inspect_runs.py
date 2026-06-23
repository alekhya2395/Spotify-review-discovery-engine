"""Quick inspection helper: show per-source totals on disk."""
import json
import glob
from pathlib import Path

import pandas as pd


print("=" * 70)
print("DATA ON DISK (per source)")
print("=" * 70)
grand_total = 0
for src_dir in sorted(Path("data/raw").glob("*")):
    if not src_dir.is_dir():
        continue
    pq_files = sorted(src_dir.rglob("*.parquet"))
    if not pq_files:
        print(f"\n[{src_dir.name}]  no parquet files")
        continue
    total = 0
    for f in pq_files:
        try:
            total += len(pd.read_parquet(f))
        except Exception as exc:
            print(f"  WARN: failed to read {f.name}: {exc}")
    grand_total += total
    print(f"\n[{src_dir.name}]  files={len(pq_files)}  records_on_disk={total}")
    for f in pq_files:
        try:
            n = len(pd.read_parquet(f))
        except Exception:
            n = "?"
        rel = f.relative_to(Path("data/raw"))
        print(f"  - {rel}  rows={n}")

print("\n" + "=" * 70)
print(f"GRAND TOTAL across all sources: {grand_total} reviews")
print("=" * 70)
