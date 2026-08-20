#!/usr/bin/env python
"""Name event clusters (~5 words) from their member headlines via Bedrock Haiku.

The anchor story's own title can misrepresent the event (the Oct 7 cluster's
anchor is a media-criticism piece); naming from the earliest + biggest member
headlines titles the event itself. Cached in data/cluster_titles.json.
"""
import json
from pathlib import Path

import boto3

HERE = Path(__file__).resolve().parent
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
OUT = HERE / "data" / "cluster_titles.json"


def main() -> None:
    clusters = json.loads((HERE / "data" / "event_clusters.json").read_text())
    known = json.loads(OUT.read_text()) if OUT.exists() else {}
    pending = []
    for auid, c in clusters.items():
        if auid in known:
            continue
        members = sorted(c["members"], key=lambda m: m["first"])[:2] \
            + sorted(c["members"], key=lambda m: -m["arts"])[:2]
        heads = list(dict.fromkeys(m["title"][:110] for m in members))[:3]
        pending.append((auid, c["broke"], heads))
    print(f"{len(clusters)} clusters · {len(pending)} to name")
    if not pending:
        return

    client = boto3.client("bedrock-runtime", region_name="us-west-2")
    for start in range(0, len(pending), 40):
        batch = pending[start:start + 40]
        blocks = "\n".join(
            f"{i}. broke {broke}: " + " // ".join(heads)
            for i, (_, broke, heads) in enumerate(batch))
        prompt = (
            "Each numbered item is one news EVENT, shown as 2-3 headlines from its "
            "coverage. Write a neutral event title of AT MOST 5 words naming the "
            "underlying event (like 'Hamas attacks Israel' or 'SVB collapses'), not any "
            "single article's angle. Output ONE line per item: "
            '{"i": <number>, "t": "<title>"}\n\n' + blocks)
        resp = client.converse(
            modelId=MODEL_ID,
            messages=[{"role": "user", "content": [{"text": prompt}]}],
            inferenceConfig={"maxTokens": 2500, "temperature": 0.0})
        for line in resp["output"]["message"]["content"][0]["text"].splitlines():
            line = line.strip().strip("`")
            if not line.startswith("{"):
                continue
            try:
                obj = json.loads(line)
                i = int(obj["i"])
                if 0 <= i < len(batch):
                    known[batch[i][0]] = str(obj["t"])[:48]
            except (ValueError, KeyError, TypeError):
                continue
        print(f"  named {min(start + 40, len(pending))}/{len(pending)}")
    OUT.write_text(json.dumps(known, indent=0))
    print(f"✅ {OUT.name}: {len(known)} titles")


if __name__ == "__main__":
    main()
