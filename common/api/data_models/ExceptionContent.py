from pydantic import BaseModel


class ExceptionContent(BaseModel):
    detail: str = str()
