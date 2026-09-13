import re
from time import perf_counter
from PyQt6.QtCore import QTimer

from PyQt6.QtGui import QSyntaxHighlighter, QTextCharFormat, QColor, QFont
from PyQt6.QtWidgets import QApplication
from common.core.enums.DumpDefinition import DumpLength


class PrintHighlighter(QSyntaxHighlighter):
    """Highlight only printed blocks, leaving subsequently appended log records alone."""

    json_tokens = re.compile(r'"(?:\\.|[^"\\])*"|-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?|\b(?:true|false|null)\b|[{}\[\],:]')
    dark = dict(key='#91C5FF', string='#ADDB67', number='#FFD166', literal='#FF8FCE',
                punctuation='#A5AFBC', comment='#94A3B8')
    light = dict(key='#005A9E', string='#426B17', number='#805500', literal='#9C2670',
                 punctuation='#53647A', comment='#64748B')

    def __init__(self, document):
        super().__init__(document)
        self.data_format = ''
        self.printed_blocks = 0
        self._formats = {}
        self._batch_active = False
        self._painting_batch = False
        self._next_block = 0
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(self._highlight_batch)

    def cancel(self):
        """Cancel pending work without traversing or clearing the old document."""
        self._timer.stop()
        self.printed_blocks = 0
        self._batch_active = False
        self._next_block = 0

    def rehighlight(self):
        self._timer.stop()
        self._formats.clear()
        self._batch_active = self.printed_blocks > 1000
        if not self._batch_active:
            return super().rehighlight()
        self._next_block = 0
        self._timer.start(0)

    def _highlight_batch(self):
        deadline = perf_counter() + 0.008
        block = self.document().findBlockByNumber(self._next_block)
        self._painting_batch = True
        try:
            while block.isValid() and block.blockNumber() < self.printed_blocks:
                self.rehighlightBlock(block)
                block = block.next()
                self._next_block += 1
                if perf_counter() >= deadline:
                    break
        finally:
            self._painting_batch = False
        if block.isValid() and self._next_block < self.printed_blocks:
            self._timer.start(1)
        else:
            self._batch_active = False

    def highlightBlock(self, text):
        if self._batch_active and not self._painting_batch:
            return
        if self.currentBlock().blockNumber() >= self.printed_blocks:
            return
        light = QApplication.instance().property('signalConsoleColor') in ('#F0F0F0', '#8996A3', '#FFFBEB', '#EFF1F5')
        colors = self.light if light else self.dark

        def paint(start, end, kind):
            if end <= start:
                return
            key = (light, kind)
            if key not in self._formats:
                fmt = QTextCharFormat()
                fmt.setForeground(QColor(colors[kind]))
                fmt.setFontWeight(QFont.Weight.Bold if light else QFont.Weight.Normal)
                self._formats[key] = fmt
            fmt = self._formats[key]
            # Qt positions count UTF-16 code units, unlike Python string indices.
            offset = len(text[:start].encode('utf-16-le')) // 2
            length = len(text[start:end].encode('utf-16-le')) // 2
            self.setFormat(offset, length, fmt)

        if self.data_format in ('JSON', 'SPEC', 'CONFIG'):
            for token in self.json_tokens.finditer(text):
                value = token.group()
                if value.startswith('"'):
                    kind = 'key' if text[token.end():].lstrip().startswith(':') else 'string'
                elif value in ('true', 'false', 'null'):
                    kind = 'literal'
                elif value[0] in '-0123456789':
                    kind = 'number'
                else:
                    kind = 'punctuation'
                paint(token.start(), token.end(), kind)
        elif self.data_format == 'INI':
            stripped = text.lstrip()
            if stripped.startswith((';', '#')):
                paint(0, len(text), 'comment')
            elif stripped.startswith('['):
                paint(0, len(text), 'key')
            elif '=' in text:
                split = text.index('=')
                paint(0, split, 'key')
                paint(split, split + 1, 'punctuation')
                paint(split + 1, len(text), 'string')
        elif self.data_format == 'DUMP':
            split = int(DumpLength.HEX_LINE_LENGTH)
            for token in re.finditer(r'\b[0-9A-Fa-f]{2}\b', text[:split]):
                paint(token.start(), token.end(), 'number')
            paint(split, len(text), 'string')
