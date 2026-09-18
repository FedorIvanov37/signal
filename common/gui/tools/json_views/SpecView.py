from typing import Callable
from copy import deepcopy
from loguru import logger
from PyQt6.QtCore import pyqtSignal, Qt, QTimer, QPersistentModelIndex
from PyQt6 import sip
from PyQt6.QtWidgets import QTreeWidgetItem, QItemDelegate, QApplication, QStyleOptionViewItem, QAbstractItemDelegate, QStyle
from PyQt6.QtGui import QUndoStack, QPalette, QColor
from common.gui.enums.UndoSteps import UndoSteps
from common.gui.undo_commands.RemoveItemCommand import RemoveItemCommand
from common.gui.undo_commands.InsertSubItemCommand import InsertSubItemCommand
from common.gui.undo_commands.EditItemTextCommand import EditItemTextCommand
from common.gui.undo_commands.SignalsBlocker import SignalsBlocker
from common.gui.undo_commands.InsertItemCommand import InsertItemCommand
from common.core.tools.EpaySpecification import EpaySpecification
from common.core.data_models.EpaySpecificationModel import EpaySpecModel, Validators
from common.core.data_models.EpaySpecificationModel import IsoField, FieldSet
from common.core.data_models.Types import FieldPath
from common.gui.tools.json_items.SpecItem import SpecItem
from common.gui.tools.validators.SpecValidator import SpecValidator
from common.gui.decorators.void_qt_signals import void_qt_signals
from common.gui.tools.json_views.TreeView import TreeView
from common.gui.enums.Colors import Colors
from common.gui.enums import SpecFieldDef
from common.gui.enums.RootItemNames import RootItemNames


