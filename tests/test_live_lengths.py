import pytest


@pytest.mark.parametrize('cancel', [False, True])
def test_live_lengths_through_all_ancestors(runtime, config, cancel):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QLineEdit, QTreeWidgetItem
    from common.gui.tools.json_views.JsonView import JsonView
    from common.gui.tools.json_items.FIeldItem import FieldItem
    from common.gui.enums.MainFieldSpec import ColumnsOrder

    config.validation.validation_enabled = False
    config.fields.hide_secrets = False
    tree = JsonView(config)
    tree.itemChanged.disconnect()
    parent = tree.root
    ancestors = [parent]
    for field in ('47', '227'):
        child = FieldItem([field])
        QTreeWidgetItem.addChild(parent, child)
        parent = child
        ancestors.append(parent)
    leaf = FieldItem(['01', 'abc'])
    QTreeWidgetItem.addChild(parent, leaf)
    leaf.setFlags(leaf.flags() | Qt.ItemFlag.ItemIsEditable)
    leaf.set_length()
    initial = [int(item.field_length) for item in [leaf, *ancestors]]
    tree.expandAll()
    tree.show()
    tree.setCurrentItem(leaf, ColumnsOrder.VALUE)
    tree.editItem(leaf, ColumnsOrder.VALUE)
    runtime.app.processEvents()
    editor = tree.findChild(QLineEdit)
    assert editor is not None
    editor.selectAll()
    QTest.keyClicks(editor, 'abcdef')
    assert leaf.field_data == 'abc'
    assert [int(item.field_length) for item in [leaf, *ancestors]] == [n + 3 for n in initial]
    QTest.keyClick(editor, Qt.Key.Key_Escape if cancel else Qt.Key.Key_Return)
    runtime.app.processEvents()
    expected = initial if cancel else [n + 3 for n in initial]
    assert [int(item.field_length) for item in [leaf, *ancestors]] == expected
    if not cancel:
        tree.undo_stack.undo()
        assert [int(item.field_length) for item in [leaf, *ancestors]] == initial
        tree.undo_stack.redo()
        assert [int(item.field_length) for item in [leaf, *ancestors]] == expected
    tree.close()
    tree.deleteLater()
