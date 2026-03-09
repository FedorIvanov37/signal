from enum import StrEnum


class ReleaseDefinition(StrEnum):
    EMAIL = "fedornivanov@gmail.com"
    AUTHOR = "Fedor Ivanov"
    VERSION = "v0.20"
    VERSION_NUMBER = "20"
    NAME = "signal"
    RELEASE = "March 2026"
    CONTACT = (f"<a href=\"mailto:{EMAIL}?subject=Signal's user request&body=Dear Fedor,\n\n\n"
               f"> Put your request here < \n\n\n\n"
               f"My Signal version is {VERSION} | Released in {RELEASE}\">{EMAIL}</a>")
