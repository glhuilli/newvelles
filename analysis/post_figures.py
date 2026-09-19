#!/usr/bin/env python
"""Figures and tables for the glhuilli.github.io methods post.

Outputs PNGs into the site repo (assets/posts/news-cycles/) and prints the
numbers used in the post's tables.
"""
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from explore_importance import FUNCS, add_scores, story_features  # noqa: E402
from eval_labels import load_jsonl_dir  # noqa: E402

HERE = Path(__file__).resolve().parent
SITE = Path("/Users/gastonlhuillier/Personal/glhuilli.github.io/assets/posts/news-cycles")

INK, INK2, MUTED, GRID, SURF = "#0b0b0b", "#52514e", "#898781", "#e1e0d9", "#fcfcfb"
BLUE, RED, GREEN, YELLOW, AQUA = "#2a78d6", "#e34948", "#008300", "#eda100", "#1baf7a"
plt.rcParams.update({
    "figure.facecolor": SURF, "axes.facecolor": SURF, "savefig.facecolor": SURF,
    "axes.edgecolor": GRID, "axes.labelcolor": INK2, "text.color": INK,
    "xtick.color": MUTED, "ytick.color": MUTED, "axes.grid": True,
    "grid.color": GRID, "grid.linewidth": 0.7, "axes.spines.top": False,
    "axes.spines.right": False, "font.size": 10.5, "figure.dpi": 160,
})


def fig_volume():
    df = pd.read_parquet(HERE / "data" / "stories.parquet")
    run_totals = df.groupby(["day", "run_ts"])["article_count"].sum()
    daily = run_totals.groupby("day").max().reset_index(name="articles")
    daily["date"] = pd.to_datetime(daily["day"])
    base = daily["articles"].rolling(91, center=True, min_periods=21).median()
    daily["idx"] = daily["articles"] / base
    fig, axes = plt.subplots(2, 1, figsize=(9.5, 4.6), sharex=True,
                             gridspec_kw={"hspace": 0.18})
    axes[0].plot(daily["date"], daily["articles"], lw=0.6, color=BLUE)
    axes[0].set_ylabel("articles / day")
    axes[0].set_title("Raw daily volume: pipeline growth dominates", loc="left",
                      fontsize=11, color=INK)
    axes[1].plot(daily["date"], daily["idx"], lw=0.6, color=BLUE)
    axes[1].axhline(1.0, color=MUTED, lw=0.8, ls="--")
    axes[1].set_ylabel("volume index")
    axes[1].set_title("Era-normalized: divided by a trailing 91-day median",
                      loc="left", fontsize=11, color=INK)
    fig.savefig(SITE / "fig-volume.png", bbox_inches="tight")
    plt.close(fig)
    print("fig-volume done")


def fig_confusion_and_tables():
    golden = pd.read_parquet(HERE / "data" / "golden_sample.parquet")
    haiku = load_jsonl_dir(HERE / "data" / "haiku_labels")
    m = golden.merge(haiku, on="uid", suffixes=("_g", "_h"))
    majors = sorted(golden["major"].unique())
    short = {mj: mj.replace(" & ", " / ").replace("Politics & government", "Politics")
             for mj in majors}
    SHORT = {"Politics & government": "Politics", "Conflict & security": "Conflict",
             "Crime & justice": "Crime", "Economy & work": "Economy",
             "Markets & finance": "Markets", "Science & space": "Science",
             "Climate & environment": "Climate", "Culture & entertainment": "Culture",
             "Everyday life": "Everyday", "US news (general)": "US general",
             "Tech": "Tech", "Health": "Health", "Sports": "Sports"}
    cm = pd.crosstab(m["major_g"], m["major_h"]).reindex(index=majors, columns=majors,
                                                         fill_value=0)
    cmn = cm.div(cm.sum(axis=1), axis=0)
    fig, ax = plt.subplots(figsize=(7.6, 6.6))
    im = ax.imshow(cmn.values, cmap="Blues", vmin=0, vmax=1)
    ax.set_xticks(range(len(majors)), [SHORT[x] for x in majors], rotation=45,
                  ha="right", fontsize=9)
    ax.set_yticks(range(len(majors)), [SHORT[x] for x in majors], fontsize=9)
    ax.set_xlabel("Haiku label"); ax.set_ylabel("golden label")
    ax.grid(False)
    for i in range(len(majors)):
        for j in range(len(majors)):
            v = cmn.values[i, j]
            if v >= 0.02:
                ax.text(j, i, f"{v:.2f}".lstrip("0"), ha="center", va="center",
                        fontsize=7.5, color="white" if v > 0.5 else INK2)
    ax.set_title("Major-category confusion: Haiku vs golden (row-normalized)",
                 loc="left", fontsize=11, color=INK)
    fig.savefig(SITE / "fig-confusion.png", bbox_inches="tight")
    plt.close(fig)

    per = (m.assign(maj_ok=m["major_g"] == m["major_h"],
                    sub_ok=m["sub_g"] == m["sub_h"])
           .groupby("major_g").agg(n=("maj_ok", "size"), major_acc=("maj_ok", "mean"),
                                   sub_acc=("sub_ok", "mean")).round(3))
    print("\nPER-MAJOR AGREEMENT (haiku vs golden):")
    print(per.sort_values("major_acc").to_string())
    print("fig-confusion done")


