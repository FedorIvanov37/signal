from uuid import uuid4
from http import HTTPStatus
from typing import Any
from pydantic import BaseModel
from common.lib.data_models.Transaction import Transaction
from common.api.enums.ApiRequestType import ApiRequestType
from common.lib.data_models.Config import Config
from common.lib.data_models.EpaySpecificationModel import EpaySpecModel
from common.api.data_models.Connection import Connection


class ApiRequest(BaseModel):
    request_id: uuid4 = uuid4()
    http_status: HTTPStatus = HTTPStatus.INTERNAL_SERVER_ERROR
    error: str | None = None
    response_data: Any | None = None


class ApiTransactionRequest(ApiRequest):
    request_type: ApiRequestType = ApiRequestType.OUTGOING_TRANSACTION
    transaction: Transaction | None = None


class ReversalRequest(ApiRequest):
    request_type: ApiRequestType = ApiRequestType.REVERSE_TRANSACTION
    transaction: Transaction | None = None
    original_trans_id: str


class ConfigAction(ApiRequest):
    request_type: ApiRequestType
    config: Config | None = None


class SpecAction(ApiRequest):
    request_type: ApiRequestType
    spec: EpaySpecModel | None = None


class ConnectionAction(ApiRequest):
    request_type: ApiRequestType
    connection: Connection | None = None
