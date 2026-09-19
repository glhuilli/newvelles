#!/usr/bin/env python
"""Merge Haiku label shards into story_labels.parquet, normalizing strays.

Normalization: if a (major, sub) pair is invalid but the sub key exists under
exactly one major, trust the sub and reassign the major. Unknown subs fall to
US news (general)/other-general. Records the route and taxonomy version.

Usage:
    analysis/.venv/bin/python analysis/merge_labels.py
"""
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
tax = json.loads((HERE / "taxonomy.json").read_text())
VALID = {(m, s) for m, subs in tax["majors"].items() for s in subs}
SUB_OWNER: dict = {}
for m, subs in tax["majors"].items():
    for s in subs:
        SUB_OWNER.setdefault(s, []).append(m)

rows, fixed, fallback = [], 0, 0
for f in sorted((HERE / "data" / "haiku_labels").glob("*.jsonl")):
    for line in f.read_text().splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        major, sub = r.get("major"), r.get("sub")
        if (major, sub) not in VALID:
            owners = SUB_OWNER.get(sub, [])
            if len(owners) == 1:
                major, fixed = owners[0], fixed + 1
            else:
                major, sub, fallback = "US news (general)", "other-general", fallback + 1
        tags = [str(t).lower().strip() for t in (r.get("tags") or []) if str(t).strip()][:6]
        rows.append({"story_uid": r["uid"], "major": major, "sub": sub, "tags": tags,
                     "route": "bedrock-haiku-4.5", "taxonomy_version": tax["version"]})

df = pd.DataFrame(rows).drop_duplicates(subset="story_uid")
df.to_parquet(HERE / "data" / "story_labels.parquet")
print(f"✅ story_labels.parquet: {len(df):,} stories "
      f"({fixed} major-fixed, {fallback} fell back to other-general)")
print(df["major"].value_counts().to_string())
