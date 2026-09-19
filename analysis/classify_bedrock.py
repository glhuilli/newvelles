#!/usr/bin/env python
"""Classify every story with Claude Haiku on Bedrock (major, sub, tags).

Route A of the taxonomy plan. Resumable: output is sharded JSONL under
analysis/data/haiku_labels/; existing shards are skipped. Uses IAM only.

Usage:
    analysis/.venv/bin/python analysis/classify_bedrock.py --limit 300   # smoke
    analysis/.venv/bin/python analysis/classify_bedrock.py               # full corpus
"""
import argparse
import json
import random
import re
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import boto3
import pandas as pd

HERE = Path(__file__).resolve().parent
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
BATCH = 150
OUT_DIR = HERE / "data" / "haiku_labels"
FEWSHOT_N = 12


def compact_taxonomy() -> str:
    tax = json.loads((HERE / "taxonomy.json").read_text())
    lines = []
    for major, subs in tax["majors"].items():
        keys = ", ".join(subs)
        lines.append(f"{major}: {keys}")
    return "\n".join(lines)


def fewshots() -> str:
    golden = HERE / "data" / "golden_sample.parquet"
    if not golden.exists():
        return ""
    g = pd.read_parquet(golden).sample(FEWSHOT_N, random_state=11)
    lines = ["Examples of correct output lines:"]
    for _, r in g.iterrows():
        lines.append(json.dumps({"i": 0, "major": r["major"], "sub": r["sub"],
                                 "tags": list(r["tags"])[:4]}))
    return "\n".join(lines)


PROMPT_HEAD = """You classify news headlines into a fixed taxonomy and assign meta tags.

Taxonomy (major: sub-category keys):
{taxonomy}

Rules:
- For each numbered story output ONE JSON line: {{"i": <number>, "major": "<exact major name>", "sub": "<exact sub key from that major>", "tags": ["...", ...]}}
- tags: 2-6 lowercase tags: salient named entities from the title plus group keywords more granular than the sub (e.g. "trial", "world cup", "immigration crisis", "layoffs", "ceasefire") even when the word is absent from the title.
- Choose the single best major/sub for the story's central subject. Use "other-*" subs only when nothing fits.
- Output ONLY the JSON lines, one per story, in order, nothing else.

{fewshots}

Stories:
{stories}"""


def build_prompt(batch, taxonomy, shots):
    stories = "\n".join(
        f'{i}. {r["h"]} | kw: {", ".join(r["kw"])} | en: {", ".join(r["en"])}'
        for i, r in enumerate(batch))
    return PROMPT_HEAD.format(taxonomy=taxonomy, fewshots=shots, stories=stories)


def parse_lines(text, batch):
    out = {}
    for line in text.splitlines():
        line = line.strip().strip("`")
        if not line.startswith("{"):
            continue
        try:
            obj = json.loads(line)
            i = int(obj["i"])
            if 0 <= i < len(batch):
                out[i] = {"uid": batch[i]["uid"], "major": obj["major"],
                          "sub": obj["sub"], "tags": obj.get("tags", [])[:6]}
        except (ValueError, KeyError, TypeError):
            continue
    return out


def classify_batch(client, batch, taxonomy, shots, attempt=0):
    prompt = build_prompt(batch, taxonomy, shots)
    resp = client.converse(
        modelId=MODEL_ID,
        messages=[{"role": "user", "content": [{"text": prompt}]}],
        inferenceConfig={"maxTokens": 8000, "temperature": 0.0},
    )
    text = resp["output"]["message"]["content"][0]["text"]
    parsed = parse_lines(text, batch)
    missing = [i for i in range(len(batch)) if i not in parsed]
    if missing and attempt < 2:
        sub_batch = [batch[i] for i in missing]
        retry = classify_batch(client, sub_batch, taxonomy, shots, attempt + 1)
        for j, i in enumerate(missing):
            if j in retry:
                parsed[i] = {**retry[j], "uid": batch[i]["uid"]}
    return [parsed[i] for i in sorted(parsed)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--workers", type=int, default=8)
    args = ap.parse_args()

    df = pd.read_parquet(HERE / "data" / "stories.parquet")
    per = (df.sort_values("run_ts").groupby("story_uid")
           .agg(h=("headline", "first"), kw=("keywords", "first"), en=("entities", "first")))
    records = [{"uid": uid, "h": r["h"][:160],
                "kw": json.loads(r["kw"])[:4], "en": json.loads(r["en"])[:5]}
               for uid, r in per.iterrows()]
    random.Random(5).shuffle(records)
    if args.limit:
        records = records[:args.limit]
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    taxonomy = compact_taxonomy()
    shots = fewshots()
    batches = [(bi, records[s:s + BATCH]) for bi, s in enumerate(range(0, len(records), BATCH))]
    pending = [(bi, b) for bi, b in batches if not (OUT_DIR / f"shard_{bi:04d}.jsonl").exists()]
    print(f"{len(records):,} stories · {len(batches)} batches · {len(pending)} pending")

    client = boto3.client("bedrock-runtime", region_name="us-west-2")

    def work(item):
        bi, batch = item
        for attempt in range(4):
            try:
                rows = classify_batch(client, batch, taxonomy, shots)
                with open(OUT_DIR / f"shard_{bi:04d}.jsonl", "w") as f:
                    for r in rows:
                        f.write(json.dumps(r) + "\n")
                return bi, len(rows), len(batch)
            except Exception as e:  # noqa: BLE001
                if "Throttling" in str(e) or "TooManyRequests" in str(e):
                    time.sleep(10 * (attempt + 1))
                    continue
                if attempt >= 3:
                    raise
                time.sleep(5)
        return bi, 0, len(batch)

    done = 0
    with ThreadPoolExecutor(max_workers=args.workers) as ex:
        for fut in as_completed([ex.submit(work, it) for it in pending]):
            bi, n, total = fut.result()
            done += 1
            if n < total:
                print(f"  shard {bi}: {n}/{total} parsed")
            if done % 25 == 0:
                print(f"  {done}/{len(pending)} shards")
    print("✅ done")


if __name__ == "__main__":
    main()
