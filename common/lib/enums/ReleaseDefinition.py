from enum import StrEnum


class ReleaseDefinition(StrEnum):
    EMAIL = "fedornivanov@gmail.com"
    AUTHOR = "Fedor Ivanov"
    VERSION = "v0.19.1"
    VERSION_NUMBER = "19.1"
    NAME = "signal"
    RELEASE = "Oct 2025"
    CONTACT = (f"<a href=\"mailto:{EMAIL}?subject=Signal's user request&body=Dear Fedor,\n\n\n"
               f"> Put your request here < \n\n\n\n"
               f"My Signal version is {VERSION} | Released in {RELEASE}\">{EMAIL}</a>")
