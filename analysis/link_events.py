#!/usr/bin/env python
"""Link story identities into event clusters around anchor stories.

Story identity stays untouched; this builds a star-shaped link layer around
each anchor (the top-25 stories per major). Linking options explored:

  A_raw  share >= 2 entity tokens
  A_idf  IDF-weighted shared entity tokens >= tau  (rare entities count more)
  B_jac  Jaccard over keywords+entity tokens >= tau
  C_emb  MiniLM cosine similarity to the anchor headline >= tau
  D_hyb  A_idf at a lower bar AND C_emb at a lower bar

Cluster metrics (per the 2026-08-20 spec): broke = earliest linked story day;
peak = day with max combined articles across linked stories; days = length of
the first continuous episode (coverage until a gap of >= GAP_DAYS days);
episodes = all coverage periods.

Usage:
    analysis/.venv/bin/python analysis/link_events.py --explore   # diagnostics
    analysis/.venv/bin/python analysis/link_events.py --emit      # event_clusters.json
"""
import argparse
import json
import math
from collections import Counter
from datetime import timedelta
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
GAP_DAYS = 3
WINDOW_BEFORE = 14
WINDOW_AFTER = 120
STOP_TOKENS = {"the", "new", "news", "und", "los", "las", "san", "u.s", "usa"}


def load_stories():
    df = pd.read_parquet(HERE / "data" / "stories.parquet")
    per_day = (df.groupby(["story_uid", "day"])
               .agg(outlets=("outlet_count", "max"), articles=("article_count", "max"))
               .reset_index())
    g = df.sort_values("run_ts").groupby("story_uid")
    st = g.agg(first=("day", "min"), last=("day", "max"),
               headline=("headline", "last"), kind=("kind", "first"),
               keywords=("keywords", "last"), entities=("entities", "last"))
    st["peak_outlets"] = per_day.groupby("story_uid")["outlets"].max()
    days_map = per_day.groupby("story_uid")["day"].apply(list).to_dict()
    arts_map = {(r["story_uid"], r["day"]): int(r["articles"]) for _, r in per_day.iterrows()}
    return st.reset_index(), days_map, arts_map


def ent_tokens(ent_json, kw_json=None):
    toks = set()
    for e in json.loads(ent_json):
        for t in str(e).lower().replace("'s", "").split():
            t = t.strip(".,’'’\"()")
            if t.isalpha() and len(t) >= 3 and t not in STOP_TOKENS:
                toks.add(t)
    if kw_json:
        for k in json.loads(kw_json):
            for t in str(k).lower().split():
                if t.isalpha() and len(t) >= 4 and t not in STOP_TOKENS:
                    toks.add(t)
    return toks


def build_index(st):
    st = st.copy()
    st["etoks"] = [ent_tokens(e) for e in st["entities"]]
    st["ktoks"] = [ent_tokens(e, k) for e, k in zip(st["entities"], st["keywords"])]
    df_count = Counter(t for toks in st["etoks"] for t in set(toks))
    n = len(st)
    idf = {t: math.log(n / c) for t, c in df_count.items()}
    return st, idf


_EMB = None
_EMB_UIDS = None


def embeddings(st):
    global _EMB, _EMB_UIDS
    if _EMB is not None:
        return _EMB, _EMB_UIDS
    cache = HERE / "cache" / "headline_emb.npz"
    if cache.exists():
        z = np.load(cache, allow_pickle=True)
        _EMB, _EMB_UIDS = z["emb"], list(z["uids"])
    else:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        _EMB_UIDS = st["story_uid"].tolist()
        _EMB = model.encode(st["headline"].tolist(), normalize_embeddings=True,
                            show_progress_bar=True, batch_size=256).astype(np.float32)
        cache.parent.mkdir(exist_ok=True)
        np.savez_compressed(cache, emb=_EMB, uids=np.array(_EMB_UIDS))
    return _EMB, _EMB_UIDS


def link_scores(anchor_row, cand, idf, emb=None, uid_pos=None):
    """Return per-option boolean links for candidate frame `cand`."""
    a_e, a_k = anchor_row["etoks"], anchor_row["ktoks"]
    out = {}
    shared_e = cand["etoks"].apply(lambda s: s & a_e)
    out["A_raw"] = shared_e.apply(len) >= 2
    out["A_idf"] = shared_e.apply(lambda s: sum(idf.get(t, 0) for t in s)) >= 12.0
    out["B_jac"] = cand["ktoks"].apply(
        lambda s: len(s & a_k) / len(s | a_k) if s | a_k else 0) >= 0.15
    if emb is not None:
        a_v = emb[uid_pos[anchor_row["story_uid"]]]
        sims = emb[[uid_pos[u] for u in cand["story_uid"]]] @ a_v
        out["C_emb"] = pd.Series(sims >= 0.50, index=cand.index)
        idf_score = shared_e.apply(lambda s: sum(idf.get(t, 0) for t in s))
        out["D_hyb"] = ((idf_score >= 7.0) & pd.Series(sims >= 0.35, index=cand.index)) | \
                       ((idf_score >= 16.0))
    return out


