from enum import StrEnum
from common.lib.enums.DataFormats import PrintDataFormats


class ButtonActionSigns(StrEnum):
    BUTTON_PLUS_SIGN = "✚"
    BUTTON_MINUS_SIGN = "━"
    BUTTON_NEXT_LEVEL_SIGN = "🡾"
    BUTTON_UP_SIGN = "🡹"
    BUTTON_DOWN_SIGN = "🡻"
    BUTTON_LEFT_SIGN = "🡸"
    BUTTON_RIGHT_SIGN = "🡺"


PrintButtonDataFormats = StrEnum("PrintButtonDataFormats", PrintDataFormats.__dict__.get('_member_map_'))


save_button_data_formats = {
    data_format.name: data_format.value for data_format in [
        PrintButtonDataFormats.JSON,
        PrintButtonDataFormats.INI,
        PrintButtonDataFormats.DUMP,
    ]
}


SaveButtonDataFormats = StrEnum("SaveButtonDataFormats", save_button_data_formats)


class SaveMenuActions(StrEnum):
    CURRENT_TAB = "Current tab"
    ALL_TABS = "All tabs"


class ClearMenuActions(StrEnum):
    ALL = "All"
    STRING = "String"
    JSON = PrintButtonDataFormats.JSON


class DataMenuActions(StrEnum):
    GET_DATA = f"{ButtonActionSigns.BUTTON_RIGHT_SIGN} Get from MainWindow"
    SET_DATA = f"{ButtonActionSigns.BUTTON_LEFT_SIGN} Set to MainWindow"


class ReversalMenuActions(StrEnum):
    LAST = "Reverse last"
    OTHER = "Reverse other"
    SET_REVERSAL = "Set Reversal fields"


class ApplySpecMenuActions(StrEnum):
    ONE_SESSION = "For current session"
    PERMANENTLY = "Permanently"


class SetSpecMenuActions(StrEnum):
    REMOTE_SPEC = "Set remote specification"
    LOCAL_SPEC = "Set local specification"


class Marks(StrEnum):
    CURRENT_ACTION_MARK = "•"
