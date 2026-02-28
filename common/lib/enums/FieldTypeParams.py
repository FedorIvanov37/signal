from enum import StrEnum


class FieldTypeParams(StrEnum):
    COUNTRY = "Country"
    OTHER = "Other"
    MCC = "MCC"
    DATE = "Date"
    CURRENCY = "Currency"

    MERCHANT_CATEGORY_CODE = "MCC"
    MCC_ISO = "ISO 18245 MCC"

    COUNTRY_CODE_A3 = "ISO 3166 Alpha 3"
    COUNTRY_CODE_A2 = "ISO 3166 Alpha 2"
    COUNTRY_CODE_N3 = "ISO 3166 Numeric 3"

    CURRENCY_CODE_N3 = "ISO 4217 Numeric 3"
    CURRENCY_CODE_A3 = "ISO 4217 Alpha 3"

    DATE_FORMAT = "Format in Python datetime"
    PAST_TIME = "Past time allowed"
    PRESENT_TIME = "Present time allowed"
    FUTURE_TIME = "Future time allowed"

    CHECK_LUHN = "Check Luhn algorithm"
    UPPERCASE = "Upper case only"
    LOWERCASE = "Lower case only"
    TO_UPPERCASE = "Translate to upper case"
    TO_LOWERCASE = "Translate to lower case"
    IGNORE_VALIDATIONS = "Ignore all validations"

    JUSTIFICATION_NONE = "Not set"
    JUSTIFICATION_LEFT = "Left Pad"
    JUSTIFICATION_RIGHT = ""
    JUSTIFICATION_MIN_LEN = "Min Length"
    JUSTIFICATION_MAX_LEN = "Max Length"