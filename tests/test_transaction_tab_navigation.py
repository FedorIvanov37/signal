import pytest
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLineEdit, QTreeWidgetItem


@pytest.fixture
def tree(runtime, config):
    from common.gui.tools.json_views.TransactionView import TransactionView
    config.validation.validation_enabled = False
    view = TransactionView(config)
    view.resize(800, 500)
    view.show()
    runtime.app.processEvents()
    yield view
    view.close()


def add(parent, number, value='123'):
    from common.gui.tools.json_items.FIeldItem import FieldItem
    item = FieldItem([number, value, '003'])
    QTreeWidgetItem.addChild(parent, item)
    return item


def editor_at(tree, item, column):
    QApplication.processEvents()
    assert tree.currentItem() is item
    assert tree.currentColumn() == column
    editor = QApplication.focusWidget()
    assert isinstance(editor, QLineEdit)
    assert tree.isAncestorOf(editor)
    assert editor.isVisible()
    return editor


def start(tree, item, column):
    tree.expandAll()
    tree.setCurrentItem(item, column)
    tree.editItem(item, column)
    return editor_at(tree, item, column)


def press_tab(editor, reverse=False):
    QTest.keyClick(editor, Qt.Key.Key_Backtab if reverse else Qt.Key.Key_Tab,
                   Qt.KeyboardModifier.ShiftModifier if reverse else Qt.KeyboardModifier.NoModifier)
    QApplication.processEvents()


@pytest.mark.parametrize('nested', [False, True])
def test_forward_and_reverse_editing_route(tree, nested):
    first = add(tree.root, '20')
    container = add(tree.root, '47', '')
    last = add(tree.root, '4')
    route = [(first, 0), (first, 1), (container, 0)]
    if nested:
        child = add(container, '9')
        inner = add(container, '3', '')
        leaf = add(inner, '7')
        sibling = add(container, '1')
        route += [(child, 0), (child, 1), (inner, 0), (leaf, 0), (leaf, 1), (sibling, 0), (sibling, 1)]
    else:
        route += [(container, 1)]
    route += [(last, 0), (last, 1)]
    editor = start(tree, *route[0])
    for item, column in route[1:]:
        press_tab(editor)
        editor = editor_at(tree, item, column)
    press_tab(editor)
    editor = editor_at(tree, *route[-1])
    for item, column in reversed(route[:-1]):
        press_tab(editor, reverse=True)
        editor = editor_at(tree, item, column)
    press_tab(editor, reverse=True)
    editor_at(tree, *route[0])


def test_collapsed_parent_expands_and_hidden_disabled_rows_are_skipped(tree):
    parent = add(tree.root, '47', '')
    hidden = add(parent, '1')
    hidden.setHidden(True)
    disabled = add(parent, '2')
    disabled.set_disabled(True)
    child = add(parent, '3')
    editor = start(tree, parent, 0)
    parent.setExpanded(False)
    press_tab(editor)
    editor = editor_at(tree, child, 0)
    assert parent.isExpanded()
    press_tab(editor, reverse=True)
    editor_at(tree, parent, 0)


def test_tab_commits_value_and_preserves_undo(tree):
    item = add(tree.root, '4')
    following = add(tree.root, '11')
    editor = start(tree, item, 1)
    editor.selectAll()
    QTest.keyClicks(editor, '456')
    press_tab(editor)
    editor = editor_at(tree, following, 0)
    assert item.field_data == '456'
    QTest.keyClick(editor, Qt.Key.Key_Escape)
    tree.undo_stack.undo()
    assert item.field_data == '123'


def test_tab_opens_secret_value_unmasked_and_masks_it_on_leaving(tree):
    item = add(tree.root, '2', '4111111111111111')
    following = add(tree.root, '4')
    item.hide_secret()
    editor = start(tree, item, 0)
    press_tab(editor)
    editor = editor_at(tree, item, 1)
    assert editor.text() == '4111111111111111'
    press_tab(editor)
    editor_at(tree, following, 0)
    assert item.text(1) != '4111111111111111'
    assert item.field_data == '4111111111111111'


