from common.lib.data_models.Transaction import Transaction
from common.api.data_models.ApiError import ApiError
from http import HTTPStatus


ApiResponse = tuple[Transaction | ApiError, HTTPStatus]
