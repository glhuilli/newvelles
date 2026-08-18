#!/usr/bin/env python
"""Score a label source against the golden sample.

Metrics on overlapping uids: major accuracy, sub accuracy (exact key),
tag any-overlap rate and mean Jaccard, plus a major confusion summary.

Usage:
    analysis/.venv/bin/python analysis/eval_labels.py data/haiku_labels
    analysis/.venv/bin/python analysis/eval_labels.py data/qwen_labels
    analysis/.venv/bin/python analysis/eval_labels.py data/ml_labels
"""
import json
import sys
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent


def load_jsonl_dir(path: Path) -> pd.DataFrame:
    rows = []
    for f in sorted(path.glob("*.jsonl")):
        for line in f.read_text().splitlines():
            line = line.strip()
            if line.startswith("{"):
                try:
                    rows.append(json.loads(line))
                except ValueError:
                    continue
    return pd.DataFrame(rows).drop_duplicates(subset="uid")


def main() -> None:
    src = HERE / sys.argv[1] if len(sys.argv) > 1 else HERE / "data" / "haiku_labels"
    golden = pd.read_parquet(HERE / "data" / "golden_sample.parquet")
    pred = load_jsonl_dir(src)
    m = golden.merge(pred, on="uid", suffixes=("_gold", "_pred"))
    if m.empty:
        print("no overlapping uids"); return
    maj = float((m["major_gold"] == m["major_pred"]).mean())
    sub = float((m["sub_gold"] == m["sub_pred"]).mean())
    sub_given_major = float(
        (m.loc[m["major_gold"] == m["major_pred"], "sub_gold"]
         == m.loc[m["major_gold"] == m["major_pred"], "sub_pred"]).mean())

    def as_set(v):
        if v is None:
            return set()
        return set(list(v))

    def jac(a, b):
        A, B = as_set(a), as_set(b)
        return len(A & B) / len(A | B) if A | B else 0.0

    tag_overlap = float(m.apply(lambda r: bool(as_set(r["tags_gold"]) & as_set(r["tags_pred"])),
                                axis=1).mean())
    tag_jaccard = float(m.apply(lambda r: jac(r["tags_gold"], r["tags_pred"]), axis=1).mean())

    print(f"{src.name}: n={len(m)}")
    print(f"  major accuracy:        {maj:.3f}")
    print(f"  sub accuracy:          {sub:.3f}")
    print(f"  sub | major correct:   {sub_given_major:.3f}")
    print(f"  tags any-overlap:      {tag_overlap:.3f}")
    print(f"  tags mean jaccard:     {tag_jaccard:.3f}")
    conf = (m[m["major_gold"] != m["major_pred"]]
            .groupby(["major_gold", "major_pred"]).size().nlargest(8))
    print("  top major confusions:")
    for (g, p), n in conf.items():
        print(f"    {g} -> {p}: {n}")


if __name__ == "__main__":
    main()
