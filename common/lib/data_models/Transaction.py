from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict
from pydantic_core import PydanticCustomError
from common.lib.core.EpaySpecification import EpaySpecification
from common.lib.toolkit.generate_trans_id import generate_trans_id
from common.lib.data_models.Enums import generated_field
from common.lib.enums.MessageLength import MessageLength


spec: EpaySpecification = EpaySpecification()
TypeFields = dict[str, str | dict]


class Transaction(BaseModel):
    model_config: ConfigDict = ConfigDict(
        use_enum_values=True,
        validate_assignment=True
    )

    trans_id: str | None = Field(default_factory=generate_trans_id)
    message_type: str
    data_fields: TypeFields
    max_amount: int = 100
    generate_fields: list[generated_field] = []
    json_fields: list[str] = list()
    match_id: str = str()
    utrnno: str = str()
    matched: bool | None = None
    success: bool | None = None
    error: str | None = None
    resp_time_seconds: float | None = None
    sending_time: datetime | None = None
    is_request: bool | None = None
    is_reversal: bool | None = None
    is_keep_alive: bool = False

    @field_validator("max_amount", mode="before")
    @classmethod
    def check_amount(cls, amount):
        error_message = f"Wrong max_amount {amount}. Amount must be digit in range from 0 to 9 999 999 999"

        if amount is None:
            return amount

        if not str(amount).isdigit():
            raise PydanticCustomError("Incorrect max amount", error_message)

        if int(amount) not in range(0, 10_000_000_000):
            raise PydanticCustomError("Max amount out of range", error_message)

        return amount

    @field_validator("generate_fields", mode="before")
    @classmethod
    def field_to_str(cls, val):
        return [str(field) for field in val]

    @field_validator("trans_id")
    @classmethod
    def generate_transaction_id(cls, val):
        if not val:
            return generate_trans_id()

        return val

    @field_validator("message_type", mode="before")
    @classmethod
    def valid_mti(cls, mti: str):
        if len(str(mti)) != MessageLength.MESSAGE_TYPE_LENGTH:
            raise PydanticCustomError(
                "Incorrect MTI length",
                f"Incorrect MTI length. Expected {MessageLength.MESSAGE_TYPE_LENGTH}, got {len(str(mti))}"
            )

        if not mti.isdigit():
            raise PydanticCustomError("Wrong MTI value", f"Wrong MTI value {mti}. MTI must contain digits only")

        if mti not in spec.get_mti_codes():
            raise PydanticCustomError("MTI does not exist",
                                      f"No specification for MTI {mti}. Correct MTI or set it in Specification Window")

        return mti

    @field_validator("data_fields", mode="before")
    @classmethod
    def top_level_fields_in_range(cls, fields: TypeFields):
        for field in fields.keys():
            if not field.isdigit():
                raise PydanticCustomError(
                    "Non-digit field number",
                    f"Incorrect field number {field}. Field numbers must contain digits only"
                )

            if int(field) not in range(1, MessageLength.SECOND_BITMAP_CAPACITY + 1):
                raise PydanticCustomError(
                    "Field number out of range",
                    f"Wrong field number {field}. "
                    f"Top level fields must be in range 1 - {MessageLength.SECOND_BITMAP_CAPACITY}"
                )

        return fields


class OldTransaction(BaseModel):
    id: str = Field(default_factory=generate_trans_id)
    original_id: str = ""
    message_type: str = ""
    fields: TypeFields = {}


class OldTransactionConfig(BaseModel):
    model_config: ConfigDict = ConfigDict(
        use_enum_values=True
    )

    generate_fields: list[generated_field] = []
    max_amount: int | None = None

    @field_validator("generate_fields", mode="before")
    @classmethod
    def field_to_str(cls, val):
        return [str(field) for field in val]


class OldTransactionModel(BaseModel):
    config: OldTransactionConfig
    transaction: OldTransaction
