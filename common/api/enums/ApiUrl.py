from enum import StrEnum


class ApiUrl(StrEnum):
    API = "/api"
    GET_CONNECTION = "/connection"
    GET_SPECIFICATION = "/specification"
    GET_TRANSACTIONS = "/transactions"
    GET_TRANSACTION = "/transactions/{trans_id}"
    GET_CONFIG = "/config"
    CREATE_TRANSACTION = "/transactions"
    REVERSE_TRANSACTION = "/transactions/{trans_id}/reverse"
    UPDATE_SPECIFICATION = "/specification"
    RECONNECT = "/connection/restart"
    DISCONNECT = "/connection/close"
    CONNECT = "/connection/open"
    UPDATE_CONFIG = "/config"
    SIGNAL = "/about"
    CONVERT = "/tools/transactions/convert"
    VALIDATE_TRANSACTION = "/tools/transactions/validate"
    DOCUMENT = "/documentation"
