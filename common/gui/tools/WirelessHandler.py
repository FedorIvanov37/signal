from contextlib import suppress
from html import escape
from datetime import datetime
from PyQt6.QtCore import QObject, pyqtSignal
from logging import StreamHandler, LogRecord
from PyQt6.QtWidgets import QApplication
import re


class WirelessHandler(StreamHandler, QObject):
    # Python 3.14 logging.shutdown reads this after Qt may have deleted QObject.
    # Keep the lookup in Python instead of falling through to the Qt wrapper.
    flushOnClose = True
    _new_record_appeared = pyqtSignal(str)
    formatted_record_appeared = pyqtSignal(str)
    LEVEL_COLORS = {
        "DEBUG": "#70B7FF",
        "INFO": "#D6DEEB",
        "WARNING": "#FFD166",
        "ERROR": "#FF7070",
        "CRITICAL": "#FF8FCE",
    }
    _last_message: str = str()

    @staticmethod
    def console_markup(markup, light):
        colors = {"#70b7ff": "#005a9e", "#d6deeb": "#243447",
                  "#ffd166": "#805500", "#ff7070": "#b42318",
                  "#ff8fce": "#9c2670", "#7fdbca": "#176b5c",
                  "#addb67": "#426b17", "#ffffff": "#202833"}
        if not light:
            colors = {value: key for key, value in colors.items()}
        def restyle(match):
            style = re.sub("|".join(colors), lambda item: colors[item.group().lower()], match.group(), flags=re.I)
            style = re.sub(r"font-weight:\s*(?:\d+|bold|normal)",
                           "font-weight: 700" if light else "font-weight: 400", style)
            return style
        markup = re.sub(r'style="[^"]*"', restyle, markup)
        if light:
            markup = markup.replace('<pre style="', '<pre style="font-weight: 700; ')
        return markup

    @property
    def new_record_appeared(self):
        return self._new_record_appeared

    def __init__(self):
        StreamHandler.__init__(self)
        QObject.__init__(self)

    def emit(self, record: LogRecord):
        with suppress(Exception):
            text = self.format(record)
            color = self.LEVEL_COLORS.get(record.levelname, self.LEVEL_COLORS["INFO"])
            if record.levelname == 'INFO' and getattr(record, 'extra', {}).get('recovery_success'):
                color = '#ADDB67'
            display_level = "WARN" if record.levelname == "WARNING" else record.levelname
            level_separator = "" if display_level == "ERROR" else " "
            timestamp = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
            location = ""
            if record.levelname == "DEBUG":
                location = (
                    '<span style="color: #7FDBCA;">'
                    + escape(f"{record.name}:{record.funcName}:{record.lineno}")
                    + '</span> - '
                )
            markup = (
                '<pre style="color: #D6DEEB; margin: 0; font-family: Consolas;">'
                f'<span style="color: #ADDB67;">{timestamp}</span> | '
                f'<span style="color: {color}; font-weight: bold;">[{display_level}]</span>{level_separator} | '
                + location
                + f'<span style="color: {color};">{escape(text)}</span></pre>'
            )
            app = QApplication.instance()
            if app and app.property("signalConsoleColor") in ('#F0F0F0', '#8996A3', '#FFFBEB', '#EFF1F5'):
                markup = self.console_markup(markup, True)
            self.new_record_appeared.emit(text)
            self.formatted_record_appeared.emit(markup)
