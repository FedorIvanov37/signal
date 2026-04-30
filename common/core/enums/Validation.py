from enum import StrEnum


class ValidationMode(StrEnum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    FLEXIBLE = "FLEXIBLE"


class CustomValidations(StrEnum):
    FIELD_TYPE = "field_type"
    DATE_FORMAT = "date_format"
    MIN_VALUE = "min_value"
    MAX_VALUE = "max_value"
    MUST_NOT_CONTAIN = "must_not_contain"
    POSSIBLE_VALUES = "possible_values"
    MUST_START_WITH = "must_start_with"
    MUST_END_WITH = "must_end_with"
    MUST_CONTAIN = "must_contain"
    VALID_VALUES = "valid_values"
    INVALID_VALUES = "invalid_values"
    MUST_CONTAIN_ONLY = "must_contain_only"
    MUST_NOT_END_WITH = "must_not_end_with"
    MUST_NOT_START_WITH = "must_not_start_with"
    MUST_NOT_CONTAIN_ONLY = "must_not_contain_only"
    JUSTIFICATION = "justification"
    JUSTIFICATION_ELEMENT = "justification_element"
    JUSTIFICATION_LENGTH = "justification_length"
    FIELD_TYPE_VALIDATORS = "field_type_validators"


class ExtendedValidations(StrEnum):
    CURRENCY_A3 = "currency_a3"
    CURRENCY_N3 = "currency_n3"
    COUNTRY_A3 = "country_a3"
    COUNTRY_A2 = "country_a2"
    COUNTRY_N3 = "country_n3"
    MCC = "mcc"
    DATE_FORMAT = "date_format"
    PAST = "past"
    FUTURE = "future"
    CHECK_LUHN = "check_luhn"
    ONLY_UPPER = "only_upper"
    ONLY_LOWER = "only_lower"
    CHANGE_TO_UPPER = "change_to_upper"
    CHANGE_TO_LOWER = "change_to_lower"
    DO_NOT_VALIDATE = "do_not_validate"
