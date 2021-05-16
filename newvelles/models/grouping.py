import json
from collections import defaultdict
from typing import Dict, List, Tuple

from newvelles.config import debug
from newvelles.utils.text import get_top_words, group_sentences, load_embedding_model

# This version needs to be updated in case major
# changes are done to the visualization files below.
VISUALIZATION_VERSION = '0.2.0'
DEBUG = debug()
_EMBEDDING_MODEL = load_embedding_model()


def generate_top_words(groups_indexes, similar_sets, sentences):
    top_words_group = defaultdict(list)
    all_sentences = set()
    for idx, group_indexes in groups_indexes.items():
        grp_sentences = set()
        if len(group_indexes) > 1:
            for gidx in group_indexes:
                for ss in similar_sets:
                    if ss[0] == gidx:
                        for gidx2 in group_indexes:
                            if gidx2 in ss[1] and gidx != gidx2:
                                grp_sentences.add(sentences[gidx])
                                all_sentences.add(sentences[gidx])
        if DEBUG:
            print(get_top_words(list(grp_sentences)))
        top_words_group[idx] = ' '.join([x[0] for x in get_top_words(list(grp_sentences))])
    if DEBUG:
        print(f'Total news articles: {len(all_sentences)}')
        print(get_top_words(list(all_sentences), top_n=50))

    return top_words_group


def build_visualization(
        title_link: Dict[str, str],
        cluster_limit: int = 0) -> Tuple[Dict[int, Dict[str, List[str]]], Dict[int, List[str]]]:
    """
    data is defined by {sentence: link}

    TODO: refactor this method so it's easier to understand.
    TODO: Use the limit to generate only top N news
    """
    titles = [x[0] for x in title_link.items()]
    similar_sets, unique_sets = group_sentences(_EMBEDDING_MODEL, titles)
    # TODO: consider removing title_groups (currently only used for debugging)
    title_groups = defaultdict(list)
    title_groups_indexes = defaultdict(list)
    for idx, group in enumerate(
            sorted([x for x in unique_sets if len(x) > cluster_limit - 1],
                   key=lambda x: len(x),
                   reverse=True)):
        for title_idx in group:
            title_groups[idx].append(titles[title_idx])
            title_groups_indexes[idx].append(title_idx)

    top_words_group = generate_top_words(title_groups_indexes, similar_sets, titles)
    visualization = defaultdict(lambda: defaultdict(lambda: defaultdict(str)))
    for idx, group_indexes in title_groups_indexes.items():
        grp_top_words = top_words_group[idx]
        if len(group_indexes) > cluster_limit:
            if len(group_indexes) == 2:  # Needed to remove duplicate groups
                grp_idx = group_indexes[0]
                grp_idx_header, group_titles = get_top_words_gidx(grp_idx, group_indexes,
                                                                  similar_sets, titles)
                for title in group_titles:
                    visualization[grp_top_words][grp_idx_header][title] = title_link[title]
            else:
                for grp_idx in group_indexes:
                    grp_idx_header, group_titles = get_top_words_gidx(grp_idx, group_indexes,
                                                                      similar_sets, titles)
                    for title in group_titles:
                        visualization[grp_top_words][grp_idx_header][title] = title_link[title]

        # TODO: review if should include "other" news or not
        #  not convinced yet it helps as it's too much noise.
        # if include_other:
        #     grp_idx = group_indexes[0]
        #     visualization['other']['news'][titles[grp_idx]] = title_link[
        #         titles[grp_idx]]
    if DEBUG:
        print(json.dumps(visualization, indent=2))
    return visualization, title_groups


def get_top_words_gidx(grp_idx, group_indexes, similar_sets, titles):
    added = {grp_idx}
    group_titles = [titles[grp_idx]]
    for ss in similar_sets:
        if ss[0] == grp_idx:
            for grp_idx2 in group_indexes:
                if grp_idx2 in added:
                    continue
                if grp_idx2 in ss[1] and grp_idx != grp_idx2:
                    group_titles.append(titles[grp_idx2])
                    added.add(grp_idx2)
    grp_idx_header = ' '.join([x[0] for x in get_top_words(group_titles, top_n=5)])
    return grp_idx_header, group_titles
