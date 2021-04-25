from typing import List


def load_rss(rss_file_path) -> List[str]:  # pragma: no cover
    with open(rss_file_path, 'r') as f:
        for line in f.readlines():
            yield line.strip()
