from enum import StrEnum
from common.core.enums.TermFilesPath import TermDirs
from common.core.tools.ResourcePath import ResourcePath
from common.core.enums.ApplicationResources import ResourceNames


class GuiDirs(StrEnum):
    STYLE_DIR = f"{TermDirs.DATA_DIR}/style"
    DOC_DIR = f"{TermDirs.DOC_DIR}"


class GuiFiles(StrEnum):
    MAIN_LOGO = ResourceNames.MAIN_LOGO
    SIGNED_LOGO = "triforce_signed.png"
    MUSIC_ON = "music_on.png"
    MUSIC_OFF = "music_off.png"
    VVVVVV = "VVVVVV.m4a"
    GREEN_CIRCLE = "green_circle.ico"
    GREY_CIRCLE = "grey_circle.ico"
    RED_CIRCLE = "red_circle.ico"
    YELLOW_CIRCLE = "yellow_circle.ico"
    NEW_TAB = "new_tab.ico"
    HTML_DOCUMENT = ResourceNames.USER_GUIDE


class GuiFilesPath(StrEnum):
    SETTINGS = f"{GuiDirs.STYLE_DIR}/settings.svg"
    CHECK_WHITE = f"{GuiDirs.STYLE_DIR}/check_white.svg"
    CHECK_PARTIAL_WHITE = f"{GuiDirs.STYLE_DIR}/check_partial_white.svg"
    MAIN_LOGO = f"{GuiDirs.STYLE_DIR}/{GuiFiles.MAIN_LOGO}"
    SIGNED_LOGO = f"{GuiDirs.STYLE_DIR}/{GuiFiles.SIGNED_LOGO}"
    MUSIC_ON = f"{GuiDirs.STYLE_DIR}/{GuiFiles.MUSIC_ON}"
    MUSIC_OFF = f"{GuiDirs.STYLE_DIR}/{GuiFiles.MUSIC_OFF}"
    VVVVVV = f"{GuiDirs.STYLE_DIR}/{GuiFiles.VVVVVV}"
    GREEN_CIRCLE = f"{GuiDirs.STYLE_DIR}/{GuiFiles.GREEN_CIRCLE}"
    GREY_CIRCLE = f"{GuiDirs.STYLE_DIR}/{GuiFiles.GREY_CIRCLE}"
    RED_CIRCLE = f"{GuiDirs.STYLE_DIR}/{GuiFiles.RED_CIRCLE}"
    YELLOW_CIRCLE = f"{GuiDirs.STYLE_DIR}/{GuiFiles.YELLOW_CIRCLE}"
    NEW_TAB = f"{GuiDirs.STYLE_DIR}/{GuiFiles.NEW_TAB}"
    DOC = f"{GuiDirs.DOC_DIR}/{GuiFiles.HTML_DOCUMENT}"


GuiFilesPath = ResourcePath.prepare(GuiFilesPath)
