from enum import StrEnum


class LogMarks(StrEnum):
    BEGIN = "## Begin command line job ID %s ##"
    FINISH = "## Finish command line job ID %s ##"
