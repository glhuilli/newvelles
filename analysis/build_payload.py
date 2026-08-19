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
    out = pd.DataFrame({"articles": articles, "stories": stories}).reset_index()
    # era-normalized volume index: level shifts from pipeline changes (feed
    # count, story merging) divide out against a trailing/centered 91-day
    # median; 1.0 = a typical day for that era
    base = out["articles"].rolling(91, center=True, min_periods=21).median()
    out["idx"] = (out["articles"] / base).round(3)
    return out


def weekly_sections(per_day):
    """Weekly distinct stories per group: taxonomy majors when labels exist,
    legacy sections otherwise. Top 7 groups + Other (palette ceiling)."""
    d = per_day.copy()
    labels_path = HERE / "data" / "story_labels.parquet"
    if labels_path.exists():
        lab = pd.read_parquet(labels_path)
        d = d.merge(lab[["story_uid", "major"]], on="story_uid", how="left")
        d["group"] = d["major"].fillna("Other")
    else:
        d["group"] = d["section"]
    d["week"] = pd.to_datetime(d["day"]).dt.to_period("W-SUN").dt.start_time.dt.strftime("%Y-%m-%d")
    top = d.groupby("group")["story_uid"].nunique().nlargest(TOP_SECTIONS).index.tolist()
    d["sec"] = d["group"].where(d["group"].isin(top), "Other")
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


def _label_map():
    p = HERE / "data" / "story_labels.parquet"
    if not p.exists():
        return {}
    lab = pd.read_parquet(p)
    return dict(zip(lab["story_uid"], lab["sub"]))


def ledger(stories, curves, n=80):
    subs = _label_map()
    led = (stories[stories["kind"] == "story"]
           .nlargest(n * 3, ["peak_outlets", "days_seen"])
           # identity occasionally splits one story across a gap; keep the
           # strongest row per headline so the ledger reads one row per story
           .drop_duplicates(subset="headline", keep="first")
           .head(n))
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
            "cat": subs.get(s["story_uid"], ""),
        })
    return out


def annotations(led, n=15, min_gap_days=45):
    """Flags = era-relative standouts: peak outlets divided by the median peak
    among that calendar year's ledger stories, so a 17-outlet 2022 story
    outranks an 18-outlet 2026 story from a 40% bigger pipeline."""
    year_median = (pd.DataFrame(led).assign(year=lambda t: t["peak_day"].str[:4])
                   .groupby("year")["peak_outlets"].median().to_dict())
    scored = sorted(led, key=lambda r: -(r["peak_outlets"]
                                         / max(1.0, year_median[r["peak_day"][:4]])))
    chosen = []

    def try_add(row):
        d = pd.Timestamp(row["peak_day"])
        if all(abs((d - pd.Timestamp(c["d"])).days) >= min_gap_days for c in chosen):
            chosen.append({"d": row["peak_day"], "uid": row["uid"],
                           "label": row["headline"][:48] + ("…" if len(row["headline"]) > 48 else ""),
                           "outlets": row["peak_outlets"]})
            return True
        return False

    # per-year quota first: quiet-pipeline years (2024's max was 11 outlets)
    # still get their top stories on the timeline
    by_year: dict = {}
    for row in scored:
        by_year.setdefault(row["peak_day"][:4], []).append(row)
    for year_rows in by_year.values():
        added = 0
        for row in year_rows:
            if added >= 2:
                break
            added += try_add(row)
    for row in scored:                      # then fill globally
        if len(chosen) >= n:
            break
        try_add(row)
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
    subs = _label_map()
    return {
        "base": [{"d": r["first"], "span": int(r["span"]), "peak": int(r["peak_outlets"])}
                 for _, r in base.iterrows()],
        "named": [{"d": r["first"], "span": int(r["span"]), "peak": int(r["peak_outlets"]),
                   "label": r["headline"][:40],
                   "cat": subs.get(r["story_uid"], "")} for _, r in named.iterrows()],
        "total": int(len(stories)),
        "shown": int(len(base)),
    }


def _cluster_name(curve):
    c = np.asarray(curve)
    c = c / (c.max() or 1.0)
    peaks = ((c[1:-1] > np.maximum(c[:-2], c[2:])) & (c[1:-1] > 0.5)).sum()
    pos = int(np.argmax(c)) / (len(c) - 1)
    width = float((c > 0.5).mean())
    if peaks >= 2:
        return "Double peak"
    if pos <= 0.2:
        return "Flash" if width < 0.3 else "Fast start, long tail"
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
    seen: dict = {}
    for c in clusters:  # same-name clusters get their peak position as a distinguisher
        if c["name"] in seen or sum(1 for o in clusters if o["name"] == c["name"]) > 1:
            pos = int(100 * np.argmax(c["medoid"]) / (len(c["medoid"]) - 1))
            seen[c["name"]] = True
            c["name"] = f"{c['name']} · peak at {pos}%"
    return {"clusters": clusters, "silhouette": round(sil, 3), "n": int(len(X))}


def _msummary(series):
    s = pd.Series(series)
    if s.empty:
        return None
    return {"median": round(float(s.median()), 1),
            "p25": round(float(s.quantile(0.25)), 1),
            "p75": round(float(s.quantile(0.75)), 1)}


