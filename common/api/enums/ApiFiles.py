from enum import StrEnum
from common.lib.enums.TermFilesPath import TermDirs


class ApiFiles(StrEnum):
    ECHO_TEST = f"{TermDirs.API_TRANSACTIONS}/echo-test.json"
    PURCHASE = f"{TermDirs.API_TRANSACTIONS}/purchase.json"
    KEEP_ALIVE = f"{TermDirs.API_TRANSACTIONS}/keep-alive.json"
    PAYOUT = f"{TermDirs.API_TRANSACTIONS}/payout.json"
