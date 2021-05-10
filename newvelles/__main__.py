from typing import Any, Dict
from collections import defaultdict
import click

from newvelles.models.grouping import build_visualization
from newvelles.display.show import print_sorted_grouped_titles, print_viz
from newvelles.feed.load import load_rss
from newvelles.feed.log import log_entries, log_groups, log_visualization
from newvelles.feed.parser import parse_feed


def build_data(feeds: Any) -> Dict[str, str]:
    title_data = {}
    news_data: Dict[str, Any] = defaultdict(list)
    for feed_title, entry in parse_feed(feeds):
        title_data[entry.title] = entry.link
        news_data[feed_title].append(entry)
    log_entries(news_data)
    return title_data


@click.command()
@click.option('--rss_file', default='./data/rss_source.txt', help='Txt file with RSS urls')
@click.option('--limit', default=10, help='Top N news')
@click.option('--query', default='', help='Limit news to a particular query')
@click.option('--stats', is_flag=True, help='Add stats for each news article')
@click.option('--debug', is_flag=True, help='Add stats for each news article')
def main(rss_file, limit, query, stats, debug):
    feeds = load_rss(rss_file)
    title_data = build_data(feeds)
    visualization_data, group_sentences = build_visualization(title_data, debug)

    # log data
    log_visualization(visualization_data)
    log_groups(group_sentences)

    if debug:
        print_sorted_grouped_titles(group_sentences, stats)
        print_viz(visualization_data)


if __name__ == '__main__':
    main()
