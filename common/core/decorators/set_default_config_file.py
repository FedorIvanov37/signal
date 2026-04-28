from common.core.enums.TermFilesPath import TermFilesPath
from functools import wraps
from pathlib import Path
from typing import Any


def set_default_config_file(cls):
    original_init = cls.__init__

    @wraps(original_init)
    def __init__(self, json_path: str | Path | None = None, **fields_data: Any) -> None:
        if json_path is None and not fields_data:
            json_path = TermFilesPath.CONFIG

        original_init(self, json_path=json_path, **fields_data)

    cls.__init__ = __init__

    return cls
