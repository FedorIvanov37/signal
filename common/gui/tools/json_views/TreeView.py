from PyQt6.QtWidgets import QTreeWidget, QApplication, QWidget, QToolButton, QHeaderView, QStyleOptionHeader, QStyle
from PyQt6.QtGui import QUndoStack, QFont, QPalette, QColor, QPen, QPainter, QPolygonF
from PyQt6.QtCore import pyqtSignal, Qt, QPointF, QTimer
from common.gui.decorators.void_qt_signals import void_qt_signals
from common.gui.enums.Colors import Colors
from common.gui.enums import MainFieldSpec


class FieldSortHeader(QHeaderView):
    """Reserve room for the sort button only in its own section."""
    label_inset = 27

    def __init__(self, column, parent):
        super().__init__(Qt.Orientation.Horizontal, parent)
        self.sort_column = column
        self.setStyleSheet('QHeaderView { padding: 0; }')
        self.setStretchLastSection(True)

    def sectionSizeFromContents(self, logical_index):
        size = super().sectionSizeFromContents(logical_index)
        if logical_index == self.sort_column:
            size.setWidth(size.width() + self.label_inset)
        return size

    def paintSection(self, painter, rect, logical_index):
        if logical_index != self.sort_column:
            painter.save()
            super().paintSection(painter, rect, logical_index)
            painter.restore()
            return
        option = QStyleOptionHeader()
        self.initStyleOptionForIndex(option, logical_index)
        option.rect = rect
        text = option.text
        option.text = ''
        painter.save()
        self.style().drawControl(QStyle.ControlElement.CE_Header, option, painter, self)
        option.text = text
        option.rect = rect.adjusted(self.label_inset, 0, 0, 0)
        self.style().drawControl(QStyle.ControlElement.CE_HeaderLabel, option, painter, self)
        painter.restore()


