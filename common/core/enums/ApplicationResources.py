from enum import StrEnum
from common.core.enums.TermFilesPath import TermDirs
from common.core.tools.ResourcePath import ResourcePath


class ResourceNames(StrEnum):
    MAIN_LOGO = 'triforce_unsigned.png'
    USER_GUIDE = 'signal_user_guide.html'


class ApplicationResources(StrEnum):
    MAIN_LOGO = f'{TermDirs.DATA_DIR}/style/{ResourceNames.MAIN_LOGO}'
    USER_GUIDE = f'{TermDirs.DOC_DIR}/{ResourceNames.USER_GUIDE}'


ApplicationResources = ResourcePath.prepare(ApplicationResources)
