#!/usr/bin/env python
"""Aggregate stories.parquet into the dashboard payload and build the site.

Runs in the analysis venv (analysis/requirements.txt), never in the
deployment environment.

Usage:
    analysis/.venv/bin/python analysis/build_payload.py            # data.json only
    analysis/.venv/bin/python analysis/build_payload.py --site     # + site/index.html
"""
import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
PARQUET = HERE / "data" / "stories.parquet"
D3_MIN = HERE / "vendor" / "d3.min.js"
TOP_SECTIONS = 7
CURVE_POINTS = 24


def load_frames():
    df = pd.read_parquet(PARQUET)
    df["day"] = df["day"].astype(str)
    # per (story, day): the day's strongest observation
    per_day = (df.groupby(["story_uid", "day"])
               .agg(outlets=("outlet_count", "max"), articles=("article_count", "max"),
                    section=("section", "first"), kind=("kind", "first"),
                    headline=("headline", "first"))
               .reset_index())
    return df, per_day


def per_story(per_day):
    g = per_day.groupby("story_uid")
    st = g.agg(first=("day", "min"), last=("day", "max"), days_seen=("day", "nunique"),
               peak_outlets=("outlets", "max"), peak_articles=("articles", "max"),
               section=("section", lambda s: s.mode().iat[0]),
               kind=("kind", lambda s: s.mode().iat[0]))
    peak_rows = per_day.loc[per_day.groupby("story_uid")["outlets"].idxmax()]
    st["headline"] = peak_rows.set_index("story_uid")["headline"]
    st["peak_day"] = peak_rows.set_index("story_uid")["day"]
    st["span"] = ((pd.to_datetime(st["last"]) - pd.to_datetime(st["first"])).dt.days + 1)
    return st.reset_index()


def daily_series(df):
    run_totals = df.groupby(["day", "run_ts"])["article_count"].sum()
    articles = run_totals.groupby("day").max()
    stories = df.groupby("day")["story_uid"].nunique()
    return pd.DataFrame({"articles": articles, "stories": stories}).reset_index()


def weekly_sections(per_day):
    d = per_day.copy()
    d["week"] = pd.to_datetime(d["day"]).dt.to_period("W-SUN").dt.start_time.dt.strftime("%Y-%m-%d")
    top = d.groupby("section")["story_uid"].nunique().nlargest(TOP_SECTIONS).index.tolist()
    d["sec"] = d["section"].where(d["section"].isin(top), "Other")
    wk = (d.groupby(["week", "sec"])["story_uid"].nunique().unstack(fill_value=0)
          .reset_index())
    order = [s for s in top if s in wk.columns] + (["Other"] if "Other" in wk.columns else [])
    return wk, order


def story_curve(days, outlets, first, last, n=CURVE_POINTS):
    idx = pd.date_range(first, last, freq="D").strftime("%Y-%m-%d")
    series = pd.Series(0.0, index=idx)
    series.loc[days] = outlets
    v = series.to_numpy(dtype=float)
    if len(v) < 2:
        v = np.repeat(v, 2)
    xs = np.linspace(0, len(v) - 1, n)
    return np.interp(xs, np.arange(len(v)), v)


def build_curves(per_day, stories, min_days):
    sel = stories[stories["days_seen"] >= min_days]
    rows = per_day[per_day["story_uid"].isin(sel["story_uid"])]
    grouped = {uid: (g["day"].tolist(), g["outlets"].tolist())
               for uid, g in rows.groupby("story_uid")}
    curves = {}
    for _, s in sel.iterrows():
        days, outlets = grouped[s["story_uid"]]
        curves[s["story_uid"]] = story_curve(days, outlets, s["first"], s["last"])
    return curves


