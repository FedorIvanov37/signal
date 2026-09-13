from pathlib import Path

from common.core.data_models.Config import Config
from common.core.enums.TermFilesPath import TermFilesPath


def load_startup_config():
    """Use defaults only when the regular configuration file is missing."""
    try:
        return Config(TermFilesPath.CONFIG), None
    except (ValueError, OSError) as error:
        missing = isinstance(error, FileNotFoundError) or isinstance(error.__cause__, FileNotFoundError)
        if not missing or not Path(TermFilesPath.DEFAULT_CONFIG).is_file():
            raise
    config = Config(TermFilesPath.DEFAULT_CONFIG)
    # Subsequent saves belong to the regular config, never the defaults template.
    config._source_file = str(Path(TermFilesPath.CONFIG).resolve())
    return config, (f'Configuration file "{TermFilesPath.CONFIG}" not found. '
                    'Default settings have been loaded')
