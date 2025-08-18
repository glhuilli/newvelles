import json
import os

# Configure TensorFlow Hub cache to use writable directory in Lambda
os.environ['TFHUB_CACHE_DIR'] = '/tmp/tfhub_cache'
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'  # Reduce TensorFlow logging

from newvelles.config import config
from newvelles.feed.load import build_data_from_rss_feeds, build_data_from_rss_feeds_list
from newvelles.feed.log import log_s3
from newvelles.models.grouping import build_visualization


CONFIG = config()

# Environment-aware RSS file selection
# Production: Full RSS source list (84 feeds)
# QA/Testing: Reliable subset for faster testing (13 feeds)
RSS_FILE_PRODUCTION = "/var/task/data/rss_source.txt"
RSS_FILE_QA = "/var/task/data/rss_qa_reliable.txt"

# Detect environment (production vs QA) based on S3 bucket configuration
def get_rss_file():
    # Check if QA environment variables are set
    qa_bucket = os.environ.get('AWS_S3_BUCKET', '')
    if 'qa' in qa_bucket.lower() or 'test' in qa_bucket.lower():
        print(f"🧪 QA/Testing environment detected (bucket: {qa_bucket})")
        return RSS_FILE_QA
    else:
        print("🏭 Production environment detected")
        return RSS_FILE_PRODUCTION

RSS_FILE = get_rss_file()

# Fallback RSS links in case file is not found
# Production fallback: Subset of reliable sources
# QA fallback: Same reliable sources for consistency
FALLBACK_RSS_LINKS = [
    'https://finance.yahoo.com/rss/',
    'https://rss.nytimes.com/services/xml/rss/nyt/HomePage.xml',
    'https://feeds.npr.org/1001/rss.xml',
    'https://www.wired.com/feed',
    'https://feeds.bbci.co.uk/news/world/rss.xml',
    'https://rss.nytimes.com/services/xml/rss/nyt/Technology.xml',
    'https://lifehacker.com/rss',
    'https://feeds.npr.org/1019/rss.xml',
    'https://moxie.foxnews.com/google-publisher/politics.xml',
    'https://rss.politico.com/healthcare.xml',
    'https://www.yahoo.com/news/rss',
    'https://nypost.com/feed/',
    'https://www.newsweek.com/rss',
]


def run() -> bool:
    try:
        # Try to load from file first
        title_data = build_data_from_rss_feeds(RSS_FILE)
        feed_count = 84 if 'rss_source.txt' in RSS_FILE else 13
        print(f"✅ Loaded RSS feeds from file: {RSS_FILE}")
        print(f"📡 Using {feed_count} RSS sources ({'production' if feed_count == 84 else 'QA'} configuration)")
        print(f"📊 Processed {len(title_data)} news entries from RSS feeds")
    except Exception as e:
        # Fallback to hardcoded list if file not found
        print(f"⚠️ Could not load RSS file ({e}), using fallback list")
        title_data = build_data_from_rss_feeds_list(FALLBACK_RSS_LINKS, log=False)
        print(f"📊 Processed {len(title_data)} news entries from fallback feeds")
    
    if not title_data:
        print("❌ No news data found - aborting")
        return False
    
    cluster_limit = int(CONFIG['PARAMS']['cluster_limit'])
    print(f"🧮 Building visualization with cluster limit: {cluster_limit}")
    
    visualization_data, group_sentences = build_visualization(title_data,
                                                              cluster_limit=cluster_limit)
    print(f"📈 Generated visualization with {len(visualization_data.get('groups', []))} groups")
    
    print("📤 Uploading to S3...")
    log_s3(visualization_data)
    print("✅ S3 upload completed successfully")
    
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
