from pydantic import BaseModel, Field, field_validator
from pydantic_core import PydanticCustomError, ValidationError
from common.lib.core.EpaySpecification import EpaySpecification
from random import randint
from common.lib.data_models.Dictionaries import Currencies
from common.lib.enums.TermFilesPath import TermFilesPath


spec: EpaySpecification = EpaySpecification()


class TransData(BaseModel):
    card_number: str = Field(..., min_length=16, max_length=19)
    cvv_code: str = Field(..., min_length=3, max_length=3)
    expiration_yymm: str = Field(..., min_length=4, max_length=4)
    amount: float = float(randint(100, 1000))
    currency: str = Field(min_length=3, max_length=3, default_factory=lambda: "EUR")

    @field_validator("amount", mode="before")
    @classmethod
    def check_amount(cls, amount):
        try:
            return float(amount)
        except ValueError:
            pass

        return 100.00

    @field_validator("card_number", "cvv_code", "expiration_yymm", mode="before")
    @classmethod
    def validate_number(cls, field_data):
        if not str(field_data).isdigit():
            raise PydanticCustomError(
                f"Non-digit value set for transaction data: {field_data}",
                "Change the field data and try again"
            )

        return field_data

    @field_validator("currency", mode="before")
    @classmethod
    def check_currency(cls, currency):
        if not currency:
            return currency

        try:
            currencies = Currencies.parse_file(TermFilesPath.CURRENCY_DICT)
        except ValidationError | PydanticCustomError:
            return currency

        if currency not in currencies.currencies:
            raise PydanticCustomError(
                f"No currency {currency} exists in the currencies dictionary",
                "Change the currency to any valid one"
            )

        return currency
