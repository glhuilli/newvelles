import click
import json
import os

from newvelles.config import config, debug
from newvelles.display.show import print_sorted_grouped_titles, print_viz
from newvelles.feed.load import build_data_from_rss_feeds
from newvelles.models.grouping import build_visualization


@click.command()
@click.option('--rss_file', default='./data/rss_source_short.txt', help='Txt file with RSS urls')
def main(rss_file):
    if not os.path.exists('./data/rss_titles.json'):
        print('Building title data...')
        title_data = build_data_from_rss_feeds(rss_file)
        with open('./data/rss_titles.json', 'w') as f:
            json.dump(title_data, f, indent=2)
    else:
        print('Loading title data...')
        with open('./data/rss_titles.json', 'r') as f:
            title_data = json.load(f)
    visualization_data, _ = build_visualization(title_data)
    print_viz(visualization_data)
    print_sorted_grouped_titles(visualization_data)


if __name__ == '__main__':
    main()
