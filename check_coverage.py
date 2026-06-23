"""Compare unique reviews in data/raw/ vs unique insights in CSV.

Tells you exactly:
- How many unique review_ids exist on disk
- How many are covered by insights.csv
- How many are missing (still un-analyzed)
- Whether any review_id has duplicate rows in the CSV
"""

import json
import glob
from pathlib import Path
import pandas as pd


raw_ids = set()
raw_files = 0
raw_lines = 0
for path in glob.glob("data/raw/**/*.jsonl", recursive=True):
    raw_files += 1
    try:
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                raw_lines += 1
                try:
                    rec = json.loads(line)
                except json.JSONDecodeError:
                    continue
                rid = rec.get("review_id")
                if rid and rec.get("text"):
                    raw_ids.add(rid)
    except OSError:
        continue


csv_path = Path("data/processed/insights.csv")
if not csv_path.exists():
    print("insights.csv does not exist yet")
    raise SystemExit(0)

df = pd.read_csv(csv_path)
csv_total_rows = len(df)
csv_unique_ids = set(df["review_id"].dropna().astype(str))
dup_count = csv_total_rows - len(csv_unique_ids)

analyzed = raw_ids & csv_unique_ids
missing = raw_ids - csv_unique_ids
orphans = csv_unique_ids - raw_ids

print("=" * 70)
print("PHASE 2 COVERAGE REPORT")
print("=" * 70)
print(f"Raw reviews on disk:                  {len(raw_ids):>6} unique  ({raw_lines} total lines across {raw_files} files)")
print(f"insights.csv rows:                    {csv_total_rows:>6} total")
print(f"insights.csv unique review_ids:       {len(csv_unique_ids):>6}")
if dup_count:
    print(f"  duplicate rows in CSV:              {dup_count:>6}  (same review_id more than once)")
print()
print(f"Reviews analyzed (raw AND csv):       {len(analyzed):>6}  ({100*len(analyzed)/max(1,len(raw_ids)):.1f}% coverage)")
print(f"Reviews missing (raw - csv):          {len(missing):>6}  (still to analyze)")
if orphans:
    print(f"Orphans (csv ids not in raw):         {len(orphans):>6}  (curious — possibly leftover from earlier runs)")
print("=" * 70)

if missing:
    print("\nSample of missing review_ids (first 10):")
    for rid in list(missing)[:10]:
        print(f"  - {rid}")

if missing:
    pct = 100 * len(analyzed) / len(raw_ids)
    print(f"\nTo analyze the remaining {len(missing)} reviews, run:")
    print(f"  python run_phase2.py -m llama-3.1-8b-instant")
    print(f"(dedup automatically skips the {len(analyzed)} already done)")
else:
    print("\nAll raw reviews are analyzed. Phase 2 is complete.")
