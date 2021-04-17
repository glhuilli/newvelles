from typing import Any, Dict
from collections import defaultdict

import click

from newvelles.display.show import print_sorted_grouped_titles
from newvelles.feed.load import load_paths
from newvelles.feed.log import log_entries
from newvelles.feed.parser import parse_feed


@click.command()
@click.option('--limit', default=10, help='Top N news')
@click.option('--query', default='', help='Limit news to a particular query')
@click.option('--stats', is_flag=True, help='Add stats for each news article')
def main(limit, query, stats):
    feeds = load_paths()
    sentences = []
    data: Dict[str, Any] = defaultdict(list)
    for feed_title, entry in parse_feed(feeds):
        sentences.append(entry.title)
        data[feed_title].append(entry)
    log_entries(data)
    print_sorted_grouped_titles(sentences, stats)


if __name__ == '__main__':
    main()
