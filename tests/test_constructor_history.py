from types import SimpleNamespace


def test_constructor_field_switch_text_and_hotkeys(runtime, config):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from common.gui.windows.complex_fields_window import ComplexFieldsParser
    from common.gui.undo_commands.EditItemTextCommand import EditItemTextCommand
    transaction = runtime.Transaction(message_type='0200', data_fields={
        '47': {'227': {'01': 'Limassol'}}, '48': {'51': 'SOME ONE'}})
    terminal = SimpleNamespace(parse_main_window_tab=lambda: transaction)
    window = ComplexFieldsParser(config, terminal)
    try:
        window.show()
        runtime.app.processEvents()
        index47 = next(i for i in range(window.FieldNumber.count()) if window.FieldNumber.itemText(i).startswith('47 -'))
        index48 = next(i for i in range(window.FieldNumber.count()) if window.FieldNumber.itemText(i).startswith('48 -'))
        window.FieldNumber.setCurrentIndex(index47)
        stack = window.JsonView.undo_stack
        stack.clear()
        leaf = window.JsonView.root.child(0).child(0).child(0)
        stack.push(EditItemTextCommand(window.JsonView, leaf, 1, 'Limassol', 'Paris'))
        window.FieldNumber.setCurrentIndex(index48)
        assert window.get_field_number() == '48'
        window.UndoButton.click()
        assert window.get_field_number() == '47'
        assert window.JsonView.root.child(0).child(0).child(0) is leaf
        assert leaf.field_data == 'Paris'
        window.UndoButton.click()
        assert leaf.field_data == 'Limassol'
        window.RedoButton.click()
        window.RedoButton.click()
        assert window.get_field_number() == '48'
        original = window.TextData.toPlainText()
        window.TextData.setFocus()
        window.TextData.selectAll()
        QTest.keyClicks(window.TextData, 'x')
        QTest.keyClick(window.TextData, Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
        assert window.TextData.toPlainText() == original
        QTest.keyClick(window.TextData, Qt.Key.Key_Y, Qt.KeyboardModifier.ControlModifier)
        assert window.TextData.toPlainText() == 'x'
        window.DownButton.click()
        assert window.TextData.toPlainText() == '5108SOME ONE'
        previous = window.TextData.toPlainText()
        window.drop_field_text('{"48":{"51":"NEW"}}')
        assert window.TextData.toPlainText() == '5103NEW'
        window.UndoButton.click()
        assert window.TextData.toPlainText() == previous
        window.UndoButton.click()
        assert window.TextData.toPlainText() == 'x'
        window.RedoButton.click()
        old_item = window.JsonView.root.child(0)
        window.UpButton.click()
        assert window.JsonView.root.child(0) is not old_item
        window.UndoButton.click()
        assert window.JsonView.root.child(0) is old_item
        window.history_action(window.clear_all, 'Clear all')
        assert window.JsonView.root.childCount() == 0
        window.UndoButton.click()
        assert window.JsonView.root.childCount() == 1
        assert window.TextData.toPlainText() == '5108SOME ONE'
    finally:
        window.hide()
        window.deleteLater()