class TreeView(QTreeWidget):
    field_removed: pyqtSignal = pyqtSignal()
    field_changed: pyqtSignal = pyqtSignal()
    field_added: pyqtSignal = pyqtSignal()
    root = None

    def __init__(self, parent=None):
        super(TreeView, self).__init__(parent=parent)
        self.undo_stack = QUndoStack(self)
        self.setup()

    def setup(self):
        self.setFont(QFont("Calibri", 12))
        self.header().setFont(QFont("Calibri", 12))
        self.setAllColumnsShowFocus(True)
        self.setAlternatingRowColors(True)
        self.setEditTriggers(self.EditTrigger.NoEditTriggers)
        self.setSortingEnabled(False)

        palette = QPalette()
        palette.setColor(palette.ColorRole.AlternateBase, QColor(Colors.LIGHT_GREY))
        color = QApplication.instance().property("signalSelectionColor") or Colors.SELECTION_BLUE
        palette.setColor(QPalette.ColorRole.Highlight, QColor(color))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor(Colors.WHITE))
        self.setPalette(palette)
        # Native Windows styles may otherwise use the OS accent color.

    def setup_field_sorting(self, column: int) -> None:
        self._field_sort_column = column
        owner = self
        config = getattr(getattr(self, 'window', None), 'config', None)
        while owner is not None and config is None:
            config = getattr(owner, 'config', None)
            owner = owner.parent()
        self._auto_sort_enabled = bool(config and config.fields.auto_sort)
        self._auto_sort_timer = QTimer(self)
        self._auto_sort_timer.setSingleShot(True)
        self._auto_sort_timer.timeout.connect(self.apply_auto_sort)
        alignment = self.header().defaultAlignment()
        self.setHeader(FieldSortHeader(column, self))
        self.header().setFont(self.font())
        self.header().setDefaultAlignment(alignment)
        self.headerItem().setTextAlignment(
            self._field_sort_column, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.header().setSectionsClickable(True)
        self.header().sectionClicked.connect(self.sort_top_level_fields)
        self.sort_fields_button = QToolButton(self.header().viewport())
        self.sort_fields_button.setText("↑")
        self.sort_fields_button.setToolTip("Sort fields ascending")
        self.sort_fields_button.setAccessibleName("Sort fields ascending")
        self.sort_fields_button.setAutoRaise(True)
        self.sort_fields_button.setStyleSheet("QToolButton { padding: 0; }")
        self.sort_fields_button.clicked.connect(
            lambda: self.sort_top_level_fields(self._field_sort_column))
        self.header().geometriesChanged.connect(self._position_sort_button)
        self.header().sectionResized.connect(self._position_sort_button)
        self.header().sectionMoved.connect(self._position_sort_button)
        self._position_sort_button()

    def _position_sort_button(self, *args):
        header = self.header()
        column = self._field_sort_column
        height = min(22, header.height())
        left = header.sectionViewportPosition(column)
        self.sort_fields_button.setGeometry(left + 3, (header.height() - height) // 2 - 5, 20, height)
        self.sort_fields_button.setVisible(not header.isSectionHidden(column))

    def schedule_auto_sort(self, *_):
        if self._auto_sort_enabled:
            self._auto_sort_timer.start(0)

    def set_auto_sort(self, enabled):
        became_enabled = enabled and not self._auto_sort_enabled
        self._auto_sort_enabled = enabled
        self._auto_sort_timer.stop()
        if became_enabled:
            self.apply_auto_sort()

    def apply_auto_sort(self):
        if self._auto_sort_enabled and self.root is not None:
            if getattr(self, '_field_number_editing', False):
                return
            parents = [self.root]
            for parent in parents:
                children = parent.get_children()
                if any(not item.text(self._field_sort_column).strip() for item in children):
                    # Keep unfinished rows in place at every nesting level.
                    return
                parents.extend(item for item in children if item.childCount())
            current = self.currentItem()
            column = self.currentColumn()
            for parent in parents:
                parent.sortChildren(self._field_sort_column, Qt.SortOrder.AscendingOrder)
            if current is not None:
                if self.currentItem() is not current:
                    self.setCurrentItem(current, column)
                self.scrollToItem(current)

    def sort_top_level_fields(self, column: int) -> None:
        """Sort fields at every level without detaching rows or their widgets."""
        if column != self._field_sort_column:
            return

        parents = [self.root]
        while parents:
            parent = parents.pop()
            parent.sortChildren(column, Qt.SortOrder.AscendingOrder)
            parents.extend(child for child in parent.get_children() if child.childCount())

    def drawBranches(self, painter, rect, index):
        if QApplication.instance().property("signalTreeColor") in ('#F0F0F0', '#8996A3', '#FFFBEB', '#EFF1F5'):
            return super().drawBranches(painter, rect, index)
        if not self.model().hasChildren(index):
            return
        rtl = self.layoutDirection() == Qt.LayoutDirection.RightToLeft
        x = rect.left() + self.indentation() / 2 if rtl else rect.right() - self.indentation() / 2 + 1
        y = rect.center().y()
        if self.isExpanded(index):
            points = [(x - 3, y - 2), (x, y + 1), (x + 3, y - 2)]
        else:
            direction = -1 if rtl else 1
            points = [(x - direction, y - 3), (x + 2 * direction, y), (x - direction, y + 3)]
        painter.save()
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QPen(QColor("#FFFFFF"), 1.4))
        painter.drawPolyline(QPolygonF([QPointF(px, py) for px, py in points]))
        painter.restore()

    def resize_all(self, exceptions: list[int] | None = None):
        if exceptions is None:
            exceptions = []

        for column in range(self.columnCount()):
            if column in exceptions:
                continue

            self.resizeColumnToContents(column)

    def make_order(self):
        self.collapseAll()
        self.expandAll()
        self.resize_all(exceptions=[MainFieldSpec.ColumnsOrder.DESCRIPTION])

    def setFocus(self) -> None:
        if not (item := self.currentItem()):
            item = self.root

        if item.isHidden():
            item = self.root

        self.setCurrentItem(item)
        self.scrollToItem(item)

        QTreeWidget.setFocus(self)

    def edit_column(self, column: int):
        if not self.hasFocus():
            self.setFocus()

        if not (item := self.currentItem()):
            return

        self.editItem(item, column)

    def search(self, text: str, parent = None) -> None:
        if not text:
            self.unhide_all()
            return

        if parent is None:
            parent = self.root

        text = text.strip()

        for item in parent.get_children():
            if item.childCount():
                self.search(text, parent=item)

            item_found: bool = self.value_in_item(text, item)

            item.setHidden(not item_found)
            item.setExpanded(item_found)

            if item.childCount() and self.value_in_item(text, item, check_subfields=False):
                self.unhide_all(item)

    def unhide_all(self, parent=None):
        if parent is None:
            parent = self.root

        for item in parent.get_children():
            if item.childCount():
                self.unhide_all(item)

            item.setHidden(False)

    @void_qt_signals
    def clean(self):
        self.root.takeChildren()

    def undo(self):
        self._apply_history(redo=False)
        self.field_changed.emit()
        self.setFocus()

    def clear_with_history(self, mti=None):
        if not self.root.childCount() and (mti is None or mti.currentIndex() == -1):
            return
        from common.gui.undo_commands.ClearTreeCommand import ClearTreeCommand
        self.undo_stack.push(ClearTreeCommand(self, mti))

    def redo(self):
        self._apply_history(redo=True)
        self.field_changed.emit()
        self.setFocus()

    def _apply_history(self, *, redo):
        from common.gui.tools.json_items.FIeldItem import FieldItem
        from common.gui.enums.CheckBoxesDefinition import CheckBoxesDefinition

        stack = self.undo_stack
        while stack.canRedo() if redo else stack.canUndo():
            command = stack.command(stack.index() if redo else stack.index() - 1)
            item = getattr(command, "item", None)
            generated = (isinstance(item, FieldItem)
                         and item.checkbox_checked(CheckBoxesDefinition.GENERATE))
            if generated:
                # QUndoStack skips obsolete commands without replaying them.
                command.setObsolete(True)
            if redo:
                stack.redo()
            else:
                stack.undo()
            if not generated:
                break

    def value_in_item(self, value: str, item, check_subfields=True):
        if value in item.field_number:
            return True

        if value.lower() in item.description.lower():
            return True

        try:
            if value.lower() in item.field_data.lower():
                return True

        except AttributeError:
            pass

        if check_subfields:
            for child in item.get_children():
                if not self.value_in_item(value, child):
                    continue

                return True

        return False
