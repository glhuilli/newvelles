from typing import Dict, List
from collections import defaultdict

import click

from newvelles.feed.load import load_paths
from newvelles.feed.parser import parse_feed
from newvelles.utils.text import group_sentences, load_embedding_model


EMBEDDING_MODEL = load_embedding_model()


@click.command()
@click.option('--limit', default=10, help='Top N news')
@click.option('--query', default='', help='Limit news to a particular query')
@click.option('--stats', is_flag=True, help='Add stats for each news article')
def main(limit, query, stats):
    # print(f'fetch news...{limit} {query} {stats}')
    feeds = load_paths()
    data: Dict[str, List[str]] = defaultdict(list)
    sentences = []
    for feed_tuple in parse_feed(feeds):
        data[feed_tuple[0]].append(feed_tuple[1])
        sentences.append(feed_tuple[1])
    unique_sets = group_sentences(EMBEDDING_MODEL, sentences)
    all_news = []
    for s in unique_sets:
        if len(s) > 1:
            print('******')
            for i in s:
                print(sentences[i])
        else:
            all_news.append(sentences[s[0]])
    for s in all_news:
        print(s)


if __name__ == '__main__':
    main()
