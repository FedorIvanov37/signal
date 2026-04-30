from pydantic import BaseModel
from common.core.data_models.Transaction import Transaction


class TransStatus(BaseModel):
    done: bool = False
    timeout: bool = False
    response: Transaction = None
