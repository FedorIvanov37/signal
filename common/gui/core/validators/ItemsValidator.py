from common.lib.core.validators.Validator import Validator
from common.lib.core.EpaySpecification import EpaySpecification
from common.lib.data_models.Config import Config
from common.gui.core.json_items.FIeldItem import FieldItem
from common.lib.data_models.Validation import ValidationResult, ValidationTypes
from common.lib.data_models.EpaySpecificationModel import IsoField, Justification


class ItemsValidator:
    spec: EpaySpecification = EpaySpecification()

    def __init__(self, config: Config):
        self.config: Config = config
        self.validator = Validator(self.config)

    def validate_item(self, item: FieldItem):
        validation_result: ValidationResult = ValidationResult()
        validation_result: ValidationResult = self._validate_field_number(item, validation_result)

        field_path: list[str] = item.get_field_path()

        if not self.spec.is_field_complex(field_path):
            validation_result: ValidationResult = self.validator.validate_field_data(
                field_path, item.field_data, validation_result)

        self.validator.process_validation_result(validation_result)

    def validate_field_number(self, item: FieldItem, validation_result: ValidationResult | None = None):
        if validation_result is None:
            validation_result: ValidationResult = ValidationResult()

        validation_result: ValidationResult = self._validate_field_number(item, validation_result)

        self.validator.process_validation_result(validation_result)

    def _validate_field_number(self, item: FieldItem, validation_result: ValidationResult | None = None):
        if validation_result is None:
            validation_result = ValidationResult()

        field_path = item.get_field_path()

        validation_map = {
            self.validator.validate_field_path: (field_path, validation_result),
            self.validator.validate_field_spec: (field_path, validation_result),
            self._validate_duplicates: (item, validation_result),
        }

        for validation, args in validation_map.items():
            validation_result: ValidationResult = validation(*args)

        return validation_result

    def validate_item_spec(self, item: FieldItem):
        validation_result: ValidationResult = ValidationResult()

        if field_path := item.get_field_path():
            validation_result: ValidationResult = self.validator.validate_field_spec(field_path, validation_result)
        else:
            validation_result.errors[ValidationTypes.FIELD_PATH_VALIDATION].add("Lost field path")

        self.validator.process_validation_result(validation_result)

    def validate_duplicates(self, item: FieldItem, parent: FieldItem):
        validation_result: ValidationResult = self._validate_duplicates(item, ValidationResult(), parent)
        self.validator.process_validation_result(validation_result)

    @staticmethod
    def _validate_duplicates(item: FieldItem, validation_result: ValidationResult, parent: FieldItem = None):
        errors = validation_result.errors[ValidationTypes.DUPLICATED_FIELDS_VALIDATION]

        if item is None:
            return validation_result

        if not item.field_number:
            return validation_result

        if parent is None and not (parent := item.parent()):
            return validation_result

        field_numbers = [
            child_item.field_number for child_item in parent.get_children()
            if child_item.field_number and not child_item.is_disabled
        ]

        if field_numbers.count(item.field_number) > 1:
            errors.add(f"Duplicated field number {item.get_field_path(string=True)}")

        return validation_result

    def modify_all_fields_data(self, parent: FieldItem):
        for child_item in parent.get_children():
            if child_item.childCount():
                self.modify_all_fields_data(parent=child_item)
                continue

            self.modify_field_data(child_item)

    def modify_field_data(self, item: FieldItem) -> None:
        if not (validations := self.spec.get_field_validations(item.get_field_path())):
            return

        if validations.justification:
            item.field_data = self.get_justified_field_data(item.spec, item.field_data)

        if validations.field_type_validators.change_to_lower and validations.field_type_validators.change_to_upper:
            item.field_data = item.field_data.upper()
            return

        if validations.field_type_validators.change_to_lower:
            item.field_data = item.field_data.lower()

        if validations.field_type_validators.change_to_upper:
            item.field_data = item.field_data.upper()

    @staticmethod
    def get_justified_field_data(field_spec: IsoField, value: str) -> str:
        if not field_spec:
            return value

        if field_spec.validators.justification is None:
            return value

        if not (just_letter := field_spec.validators.justification_element):
            return value

        if not (just_length := field_spec.validators.justification_length):
            return value

        if field_spec.validators.justification == Justification.RIGHT:
            return value.ljust(just_length, just_letter)

        if field_spec.validators.justification == Justification.LEFT:
            return value.rjust(just_length, just_letter)

        return value