def cluster_metrics(uids, days_map, arts_map, anchor_uid):
    all_days = sorted({d for u in uids for d in days_map.get(u, [])})
    if not all_days:
        return None
    day_arts = Counter()
    for u in uids:
        for d in days_map.get(u, []):
            day_arts[d] += arts_map.get((u, d), 0)
    # episodes: split where gap > GAP_DAYS
    episodes = [[all_days[0], all_days[0]]]
    for d in all_days[1:]:
        if (pd.Timestamp(d) - pd.Timestamp(episodes[-1][1])).days > GAP_DAYS:
            episodes.append([d, d])
        else:
            episodes[-1][1] = d
    peak_day = max(day_arts, key=day_arts.get)
    # the event's main run is the episode containing the peak; stray earlier
    # links (a lone related story days before) must not hijack "broke"
    main_ep = next(ep for ep in episodes if ep[0] <= peak_day <= ep[1])
    ep_days = (pd.Timestamp(main_ep[1]) - pd.Timestamp(main_ep[0])).days + 1
    return {"broke": main_ep[0], "peak_day": peak_day,
            "peak_articles": int(day_arts[peak_day]),
            "days": int(ep_days), "coverage_days": len(all_days),
            "episodes": episodes, "n_stories": len(uids)}


def candidates_for(st, anchor):
    lo = (pd.Timestamp(anchor["first"]) - timedelta(days=WINDOW_BEFORE)).strftime("%Y-%m-%d")
    hi = (pd.Timestamp(anchor["first"]) + timedelta(days=WINDOW_AFTER)).strftime("%Y-%m-%d")
    return st[(st["first"] >= lo) & (st["first"] <= hi)]


def explore(st, idf, days_map, arts_map):
    emb, uids = embeddings(st)
    uid_pos = {u: i for i, u in enumerate(uids)}
    TESTS = {
        "Oct 7 (media-criticism anchor)": "h_e760a5b8af",
        "Musk-Twitter (resignations anchor)": "h_8ba72ca67e",
        "SVB (mortgage-rates anchor)": "h_279b6ff5cd",
        "Queen dies (King Charles anchor)": "h_f3fa0e9aa7",
    }
    sti = st.set_index("story_uid")
    for name, auid in TESTS.items():
        anchor = sti.loc[auid]
        anchor = anchor.copy(); anchor["story_uid"] = auid
        cand = candidates_for(st, anchor)
        links = link_scores(anchor, cand, idf, emb, uid_pos)
        print(f"\n{'='*100}\n{name} · anchor: {anchor['headline'][:70]}")
        for opt, mask in links.items():
            sel = cand[mask]
            uids_sel = set(sel["story_uid"]) | {auid}
            m = cluster_metrics(uids_sel, days_map, arts_map, auid)
            print(f"  {opt:<6} n={len(uids_sel):>4} broke={m['broke']} peak={m['peak_day']} "
                  f"days={m['days']:>3} covdays={m['coverage_days']:>3} eps={len(m['episodes'])}")
        # leakage probe: show 6 lowest-overlap members of D_hyb for eyeballing
        sel = cand[links["D_hyb"]]
        sample = sel.sample(min(6, len(sel)), random_state=1)
        for _, r in sample.iterrows():
            print(f"     D_hyb e.g. [{r['first']}] {r['headline'][:78]}")


def emit(st, idf, days_map, arts_map):
    emb, uids = embeddings(st)
    uid_pos = {u: i for i, u in enumerate(uids)}
    data = json.loads((HERE / "site" / "data.json").read_text())
    labels = pd.read_parquet(HERE / "data" / "story_labels.parquet").set_index("story_uid")
    anchors = {t["uid"] for v in data["drill"].values() for mode in ("top", "top_yearly")
               for t in v[mode]} | {e["uid"] for e in data.get("events", [])}
    sti = st.set_index("story_uid")
    out = {}
    for auid in sorted(anchors):
        if auid not in sti.index:
            continue
        anchor = sti.loc[auid].copy(); anchor["story_uid"] = auid
        cand = candidates_for(st, anchor)
        links = link_scores(anchor, cand, idf, emb, uid_pos)
        sel = cand[links["D_hyb"]]
        uids_sel = set(sel["story_uid"]) | {auid}
        m = cluster_metrics(uids_sel, days_map, arts_map, auid)
        members = []
        rows = st[st["story_uid"].isin(uids_sel)]
        rows = rows.assign(vol=[sum(arts_map.get((u, d), 0) for d in days_map.get(u, []))
                                for u in rows["story_uid"]]).sort_values("vol", ascending=False)
        for _, r in rows.head(15).iterrows():
            u = r["story_uid"]
            members.append({
                "uid": u, "title": r["headline"][:110], "first": r["first"],
                "days": len(days_map.get(u, [])), "outlets": int(r["peak_outlets"]),
                "arts": int(r["vol"]),
                "tags": list(labels.loc[u, "tags"])[:3] if u in labels.index else [],
            })
        m["members"] = members
        out[auid] = m
    path = HERE / "data" / "event_clusters.json"
    path.write_text(json.dumps(out))
    print(f"✅ {path.name}: {len(out)} anchor clusters")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--explore", action="store_true")
    ap.add_argument("--emit", action="store_true")
    args = ap.parse_args()
    st, days_map, arts_map = load_stories()
    st, idf = build_index(st)
    if args.explore:
        explore(st, idf, days_map, arts_map)
    if args.emit:
        emit(st, idf, days_map, arts_map)


if __name__ == "__main__":
    main()
