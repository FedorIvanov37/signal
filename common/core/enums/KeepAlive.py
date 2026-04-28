from enum import StrEnum, IntEnum


class TransTypes(StrEnum):
    TRANS_TYPE_TRANSACTION = "Transaction"
    TRANS_TYPE_KEEP_ALIVE = "Keep Alive"


class IntervalNames(StrEnum):
    KEEP_ALIVE_1S = "1 second"
    KEEP_ALIVE_5S = "5 seconds"
    KEEP_ALIVE_10S = "10 seconds"
    KEEP_ALIVE_30S = "30 seconds"
    KEEP_ALIVE_60S = "60 seconds"
    KEEP_ALIVE_300S = "300 seconds"
    KEEP_ALIVE_DEFAULT = "%s seconds"
    KEEP_ALIVE_ONCE = "Send once"
    KEEP_ALIVE_STOP = "Stop"


intervals_map: dict[str, int] = {
    IntervalNames.KEEP_ALIVE_1S.name: 1,
    IntervalNames.KEEP_ALIVE_5S.name: 5,
    IntervalNames.KEEP_ALIVE_10S.name: 10,
    IntervalNames.KEEP_ALIVE_30S.name: 30,
    IntervalNames.KEEP_ALIVE_60S.name: 60,
    IntervalNames.KEEP_ALIVE_300S.name: 300,
}


IntervalTimes: IntEnum = IntEnum("IntervalTimes", intervals_map)
