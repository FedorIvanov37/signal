from common.lib.core.validators.Validator import Validator
from common.lib.data_models.Config import Config
from common.lib.data_models.Transaction import Transaction
from common.lib.data_models.Validation import ValidationResult
from common.lib.data_models.Types import FieldPath
from contextlib import suppress


class TransValidator:
    _config: Config

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, config):
        self._config = config

        with suppress(AttributeError):
            self.validator.config = config

    def __init__(self, config: Config):
        self._config = config
        self.validator = Validator(self.config)

    def validate_transaction(self, transaction: Transaction) -> None:
        validation_result: ValidationResult = ValidationResult()
        validation_result = self.validator.validate_mti(transaction.message_type, validation_result)
        validation_result = self.validator.validate_fields(transaction.data_fields, validation_result)
        self.validator.process_validation_result(validation_result)

    def validate_fields(self, fields) -> None:
        validation_result: ValidationResult = self.validator.validate_fields(fields, ValidationResult())
        self.validator.process_validation_result(validation_result)

    def validate_field_spec(self, field_path: FieldPath) -> None:
        validation_result: ValidationResult = self.validator.validate_field_spec(field_path, ValidationResult())
        self.validator.process_validation_result(validation_result)
