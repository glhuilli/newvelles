from typing import Any, Dict, List
import json

from datetime import datetime


_LOG_PATH = '/var/data/newvelles/logs'
_LOG_NAME = 'all_entries'


def log_entries(entries: Dict[str, List[Any]], output_path: str = _LOG_PATH) -> None:
    log_path = f"{output_path}/{_LOG_NAME}_{'.'.join(datetime.now().isoformat().split('.')[:-1])}.jsons"
    with open(log_path, 'w') as f:
        for feed, entries in entries.items():
            f.write(json.dumps({'feed': feed, 'entries': entries})+'\n')
