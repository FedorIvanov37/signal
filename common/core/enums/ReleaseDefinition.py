from enum import StrEnum


class ReleaseDefinition(StrEnum):
    EMAIL = "fedornivanov@gmail.com"
    AUTHOR = "Fedor Ivanov"
    VERSION = "v0.21"
    VERSION_NUMBER = "21"
    NAME = "signal"
    RELEASE = "Sep 2026"
    CONTACT = (f"<a href=\"mailto:{EMAIL}?subject=Signal's user request&body=Dear Fedor,\n\n\n"
               f"> Put your request here < \n\n\n\n"
               f"My Signal version is {VERSION} | Released in {RELEASE}\">{EMAIL}</a>")
