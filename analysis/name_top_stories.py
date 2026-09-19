#!/usr/bin/env python
"""Generate ~5-word event titles for the per-major top stories (Bedrock Haiku).

Reads the drill tops out of site/data.json, names any uid missing from
data/short_titles.json, and appends to that file. Re-run build_payload
afterwards to merge the titles into the payload.
"""
import json
from pathlib import Path

import boto3

HERE = Path(__file__).resolve().parent
MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
OUT = HERE / "data" / "short_titles.json"


def main() -> None:
    data = json.loads((HERE / "site" / "data.json").read_text())
    rows = [(t["uid"], t["title"]) for d in data.get("drill", {}).values() for t in d["top"]]
    known = json.loads(OUT.read_text()) if OUT.exists() else {}
    pending = [(u, h) for u, h in dict(rows).items() if u not in known]
    print(f"{len(rows)} top stories · {len(pending)} to name")
    if not pending:
        return

    client = boto3.client("bedrock-runtime", region_name="us-west-2")
    for start in range(0, len(pending), 60):
        batch = pending[start:start + 60]
        stories = "\n".join(f"{i}. {h[:150]}" for i, (_, h) in enumerate(batch))
        prompt = (
            "For each numbered headline write a neutral event title of AT MOST 5 words "
            "(like a timeline label: 'Kabul falls', 'SVB collapses', 'Queen Elizabeth dies'). "
            "No punctuation except internal hyphens. Output ONE line per headline: "
            '{"i": <number>, "t": "<title>"}\n\nHeadlines:\n' + stories)
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
        print(f"  named {min(start + 60, len(pending))}/{len(pending)}")
    OUT.write_text(json.dumps(known, indent=0))
    print(f"✅ {OUT.name}: {len(known)} titles")


if __name__ == "__main__":
    main()
