from re import search
from PyQt6.QtWidgets import QDialog
from common.core.data_models.Transaction import Transaction
from common.gui.forms.reversal import Ui_ReversalWindow
from common.gui.decorators.window_settings import set_window_icon, has_close_button_only


class ReversalWindow(Ui_ReversalWindow, QDialog):
    _reversal_id: str | None = None
    _accepted: bool = False

    @property
    def accepted(self):
        return self._accepted

    @accepted.setter
    def accepted(self, accepted):
        self._accepted = accepted

    @property
    def reversal_id(self):
        return self._reversal_id

    @reversal_id.setter
    def reversal_id(self, reversal_id):
        self._reversal_id = reversal_id

    def __init__(self, transactions: list[Transaction]):
        super().__init__()
        self.setupUi(self)
        self.setup(transactions)

    @set_window_icon
    @has_close_button_only
    def setup(self, transactions: list[Transaction]) -> None:
        self.ComboBoxId.currentIndexChanged.connect(lambda index: self.id_item_changed())
        self.buttonBox.accepted.connect(self.set_reversal_id)
        self.ComboBoxId.addItem("> Transaction queue")

        for transaction in transactions:
            item = f"ID: {transaction.trans_id} | UTRNNO: {transaction.utrnno}"
            self.ComboBoxId.addItem(item)

    def id_item_changed(self):
        value = search(r"ID:\s+?(\S+)", self.ComboBoxId.currentText())
        value = value.group(1) if value else value
        self.TransactionIdField.setText(str())
        self.TransactionIdField.setText(value)

    def set_reversal_id(self):
        self.reversal_id = self.TransactionIdField.text()
