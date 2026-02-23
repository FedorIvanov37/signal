from os import remove, listdir, path
from random import sample
from datetime import datetime
from loguru import logger
from common.lib.data_models.Config import Config
from common.lib.enums.TermFilesPath import TermDirs
from common.lib.core.EpaySpecification import EpaySpecification
from common.lib.decorators.singleton import singleton


@singleton
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

    def backup_spec(self) -> str | None:
        if not (filename := self.get_spec_file_name()):
            logger.error("Cannot get Specification Backup filename")
            return

        with open(filename, "w") as file:
            file.write(self.spec.spec.model_dump_json(indent=4))

        self.clear_spec_backup()

        return filename

    def clear_spec_backup(self):
        storage_debt = self.config.specification.backup_storage_depth

        try:
            files = listdir(TermDirs.SPEC_BACKUP_DIR)
        except Exception as dir_access_error:
            logger.error(f"Cannot get specification backup files list: {dir_access_error}")
            return

        files.sort(reverse=True)

        while files:
            if len(files) <= storage_debt:
                return

            file = files.pop()

            if not (file.startswith(self.filename_head) and file.endswith(self.filename_tail)):
                continue

            try:
                remove(f"{TermDirs.SPEC_BACKUP_DIR}/{file}")
            except Exception as remove_error:
                logger.error(f"Cannot cleanup specification backup directory: {remove_error}")
                return