def fig_ranking_profile():
    st = add_scores(story_features())
    st = st[st["kind"] == "story"]
    rows = []
    for f in FUNCS:
        top = st.nlargest(100, f)
        rows.append({"f": f, "med_days": top["days_seen"].median(),
                     "med_arts": top["total_articles"].median(),
                     "med_outlets": top["peak_outlets"].median()})
    prof = pd.DataFrame(rows)
    print("\nTOP-100 SELECTION PROFILE PER FUNCTION:")
    print(prof.to_string(index=False))
    labels = ["F1\npeak", "F2\nvolume", "F3\nbreadth", "F4\ncomposite", "F5\nburst×legs"]
    fig, axes = plt.subplots(1, 3, figsize=(9.8, 3.0))
    for ax, col, title, color in [
            (axes[0], "med_outlets", "median peak outlets", BLUE),
            (axes[1], "med_days", "median days seen", YELLOW),
            (axes[2], "med_arts", "median total articles", AQUA)]:
        ax.bar(labels, prof[col], color=color, width=0.62)
        ax.set_title(title, loc="left", fontsize=10.5, color=INK)
        ax.grid(axis="x")
    fig.suptitle("What each importance function selects for (its top-100 stories)",
                 x=0.01, ha="left", fontsize=11.5, color=INK)
    fig.tight_layout(rect=[0, 0, 1, 0.93])
    fig.savefig(SITE / "fig-ranking-profile.png", bbox_inches="tight")
    plt.close(fig)

    print("\nSPEARMAN (all stories):")
    print(st[FUNCS].corr(method="spearman").round(3).to_string())
    print("fig-ranking-profile done")


def fig_fragmentation():
    clusters = json.loads((HERE / "data" / "event_clusters.json").read_text())
    df = pd.read_parquet(HERE / "data" / "stories.parquet")
    anchor_days = df.groupby("story_uid")["day"].nunique()
    xs, ys = [], []
    for uid, c in clusters.items():
        if uid in anchor_days.index:
            xs.append(anchor_days[uid]); ys.append(c["days"])
    xs, ys = np.array(xs), np.array(ys)
    fig, ax = plt.subplots(figsize=(6.2, 5.2))
    ax.scatter(xs, ys, s=16, color=BLUE, alpha=0.5, edgecolors="none")
    lim = [0.8, max(ys.max(), xs.max()) * 1.3]
    ax.plot(lim, lim, color=MUTED, lw=0.9, ls="--")
    ax.set_xscale("log"); ax.set_yscale("log")
    ax.set_xlim(lim); ax.set_ylim(lim)
    ax.set_xlabel("days in the news — single story identity")
    ax.set_ylabel("days in the news — linked event cluster")
    ax.set_title("Fragmentation correction: identity vs event duration (308 events)",
                 loc="left", fontsize=11, color=INK)
    med_ratio = np.median(ys / np.maximum(xs, 1))
    ax.text(0.03, 0.95, f"median ratio ×{med_ratio:.1f}", transform=ax.transAxes,
            fontsize=10, color=INK2, va="top")
    fig.savefig(SITE / "fig-fragmentation.png", bbox_inches="tight")
    plt.close(fig)
    print(f"\nfrag: median cluster/identity days ratio = {med_ratio:.2f}; "
          f"identities with days<=2: {(xs <= 2).mean():.0%}; "
          f"clusters with days>=14: {(ys >= 14).mean():.0%}")
    print("fig-fragmentation done")


