from loguru import logger
from common.lib.data_models.Types import FieldPath
from common.lib.data_models.Transaction import Transaction, TypeFields
from common.lib.core.EpaySpecification import EpaySpecification
from common.lib.core.Parser import Parser
from common.lib.data_models.Config import Config
from common.lib.enums.TextConstants import TextConstants
from common.lib.enums.ReleaseDefinition import ReleaseDefinition
from PyQt6.QtCore import QObject


class LogPrinter(QObject):
    spec: EpaySpecification = EpaySpecification()
    default_level = logger.info
    _config: Config

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, config):
        self._config = config

    def __init__(self, config: Config):
        super().__init__()
        self.config = config

    @staticmethod
    def print_multi_row(data: str, level=default_level):
        for string in data.splitlines():
            level(string)

        level("")

    @staticmethod
    def startup_finished(level=default_level):
        level("Startup finished")

    def print_startup_info(self, level=default_level):
        LogPrinter.print_multi_row(TextConstants.HELLO_MESSAGE)
        self.print_config(self.config, level=level)

    def print_config(self, config: Config | None = None, path=None, level=default_level):
        if config is None:
            config = self.config

        config_data = f"## Configuration parameters ##\n\n"

        if path is not None:
            config_data = f"{config_data}Path: {path}\n\n"

        config_data = f"{config_data}{config.model_dump_json(indent=4)}\n\n"
        config_data = f"{config_data}## End of configuration parameters ##"

        self.print_multi_row(config_data, level=level)

    def print_dump(self, transaction: Transaction, level=logger.debug):
        if not (dump := Parser.create_sv_dump(transaction)):
            return

        self.print_multi_row(dump, level)

    def print_about(self):
        elements = [
            TextConstants.HELLO_MESSAGE,
            "Use only on test environment",
            f"Version {ReleaseDefinition.VERSION}",
            f"Released in {ReleaseDefinition.RELEASE}",
            f"Developed by {ReleaseDefinition.AUTHOR}",
            f"Contact {ReleaseDefinition.EMAIL}"
        ]

        message = "\n\n  ".join(elements)

        self.print_multi_row(message)

    def print_transaction(self, transaction: Transaction, level=default_level):
        if transaction.is_keep_alive:
            return

        transaction: Transaction = transaction.copy(deep=True)
        transaction: Transaction = Parser.parse_complex_fields(transaction, split=False)

        if self.config.fields.hide_secrets:
            transaction: Transaction = Parser.hide_secret_fields(transaction)

        level(str())

        bitmap = ", ".join(transaction.data_fields.keys())
        trans_id = transaction.trans_id

        if transaction.matched and not transaction.is_request:
            trans_id = transaction.match_id

        level(f"[TRANS_ID][{trans_id}]")

        if transaction.utrnno:
            level(f"[UTRNNO  ][{transaction.utrnno}]")

        level(f"[MSG_TYPE][{transaction.message_type}]")
        level(f"[BITMAP  ][{bitmap}]")

        desc_length = self.get_max_desc_length(transaction)

        for field, field_data in transaction.data_fields.items():
            message: str = str()
            length: str = str(len(field_data))

            for element in field, length, field_data:
                size: int = int() if element is field_data else 3
                message: str = message + f"[{element.zfill(size)}]"

            if self.config.debug.print_description:
                if description := self.get_field_description([field]):
                    message = f"[%-{desc_length}s]%s" % (description, message)

            level(message)

            if not self.spec.is_field_complex([field]):
                continue

            if not self.config.debug.parse_subfields:
                continue

            if isinstance(field_data, str):
                try:
                    self.print_complex_field(field, Parser.split_complex_field(field, field_data), desc_len=desc_length)
                except ValueError as parsing_error:
                    logger.error(f"Cannot parse field {field} data: {parsing_error}")

        level(str())

    def print_complex_field(
            self,
            field_number,
            field_data: TypeFields,
            field_path: list | None = None,
            desc_len: int = 0
    ):

        if not self.config.debug.parse_subfields:
            return

        if field_path is None:
            field_path = [field_number]

        for subfield, subfield_data in field_data.items():
            if not isinstance(subfield_data, str):
                field_path.append(subfield)
                self.print_complex_field(field_number, subfield_data, field_path, desc_len)
                field_path.pop()
                continue

            root_field = field_path[int()]
            root_field = root_field.zfill(3)
            fields = field_path[1:]
            fields.insert(int(), root_field)
            message = '.'.join(fields)
            message = f"[{message}.{subfield}]"
            message = f"{message}[{str(len(subfield_data)).zfill(3)}]"
            message = f"{message}[{subfield_data}]"

            if self.config.debug.print_description:
                field_desc = self.get_field_description(field_path + [subfield])
                message = f"[%-{desc_len}s]%s" % (field_desc, message)

            logger.info(message)

    def get_max_desc_length(self, transaction: Transaction) -> int:
        desc_length = int()
        data_fields: TypeFields = dict()

        for field, field_data in transaction.data_fields.items():
            if not self.spec.is_field_complex([field]):
                data_fields[field] = field_data
                continue

            if not self.config.debug.parse_subfields:
                data_fields[field] = field_data
                continue

            if isinstance(field_data, str):
                try:
                    field_data = Parser.split_complex_field(field, field_data)
                except ValueError:
                    continue

            data_fields[field] = field_data

        for path in self.get_all_paths(data_fields):
            if not (field_spec := self.spec.get_field_spec(path)):
                continue

            if not (field_desc := field_spec.description):
                continue

            if len(field_desc) > desc_length:
                desc_length = len(field_desc)

        return desc_length

    def get_all_paths(self, fields: TypeFields, prefix=None):
        if prefix is None:
            prefix = list()

        paths = list()

        for key, value in fields.items():
            current_path = prefix + [key]
            paths.append(current_path)

            if isinstance(value, dict):
                paths.extend(self.get_all_paths(value, current_path))

        return paths

    def get_field_description(self, field_path: FieldPath):
        if not (field_spec := self.spec.get_field_spec(field_path)):
            return str()

        if not (field_description := field_spec.description):
            return str()

        return field_description

    @staticmethod
    def print_version(level=default_level):
        level(f"{TextConstants.SYSTEM_NAME} {ReleaseDefinition.VERSION} | {ReleaseDefinition.RELEASE}")
