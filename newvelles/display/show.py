import json
from typing import Dict, List


def print_sorted_grouped_titles(group_sentences: Dict[int, List[str]], stats: bool) -> None:
    for group, sentences in group_sentences.items():
        print('*' * 50)
        for sentence in sentences:
            print(sentence)
    if stats:
        print(f'total groups: {len(group_sentences)}')


def print_viz(visualization):
    print(json.dumps(visualization, indent=2))