def core_stats(df, per_day):
    """The core-stats matrix at run/day/week grain, plus the top-10 source table.

    Definitions: an observation is one (run, story) row; distinct counts unique
    story_uids in the window; new counts stories on their first_seen day.
    """
    if "outlets" not in df.columns:
        return None
    first_seen = df.groupby("story_uid")["day"].min()
    d = per_day.copy()
    d["week"] = pd.to_datetime(d["day"]).dt.to_period("W-SUN").dt.start_time.dt.strftime("%Y-%m-%d")
    dfw = df.merge(d[["story_uid", "day", "week"]].drop_duplicates(), on=["story_uid", "day"])

    def grain(g_obs, g_distinct, g_new):
        return {"observations": _msummary(g_obs), "distinct": _msummary(g_distinct),
                "new": _msummary(g_new)}

    per_run = df.groupby("run_ts")["story_uid"]
    new_day = first_seen.value_counts()
    new_week = (pd.Series(pd.to_datetime(first_seen.values))
                .dt.to_period("W-SUN").dt.start_time.dt.strftime("%Y-%m-%d").value_counts())
    first_run = df.groupby("story_uid")["run_ts"].min().value_counts()
    grains = {
        "run": grain(per_run.size(), per_run.nunique(),
                     first_run.reindex(df["run_ts"].unique(), fill_value=0)),
        "day": grain(df.groupby("day").size(), df.groupby("day")["story_uid"].nunique(),
                     new_day.reindex(df["day"].unique(), fill_value=0)),
        "week": grain(dfw.groupby("week").size(), dfw.groupby("week")["story_uid"].nunique(),
                      new_week),
    }

    # per-source: explode outlets on the per-(story, day) strongest observation
    rows = df.loc[df.groupby(["story_uid", "day"])["outlet_count"].idxmax(),
                  ["story_uid", "day", "run_ts", "outlets"]]
    rows = rows.assign(outlet=rows["outlets"].apply(
        lambda j: [o.get("outlet") for o in json.loads(j)])).explode("outlet").dropna(subset=["outlet"])
    per_src_day = rows.groupby(["outlet", "day"])["story_uid"].nunique()
    src_day_medians = per_src_day.groupby("outlet").median()
    grains["per_source"] = {
        "distinct_per_day": _msummary(src_day_medians),
        "note": "median across sources of each source's median distinct stories per active day",
    }

    totals = rows.groupby("outlet").agg(stories=("story_uid", "nunique"),
                                        obs_days=("story_uid", "size"),
                                        days=("day", "nunique"))
    all_story_days = int(totals["obs_days"].sum())
    top = totals.nlargest(10, "stories")
    top_sources = [{
        "source": src, "stories": int(r["stories"]), "story_days": int(r["obs_days"]),
        "active_days": int(r["days"]),
        "median_per_day": round(float(per_src_day.loc[src].median()), 1),
        "share": round(float(r["obs_days"]) / all_story_days, 4),
    } for src, r in top.iterrows()]
    return {"grains": grains, "top_sources": top_sources,
            "n_sources": int(len(totals))}


def categories(per_day, stories):
    """Core stats per sub-category, ranked by distinct stories."""
    labels_path = HERE / "data" / "story_labels.parquet"
    if not labels_path.exists():
        return None
    labels = pd.read_parquet(labels_path)
    lab = labels.set_index("story_uid")
    st = stories.join(lab, on="story_uid", how="inner")
    pdl = per_day.merge(labels[["story_uid", "major", "sub"]], on="story_uid", how="inner")

    from collections import Counter
    out = []
    per_sub_day = pdl.groupby(["sub", "day"])["story_uid"].nunique()
    total_stories = len(st)
    for (major, sub), g in st.groupby(["major", "sub"]):
        tag_counts = Counter(t for tags in g["tags"] for t in list(tags))
        exemplar = g.loc[g["peak_outlets"].idxmax()]
        out.append({
            "major": major, "sub": sub,
            "stories": int(len(g)),
            "share": round(len(g) / total_stories, 4),
            "story_days": int(g["days_seen"].sum()),
            "median_per_day": round(float(per_sub_day.loc[sub].median()), 1)
            if sub in per_sub_day.index.get_level_values(0) else 0,
            "active_days": int(per_sub_day.loc[sub].shape[0])
            if sub in per_sub_day.index.get_level_values(0) else 0,
            "top_tags": [t for t, _ in tag_counts.most_common(5)],
            "exemplar": exemplar["headline"][:90],
        })
    out.sort(key=lambda r: -r["stories"])
    majors_order = list(pd.Series([r["major"] for r in out]).drop_duplicates())
    coverage = round(len(st) / len(stories), 4)
    return {"subs": out, "coverage": coverage, "labeled": int(len(st)),
            "majors_order": majors_order}


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
    # annotation pool: top stories PER YEAR (a global pool starves quiet-feed
    # years like 2024, whose loudest story peaked at 11 outlets)
    st_ann = stories[stories["kind"] == "story"].copy()
    st_ann["year"] = st_ann["peak_day"].str[:4]
    ann_pool = [
        {"uid": r["story_uid"], "headline": r["headline"],
         "peak_outlets": int(r["peak_outlets"]), "peak_day": r["peak_day"]}
        for _, g in st_ann.groupby("year")
        for _, r in g.nlargest(40, "peak_outlets").drop_duplicates("headline").iterrows()
    ]

    payload = {
        "meta": {
            "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
            "first_day": daily["day"].min(), "last_day": daily["day"].max(),
            "runs": int(df["run_ts"].nunique()), "rows": int(len(df)),
            "stories": int(len(stories)),
        },
        "daily": [{"d": r["day"], "a": int(r["articles"]), "s": int(r["stories"]),
                   "x": float(r["idx"]) if pd.notna(r["idx"]) else 1.0}
                  for _, r in daily.iterrows()],
        "sections": order,
        "weekly": [{"d": r["week"], **{s: int(r.get(s, 0)) for s in order}}
                   for _, r in wk.iterrows()],
        "ledger": led,
        "annotations": annotations(ann_pool),
        "lifetimes": lifetimes(stories),
        "archetypes": archetypes(curves),
        "discords": discords(daily),
        "stats": core_stats(df, per_day),
        "categories": categories(per_day, stories),
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
