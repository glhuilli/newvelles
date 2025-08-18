import time
from datetime import datetime

import click

from newvelles.config import config, debug
from newvelles.display.show import print_sorted_grouped_titles, print_viz
from newvelles.feed.load import build_data_from_rss_feeds
from newvelles.feed.log import log_groups, log_visualization
from newvelles.models.grouping import build_visualization

CONFIG = config()
DEBUG = debug()


def run(rss_file: str, s3: bool) -> None:
    title_data = build_data_from_rss_feeds(rss_file)
    cluster_limit = int(CONFIG["PARAMS"]["cluster_limit"])
    visualization_data, group_sentences = build_visualization(
        title_data, cluster_limit=cluster_limit
    )
    # log data
    log_visualization(visualization_data, s3=s3)
    log_groups(group_sentences)

    if DEBUG:
        print_sorted_grouped_titles(group_sentences)
        print_viz(visualization_data)


def run_daemon(rss_file, s3):
    while True:
        run(rss_file, s3)
        wait_time = int(float(CONFIG["DAEMON"]["wait_time"]) * 60)
        if CONFIG["DAEMON"]["debug"] == "True":
            print(
                "*" * 100 +
                f"\nLatest run: {datetime.now().isoformat()}\n" +
                f"\nwaiting for {wait_time} seconds..\n" +
                "*" * 100
            )
        time.sleep(wait_time)


@click.command()
@click.option("--rss_file", default="./data/rss_source.txt", help="Txt file with RSS urls")
@click.option("--daemon", is_flag=True, help="Runs in daemon mode")
@click.option("--s3", is_flag=True, help="Uploads latest news to S3 bucket")
def main(rss_file, daemon, s3):
    """
    Given a file with RSS links, generate a dictionary that can be used to visualize all news.

    Note that I'm decoupling the daemon config (via newvelles.ini) from the trigger (via click)
    """
    if daemon:
        run_daemon(rss_file, s3)
    else:
        run(rss_file, s3)


if __name__ == "__main__":
    main()
