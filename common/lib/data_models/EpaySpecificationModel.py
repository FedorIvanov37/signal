from pydantic import BaseModel, Field, field_validator, ConfigDict
from common.lib.data_models.Types import FieldPath
from typing import ForwardRef
from enum import Enum


FieldSet = dict[str, ForwardRef("IsoField")]
RawFieldSet = dict[str, str | dict]
MtiValue = Field(default="", max_length=4, pattern=r"^\d{4}|$")
literal_list = list[str]


class FieldTypes(str, Enum):
    COUNTRY_CODE = "COUNTRY CODE"
    CURRENCY_CODE = "CURRENCY CODE"
    MERCHANT_CATEGORY_CODE = "MERCHANT CATEGORY CODE"
    DATE = "DATE"
    OTHER = "OTHER"


class Justification(str, Enum):
    LEFT = "LEFT"
    RIGHT = "RIGHT"
    CUSTOM = "CUSTOM"


class Mti(BaseModel):
    request: str = MtiValue
    response: str = MtiValue
    description: str = str()
    is_reversible: bool = False
    reversal_mti: str = MtiValue


class LogicalValidators(BaseModel):
    currency_a3: bool = False
    currency_n3: bool = False
    country_a3: bool = False
    country_a2: bool = False
    country_n3: bool = False
    mcc: bool = False
    date_format: str = ""
    past: bool = False
    present: bool = False
    future: bool = False
    check_luhn: bool = False
    only_upper: bool = False
    only_lower: bool = False
    change_to_upper: bool = False
    change_to_lower: bool = False
    do_not_validate: bool = False


class Validators(BaseModel):
    field_type: FieldTypes | None = None
    date_format: str | None = None
    min_value: int = 0
    max_value: int = 0
    must_not_contain: literal_list = list()
    possible_values: literal_list = list()
    must_start_with: literal_list = list()
    must_end_with: literal_list = list()
    must_contain: literal_list = list()
    valid_values: literal_list = list()
    invalid_values: literal_list = list()
    must_contain_only: literal_list = list()
    must_not_end_with: literal_list = list()
    must_not_start_with: literal_list = list()
    must_not_contain_only: literal_list = list()
    justification: Justification | None = None
    justification_element: str | None = None
    justification_length: int = 0
    field_type_validators: LogicalValidators | None = LogicalValidators()

    @field_validator("field_type_validators", mode="before")
    @classmethod
    def substitute_none_validator(cls, val):
        if val is None:
            return LogicalValidators()

        return val


class IsoField(BaseModel):
    model_config: ConfigDict = ConfigDict(validate_assignment=True)

    validators: Validators | None = Validators()
    field_number: str = ""
    field_path: list = []
    min_length: int
    max_length: int
    var_length: int
    tag_length: int
    generate: bool
    reversal: bool
    matching: bool
    alpha: bool
    numeric: bool
    special: bool
    reserved_for_future: bool
    description: str = str()
    is_secret: bool = False
    is_utrnno: bool = False
    fields: FieldSet | None = None

    @field_validator("is_secret", mode="before")
    @classmethod
    def substitute_none_by_bool(cls, val):
        if val is None:
            return False

        return val

    @field_validator("validators", mode="before")
    @classmethod
    def substitute_none_validator(cls, val):
        if val is None:
            return Validators()

        return val


class EpaySpecModel(BaseModel):
    name: str | None = "ISO-8583 E-pay Specification"
    mti: list[Mti] = []
    fields: FieldSet = {}
    utrnno_path: FieldPath = ["47", "064"]