def test_tab_follows_sorted_rows(tree):
    first = add(tree.root, '20')
    second = add(tree.root, '4')
    tree.sort_top_level_fields(0)
    editor = start(tree, second, 1)
    press_tab(editor)
    editor = editor_at(tree, first, 0)
    press_tab(editor, reverse=True)
    editor_at(tree, second, 1)


def test_disabled_container_subtree_is_skipped_in_both_directions(tree):
    first = add(tree.root, '4')
    container = add(tree.root, '47', '')
    child = add(container, '9', '')
    add(child, '1')
    last = add(tree.root, '11')
    container.set_disabled(True)
    editor = start(tree, first, 1)
    press_tab(editor)
    editor = editor_at(tree, last, 0)
    press_tab(editor, reverse=True)
    editor_at(tree, first, 1)


def test_tab_commits_renamed_field_before_opening_its_value(tree):
    item = add(tree.root, '4')
    editor = start(tree, item, 0)
    editor.selectAll()
    QTest.keyClicks(editor, '11')
    press_tab(editor)
    editor_at(tree, item, 1)
    assert item.field_number == '11'


@pytest.mark.parametrize('key,expected', [(Qt.Key.Key_Return, '456'), (Qt.Key.Key_Escape, '123')])
def test_enter_and_escape_keep_their_normal_behavior(tree, key, expected):
    item = add(tree.root, '4')
    editor = start(tree, item, 1)
    editor.selectAll()
    QTest.keyClicks(editor, '456')
    QTest.keyClick(editor, key)
    QApplication.processEvents()
    assert item.field_data == expected
    assert tree.currentItem() is item
    assert not isinstance(QApplication.focusWidget(), QLineEdit)


def test_main_transaction_tabs_use_new_view(runtime, config):
    from common.gui.tools.tab_view.TabView import TabView
    from common.gui.tools.json_views.TransactionView import TransactionView
    from common.gui.tools.json_views.JsonView import JsonView
    from common.gui.tools.json_views.SpecView import SpecView
    tabs = TabView(config)
    tabs.show()
    for name in (None, 'Second'):
        if name:
            tabs.add_tab(name)
        view = tabs.json_view
        assert isinstance(view, TransactionView)
        item = add(view.root, '4')
        editor = start(view, item, 0)
        press_tab(editor)
        editor = editor_at(view, item, 1)
        QTest.keyClick(editor, Qt.Key.Key_Escape)
    assert 'closeEditor' not in JsonView.__dict__
    assert not issubclass(SpecView, TransactionView)
    tabs.close()


@pytest.mark.parametrize('collapsed', [False, True])
def test_constructor_uses_same_nested_editing_route(runtime, config, collapsed):
    from types import SimpleNamespace
    from common.gui.windows.complex_fields_window import ComplexFieldsParser
    from common.gui.tools.json_views.TransactionView import TransactionView

    config.validation.validation_enabled = False
    terminal = SimpleNamespace(parse_main_window_tab=lambda: SimpleNamespace(data_fields={}))
    window = ComplexFieldsParser(config, terminal)
    window.show()
    view = window.JsonView
    assert isinstance(view, TransactionView)
    assert view.isColumnHidden(4)
    container = add(view.root, '47', '')
    first = add(container, '9')
    inner = add(container, '3', '')
    leaf = add(inner, '7')
    disabled = add(container, '8')
    disabled.set_disabled(True)
    last = add(container, '1')
    route = [(container, 0), (first, 0), (first, 1), (inner, 0),
             (leaf, 0), (leaf, 1), (last, 0), (last, 1)]
    editor = start(view, *route[0])
    if collapsed:
        container.setExpanded(False)
        inner.setExpanded(False)
    for item, column in route[1:]:
        press_tab(editor)
        editor = editor_at(view, item, column)
    editor.selectAll()
    QTest.keyClicks(editor, '456')
    for item, column in reversed(route[:-1]):
        press_tab(editor, reverse=True)
        editor = editor_at(view, item, column)
    assert last.field_data == '456'
    assert first.field_data == '123'
    assert disabled.field_data == '123'
    QTest.keyClick(editor, Qt.Key.Key_Escape)
    window.close()
