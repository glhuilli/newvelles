import time

import click

from newvelles.config import config, debug
from newvelles.display.show import print_sorted_grouped_titles, print_viz
from newvelles.feed.load import build_data_from_rss_feeds
from newvelles.feed.log import log_groups, log_visualization
from newvelles.models.grouping import build_visualization

CONFIG = config()
DEBUG = debug()


def run(rss_file):
    title_data = build_data_from_rss_feeds(rss_file)
    cluster_limit = int(CONFIG['PARAMS']['cluster_limit'])
    visualization_data, group_sentences = build_visualization(title_data,
                                                              cluster_limit=cluster_limit)
    # log data
    log_visualization(visualization_data)
    log_groups(group_sentences)

    if DEBUG:
        print_sorted_grouped_titles(group_sentences)
        print_viz(visualization_data)


def run_daemon(rss_file):
    run(rss_file)
    wait_time = int(CONFIG['DAEMON']['wait_time']) * 60
    if CONFIG['DAEMON']['debug'] == 'True':
        print('*' * 100 + f'\nwaiting for {wait_time} seconds..\n' + '*' * 100)
    time.sleep(wait_time)


@click.command()
@click.option('--rss_file', default='./data/rss_source.txt', help='Txt file with RSS urls')
@click.option('--daemon', is_flag=True, help='Runs in daemon mode')
def main(rss_file, daemon):
    """
    Given a file with RSS links, generate a dictionary that can be used to visualize all news.

    Note that I'm decoupling the daemon config (via newvelles.ini) from the trigger (via click)
    """
    if daemon:
        while True:
            run_daemon(rss_file)
    else:
        run(rss_file)


if __name__ == '__main__':
    main()
