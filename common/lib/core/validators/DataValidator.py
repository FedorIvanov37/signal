from common.lib.core.validators.Validator import Validator
from common.lib.data_models.Config import Config
from common.lib.data_models.Validation import ValidationResult


class DataValidator:
    _config: Config

    @property
    def config(self):
        return self._config

    @config.setter
    def config(self, config):
        self._config = config

    def __init__(self, config: Config):
        self.config: Config = config
        self.validator = Validator(self.config)

    def validate_mti(self, mti):
        validation_result: ValidationResult = self.validator.validate_mti(mti, ValidationResult())
        self.validator.process_validation_result(validation_result)

    def validate_field_number(self, field_number: int | str):
        validation_result: ValidationResult = self.validator.validate_field_number(field_number, ValidationResult())
        self.validator.process_validation_result(validation_result)

    def validate_field_path(self, field_path):
        validation_result: ValidationResult = self.validator.validate_field_path(field_path, ValidationResult())
        self.validator.process_validation_result(validation_result)

    def validate_url(self, url):
        validation_result: ValidationResult = self.validator.validate_url(url, ValidationResult())
        self.validator.process_validation_result(validation_result)
