from pydantic import BaseModel


class TransValidationErrors(BaseModel):
    validation_errors: list[str] = []
