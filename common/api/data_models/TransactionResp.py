from pydantic import BaseModel


class TransactionResp(BaseModel):
    status: str = "Transaction successfully sent to host"
