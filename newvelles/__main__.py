from collections import defaultdict

import click

from newvelles.feed.load import load_paths
from newvelles.feed.parser import parse_feed
from newvelles.utils.text import process_content


@click.command()
@click.option('--limit', default=10, help='Top N news')
@click.option('--query', default='', help='Limit news to a particular query')
@click.option('--stats', is_flag=True, help='Add stats for each news article')
def main(limit, query, stats):
    print(f'fetch news...{limit} {query} {stats}')
    feeds = load_paths()
    data = defaultdict(list)
    for feed_tuple in parse_feed(feeds):
        data[feed_tuple[0]].append(process_content(feed_tuple[1]))

    print(data)


if __name__ == '__main__':
    main()
