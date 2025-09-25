from http import HTTPStatus


class TerminalApiError(Exception):
    def __init__(self, detail: str | Exception, http_status: HTTPStatus):
        self.detail = str(detail)
        self.http_status = http_status
