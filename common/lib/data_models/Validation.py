from enum import StrEnum
from pydantic import BaseModel, field_validator, ConfigDict


class ValidationTypes(StrEnum):
    FIELD_DATA_PRE_VALIDATION = "FIELD_DATA_PRE_VALIDATION"
    FIELD_DATA_MAIN_VALIDATION = "FIELD_DATA_MAIN_VALIDATION"
    FIELD_DATA_CUSTOM_VALIDATION = "FIELD_DATA_CUSTOM_VALIDATION"
    EXTENDED_VALIDATION = "EXTENDED_VALIDATION"
    TRANSACTION_VALIDATION = "TRANSACTION_VALIDATION"
    URL_VALIDATION = "URL_VALIDATION"
    MTI_VALIDATION = "MTI_VALIDATION"
    LUHN_VALIDATION = "LUHN_VALIDATION"
    FIELDS_VALIDATION = "FIELDS_VALIDATION"
    FIELD_NUMBER_VALIDATION = "FIELD_NUMBER_VALIDATION"
    FIELD_PATH_VALIDATION = "FIELD_PATH_VALIDATION"
    FIELD_DATA_VALIDATION = "FIELD_DATA_VALIDATION"
    FIELD_SPEC_VALIDATION = "FIELD_SPEC_VALIDATION"
    COUNTRY_VALIDATION = "COUNTRY_VALIDATION"
    CURRENCY_VALIDATION = "CURRENCY_VALIDATION"
    DUPLICATED_FIELDS_VALIDATION = "DUPLICATED_FIELDS_VALIDATION"
    OTHER_VALIDATION = "OTHER_VALIDATION"


class ValidationResult(BaseModel):
    model_config: ConfigDict = ConfigDict(validate_assignment=True, validate_default=True)

    errors: dict[ValidationTypes, set[str]] = dict()

    critical_validation_types: list[ValidationTypes] = [
        ValidationTypes.FIELD_DATA_PRE_VALIDATION,
        ValidationTypes.FIELD_DATA_MAIN_VALIDATION,
        ValidationTypes.MTI_VALIDATION,
        ValidationTypes.DUPLICATED_FIELDS_VALIDATION,
    ]

    @field_validator("errors", mode="before")
    @classmethod
    def put_error_empty_sets(cls, error_dict):
        if not isinstance(error_dict, dict):
            raise ValueError("ValidationResult.errors must be dict[ValidationTypes, set[str]]")

        for validation in ValidationTypes:
            err_set = set()
            error_dict[validation] = err_set

        return error_dict