class SpecView(TreeView):

    class SpecViewDelegate(QItemDelegate):
        def paint(self, painter, option, index):
            if index.data(Qt.ItemDataRole.CheckStateRole) is None or not (
                option.state & QStyle.StateFlag.State_HasFocus
            ):
                return super().paint(painter, option, index)
            # Check-state cells have no text to focus: outline the indicator.
            unfocused = QStyleOptionViewItem(option)
            unfocused.state &= ~QStyle.StateFlag.State_HasFocus
            super().paint(painter, unfocused, index)
            indicator_option = QStyleOptionViewItem(option)
            indicator_option.features |= QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
            indicator_option.checkState = Qt.CheckState(index.data(Qt.ItemDataRole.CheckStateRole))
            indicator = self.tree.style().subElementRect(
                QStyle.SubElement.SE_ItemViewItemCheckIndicator, indicator_option, self.tree)
            focus_rect = indicator.adjusted(-2, -2, 2, 2).intersected(option.rect)
            self.drawFocus(painter, option, focus_rect)

        def drawDisplay(self, painter, option, rect, text):
            if QApplication.instance().property("signalTreeColor") not in ('#F0F0F0', '#8996A3', '#FFFBEB', '#EFF1F5'):
                option = QStyleOptionViewItem(option)
                source = option.palette.color(QPalette.ColorRole.Text).name().lower()
                color = {"#000000": "#CDD5DF", "#ffffff": "#CDD5DF",
                         "#ff0000": "#FF8D96", "#800000": "#FF8D96",
                         "#0000ff": "#91C5FF"}.get(source, source)
                option.palette.setColor(QPalette.ColorRole.Text, QColor(color))
                if source in ("#ff0000", "#800000", "#0000ff"):
                    option.palette.setColor(QPalette.ColorRole.HighlightedText, QColor(color))
            super().drawDisplay(painter, option, rect, text)

        def __init__(self, tree: TreeView, stack: QUndoStack):
            super().__init__()

            self.tree = tree
            self.stack = stack

        def setModelData(self, editor, model, idx):
            if self.tree.window.read_only:
                self.tree.warn_blocked(QPersistentModelIndex(idx))
                return
            role = Qt.ItemDataRole.EditRole

            old = model.data(idx, role) or str()

            with SignalsBlocker(self.tree):
                super().setModelData(editor, model, idx)

            new = model.data(idx, role) or str()

            if new != old:
                item = self.tree.itemFromIndex(idx)
                self.stack.push(EditItemTextCommand(self.tree, item, idx.column(), old, new))
                if idx.column() == self.tree._field_sort_column:
                    self.tree.schedule_auto_sort()

    _spec: EpaySpecification = EpaySpecification()
    search_finished = pyqtSignal()

    # Reject function execution when read only mode is active
    def reject_in_read_only_mode(fuction: Callable, *args, **kwargs):
        def wrapper(self, *args, **kwargs):
            if not self.window.read_only:
                return fuction(self)

            if not self.hasFocus():
                self.setFocus()

            self.warn_blocked(fuction.__name__)

        return wrapper

    @property
    def spec(self):
        return self._spec

    def __init__(self, window):
        super(SpecView, self).__init__()
        self.root: SpecItem = SpecItem([RootItemNames.SPECIFICATION_ROOT_NAME])
        self.window = window
        self._tab_editing = False
        self._last_blocked_warning = None
        self._pending_validation = {}
        self._validation_timer = QTimer(self)
        self._validation_timer.setSingleShot(True)
        self._validation_timer.timeout.connect(self._validate_departed_cells)
        self.validator = SpecValidator()
        self.setItemDelegate(QItemDelegate())
        self._setup()
        self.selectionModel().currentChanged.connect(self._schedule_validation)
        self.selectionModel().currentChanged.connect(self._reset_blocked_warning)
        QApplication.instance().focusChanged.connect(self._schedule_validation)

    def _reset_blocked_warning(self, *args):
        self._last_blocked_warning = None

    def warn_blocked(self, target, message="Read-only mode. Clear the checkbox at the top of the window"):
        warning = (target, message)
        if warning != self._last_blocked_warning:
            self._last_blocked_warning = warning
            logger.warning(message)

    def _schedule_validation(self, *args):
        if self._pending_validation:
            self._validation_timer.start(0)

    def _validate_departed_cells(self):
        focused = QApplication.focusWidget()
        inside = focused is self or (focused is not None and self.isAncestorOf(focused))
        current, column = self.currentItem(), self.currentColumn()
        for key, (item, columns) in list(self._pending_validation.items()):
            if sip.isdeleted(item) or item.treeWidget() is not self:
                self._pending_validation.pop(key, None)
                continue
            if not inside or item is not current:
                self._pending_validation.pop(key, None)
                self._validate_row(item)
            else:
                for previous in list(columns):
                    if previous != column:
                        columns.remove(previous)
                        self._validate_departed_column(item, previous)

    def _validate_departed_column(self, item, column):
        try:
            self.validator.validate_column(item, column)
            if item is not self.root and column in (SpecFieldDef.ColumnsOrder.MIN_LENGTH, SpecFieldDef.ColumnsOrder.MAX_LENGTH):
                self.validator.validate_length_relation(item)
        except ValueError as error:
            logger.warning(error)

    def _validate_row(self, item):
        if item is not self.root and item.reserved_for_future:
            return
        with SignalsBlocker(self):
            result = self.validator.validate_spec_row(item)
            errors = {error for group in result.errors.values() for error in group}
            for error in sorted(errors):
                logger.error(error)
            if errors:
                item.set_item_color(Colors.RED)
            else:
                item.set_item_color()

    def _setup(self):
        self.setAllColumnsShowFocus(False)
        self.setTabKeyNavigation(True)
        self.setHeaderLabels(SpecFieldDef.Columns)
        self.addTopLevelItem(self.root)
        self.setup_field_sorting(SpecFieldDef.ColumnsOrder.FIELD)
        self.setItemDelegate(self.SpecViewDelegate(self, self.undo_stack))
        self.itemDoubleClicked.connect(self.editItem)
        self.itemClicked.connect(self.process_item_click)
        self.itemChanged.connect(self.process_item_change)
        # self.currentItemChanged.connect(self.print_path)
        self.parse_spec()
        self.make_order()
        self.collapseAll()
        self.root.setExpanded(True)
        self.resizeColumnToContents(SpecFieldDef.ColumnsOrder.DESCRIPTION)

    def print_path(self, current_item: SpecItem, previous_item: SpecItem):
        if current_item is previous_item:
            return

        item: SpecItem
        path: FieldPath

        if not (path := current_item.get_field_path()):
            return

        if not any((current_item.field_number, current_item.description)):
            return

        description: str = self.spec.get_field_description(path, string=True)
        path: str = current_item.get_field_path(string=True)

        logger.info(f"{path} - {description}")

    def set_read_only(self, readonly: bool = True, parent: SpecItem | None = None) -> None:
        if parent is None:
            self._reset_blocked_warning()
        if readonly:
            self._tab_editing = False
        if parent is None:
            parent = self.root

        spec_item: SpecItem

        for spec_item in parent.get_children():
            with SignalsBlocker(self):
                spec_item.set_read_only(readonly)

            if not spec_item.get_children():
                continue

            self.set_read_only(readonly=readonly, parent=spec_item)

    def _checkbox_edit_warning(self, item: SpecItem, column: int):
        if self.window.read_only:
            return "Read-only mode. Clear the checkbox at the top of the window"
        if item.is_secret_pan(column):
            return "The card number must always be masked"
        if column == SpecFieldDef.ColumnsOrder.CAN_BE_GENERATED:
            return 'The "Generate" setting is predefined and cannot be changed'

    @void_qt_signals
    def process_item_click(self, item: SpecItem, column: int) -> None:
        if self.window.read_only:
            return
        if column in SpecFieldDef.Checkboxes:
            if warning := self._checkbox_edit_warning(item, column):
                self.warn_blocked(QPersistentModelIndex(self.indexFromItem(item, column)), warning)

    def _navigation_cells(self):
        columns = [self.header().logicalIndex(i) for i in range(self.columnCount())]
        columns = [column for column in columns if not self.isColumnHidden(column)]
        pending = [self.root]
        while pending:
            item = pending.pop()
            if item.isHidden():
                continue
            for column in columns:
                if item is self.root and column not in (
                    SpecFieldDef.ColumnsOrder.FIELD, SpecFieldDef.ColumnsOrder.DESCRIPTION
                ):
                    continue
                yield item, column
            pending.extend(reversed(item.get_children()))

    def _navigate_editing_cell(self, reverse=False):
        cells = list(self._navigation_cells())
        if not cells:
            return
        current = self.currentItem(), self.currentColumn()
        if current in cells:
            position = cells.index(current) + (-1 if reverse else 1)
            position = max(0, min(position, len(cells) - 1))
        else:
            position = len(cells) - 1 if reverse else 0
        item, column = cells[position]
        self._focus_cell(item, column)
        if self._tab_editing and not self.window.read_only and column not in SpecFieldDef.Checkboxes:
            self.editItem(item, column)

    def _focus_cell(self, item, column):
        parent = item.parent()
        while parent is not None:
            parent.setExpanded(True)
            parent = parent.parent()
        self.setFocus()
        self.setCurrentItem(item, column)
        self.scrollTo(self.indexFromItem(item, column))

    def _navigate_arrow(self, key):
        rows = []
        for item, column in self._navigation_cells():
            if not rows or rows[-1][0] is not item:
                rows.append((item, []))
            rows[-1][1].append(column)
        if not rows:
            return
        current, column = self.currentItem(), self.currentColumn()
        row = next((i for i, (item, _) in enumerate(rows) if item is current), 0)
        item, columns = rows[row]
        if key in (Qt.Key.Key_Left, Qt.Key.Key_Right):
            position = columns.index(column) if column in columns else 0
            position += -1 if key == Qt.Key.Key_Left else 1
            column = columns[max(0, min(position, len(columns) - 1))]
        else:
            row += -1 if key == Qt.Key.Key_Up else 1
            item, columns = rows[max(0, min(row, len(rows) - 1))]
            if column not in columns:
                column = min(columns, key=lambda candidate: abs(
                    self.header().visualIndex(candidate) - self.header().visualIndex(column)))
        self._focus_cell(item, column)

    def mousePressEvent(self, event):
        self._tab_editing = False
        super().mousePressEvent(event)
        if not self.window.read_only or event.button() != Qt.MouseButton.LeftButton:
            return
        index = self.indexAt(event.position().toPoint())
        if not index.isValid() or index.data(Qt.ItemDataRole.CheckStateRole) is None:
            return
        option = QStyleOptionViewItem()
        self.initViewItemOption(option)
        option.rect = self.visualRect(index)
        option.features |= QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
        option.checkState = Qt.CheckState(index.data(Qt.ItemDataRole.CheckStateRole))
        indicator = self.style().subElementRect(QStyle.SubElement.SE_ItemViewItemCheckIndicator, option, self)
        if indicator.contains(event.position().toPoint()):
            self.warn_blocked(QPersistentModelIndex(index))

    def closeEditor(self, editor, hint):
        hints = QAbstractItemDelegate.EndEditHint
        if hint == hints.RevertModelCache:
            self._tab_editing = False
        if hint not in (hints.EditNextItem, hints.EditPreviousItem):
            return super().closeEditor(editor, hint)
        super().closeEditor(editor, hints.NoHint)
        self._navigate_editing_cell(reverse=hint == hints.EditPreviousItem)

    def keyPressEvent(self, event):
        if event.key() in (Qt.Key.Key_Left, Qt.Key.Key_Right, Qt.Key.Key_Up, Qt.Key.Key_Down):
            self._navigate_arrow(event.key())
            event.accept()
            return
        if event.key() in (Qt.Key.Key_Tab, Qt.Key.Key_Backtab):
            reverse = event.key() == Qt.Key.Key_Backtab or bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier)
            self._navigate_editing_cell(reverse=reverse)
            event.accept()
            return
        item, column = self.currentItem(), self.currentColumn()
        if event.key() == Qt.Key.Key_Space and item is not None and column in SpecFieldDef.Checkboxes:
            if warning := self._checkbox_edit_warning(item, column):
                self.warn_blocked(QPersistentModelIndex(self.indexFromItem(item, column)), warning)
            elif item.data(column, Qt.ItemDataRole.CheckStateRole) is not None:
                self._tab_editing = True
                item.setCheckState(column, Qt.CheckState.Unchecked if item.is_checked(column) else Qt.CheckState.Checked)
            event.accept()
            return
        if event.key() == Qt.Key.Key_Escape:
            self._tab_editing = False
        typing = bool(event.text() and event.text().isprintable()) and not (
            event.modifiers() & (Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier
                                 | Qt.KeyboardModifier.MetaModifier)
        )
        if item is not None and column not in SpecFieldDef.Checkboxes and (
            event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter, Qt.Key.Key_F2) or typing
        ):
            self.editItem(item, column)
            editor = QApplication.focusWidget()
            if typing and editor is not self and self.isAncestorOf(editor):
                QApplication.sendEvent(editor, event)
            event.accept()
            return
        super().keyPressEvent(event)

    @void_qt_signals
    def process_item_change(self, item: SpecItem, column: int):
        if item.is_secret_pan(column):
            item.set_checkbox(column)

        if all((
            column > SpecFieldDef.ColumnsOrder.TAG_LENGTH,
            item.checkState(column) is not Qt.CheckState.PartiallyChecked,
            self.window.read_only,
        )):
            item.setCheckState(column, Qt.CheckState.Unchecked if item.is_checked(column) else Qt.CheckState.Checked)

        match column:
            case SpecFieldDef.ColumnsOrder.CAN_BE_GENERATED:
                item.set_checkbox(column, item.field_number in self.spec.get_fields_to_generate())
                return

            case SpecFieldDef.ColumnsOrder.SECRET:
                self.cascade_checkboxes(item)

            case SpecFieldDef.ColumnsOrder.TAG_LENGTH:
                self.cascade_tag_length(item)

        _, columns = self._pending_validation.setdefault(id(item), (item, set()))
        columns.add(column)
        result = self.validator.validate_spec_row(item)
        if not any(result.errors.values()):
            with SignalsBlocker(self):
                item.set_item_color()
        self._schedule_validation()

    def search(self, text: str, parent: SpecItem | None = None) -> None:
        TreeView.search(self, text, parent)
        self.search_finished.emit()

    @staticmethod
    def cascade_tag_length(parent: SpecItem):
        child_item: SpecItem

        for child_item in parent.get_children():
            child_item.var_length = parent.tag_length

    @void_qt_signals
    def cascade_checkboxes(self, parent: SpecItem) -> None:
        child_item: SpecItem
        is_checked: bool = parent.is_checked(SpecFieldDef.ColumnsOrder.SECRET)

        for child_item in parent.get_children():
            child_item.set_checkbox(SpecFieldDef.ColumnsOrder.SECRET, is_checked)

            if child_item.childCount():
                self.cascade_checkboxes(child_item)

    def editItem(self, item, column):
        if item is self.root and column not in (SpecFieldDef.ColumnsOrder.DESCRIPTION, SpecFieldDef.ColumnsOrder.FIELD):
            return

        if column > SpecFieldDef.ColumnsOrder.TAG_LENGTH:
            return

        if column == SpecFieldDef.ColumnsOrder.CAN_BE_GENERATED:
            return

        if self.window.read_only:
            self.warn_blocked(QPersistentModelIndex(self.indexFromItem(item, column)))
            return

        TreeView.editItem(self, item, column)
        self._tab_editing = True

    def validate_all(self, parent: SpecItem | None = None) -> None:
        if parent is None:
            parent = self.root

        child_item: SpecItem

        for child_item in parent.get_children():

            self._validate_row(child_item)

            if not child_item.childCount():
                continue

            self.validate_all(parent=child_item)

    def hide_reserved(self, hide=True):
        item: SpecItem

        for item in self.root.get_children():

            if item.reserved_for_future:
                item.setHidden(hide)

    def reload_spec(self, commit):
        spec: EpaySpecModel = self.generate_spec()
        self.spec.reload_spec(spec, commit, config=self.window.config)

    def reload(self):
        self.setup()

    def make_order(self):
        TreeView.make_order(self)
        self.hide_reserved()

    @reject_in_read_only_mode
    def minus(self):
        def callback(_item_parent: SpecItem, _item: SpecItem, step: UndoSteps):
            if step == UndoSteps.UNDO:
                self.setCurrentItem(_item)
                item.setExpanded(True)

            self.setFocus()

        if not (item := self.currentItem()):
            return

        if item is self.root:
            self.setCurrentItem(self.root)
            self.setFocus()
            return

        self.undo_stack.push(RemoveItemCommand(self, item, callback))

    @reject_in_read_only_mode
    def plus(self):
        def callback(new_item: SpecItem, step: UndoSteps):
            if step is not UndoSteps.REDO:
                return

            self.setCurrentItem(new_item)
            self.setFocus()

        item = SpecItem([])

        if not (current_item := self.currentItem()):
            return

        if not (parent := current_item.parent()):
            return

        self.undo_stack.push(InsertItemCommand(self, item, parent, parent.indexOfChild(current_item) + 1, callback))

    @reject_in_read_only_mode
    def next_level(self):
        def callback(_parent: SpecItem, _item: SpecItem, step: UndoSteps):
            if step == UndoSteps.REDO:
                self.setCurrentItem(_item)

            self.setFocus()

        if not (current_item := self.currentItem()):
            return

        item = SpecItem([])

        self.undo_stack.push(InsertSubItemCommand(self, current_item, item, callback))

    @void_qt_signals
    def parse_field_spec(self, field_spec: IsoField):
        if not (item := self.get_item_by_path(field_spec.field_path)):
            return

        item.parse_field_spec(field_spec)
        item.spec = deepcopy(field_spec)

    def parse_spec(self, spec=None):
        self._validation_timer.stop()
        self._pending_validation.clear()
        if spec is None:
            spec = self.spec

        current_path = None
        current_item: SpecItem

        if current_item := self.currentItem():
            current_path = current_item.get_field_path()

        self.clean()
        self.root.setText(SpecFieldDef.ColumnsOrder.DESCRIPTION, spec.name)
        self._draft_spec = deepcopy(spec.spec if hasattr(spec, 'spec') else spec)
        self.parse_spec_fields(spec.fields)
        self.collapseAll()
        self.expandItem(self.root)
        self.set_current_item_by_path(current_path)
        self.validate_all()
        self.set_read_only(self.window.read_only)
        self.schedule_auto_sort()

    def get_item_by_path(self, field_path: FieldPath, parent: SpecItem | None = None) -> SpecItem:
        if parent is None:
            parent = self.root

        for child in parent.get_children():
            if child.get_field_path() == field_path:
                return child

            if child.get_children():
                if child := self.get_item_by_path(field_path, parent=child):
                    return child

    def set_current_item_by_path(self, field_path: FieldPath, parent: SpecItem | None = None):
        if parent is None:
            parent = self.root

        for item in parent.get_children():
            if item.get_field_path() == field_path:
                self.setCurrentItem(item)
                self.scrollToItem(item)
                return

            if item.get_children():
                self.set_current_item_by_path(field_path=field_path, parent=item)

    def parse_spec_fields(self, input_json, parent: QTreeWidgetItem = None):
        if parent is None:
            parent = self.root

        def field_order(key):
            number = input_json[key].field_number
            if not number:
                return (0, 0)
            return (1, int(number)) if number.isascii() and number.isdigit() else (2, number)

        for field in sorted(input_json, key=field_order):

            if field == self.spec.FIELD_SET.FIELD_001_BITMAP_SECONDARY:
                continue

            field_data: IsoField = input_json[field]

            field_data_for_item = [
                field_data.field_number,
                field_data.description,
                field_data.min_length,
                field_data.max_length,
                field_data.var_length,
                field_data.tag_length,
            ]

            field_data_for_item: list[str] = list(map(str, field_data_for_item))

            checkboxes: dict[int, bool] = {
                SpecFieldDef.ColumnsOrder.USE_FOR_MATCHING: field_data.matching,
                SpecFieldDef.ColumnsOrder.USE_FOR_REVERSAL: field_data.reversal,
                SpecFieldDef.ColumnsOrder.CAN_BE_GENERATED: field_data.generate,
                SpecFieldDef.ColumnsOrder.ALPHA: field_data.alpha,
                SpecFieldDef.ColumnsOrder.NUMERIC: field_data.numeric,
                SpecFieldDef.ColumnsOrder.SPECIAL: field_data.special,
                SpecFieldDef.ColumnsOrder.SECRET: field_data.is_secret
            }

            item: SpecItem = SpecItem(field_data_for_item)
            item.spec = deepcopy(field_data)

            item.set_checkboxes(checkboxes)

            parent.addChild(item)

            if field_data.fields:
                self.parse_spec_fields(input_json=field_data.fields, parent=item)

        self.make_order()

    def generate_spec(self) -> EpaySpecModel:
        errors = set()
        pending = [self.root]
        while pending:
            row = pending.pop()
            pending.extend(row.get_children())
            if row is not self.root and row.reserved_for_future:
                for column in (SpecFieldDef.ColumnsOrder.FIELD, SpecFieldDef.ColumnsOrder.DESCRIPTION):
                    try:
                        self.validator.validate_column(row, column)
                    except ValueError as error:
                        errors.add(str(error))
            else:
                result = self.validator.validate_spec_row(row)
                errors.update(error for group in result.errors.values() for error in group)
        if errors:
            raise ValueError('Invalid specification:\n' + '\n'.join(sorted(errors)))
        name: str = self.root.text(SpecFieldDef.ColumnsOrder.DESCRIPTION)
        fields_set: FieldSet

        def generate_fields(spec_item: SpecItem = None) -> FieldSet:
            if spec_item is None:
                spec_item = self.root

            fields: FieldSet = dict()

            row: SpecItem

            for row in spec_item.get_children():
                field = IsoField(
                    field_number=row.field_number,
                    field_path=row.get_field_path(),
                    min_length=row.min_length,
                    max_length=row.max_length,
                    var_length=row.var_length,
                    tag_length=row.tag_length,
                    generate=row.generate,
                    reversal=row.reversal,
                    matching=row.matching,
                    alpha=row.alpha,
                    numeric=row.numeric,
                    special=row.special,
                    reserved_for_future=row.reserved_for_future,
                    description=row.description,
                    is_secret=row.is_secret,
                    is_utrnno=row.spec.is_utrnno if row.spec else False,
                    fields=None
                )

                fields[row.field_number] = field

                if not(validators := row.spec.validators if row.spec else self.spec.get_field_validations(field.field_path)):
                    validators = Validators()

                field.validators = validators

                if not row.childCount():
                    continue

                if not (field_object := fields.get(row.field_number)):
                    continue

                field_object.fields = generate_fields(row)

            return fields

        fields_set: FieldSet = generate_fields()

        return EpaySpecModel(name=name, fields=fields_set, mti=self._draft_spec.mti, utrnno_path=self._draft_spec.utrnno_path)

    def finish_editing(self):
        editor = QApplication.focusWidget()
        if self.state() == self.State.EditingState and editor is not None and self.isAncestorOf(editor):
            self.commitData(editor)
            self.closeEditor(editor, QAbstractItemDelegate.EndEditHint.NoHint)

    def draft_snapshot(self):
        def snapshot(item):
            return ([item.text(column) for column in range(self.columnCount())],
                    [item.data(column, Qt.ItemDataRole.CheckStateRole) for column in range(self.columnCount())],
                    [snapshot(child) for child in item.get_children()],
                    deepcopy(item.spec.validators) if item.spec else None)
        return snapshot(self.root), deepcopy(self._draft_spec.mti), list(self._draft_spec.utrnno_path)
