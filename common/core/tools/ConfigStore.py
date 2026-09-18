"""Validated configuration persistence; failed writes leave the old file intact."""
from common.core.tools.DebugTrace import trace_operation
import os
import tempfile
from pathlib import Path

from pydantic import ValidationError
from loguru import logger

from common.core.data_models.Config import Config
from common.core.enums.TermFilesPath import TermFilesPath
from common.core.exceptions.exceptions import DataFileError


@trace_operation
def save_config(config: Config, filename=TermFilesPath.CONFIG) -> None:
    path = Path(filename)
    logger.debug("Config save requested: file={}", path)
    try:
        # Dump/validate, rather than model_validate(instance), also checks mutated models.
        validated = Config.model_validate_json(config.model_dump_json())
    except (ValidationError, ValueError) as error:
        raise DataFileError(path, "save", "configuration contains invalid values") from error
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", suffix=".tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(validated.model_dump_json(indent=4))
            stream.flush()
            os.fsync(stream.fileno())
        logger.debug("Config temporary file flushed; replacing target: file={}", path)
        os.replace(temporary, path)
        logger.debug("Config file replaced successfully: file={}", path)
    except OSError as error:
        reason = "access denied; check file and directory permissions" if isinstance(error, PermissionError) else error.strerror or str(error)
        raise DataFileError(path, "save", reason) from error
    finally:
        if temporary is not None:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                pass  # Preserve the original failure; the target was never truncated.
