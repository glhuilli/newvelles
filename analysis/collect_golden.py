#!/usr/bin/env python
"""Merge and validate golden-label batches into golden_sample.parquet."""
import json
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
tax = json.loads((HERE / "taxonomy.json").read_text())
VALID = {(major, sub) for major, subs in tax["majors"].items() for sub in subs}
MAJORS = set(tax["majors"])

inputs = {}
for f in sorted((HERE / "data" / "golden_input").glob("*.jsonl")):
    for line in f.read_text().splitlines():
        r = json.loads(line)
        inputs[r["uid"]] = r

rows, bad = [], []
for f in sorted((HERE / "data" / "golden_labels").glob("*.jsonl")):
    for line in f.read_text().splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            r = json.loads(line)
        except ValueError:
            bad.append((f.name, line[:60]))
            continue
        if r.get("uid") not in inputs:
            bad.append((f.name, f"unknown uid {r.get('uid')}"))
            continue
        if (r.get("major"), r.get("sub")) not in VALID:
            bad.append((f.name, f"{r.get('uid')}: invalid {r.get('major')}/{r.get('sub')}"))
            continue
        tags = [str(t).lower().strip() for t in (r.get("tags") or [])][:6]
        rows.append({"uid": r["uid"], "headline": inputs[r["uid"]]["h"],
                     "major": r["major"], "sub": r["sub"], "tags": tags})

df = pd.DataFrame(rows).drop_duplicates(subset="uid")
missing = set(inputs) - set(df["uid"])
print(f"labeled: {len(df)}/{len(inputs)} · invalid lines: {len(bad)} · missing: {len(missing)}")
for name, msg in bad[:8]:
    print("  bad:", name, msg)
if missing:
    (HERE / "data" / "golden_missing.jsonl").write_text(
        "\n".join(json.dumps(inputs[u]) for u in sorted(missing)))
    print("  missing uids written to data/golden_missing.jsonl")

other_share = df["sub"].str.startswith("other-").mean()
print(f"\n'other-*' share: {other_share:.1%}")
print("\nmajor distribution:")
print(df["major"].value_counts().to_string())
print("\ntop 20 subs:")
print(df["sub"].value_counts().head(20).to_string())
empty_subs = {s for _, s in VALID} - set(df["sub"])
print(f"\nsubs never used ({len(empty_subs)}):", sorted(empty_subs))

df.to_parquet(HERE / "data" / "golden_sample.parquet")
print(f"\n✅ golden_sample.parquet: {len(df)} rows")
