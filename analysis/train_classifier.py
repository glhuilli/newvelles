#!/usr/bin/env python
"""Route C: sentence-embedding classifier trained on the golden sample.

Train/test split on golden labels; logistic regression over MiniLM embeddings
for major and sub; meta tags via k-NN transfer from training neighbors.
Writes test-split predictions to data/ml_labels/predictions.jsonl for
eval_labels.py, and prints its own accuracy summary.

Usage:
    analysis/.venv/bin/python analysis/train_classifier.py
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.neighbors import NearestNeighbors

HERE = Path(__file__).resolve().parent
OUT = HERE / "data" / "ml_labels"


def main() -> None:
    golden = pd.read_parquet(HERE / "data" / "golden_sample.parquet")
    train, test = train_test_split(golden, test_size=0.25, random_state=42,
                                   stratify=golden["major"])
    print(f"train {len(train)} / test {len(test)}")

    model = SentenceTransformer("all-MiniLM-L6-v2")
    emb_train = model.encode(train["headline"].tolist(), show_progress_bar=False,
                             normalize_embeddings=True)
    emb_test = model.encode(test["headline"].tolist(), show_progress_bar=False,
                            normalize_embeddings=True)

    clf_major = LogisticRegression(max_iter=2000, C=4.0).fit(emb_train, train["major"])
    clf_sub = LogisticRegression(max_iter=2000, C=4.0).fit(emb_train, train["sub"])
    pred_major = clf_major.predict(emb_test)
    pred_sub = clf_sub.predict(emb_test)

    # meta tags: inherit from the 5 nearest training headlines (open vocabulary
    # is not classifiable; nearest-neighbor transfer is the honest approximation)
    nn = NearestNeighbors(n_neighbors=5, metric="cosine").fit(emb_train)
    _, idx = nn.kneighbors(emb_test)
    train_tags = train["tags"].tolist()
    pred_tags = []
    for row in idx:
        counts: dict = {}
        for j in row:
            for t in train_tags[j]:
                counts[t] = counts.get(t, 0) + 1
        pred_tags.append([t for t, c in sorted(counts.items(), key=lambda kv: -kv[1])
                          if c >= 2][:4] or
                         [t for t, _ in sorted(counts.items(), key=lambda kv: -kv[1])][:2])

    maj_acc = float((pred_major == test["major"]).mean())
    sub_acc = float((pred_sub == test["sub"]).mean())
    print(f"major accuracy: {maj_acc:.3f} · sub accuracy: {sub_acc:.3f}")

    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "predictions.jsonl", "w") as f:
        for (_, r), m, s, tg in zip(test.iterrows(), pred_major, pred_sub, pred_tags):
            f.write(json.dumps({"uid": r["uid"], "major": m, "sub": s, "tags": tg}) + "\n")
    print(f"✅ {OUT / 'predictions.jsonl'} ({len(test)} rows)")


if __name__ == "__main__":
    main()
