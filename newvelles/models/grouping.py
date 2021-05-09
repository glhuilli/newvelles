from typing import Any, Dict, List, NamedTuple, Tuple
from collections import defaultdict, Counter

from newvelles.utils.text import group_sentences, load_embedding_model, process_content


_EMBEDDING_MODEL = load_embedding_model()


def build_visualization(data: Dict[str, str], debug: bool) -> Tuple[Dict[int, Dict[str, List[str]]], Dict[int, List[str]]]:
    """
    data is defined by {sentence: link}

    TODO: refactor this method.
    """
    sentences = [x[0] for x in data.items()]
    similar_sets, unique_sets = group_sentences(_EMBEDDING_MODEL, sentences)
    groups = defaultdict(list)
    groups_indexes = defaultdict(list)
    for idx, group in enumerate(sorted([x for x in unique_sets if len(x) > 1], key=lambda x: len(x), reverse=True)):
        for title_idx in group:
            groups[idx].append(sentences[title_idx])
            groups_indexes[idx].append(title_idx)

    top_words_group = defaultdict(list)
    all_sentences = set()
    for idx, group_indexes in groups_indexes.items():
        grp_sentences = set()
        if len(group_indexes):
            for gidx in group_indexes:
                for ss in similar_sets:
                    if ss[0] == gidx:
                        for gidx2 in group_indexes:
                            if gidx2 in ss[1] and gidx != gidx2:
                                grp_sentences.add(sentences[gidx])
                                all_sentences.add(sentences[gidx])
        if debug:
            print(get_top_words(list(grp_sentences)))
        top_words_group[idx] = ' '.join([x[0] for x in get_top_words(list(grp_sentences))])

    if debug:
        print(f'Total news articles: {len(all_sentences)}')
        print(get_top_words(list(all_sentences), top_n=50))

    visualization = defaultdict(lambda: defaultdict(lambda: defaultdict(str)))
    for idx, group_indexes in groups_indexes.items():
        if len(group_indexes):
            for gidx in group_indexes:
                for ss in similar_sets:
                    if ss[0] == gidx:
                        for gidx2 in group_indexes:
                            if gidx2 in ss[1] and gidx != gidx2:
                                grp_top_words = top_words_group[idx]
                                visualization[grp_top_words][sentences[gidx]][sentences[gidx2]] = data[sentences[gidx2]]

    return visualization, groups


def get_top_words(sentences: List[str], top_n: int = 10) -> List[Tuple[str, int]]:
    words = Counter()
    for sentence in sentences:
        words.update(process_content(sentence))
    return sorted(words.items(), key=lambda x: x[1], reverse=True)[:top_n]
