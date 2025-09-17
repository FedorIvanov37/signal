from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtWidgets import QDialog, QTableWidgetItem, QCheckBox, QHBoxLayout, QWidget, QHeaderView
from common.lib.core.EpaySpecification import EpaySpecification, Mti
from common.gui.forms.mti_spec import Ui_MtiSpecWindow
from common.gui.decorators.window_settings import set_window_icon, has_close_button_only
from common.gui.enums import ButtonActions


class MtiSpecWindow(Ui_MtiSpecWindow, QDialog):
    _spec: EpaySpecification = EpaySpecification()
    _changed: pyqtSignal = pyqtSignal()
    _need_to_set_mti: pyqtSignal = pyqtSignal(list)

    @property
    def need_to_set_mti(self):
        return self._need_to_set_mti

    @property
    def changed(self):
        return self._changed

    @property
    def spec(self):
        return self._spec

    def __init__(self):
        super(MtiSpecWindow, self).__init__()
        self.setupUi(self)
        self.setup()

    @set_window_icon
    @has_close_button_only
    def setup(self):
        self.ButtonPlus.setText(ButtonActions.ButtonActionSigns.BUTTON_PLUS_SIGN)
        self.ButtonMinus.setText(ButtonActions.ButtonActionSigns.BUTTON_MINUS_SIGN)
        self.ButtonPlus.clicked.connect(self.plus)
        self.ButtonMinus.clicked.connect(self.minus)
        self.ButtonSave.clicked.connect(self.ok)
        self.ButtonCancel.clicked.connect(self.cancel)
        self.parse_mti_list(self.spec.spec.mti)
        self.MtiTable.verticalHeader().hide()

    def minus(self):
        position = self.MtiTable.currentRow()
        self.MtiTable.removeRow(position)

        if self.MtiTable.item(position, 0) is None:
            position = position - 1

        self.MtiTable.setCurrentCell(position, 0)

    def add_item(self, row_set=None):
        if row_set is None:
            row_set = ("", "", "", False, "")

        for item_count, item_data in enumerate(row_set):
            item = self.MtiItem(self.MtiTable, item_data)

            if isinstance(item_data, bool):
                item.set_checkbox(item_data, self.MtiTable.rowCount() - 1, item_count)

            self.MtiTable.setItem(self.MtiTable.rowCount(), item_count, item)

    def ok(self):
        mti_list = self.create_mti_list()
        self.need_to_set_mti.emit(mti_list)
        self.accept()

    def cancel(self):
        self.close()

    def add_bottom_row(self, row_data=None):
        if not row_data:
            row_data = (None, None, None, False, None)

        self.MtiTable.insertRow(self.MtiTable.rowCount())

        for item_count, item_data in enumerate(row_data):
            item = self.MtiItem(self.MtiTable, item_data)

            if isinstance(item_data, bool):
                item.set_checkbox(item_data, self.MtiTable.rowCount() - 1, item_count)

            self.MtiTable.setItem(self.MtiTable.rowCount() - 1, item_count, item)

    def plus(self):
        self.add_bottom_row()
        self.MtiTable.scrollToBottom()
        self.MtiTable.setCurrentCell(self.MtiTable.rowCount() - 1, int())
        self.MtiTable.editItem(self.MtiTable.currentItem())

    def parse_mti_list(self, mti_list: list[Mti]):
        for row_count, mti in enumerate(mti_list):
            row_set = (mti.description, mti.request, mti.response, mti.is_reversible, mti.reversal_mti)
            self.add_bottom_row(row_set)

        header_view: QHeaderView = self.MtiTable.horizontalHeader()
        header_view.setSectionResizeMode(header_view.ResizeMode.ResizeToContents)

    def create_mti_list(self) -> list[Mti] | None:
        result: list = list()

        for row in range(self.MtiTable.rowCount()):
            mti_list = list()

            for column in range(self.MtiTable.columnCount()):
                if not (item := self.MtiTable.item(row, column)):
                    continue

                item_data: bool | str = item.checked if item.checkbox else item.text()

                mti_list.append(item_data)

            mti: Mti = Mti()

            mti.description, mti.request, mti.response, mti.is_reversible, mti.reversal_mti = mti_list

            if not all((mti.request, mti.response)):
                continue

            if mti.is_reversible and not mti.reversal_mti:
                continue

            result.append(mti)

        return result

    class MtiItem(QTableWidgetItem):
        _changed: bool = False
        _checked: bool = False
        _checkbox: QCheckBox = None

        @property
        def changed(self):
            return self._changed

        @changed.setter
        def changed(self, changed):
            self._changed = changed

        @property
        def checkbox(self):
            return self._checkbox

        @checkbox.setter
        def checkbox(self, checkbox):
            self._checkbox = checkbox

        @property
        def checked(self):
            if not self.checkbox:
                return False

            return self.checkbox.isChecked()

        def __init__(self, mti_table, item_data):
            super().__init__(item_data)
            self.MtiTable = mti_table

        def set_checkbox(self, state: bool, row_number: int, column_number: int) -> None:
            self.changed = True
            cell_widget = QWidget()
            self.checkbox: QCheckBox = QCheckBox()
            self.checkbox.setChecked(state)
            self.checkbox.setText(" ")
            lay_out = QHBoxLayout(cell_widget)
            lay_out.addWidget(self.checkbox)
            lay_out.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lay_out.setContentsMargins(0, 0, 0, 0)
            cell_widget.setLayout(lay_out)
            self.MtiTable.setCellWidget(row_number, column_number, cell_widget)
