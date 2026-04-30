from enum import StrEnum, IntEnum


class DumpLength(IntEnum):
    LINE_LENGTH = 32
    HEX_LINE_LENGTH = 51
    ASCII_LINE_LENGTH = 16
    BYTE_LENGTH = 2


class DumpFillers(StrEnum):
    SEPARATOR = "."
    ASCII_BITMAP = "........"
