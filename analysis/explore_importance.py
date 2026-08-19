#!/usr/bin/env python
"""Explore importance-score functions for top-story selection.

Features per story (era-normalized within the story's first-seen year):
  peak_outlets   max outlets in one run
  total_outlets  distinct outlets across the story's whole life
  total_articles sum over days of the day's max article count
  days_seen      distinct days observed
  ttp            days from broke to (article-)peak

Candidate functions (rank-based comparison + Spearman vs current):
  F1 current    era-relative peak outlets (what the dashboard uses today)
  F2 volume     era-relative total articles
  F3 breadth    era-relative total outlets × log2(1 + days_seen)
  F4 composite  mean within-year z of log1p(peak_outlets, total_outlets,
                days_seen, total_articles)
  F5 burst+legs F1 × (1 + log2(1 + days_seen)/4) × (1 + ttp/span)
"""
import json
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent


def story_features():
    df = pd.read_parquet(HERE / "data" / "stories.parquet")
    per_day = (df.groupby(["story_uid", "day"])
               .agg(outlets=("outlet_count", "max"), articles=("article_count", "max"),
                    headline=("headline", "first"), kind=("kind", "first"))
               .reset_index())
    outlet_sets = (df.assign(o=df["outlets"].apply(
        lambda j: [x.get("outlet") for x in json.loads(j)]))
        .groupby("story_uid")["o"].apply(lambda s: len({o for lst in s for o in lst})))
    g = per_day.groupby("story_uid")
    st = g.agg(first=("day", "min"), last=("day", "max"), days_seen=("day", "nunique"),
               peak_outlets=("outlets", "max"), total_articles=("articles", "sum"),
               kind=("kind", "first"))
    peak_rows = per_day.loc[per_day.groupby("story_uid")["outlets"].idxmax()]
    st["headline"] = peak_rows.set_index("story_uid")["headline"]
    st["peak_day"] = peak_rows.set_index("story_uid")["day"]
    art_rows = per_day.loc[per_day.groupby("story_uid")["articles"].idxmax()]
    st["peak_day_articles"] = art_rows.set_index("story_uid")["day"]
    st["total_outlets"] = outlet_sets
    st["span"] = (pd.to_datetime(st["last"]) - pd.to_datetime(st["first"])).dt.days + 1
    st["ttp"] = (pd.to_datetime(st["peak_day_articles"]) - pd.to_datetime(st["first"])).dt.days
    st["year"] = st["first"].str[:4]
    return st.reset_index()


def _rel(st, col):
    med = st.groupby("year")[col].transform("median").clip(lower=1)
    return st[col] / med


def _zlog(st, col):
    v = np.log1p(st[col])
    grp = v.groupby(st["year"])
    return (v - grp.transform("mean")) / grp.transform("std").replace(0, 1)


def add_scores(st):
    st["F1_current"] = _rel(st, "peak_outlets")
    st["F2_volume"] = _rel(st, "total_articles")
    st["F3_breadth"] = _rel(st, "total_outlets") * np.log2(1 + st["days_seen"])
    st["F4_composite"] = (_zlog(st, "peak_outlets") + _zlog(st, "total_outlets")
                          + _zlog(st, "days_seen") + _zlog(st, "total_articles")) / 4
    st["F5_burst_legs"] = (st["F1_current"]
                           * (1 + np.log2(1 + st["days_seen"]) / 4)
                           * (1 + st["ttp"] / st["span"].clip(lower=1)))
    return st


FUNCS = ["F1_current", "F2_volume", "F3_breadth", "F4_composite", "F5_burst_legs"]


def main():
    st = add_scores(story_features())
    st = st[st["kind"] == "story"]
    labels = pd.read_parquet(HERE / "data" / "story_labels.parquet")
    st = st.merge(labels[["story_uid", "major", "sub"]], on="story_uid", how="inner")

    print("=== Spearman rank correlation across ALL stories ===")
    print(st[FUNCS].corr(method="spearman").round(3).to_string())

    for major in ["Culture & entertainment", "Conflict & security"]:
        seg = st[st["major"] == major]
        print(f"\n=== {major}: top 10 per function ===")
        for f in FUNCS:
            print(f"\n-- {f} --")
            for _, r in seg.nlargest(10, f).iterrows():
                print(f"  {r['first']} p{r['peak_outlets']:>2} o{r['total_outlets']:>2} "
                      f"d{r['days_seen']:>3} a{int(r['total_articles']):>4} | {r['headline'][:66]}")

    slap = st[st["headline"].str.contains("Will Smith Hits Chris Rock", na=False)]
    if len(slap):
        seg = st[st["major"] == "Culture & entertainment"]
        for f in FUNCS:
            rank = int((seg[f] > slap[f].max()).sum()) + 1
            print(f"\nWill Smith slap rank in Culture under {f}: #{rank}")


if __name__ == "__main__":
    main()
