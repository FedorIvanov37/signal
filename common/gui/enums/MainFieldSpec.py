from enum import StrEnum, IntEnum
from common.core.tools.EpaySpecification import EpaySpecification


class Columns(StrEnum):
    FIELD = "Field"
    VALUE = "Value"
    LENGTH = "Length"
    DESCRIPTION = "Description"
    PROPERTY = "Property"


ColumnsOrder = IntEnum(
    "ColumnsOrder", {column: position for position, column in enumerate([column.name for column in Columns])}
)


GeneratedFields = StrEnum(
    "GeneratedFields", EpaySpecification().get_generated_fields_dict()
)
