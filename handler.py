import json

from newvelles.config import config
from newvelles.feed.load import build_data_from_rss_feeds
from newvelles.feed.log import log_groups, log_visualization
from newvelles.models.grouping import build_visualization


CONFIG = config()


def run() -> bool:
    title_data = build_data_from_rss_feeds('./rss_source_short.txt')
    cluster_limit = int(CONFIG['PARAMS']['cluster_limit'])
    visualization_data, group_sentences = build_visualization(title_data,
                                                              cluster_limit=cluster_limit)
    # log data
    log_visualization(visualization_data, s3=True)
    log_groups(group_sentences)
    return True


def handler(event, context):
    if run():
        body = {
            "message": 'Successful run!',
            "input": event
        }
        response = {
            "statusCode": 200,
            "body": json.dumps(body)
        }
    else:
        body = {
            "message": 'Something went wrong',
            "input": event
        }
        response = {
            "statusCode": 500,
            "body": json.dumps(body)
        }

    return response
