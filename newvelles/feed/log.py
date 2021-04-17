from typing import Any, Dict, List
import json

from datetime import datetime


_LOG_PATH = '/var/data/newvelles/logs'
_LOG_NAME = 'all_entries'


def log_entries(entries: Dict[str, List[Any]], output_path: str = _LOG_PATH) -> None:
    log_path = f"{output_path}/{_LOG_NAME}_{'.'.join(datetime.now().isoformat().split('.')[:-1])}.json'"
    with open(log_path, 'w') as f:
        json.dump(entries, f)
