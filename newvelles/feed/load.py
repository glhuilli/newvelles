from typing import List


def load_paths() -> List[str]:  # pragma: no cover
    return [
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
        'http://rss.cnn.com/rss/cnn_topstories.rss'
    ]