def fig_oct7():
    clusters = json.loads((HERE / "data" / "event_clusters.json").read_text())
    c = clusters["h_e760a5b8af"]
    df = pd.read_parquet(HERE / "data" / "stories.parquet")
    # combined daily articles across linked members requires the full member set:
    # recompute from the emitted members' uids is partial (12 kept). Approximate
    # with the corpus filter used for the case study instead: entities/keywords.
    w = df[(df["day"] >= "2023-09-25") & (df["day"] <= "2024-02-10")]
    hits = w[w["headline"].str.contains("israel|gaza|hamas", case=False, na=False) |
             w["entities"].str.contains("Israel|Gaza|Hamas", na=False)]
    per_day = (hits.groupby(["story_uid", "day"])["article_count"].max()
               .groupby("day").sum().reset_index(name="arts"))
    per_day["date"] = pd.to_datetime(per_day["day"])
    anchor = df[df["story_uid"] == "h_e760a5b8af"].groupby("day")["article_count"].max()
    fig, ax = plt.subplots(figsize=(9.8, 3.4))
    ax.bar(per_day["date"], per_day["arts"], width=1.0, color=BLUE, alpha=0.75,
           label="all linked coverage (combined articles/day)")
    for d, v in anchor.items():
        ax.bar(pd.to_datetime(d), v, width=1.0, color=RED,
               label="the single anchor identity" if d == anchor.index[0] else None)
    ax.axvline(pd.to_datetime(c["broke"]), color=INK, lw=0.9, ls=":")
    ax.text(pd.to_datetime(c["broke"]), ax.get_ylim()[1] * 0.97, " broke (Oct 7)",
            fontsize=9, color=INK, va="top")
    ax.axvline(pd.to_datetime(c["p"] if "p" in c else c["peak_day"]), color=GREEN,
               lw=0.9, ls=":")
    ax.text(pd.to_datetime(c["peak_day"]), ax.get_ylim()[1] * 0.85,
            f" peak (Oct 8, {c['peak_articles']} articles)", fontsize=9, color=GREEN)
    ax.set_ylabel("articles / day")
    ax.legend(frameon=False, fontsize=9, loc="upper right")
    ax.set_title("Anatomy of an event: October 7 coverage vs its single 'story identity'",
                 loc="left", fontsize=11, color=INK)
    fig.savefig(SITE / "fig-oct7.png", bbox_inches="tight")
    plt.close(fig)
    print("fig-oct7 done")


def precision_sample():
    clusters = json.loads((HERE / "data" / "event_clusters.json").read_text())
    titles = json.loads((HERE / "data" / "cluster_titles.json").read_text())
    rng = np.random.default_rng(3)
    picks = rng.choice(list(clusters), size=8, replace=False)
    print("\nPRECISION AUDIT SAMPLE (judge each member: related to the event?):")
    for uid in picks:
        c = clusters[uid]
        print(f"\nEVENT: {titles.get(uid)} (broke {c['broke']}, {c['n_stories']} stories)")
        for m in rng.choice(c["members"], size=min(4, len(c["members"])), replace=False):
            print(f"   [{m['first']}] {m['title'][:95]}")


if __name__ == "__main__":
    SITE.mkdir(parents=True, exist_ok=True)
    fig_volume()
    fig_confusion_and_tables()
    fig_ranking_profile()
    fig_fragmentation()
    fig_oct7()
    precision_sample()
