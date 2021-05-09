from typing import Any, Dict, List
import json

from datetime import datetime

_LATEST_PATH = '/var/data/newvelles'
_LOG_PATH = '/var/data/newvelles/logs'
_LOG_NAME = 'all_entries'
_LOG_GROUPED_NAME = 'all_grouped_entries'
_LOG_VISUALIZATION_NAME = 'newvelles_visualization'
_LOG_LATEST_VISUALIZATION_NAME = 'latest_news'
_LOG_LATEST_VISUALIZATION_METADATA_NAME = 'latest_news_metadata'

_VISUALIZATION_VERSION = '1.0'


def log_entries(entries: Dict[str, List[Any]], output_path: str = _LOG_PATH) -> None:
    log_path = f"{output_path}/{_LOG_NAME}_{'.'.join(datetime.now().isoformat().split('.')[:-1])}.jsons"
    with open(log_path, 'w') as f:
        for feed, entries in entries.items():
            f.write(json.dumps({'feed': feed, 'entries': entries})+'\n')


def log_groups(grouped_sentences: Dict[int, List[str]], output_path: str = _LOG_PATH) -> None:
    log_path = f"{output_path}/{_LOG_GROUPED_NAME}_{'.'.join(datetime.now().isoformat().split('.')[:-1])}.json"
    with open(log_path, 'w') as f:
        json.dump(grouped_sentences, f)


def log_visualization(visualization_data, output_path: str = _LOG_PATH) -> str:
    current_datetime = datetime.now().isoformat().split('.')[:-1]
    log_path = f"{output_path}/{_LOG_VISUALIZATION_NAME}_{_VISUALIZATION_VERSION}_{'.'.join(current_datetime)}.json"
    with open(log_path, 'w') as f:
        json.dump(visualization_data, f)

    log_path_latest = f"{_LATEST_PATH}/{_LOG_LATEST_VISUALIZATION_NAME}.json"
    with open(log_path_latest, 'w') as f:
        json.dump(visualization_data, f)

    latest_metadata = {
        'datetime': current_datetime,
        'version': _VISUALIZATION_VERSION,
        'latest_log_reference': log_path
    }
    log_path_latest_metadata = f"{_LATEST_PATH}/{_LOG_LATEST_VISUALIZATION_METADATA_NAME}.json"
    with open(log_path_latest_metadata, 'w') as f:
        json.dump(latest_metadata, f)

    return log_path