def ledger(stories, curves, n=80):
    led = (stories[stories["kind"] == "story"]
           .nlargest(n, ["peak_outlets", "days_seen"]))
    out = []
    for _, s in led.iterrows():
        c = curves.get(s["story_uid"])
        if c is None:
            c = story_curve([s["peak_day"]], [s["peak_outlets"]], s["first"], s["last"])
        cmax = float(c.max()) or 1.0
        peaks = int(((c[1:-1] > np.maximum(c[:-2], c[2:])) & (c[1:-1] > 0.5 * cmax)).sum())
        why = ("sustained multi-week run" if s["span"] >= 21
               else "returned for a second peak" if peaks >= 2
               else "single-burst spike" if s["span"] <= 3
               else "multi-day cycle")
        out.append({
            "uid": s["story_uid"], "headline": s["headline"], "section": s["section"],
            "first": s["first"], "peak_day": s["peak_day"], "days": int(s["days_seen"]),
            "span": int(s["span"]), "peak_outlets": int(s["peak_outlets"]),
            "peak_articles": int(s["peak_articles"]),
            "curve": [round(float(x), 2) for x in c], "why": why,
        })
    return out


def annotations(led, n=15, min_gap_days=45):
    chosen = []
    for row in sorted(led, key=lambda r: -r["peak_outlets"]):
        d = pd.Timestamp(row["peak_day"])
        if all(abs((d - pd.Timestamp(c["d"])).days) >= min_gap_days for c in chosen):
            chosen.append({"d": row["peak_day"], "uid": row["uid"],
                           "label": row["headline"][:48] + ("…" if len(row["headline"]) > 48 else ""),
                           "outlets": row["peak_outlets"]})
        if len(chosen) >= n:
            break
    return sorted(chosen, key=lambda c: c["d"])


def lifetimes(stories, base_n=3200, named_n=12):
    keep = stories[(stories["span"] >= 7) | (stories["peak_outlets"] >= 10)]
    if len(keep) > 2600:
        top = keep.nlargest(600, ["peak_outlets", "span"])
        keep = pd.concat([top, keep.drop(top.index).sample(2000, random_state=7)])
    rest = stories.drop(stories.index.intersection(keep.index), errors="ignore")
    n_fill = max(0, base_n - len(keep))
    sample = rest.sample(n=min(n_fill, len(rest)), random_state=7) if len(rest) else rest
    base = pd.concat([keep, sample])
    named = stories.assign(score=stories["span"] * stories["peak_outlets"]).nlargest(named_n, "score")
    return {
        "base": [{"d": r["first"], "span": int(r["span"]), "peak": int(r["peak_outlets"])}
                 for _, r in base.iterrows()],
        "named": [{"d": r["first"], "span": int(r["span"]), "peak": int(r["peak_outlets"]),
                   "label": r["headline"][:40]} for _, r in named.iterrows()],
        "total": int(len(stories)),
        "shown": int(len(base)),
    }


def _cluster_name(curve):
    c = np.asarray(curve)
    cmax = c.max() or 1.0
    c = c / cmax
    peaks = ((c[1:-1] > np.maximum(c[:-2], c[2:])) & (c[1:-1] > 0.5)).sum()
    argmax = int(np.argmax(c))
    pos = argmax / (len(c) - 1)
    if peaks >= 2:
        return "Double peak"
    if pos <= 0.2:
        return "Flash"
    if pos >= 0.7:
        return "Late surge"
    if c.mean() >= 0.45:
        return "Plateau"
    return "Slow burn"


