from enum import StrEnum


class LiteralValidations(StrEnum):
    MUST_CONTAIN = "Must contain"
    MUST_CONTAIN_ONLY = "Must contain only"
    MUST_NOT_CONTAIN = "Must not contain"
    MUST_NOT_CONTAIN_ONLY = "Must not contain only"
    MUST_START_WITH = "Must start with"
    MUST_NOT_START_WITH = "Must not start with"
    MUST_END_WITH = "Must end with"
    MUST_NOT_END_WITH = "Must not end with"
    VALID_VALUES = "Valid values"
    INVALID_VALUES = "Invalid values"
