from pydantic import BaseModel, field_validator


class TransValidationErrors(BaseModel):
    validation_errors: list[str] = []

    @field_validator("validation_errors", mode="after")
    @classmethod
    def sort_errors(cls, val):
        val.sort()

        return val
