from pydantic import BaseModel


class TransactionResp(BaseModel):
    status: str = "Transaction request successfully accepted. Request ID: %s"
