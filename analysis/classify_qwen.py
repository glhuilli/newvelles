#!/usr/bin/env python
"""Route D experiment: classify the golden sample with local qwen3:8b via ollama.

Smaller batches than the Bedrock route (local models lose coherence on long
lists). Resumable via output shards. Compare with eval_labels.py.

Usage:
    analysis/.venv/bin/python analysis/classify_qwen.py [--limit 500]
"""
import argparse
import json
import urllib.request
from pathlib import Path

import pandas as pd

HERE = Path(__file__).resolve().parent
OUT_DIR = HERE / "data" / "qwen_labels"
BATCH = 25
URL = "http://localhost:11434/api/generate"


def compact_taxonomy() -> str:
    tax = json.loads((HERE / "taxonomy.json").read_text())
    return "\n".join(f"{major}: {', '.join(subs)}" for major, subs in tax["majors"].items())


PROMPT = """/no_think
You classify news headlines into a fixed taxonomy and assign meta tags.

Taxonomy (major: sub-category keys):
{taxonomy}

For each numbered story output ONE JSON line:
{{"i": <number>, "major": "<exact major name>", "sub": "<exact sub key from that major>", "tags": ["...", ...]}}
tags: 2-6 lowercase tags (salient entities from the title + group keywords like "trial", "layoffs").
Output ONLY the JSON lines, in order, nothing else.

Stories:
{stories}"""


def call(prompt: str) -> str:
    body = json.dumps({"model": "qwen3:8b", "prompt": prompt, "stream": False,
                       "options": {"temperature": 0.0, "num_predict": 2500}}).encode()
    req = urllib.request.Request(URL, data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as resp:
        return json.loads(resp.read())["response"]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    golden = pd.read_parquet(HERE / "data" / "golden_sample.parquet")
    inputs = {}
    for f in sorted((HERE / "data" / "golden_input").glob("*.jsonl")):
        for line in f.read_text().splitlines():
            r = json.loads(line)
            inputs[r["uid"]] = r
    records = [inputs[u] for u in golden["uid"] if u in inputs]
    if args.limit:
        records = records[:args.limit]
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    taxonomy = compact_taxonomy()

    batches = list(enumerate(records[s:s + BATCH] for s in range(0, len(records), BATCH)))
    pending = [(bi, b) for bi, b in batches if not (OUT_DIR / f"shard_{bi:04d}.jsonl").exists()]
    print(f"{len(records)} stories · {len(pending)}/{len(batches)} shards pending")

    for done, (bi, batch) in enumerate(pending, 1):
        stories = "\n".join(f'{i}. {r["h"]} | kw: {", ".join(r["kw"])}' for i, r in enumerate(batch))
        text = call(PROMPT.format(taxonomy=taxonomy, stories=stories))
        rows = []
        for line in text.splitlines():
            line = line.strip().strip("`")
            if not line.startswith("{"):
                continue
            try:
                obj = json.loads(line)
                i = int(obj["i"])
                if 0 <= i < len(batch):
                    rows.append({"uid": batch[i]["uid"], "major": obj.get("major"),
                                 "sub": obj.get("sub"), "tags": obj.get("tags", [])[:6]})
            except (ValueError, KeyError, TypeError):
                continue
        with open(OUT_DIR / f"shard_{bi:04d}.jsonl", "w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        if done % 10 == 0:
            print(f"  {done}/{len(pending)} shards · last parsed {len(rows)}/{len(batch)}")
    print("✅ done")


if __name__ == "__main__":
    main()
