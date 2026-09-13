from common.core.tools.DebugTrace import trace_operation
from os import remove, listdir, path, makedirs
from random import sample
from datetime import datetime
from loguru import logger
from os.path import abspath, basename
from common.core.data_models.Config import Config
from common.core.enums.TermFilesPath import TermDirs
from common.core.tools.EpaySpecification import EpaySpecification
from common.core.data_models.EpaySpecificationModel import EpaySpecModel


class SpecFilesRotator:
    spec: EpaySpecification = EpaySpecification()
    filename_head = "spec_backup_"
    filename_tail = ".json"
    date_format = "%Y%m%d_%H%M%S"

    def __init__(self, config: Config):
        self.config = config

    def get_spec_file_name(self):
        file_unique_nuber = "".join(str(num) for num in sample(range(0, 10), 5))
        filename = f"{self.filename_head}{datetime.now():{self.date_format}}_{file_unique_nuber}{self.filename_tail}"
        filename = f"{TermDirs.SPEC_BACKUP_DIR}/{filename}"
        filename = path.normpath(filename)

        return filename

    @trace_operation
    def backup_spec(self, required=False, specification=None) -> str | None:
        source = specification if specification is not None else self.spec.spec
        try:
            source = EpaySpecModel.model_validate(source.model_dump())
            source.validate_for_use()
        except ValueError:
            if required:
                raise
            logger.warning('Specification backup skipped: no valid specification is available')
            return
        if not (filename := self.get_spec_file_name()):
            logger.error("Cannot determine specification backup filename")
            return

        try:
            makedirs(TermDirs.SPEC_BACKUP_DIR, exist_ok=True)
            backup_files = [name for name in listdir(TermDirs.SPEC_BACKUP_DIR)
                            if name.startswith(self.filename_head) and name.endswith(self.filename_tail)]
        except Exception as dir_access_error:
            if required:
                raise
            logger.error(f"Cannot get specification backup files list: {dir_access_error}")
            return

        if backup_files:
            logger.debug("Specification backup scan: existing_files={}", len(backup_files))

            backup_files.sort(reverse=True)
            last_backup_file = backup_files[int()]
            try:
                last_backup_spec = EpaySpecModel(abspath(f"{TermDirs.SPEC_BACKUP_DIR}/{last_backup_file}"))
            except Exception:
                last_backup_spec = None

            if last_backup_spec == source:  # Specification was not changed; return
                logger.debug("Specification backup skipped: reason=unchanged file={}", last_backup_file)
                return last_backup_file

        with open(filename, "w", encoding='utf-8') as file:
            file.write(source.model_dump_json(indent=4))
        logger.debug("Specification backup written: file={}", filename)

        self.clear_spec_backup(keep=basename(filename))

        return basename(filename)

    @trace_operation
    def clear_spec_backup(self, keep=None):
        storage_debt = max(1, self.config.specification.backup_storage_depth if self.config.specification.backup_storage else 1)

        try:
            files = [name for name in listdir(TermDirs.SPEC_BACKUP_DIR)
                     if name.startswith(self.filename_head) and name.endswith(self.filename_tail)]
        except Exception as dir_access_error:
            logger.error(f"Cannot get specification backup files list: {dir_access_error}")
            return

        files.sort(key=lambda name: (name == keep, path.getmtime(f"{TermDirs.SPEC_BACKUP_DIR}/{name}")), reverse=True)
        valid_files = []
        for name in files:
            try:
                EpaySpecModel(f"{TermDirs.SPEC_BACKUP_DIR}/{name}").validate_for_use()
            except (ValueError, OSError):
                continue
            valid_files.append(name)
        files = valid_files
        logger.debug("Specification backup cleanup: existing_files={} retention_count={}", len(files), storage_debt)

        while files:
            if len(files) <= storage_debt:
                return

            file = files.pop()

            if not (file.startswith(self.filename_head) and file.endswith(self.filename_tail)):
                continue

            try:
                remove(f"{TermDirs.SPEC_BACKUP_DIR}/{file}")
                logger.debug("Specification backup removed: file={}", file)
            except Exception as remove_error:
                logger.error(f"Cannot clean up specification backup directory: {remove_error}")
                return
