import json
from datetime import datetime
from typing import Any, Dict, List

from newvelles.models.grouping import VISUALIZATION_VERSION
from newvelles.utils.s3 import upload_to_s3

_LATEST_PATH = '/var/data/newvelles'
_LOG_PATH = '/var/data/newvelles/logs'
_LOG_NAME = 'all_entries'
_LOG_GROUPED_NAME = 'all_grouped_entries'
_LOG_VISUALIZATION_NAME = 'newvelles_visualization'
_LOG_LATEST_VISUALIZATION_NAME = 'latest_news'
_LOG_LATEST_VISUALIZATION_METADATA_NAME = 'latest_news_metadata'
_S3_BUCKET = 'public-newvelles-data'


def _current_datetime():
    return '.'.join(datetime.now().isoformat().split('.')[:-1])


def log_entries(entries: Dict[str, List[Any]], output_path: str = _LOG_PATH) -> None:
    log_path = f"{output_path}/{_LOG_NAME}_{_current_datetime()}.jsons"
    with open(log_path, 'w') as f:
        for feed, _entries in entries.items():
            f.write(json.dumps({'feed': feed, 'entries': _entries}) + '\n')


def log_groups(grouped_sentences: Dict[int, List[str]], output_path: str = _LOG_PATH) -> None:
    log_path = f"{output_path}/{_LOG_GROUPED_NAME}_{_current_datetime()}.json"
    with open(log_path, 'w') as f:
        json.dump(grouped_sentences, f)


def log_visualization(visualization_data, output_path: str = _LOG_PATH, s3: bool = False) -> str:
    current_datetime = _current_datetime()
    viz_file_name = f'{_LOG_VISUALIZATION_NAME}_{VISUALIZATION_VERSION}'
    log_path = f"{output_path}/{viz_file_name}_{current_datetime}.json"
    with open(log_path, 'w') as f:
        json.dump(visualization_data, f)

    log_path_latest = f"{_LATEST_PATH}/{_LOG_LATEST_VISUALIZATION_NAME}.json"
    with open(log_path_latest, 'w') as f:
        json.dump(visualization_data, f)

    log_path_latest_current = f"./{_LOG_LATEST_VISUALIZATION_NAME}.json"
    with open(log_path_latest_current, 'w') as f:
        json.dump(visualization_data, f)

    if s3:
        upload_to_s3(_S3_BUCKET, f'{_LOG_LATEST_VISUALIZATION_NAME}.json',
                     json.dumps(visualization_data).encode('utf-8'))

    latest_metadata = {
        'datetime': current_datetime,
        'version': VISUALIZATION_VERSION,
        'latest_log_reference': log_path
    }
    log_path_latest_metadata = f"{_LATEST_PATH}/{_LOG_LATEST_VISUALIZATION_METADATA_NAME}.json"
    with open(log_path_latest_metadata, 'w') as f:
        json.dump(latest_metadata, f)

    return log_path
