from enum import StrEnum


class IniMessageDefinition(StrEnum):
    MTI = "MTI"
    MESSAGE = "MESSAGE"
    CONFIG = "CONFIG"
    GENERATE_FIELDS = "GENERATE_FIELDS"
    MAX_AMOUNT = "MAX_AMOUNT"
