import json

from newvelles.config import config
from newvelles.feed.load import build_data_from_rss_feeds_list
from newvelles.feed.log import log_s3
from newvelles.models.grouping import build_visualization


CONFIG = config()


RSS_LINKS = [
    'https://finance.yahoo.com/rss/',
    'http://www.nytimes.com/services/xml/rss/nyt/HomePage.xml',
    'https://www.huffpost.com/section/front-page/feed',
    'https://feeds.npr.org/1001/rss.xml',
    'http://feeds.bbci.co.uk/news/world/us_and_canada/rss.xml',
    'https://rss.politico.com/economy.xml',
    'https://rss.politico.com/healthcare.xml',
    'https://rss.politico.com/congress.xml',
    'https://rss.politico.com/defense.xml',
    'https://rss.politico.com/energy.xml',
    'http://rss.cnn.com/rss/cnn_topstories.rss',
    'https://lifehacker.com/rss',
    'https://www.yahoo.com/news/rss',
    'https://feeds.npr.org/1019/rss.xml',
    'https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml',
    'https://www.wired.com/feed',
    'http://feeds.feedburner.com/FrontlineEditorsNotes',
    'https://www.newsweek.com/rss',
    'https://newyork.cbslocal.com/feed/',
    'https://washington.cbslocal.com/feed/',
    'https://sanfrancisco.cbslocal.com/feed/',
    'https://www.nydailynews.com/arcio/rss/category/news/?sort=display_date:desc',
    'https://www.mercurynews.com/feed/',
    'https://www.washingtontimes.com/rss/headlines/news/',
    'https://observer.com/feed/',
    'https://abc7news.com/feed/'
]


def run() -> bool:
    title_data = build_data_from_rss_feeds_list(RSS_LINKS, log=False)
    cluster_limit = int(CONFIG['PARAMS']['cluster_limit'])
    visualization_data, group_sentences = build_visualization(title_data,
                                                              cluster_limit=cluster_limit)
    log_s3(visualization_data)
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