def archetypes(curves, k=5, members_per=12):
    from sklearn.cluster import KMeans
    from sklearn.metrics import silhouette_score
    uids = list(curves)
    X = np.array([curves[u] / (curves[u].max() or 1.0) for u in uids])
    if len(X) < k * 4:
        return {"clusters": [], "silhouette": None, "n": len(X)}
    km = KMeans(n_clusters=k, n_init=10, random_state=0).fit(X)
    sil_sample = min(len(X), 4000)
    sil = float(silhouette_score(X[:sil_sample], km.labels_[:sil_sample]))
    rng = np.random.default_rng(7)
    clusters = []
    for ci in range(k):
        idx = np.flatnonzero(km.labels_ == ci)
        centroid = km.cluster_centers_[ci]
        medoid = X[idx[np.argmin(np.linalg.norm(X[idx] - centroid, axis=1))]]
        sample = rng.choice(idx, size=min(members_per, len(idx)), replace=False)
        clusters.append({
            "name": _cluster_name(medoid), "size": int(len(idx)),
            "share": round(float(len(idx)) / len(X), 3),
            "medoid": [round(float(v), 3) for v in medoid],
            "members": [[round(float(v), 3) for v in X[i]] for i in sample],
        })
    clusters.sort(key=lambda c: -c["size"])
    return {"clusters": clusters, "silhouette": round(sil, 3), "n": int(len(X))}


def discords(daily, m=14, top=5):
    v = daily["articles"].to_numpy(dtype=float)
    n = len(v) - m + 1
    if n < 3 * m:
        return []
    windows = np.lib.stride_tricks.sliding_window_view(v, m)
    mu = windows.mean(axis=1, keepdims=True)
    sd = windows.std(axis=1, keepdims=True)
    Z = (windows - mu) / np.where(sd < 1e-9, 1.0, sd)
    profile = np.full(n, np.inf)
    for i in range(n):
        d = np.linalg.norm(Z - Z[i], axis=1)
        lo, hi = max(0, i - m // 2), min(n, i + m // 2 + 1)
        d[lo:hi] = np.inf
        profile[i] = d.min()
    days = daily["day"].tolist()
    out, taken = [], []
    for i in np.argsort(-profile):
        if any(abs(int(i) - t) < m for t in taken):
            continue
        taken.append(int(i))
        seg = v[i:i + m]
        out.append({"start": days[int(i)], "end": days[int(i) + m - 1],
                    "score": round(float(profile[i]), 2),
                    "curve": [round(float(x), 1) for x in seg]})
        if len(out) >= top:
            break
    return out


def build(site: bool):
    df, per_day = load_frames()
    stories = per_story(per_day)
    daily = daily_series(df)
    wk, order = weekly_sections(per_day)
    curves = build_curves(per_day, stories, min_days=5)
    led = ledger(stories, curves)

    payload = {
        "meta": {
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "first_day": daily["day"].min(), "last_day": daily["day"].max(),
            "runs": int(df["run_ts"].nunique()), "rows": int(len(df)),
            "stories": int(len(stories)),
        },
        "daily": [{"d": r["day"], "a": int(r["articles"]), "s": int(r["stories"])}
                  for _, r in daily.iterrows()],
        "sections": order,
        "weekly": [{"d": r["week"], **{s: int(r.get(s, 0)) for s in order}}
                   for _, r in wk.iterrows()],
        "ledger": led,
        "annotations": annotations(led),
        "lifetimes": lifetimes(stories),
        "archetypes": archetypes(curves),
        "discords": discords(daily),
    }
    out = HERE / "site" / "data.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(payload), encoding="utf-8")
    print(f"data.json: {out.stat().st_size / 1e6:.2f} MB · "
          f"{payload['meta']['stories']:,} stories · {payload['meta']['runs']:,} runs · "
          f"archetype silhouette {payload['archetypes']['silhouette']}")

    if site:
        template = (HERE / "site" / "template.html").read_text(encoding="utf-8")
        html = (template
                .replace("/*__D3__*/", D3_MIN.read_text(encoding="utf-8"))
                .replace("/*__DATA__*/", "window.DATA = " + json.dumps(payload) + ";"))
        (HERE / "site" / "index.html").write_text(html, encoding="utf-8")
        print(f"site/index.html: {(HERE / 'site' / 'index.html').stat().st_size / 1e6:.2f} MB")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--site", action="store_true")
    build(ap.parse_args().site)
