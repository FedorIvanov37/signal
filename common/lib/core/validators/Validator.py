from typing import Callable
from datetime import datetime
from string import digits, ascii_letters, punctuation, whitespace 
from pydantic import AnyHttpUrl, ValidationError
from copy import deepcopy
from common.lib.exceptions.exceptions import DataValidationError, DataValidationWarning
from common.lib.core.EpaySpecification import EpaySpecification
from common.lib.data_models.Types import FieldPath
from common.lib.data_models.Config import Config
from common.lib.data_models.Validation import ValidationResult, ValidationTypes
from common.lib.data_models.EpaySpecificationModel import IsoField
from common.lib.enums.Validation import ValidationMode, CustomValidations, ExtendedValidations
from common.lib.data_models.Transaction import TypeFields
from common.gui.enums.FieldTypeParams import FieldTypeParams
from common.lib.core.Parser import Parser


class Validator:
    _spec: EpaySpecification = EpaySpecification()

    @property
    def spec(self):
        return self._spec

    def __init__(self, config: Config):
        self.config = config

    @staticmethod
    def validate_url(url: str, validation_result: ValidationResult):
        errors = validation_result.errors[ValidationTypes.URL_VALIDATION]

        try:
            AnyHttpUrl(url)
        except ValidationError as validation_error:
            errors.add(str(validation_error))

        return validation_result

    @staticmethod
    def field_path_to_str(field_path: FieldPath) -> str:
        return ".".join(field_path)

    def validate_mti(self, mti, validation_result: ValidationResult):
        errors = validation_result.errors[ValidationTypes.MTI_VALIDATION]

        if mti in self.spec.get_mti_codes():
            return validation_result

        errors.add(f"Unknown MTI: {mti}")

        return validation_result

    @staticmethod
    def check_luhn(value: str) -> bool:  # Based on code example from https://en.wikipedia.org/wiki/Luhn_algorithm
        def digits_of(val):
            return [int(dig) for dig in str(val)]

        if not value.isdigit():
            return False

        digits_kit: list[int] = digits_of(value)
        odd_digits: list[int] = digits_kit[-1::-2]
        even_digits: list[int] = digits_kit[-2::-2]
        checksum: int = int()
        checksum += sum(odd_digits)

        for digit in even_digits:
            checksum += sum(digits_of(digit * 2))

        status: bool = checksum % 10 == int()

        return status

    def validate_field_number(self, field_number: int | str, validation_result: ValidationResult, is_top_level_field=True): # Field number validations, such as the number should contain digits only, etc
        errors = validation_result.errors[ValidationTypes.FIELD_NUMBER_VALIDATION]

        if not field_number:  # Field number should be not empty
            errors.add("Lost field number")

        if not str(field_number).isdigit():  # Field number should be a number
            errors.add(f'Non-digit field number "{field_number}"')

        if not is_top_level_field:
            return validation_result

        # Top level fields should be in range 2-128

        min_field = int(self.spec.FIELD_SET.FIELD_002_PRIMARY_ACCOUNT_NUMBER)
        max_field = int(self.spec.FIELD_SET.FIELD_128_SECONDARY_MAC_DATA)

        if int(field_number) not in range(min_field, max_field + 1):
            err = f"Incorrect field number {field_number}. Top level field must be in range {min_field} - {max_field}"
            errors.add(err)

        return validation_result

    def validate_field_spec(self, field_path: FieldPath, validation_result: ValidationResult):
        errors: set[str] = validation_result.errors[ValidationTypes.FIELD_SPEC_VALIDATION]

        spec: IsoField | None = self.spec.get_field_spec(field_path)

        if spec is not None:
            return validation_result

        errors.add(f"Field {self.field_path_to_str(field_path)} - lost field specification")

        return validation_result

    def validate_field_path(self, field_path: FieldPath, validation_result: ValidationResult):
        errors = validation_result.errors[ValidationTypes.FIELD_PATH_VALIDATION]

        if not field_path:
            errors.add("Empty field path")
            return validation_result

        if str() in field_path:
            field_path: map = map(lambda field_data: field_data if field_data else '<empty>', field_path)
            field_path: str = self.field_path_to_str(list(field_path))
            errors.add(f"{field_path} - empty field number in field path")
            return validation_result

        for level, field in enumerate(field_path, start=1):
            validation_result = self.validate_field_number(field, validation_result, level == 1)

        return validation_result

    def validate_field_data(self, field_path: FieldPath, field_value: str, validation_result: ValidationResult):
        """
        The general validation method validates field data by all possible check

        Each checklist is separated and added to its sub-function such as Validator.validate_field_data.main_validations,
        Validator.validate_field_data.custom_validations, and so on

        The method execution flow is written below, after the functions declaration
        """

        def fields_pre_validation():  # Basic validations, actual for any field
            errors: set[str] = set()
            length = len(field_value)

            if not field_value:  # Field should contain the data
                errors.add(f"{path} - lost field value for field")

            if not all(field.isdigit() for field in field_path):  # Field number should be digit
                errors.add(f"Field numbers can be digits only. {path} is wrong value")

            if length > field_spec.max_length:  # Max length validation
                errors.add(f"Field {path} - Over MaxLength. Max length: {field_spec.max_length}, got: {length}")

            if length < field_spec.min_length:  # Min length validation
                errors.add(f"Field {path} - Less MinLength. Min length: {field_spec.min_length}, got: {length}")

            return errors

        def main_validations(): # ANS-validation. Checks the occurrence of non-allowed charset
            errors: set[str] = set()
            alphabetic: str = ascii_letters
            numeric: str = digits
            specials: str = punctuation + whitespace 
            valid_values: str = alphabetic + numeric + specials

            for letter in field_value:
                if letter not in valid_values:  # Only ascii-printable allowed
                    errors.add(f"Field {path} - non-printable letters in field. Seems like a problem with encoding")

                if letter in ascii_letters and not field_spec.alpha:  # Validation charset - alphabetic
                    errors.add(f"Field {path_desc} - alphabetic values not allowed")

                if letter in digits and not field_spec.numeric:  # Validation charset - numeric
                    errors.add(f"Field {path_desc} - numeric values not allowed")

                if letter in specials and not field_spec.special:  # Validation charset - special
                    errors.add(f"Field {path_desc} - special values not allowed")

            return errors

        def custom_validations():  # Custom string validations set by user on Field Validations window
            errors: set[str] = set()

            for validation, patterns in field_spec.validators.model_dump().items():
                if not patterns or not isinstance(patterns, list):
                    continue

                patterns_str = ", ".join(patterns)

                match validation:
                    case CustomValidations.VALID_VALUES:  # Exact allowed value validation
                        if not field_value in patterns:
                            errors.add(f'Field {path_desc} must contain one of the following: {patterns_str}')

                    case CustomValidations.INVALID_VALUES:  # Exact not allowed value validation
                        if field_value in patterns:
                            errors.add(f'Field {path_desc} must not contain one of the following: {patterns_str}')

                    case CustomValidations.MUST_START_WITH:
                        value_start_with = [True for pattern in patterns if field_value.startswith(pattern)]

                        if not any(value_start_with):
                            errors.add(f"Field {path_desc} must start with one of the following: {patterns_str}")

                    case CustomValidations.MUST_NOT_START_WITH:
                        value_start_with = [True for pattern in patterns if field_value.startswith(pattern)]

                        if any(value_start_with):
                            errors.add(f"Field {path_desc} must not start with one of the following: {patterns_str}")

                    case CustomValidations.MUST_END_WITH:
                        value_end_with = [True for pattern in patterns if field_value.endswith(pattern)]

                        if not any(value_end_with):
                            errors.add(f"Field {path_desc} must end with one of the following: {patterns_str}")

                    case CustomValidations.MUST_NOT_END_WITH:
                        value_end_with = [True for pattern in patterns if field_value.endswith(pattern)]

                        if any(value_end_with):
                            errors.add(f"Field {path_desc} must not end with one of the following: {patterns_str}")

                    case CustomValidations.MUST_CONTAIN:
                        value_contains = [True for pattern in patterns if pattern in field_value]

                        if not any(value_contains):
                            errors.add(f"Field {path_desc} must contain one of the following: {patterns_str}")

                    case CustomValidations.MUST_NOT_CONTAIN:
                        value_contains = [True for pattern in patterns if pattern in field_value]

                        if any(value_contains):
                            errors.add(f"Field {path_desc} must not contain one of the following: {patterns_str}")

                    case CustomValidations.MUST_CONTAIN_ONLY:
                        value = field_value

                        for pattern in patterns:
                            value = value.replace(pattern, str())

                        if value:
                            errors.add(f"Field {path_desc} must contain only one or multiple: {patterns_str}")

                    case CustomValidations.MUST_NOT_CONTAIN_ONLY:
                        value = field_value

                        for pattern in patterns:
                            value = value.replace(pattern, str())

                        if not value:
                            errors.add(f"Field {path_desc} must not contain only one or multiple: {patterns_str}")

            return errors

        def country_validations(): # Validation ISO-4217 country codes
            errors: set[str] = set()
            allowed_country_codes: list[str] = list()

            if field_spec.validators.field_type_validators.country_a2:
                allowed_country_codes.extend([country.code_a2 for country in self.spec.dictionary.countries.countries])

            if field_spec.validators.field_type_validators.country_a3:
                allowed_country_codes.extend([country.code_a3 for country in self.spec.dictionary.countries.countries])

            if field_spec.validators.field_type_validators.country_n3:
                allowed_country_codes.extend([country.code_n3 for country in self.spec.dictionary.countries.countries])

            for field, value in field_spec.validators.field_type_validators.model_dump().items():
                if not value:
                    continue

                if field not in (ExtendedValidations.COUNTRY_A3, ExtendedValidations.COUNTRY_N3, ExtendedValidations.COUNTRY_A2):
                    continue

                if field_value in allowed_country_codes:
                    continue

                errors.add(f"Field {path_desc} must contain valid ISO country code")

            return errors

        def currency_validation():  # Check valid currency code by the currency dictionary
            errors: set[str] = set()
            allowed_currency_codes: list[str] = list()

            if field_spec.validators.field_type_validators.currency_a3:
                allowed_currency_codes.extend([curr.code_a3 for curr in self.spec.dictionary.currencies.currencies])

            if field_spec.validators.field_type_validators.currency_n3:
                allowed_currency_codes.extend([curr.code_n3 for curr in self.spec.dictionary.currencies.currencies])

            for field, value in field_spec.validators.field_type_validators.model_dump().items():
                if not value:
                    continue

                if field not in (ExtendedValidations.CURRENCY_A3, ExtendedValidations.COUNTRY_N3):
                    continue

                if field_value not in allowed_currency_codes:
                    errors.add(f'Field {path_desc} must contain valid ISO currency code. The value "{field_value}" is not allowed')

            return errors

        def extended_validations():  # Extended, logical validation, based on business-purpose of the data field
            errors: set[str] = set()

            for field, value in field_spec.validators.field_type_validators.model_dump().items():
                if not value:
                    continue

                match field:
                    case ExtendedValidations.CHECK_LUHN:  # Check by the Luhn algorithm
                        if not self.check_luhn(field_value):
                            errors.add(f"Field {path_desc} - did not pass validation by the Luhn algorithm")

                    case ExtendedValidations.MCC:  # Valid merchant category code
                        mcc_list = (mcc.code for mcc in self.spec.dictionary.merch_cat_codes.merchant_category_codes)

                        if field_value not in mcc_list:
                            errors.add(f"Field {path_desc} - must contain valid {FieldTypeParams.MCC_ISO}")

                    case ExtendedValidations.ONLY_UPPER:  # Only UPPER case allowed
                        if not field_value.isupper():
                            errors.add(f"Field {path_desc} - allowed UPPER case only")

                    case ExtendedValidations.ONLY_LOWER:  # Only lower case allowed
                        if not field_value.islower():
                            errors.add(f"Field {path_desc} - allowed lower case only")

                    case ExtendedValidations.DATE_FORMAT:  # Date format and timeframes
                        date: datetime | None = None
                        date_format: str = field_spec.validators.field_type_validators.date_format

                        if field_spec.validators.field_type_validators.date_format:
                            try:
                                date: datetime = datetime.strptime(field_value, date_format)
                            except ValueError:
                                errors.add(f'Field {path_desc} - must contain date in the following format: "{date_format}"')

                        if date is not None:
                            current_date = datetime.strptime(datetime.strftime(datetime.now(), date_format), date_format)

                            if date < current_date and not field_spec.validators.field_type_validators.past:
                                errors.add(f"Field {path_desc} - past time not allowed")

                            if date > current_date and not field_spec.validators.field_type_validators.future:
                                errors.add(f"Field {path_desc} - future time not allowed")

                            if date == current_date and not field_spec.validators.field_type_validators.present:
                                errors.add(f"Field {path_desc} - present time not allowed")

            return errors

        # The method validate_field_data execution begins here

        path: str = self.field_path_to_str(field_path)

        if not (field_spec := self.spec.get_field_spec(field_path)):
            return validation_result

        path_desc: str = f"{path} - {field_spec.description}"

        if field_spec.validators.field_type_validators.do_not_validate:  # When all the field validations should be ignored
            validation_result.errors = deepcopy(ValidationResult().errors)  # Clean the errors
            return validation_result

        validators_map: dict[ValidationTypes, Callable] = {
            ValidationTypes.FIELD_DATA_PRE_VALIDATION: fields_pre_validation,
            ValidationTypes.FIELD_DATA_MAIN_VALIDATION: main_validations,
            ValidationTypes.FIELD_DATA_CUSTOM_VALIDATION: custom_validations,
            ValidationTypes.EXTENDED_VALIDATION: extended_validations,
            ValidationTypes.CURRENCY_VALIDATION: currency_validation,
            ValidationTypes.COUNTRY_VALIDATION: country_validations,
        }

        for check_type, validator in validators_map.items():
            validation_errors: set[str] = validator()

            if validation_result.errors.get(check_type) is None:
                validation_result.errors[check_type] = set()

            validation_result.errors[check_type].update(validation_errors)

        return validation_result

    def process_validation_result(self, validation_result: ValidationResult):
        errors: set[str] = set()

        for error_set in validation_result.errors.values():
            if not isinstance(error_set, set):
                continue

            errors.update(error_set)

        if not errors:
            return

        errors_string = "\n".join(errors)

        match self.config.validation.validation_mode:
            case ValidationMode.ERROR:
                raise DataValidationError(errors_string)

            case ValidationMode.WARNING:
                raise DataValidationWarning(errors_string)

            case ValidationMode.FLEXIBLE:
                for check_type in validation_result.errors:
                    if not validation_result.errors.get(check_type):
                        continue

                    if check_type in validation_result.critical_validation_types:
                        raise DataValidationError(errors_string)

                    raise DataValidationWarning(errors_string)

    def validate_fields(self, fields: TypeFields, validation_result: ValidationResult, field_path: FieldPath | None = None):
        if field_path is None:
            field_path: FieldPath = []

        for field, value in fields.items():
            field_path.append(field)

            if self.spec.is_field_complex(field_path):
                field_value_dict = value

                if not isinstance(value, dict):
                    field_value_dict = Parser.split_complex_field(field_path[int()], value)

                validation_result = self.validate_fields(fields=field_value_dict, validation_result=validation_result, field_path=field_path)
                field_path.pop()
                continue

            validation_result = self.validate_field_spec(field_path, validation_result)
            validation_result = self.validate_field_data(field_path, value, validation_result)

            field_path.pop()

        return validation_result
