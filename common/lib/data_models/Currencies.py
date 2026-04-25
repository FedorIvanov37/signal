from typing import Literal
from pydantic import BaseModel, Field, field_validator, PositiveInt
from common.lib.decorators.json_file_model import json_file_model


class Currency(BaseModel):
    name: str
    code_a3: str = Field(..., min_length=3, max_length=3)
    code_n3: str = Field(..., min_length=1, max_length=3)
    exponent: PositiveInt | Literal[int()] = Field(..., gt=-1, lt=5)

    @field_validator("code_a3", mode="before")
    @classmethod
    def non_digits_only(cls, val):
        if not str(val).isalpha():
            raise ValueError("Only alphabetic allowed")

        return val

    @field_validator("code_n3", mode="before")
    @classmethod
    def digits_only(cls, val):
        val = str(val).zfill(3)

        if not val.isdigit():
            raise ValueError("Only numeric codes allowed")

        return val


@json_file_model
class Currencies(BaseModel):
    currencies: list[Currency] = list()
