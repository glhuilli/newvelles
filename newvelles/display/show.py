from typing import List

from newvelles.utils.text import group_sentences, load_embedding_model


_EMBEDDING_MODEL = load_embedding_model()


def print_sorted_grouped_titles(sentences: List[str], stats: bool) -> None:
    unique_sets = group_sentences(_EMBEDDING_MODEL, sentences)
    total_groups = 0
    for s in sorted([x for x in unique_sets if len(x) > 1], key=lambda x: len(x), reverse=True):
        print('*' * 100)
        total_groups += 1
        for i in s:
            print(sentences[i])
    if stats:
        print(f'total groups: {total_groups}')
