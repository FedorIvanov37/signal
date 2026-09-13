from unittest.mock import Mock

import pytest
from PyQt6.QtWidgets import QTreeWidgetItem


@pytest.fixture(params=['transaction', 'specification'])
def history_tree(runtime, config, request):
    from types import SimpleNamespace
    from common.gui.tools.json_views.JsonView import JsonView
    from common.gui.tools.json_views.SpecView import SpecView
    from common.gui.tools.json_items.FIeldItem import FieldItem
    from common.gui.tools.json_items.SpecItem import SpecItem

    config.validation.validation_enabled = False
    if request.param == 'transaction':
        tree, item_type = JsonView(config), FieldItem
    else:
        tree, item_type = SpecView(SimpleNamespace(read_only=False)), SpecItem
    tree.root.takeChildren()
    # Isolate the shared history commands from editor validation callbacks.
    tree.itemChanged.disconnect()
    yield tree, item_type
    tree.close()


def children(parent):
    return [parent.child(index) for index in range(parent.childCount())]


@pytest.mark.parametrize('nested', [False, True])
@pytest.mark.parametrize('sort_rows', [False, True])
def test_insert_history_removes_its_own_row(history_tree, nested, sort_rows):
    from common.gui.undo_commands.InsertItemCommand import InsertItemCommand

    tree, item_type = history_tree
    parent = tree.root
    if nested:
        parent = item_type(['48'])
        QTreeWidgetItem.addChild(tree.root, parent)
    existing, inserted = item_type(['20']), item_type(['10'])
    QTreeWidgetItem.addChild(parent, existing)
    command = InsertItemCommand(tree, inserted, parent, 1)
    tree.undo_stack.push(command)
    if sort_rows:
        tree.sort_top_level_fields(0)
    expected = [inserted, existing] if sort_rows else [existing, inserted]
    assert children(parent) == expected
    for _ in range(3):
        tree.undo_stack.undo()
        assert children(parent) == [existing]
        assert command.item is inserted
        tree.undo_stack.redo()
        assert children(parent) == expected


@pytest.mark.parametrize('nested', [False, True])
@pytest.mark.parametrize('sort_rows', [False, True])
def test_remove_redo_removes_its_own_row(history_tree, nested, sort_rows):
    from common.gui.undo_commands.RemoveItemCommand import RemoveItemCommand
    from common.gui.enums.UndoSteps import UndoSteps

    tree, item_type = history_tree
    parent = tree.root
    if nested:
        parent = item_type(['48'])
        QTreeWidgetItem.addChild(tree.root, parent)
    removed, existing = item_type(['20']), item_type(['10'])
    parent.addChildren([removed, existing])
    callback = Mock()
    tree.undo_stack.push(RemoveItemCommand(tree, removed, callback))
    assert children(parent) == [existing]
    tree.undo_stack.undo()
    if sort_rows:
        tree.sort_top_level_fields(0)
    expected = [existing, removed] if sort_rows else [removed, existing]
    for _ in range(3):
        tree.undo_stack.redo()
        assert children(parent) == [existing]
        callback.assert_called_with(parent, removed, UndoSteps.REDO)
        tree.undo_stack.undo()
        assert children(parent) == expected
        callback.assert_called_with(parent, removed, UndoSteps.UNDO)


def test_subitem_history_survives_sorting(history_tree):
    from common.gui.undo_commands.InsertSubItemCommand import InsertSubItemCommand
    from common.gui.enums.UndoSteps import UndoSteps

    tree, item_type = history_tree
    parent = item_type(['48'])
    QTreeWidgetItem.addChild(tree.root, parent)
    existing, inserted = item_type(['10']), item_type(['20'])
    QTreeWidgetItem.addChild(parent, existing)
    callback = Mock()
    command = InsertSubItemCommand(tree, parent, inserted, callback)
    tree.undo_stack.push(command)
    tree.sort_top_level_fields(0)
    assert children(parent) == [existing, inserted]
    for _ in range(3):
        tree.undo_stack.undo()
        assert children(parent) == [existing]
        assert command.sub_item is inserted
        callback.assert_called_with(parent, inserted, UndoSteps.UNDO)
        tree.undo_stack.redo()
        assert children(parent) == [existing, inserted]
        callback.assert_called_with(parent, inserted, UndoSteps.REDO)


def test_clear_restores_rows_and_previous_history(history_tree):
    from PyQt6.QtWidgets import QComboBox
    from common.gui.undo_commands.InsertItemCommand import InsertItemCommand
    tree, item_type = history_tree
    first, second = item_type(['20']), item_type(['10'])
    child = item_type(['1'])
    QTreeWidgetItem.addChild(first, child)
    QTreeWidgetItem.addChild(tree.root, first)
    tree.undo_stack.push(InsertItemCommand(tree, second, tree.root, 1))
    first.setExpanded(True)
    child.setHidden(True)
    tree.setCurrentItem(first)
    mti = QComboBox()
    mti.addItems(['0100', '0110'])
    mti.setCurrentIndex(1)
    tree.clear_with_history(mti)
    assert not children(tree.root) and mti.currentIndex() == -1
    count = tree.undo_stack.count()
    tree.clear_with_history(mti)
    assert tree.undo_stack.count() == count
    for _ in range(3):
        tree.undo()
        assert children(tree.root) == [first, second]
        assert first.child(0) is child and first.isExpanded() and child.isHidden()
        assert mti.currentIndex() == 1
        tree.redo()
        assert not children(tree.root) and mti.currentIndex() == -1
    tree.undo()
    tree.undo()
    assert children(tree.root) == [first]
    mti.close()


@pytest.mark.parametrize('checked', [False, True])
def test_clear_preserves_generate_checkbox(runtime, config, checked):
    from common.gui.tools.json_views.JsonView import JsonView
    from common.gui.tools.json_items.FIeldItem import FieldItem
    tree = JsonView(config)
    tree.itemChanged.disconnect()
    item = FieldItem(['11', '123456'])
    QTreeWidgetItem.addChild(tree.root, item)
    item.set_checkbox(checked)
    try:
        for _ in range(2):
            tree.clear_with_history()
            runtime.app.processEvents()
            tree.undo()
            assert item.get_checkbox().isChecked() == checked
            assert item.field_data == '123456'
            tree.redo()
            tree.undo()
            assert item.get_checkbox().isChecked() == checked
    finally:
        tree.close()



def test_manual_mti_uses_tree_history_but_programmatic_change_does_not(runtime, config):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from common.gui.tools.json_views.JsonView import JsonView
    from common.gui.tools.tab_view.Widgets import TabWidget, ComboBox
    tree = JsonView(config)
    tab = TabWidget(tree)
    combo = tab.findChild(ComboBox)
    try:
        combo.setCurrentIndex(0)
        assert tree.undo_stack.count() == 0
        QTest.keyClick(combo, Qt.Key.Key_Down)
        assert combo.currentIndex() == 1
        assert tree.undo_stack.count() == 1
        tree.undo()
        assert combo.currentIndex() == 0
        tree.redo()
        assert combo.currentIndex() == 1
        combo.setCurrentIndex(2)
        assert tree.undo_stack.count() == 1
        QTest.keyClick(combo, Qt.Key.Key_Down)
        tree.undo()
        assert combo.currentIndex() == 2
    finally:
        tab.close()
