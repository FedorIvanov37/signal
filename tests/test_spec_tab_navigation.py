from types import SimpleNamespace

import pytest
from loguru import logger
from PyQt6.QtCore import Qt
from PyQt6.QtTest import QTest
from PyQt6.QtWidgets import QApplication, QLineEdit, QStyle, QStyleOptionButton

from common.gui.enums import SpecFieldDef


@pytest.fixture
def tree(runtime):
    from common.gui.tools.json_views.SpecView import SpecView
    view = SpecView(SimpleNamespace(read_only=False))
    view.root.takeChildren()
    view.resize(1000, 500)
    view.show()
    runtime.app.processEvents()
    yield view
    view.close()


def add(parent, number):
    from common.gui.tools.json_items.SpecItem import SpecItem
    item = SpecItem([number, 'Description', '0', '999', '3', '3'])
    parent.addChild(item)
    return item


def focus_at(tree, item, column):
    QApplication.processEvents()
    assert tree.currentItem() is item
    assert tree.currentColumn() == column
    focused = QApplication.focusWidget()
    if column in SpecFieldDef.Checkboxes:
        assert focused is tree
    else:
        assert isinstance(focused, QLineEdit)
        assert tree.isAncestorOf(focused)
        assert focused.isVisible()
    return focused


def start(tree, item, column):
    tree.expandAll()
    tree.setCurrentItem(item, column)
    if column in SpecFieldDef.Checkboxes:
        tree.setFocus()
        tree.setCurrentItem(item, column)
    else:
        tree.editItem(item, column)
    return focus_at(tree, item, column)


def tab(focused, reverse=False):
    QTest.keyClick(focused, Qt.Key.Key_Backtab if reverse else Qt.Key.Key_Tab,
                   Qt.KeyboardModifier.ShiftModifier if reverse else Qt.KeyboardModifier.NoModifier)
    QApplication.processEvents()


def click_checkbox(checkbox):
    option = QStyleOptionButton()
    checkbox.initStyleOption(option)
    rect = checkbox.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, checkbox)
    QTest.mouseClick(checkbox, Qt.MouseButton.LeftButton, pos=rect.center())


def test_all_columns_of_containers_before_children_and_reverse(tree):
    parent = add(tree.root, '47')
    inner = add(parent, '9')
    leaf = add(inner, '3')
    last = add(tree.root, '4')
    route = [(tree.root, 0), (tree.root, 1)]
    route += [(item, column) for item in (parent, inner, leaf, last) for column in range(tree.columnCount())]
    focused = start(tree, *route[0])
    parent.setExpanded(False)
    inner.setExpanded(False)
    for cell in route[1:]:
        tab(focused)
        focused = focus_at(tree, *cell)
    tab(focused)
    focused = focus_at(tree, *route[-1])
    for cell in reversed(route[:-1]):
        tab(focused, reverse=True)
        focused = focus_at(tree, *cell)
    tab(focused, reverse=True)
    focus_at(tree, *route[0])


def test_space_toggles_selected_checkbox_without_moving(tree):
    item = add(tree.root, '4')
    column = SpecFieldDef.ColumnsOrder.ALPHA
    focused = start(tree, item, column)
    assert not item.is_checked(column)
    for expected in (True, False):
        QTest.keyClick(focused, Qt.Key.Key_Space)
        assert item.is_checked(column) is expected
        focused = focus_at(tree, item, column)


@pytest.mark.parametrize('number,column,message', [
    ('2', SpecFieldDef.ColumnsOrder.SECRET, 'The card number must always be masked'),
    ('4', SpecFieldDef.ColumnsOrder.CAN_BE_GENERATED, 'predefined and cannot be changed'),
])
def test_protected_checkbox_is_focusable_but_space_only_warns(tree, number, column, message):
    item = add(tree.root, number)
    focused = start(tree, item, column)
    original = item.checkState(column)
    messages = []
    handler = logger.add(lambda record: messages.append(str(record)), level='WARNING')
    try:
        QTest.keyClick(focused, Qt.Key.Key_Space)
    finally:
        logger.remove(handler)
    assert item.checkState(column) == original
    assert any(message in text for text in messages)
    focus_at(tree, item, column)


@pytest.mark.parametrize('readonly', [True, False])
def test_navigation_is_silent_and_never_opens_editors(tree, readonly):
    parent = add(tree.root, '47')
    child = add(parent, '9')
    leaf = add(child, '3')
    tree.window.read_only = readonly
    tree.set_read_only(readonly)
    tree.expandAll()
    route = [(tree.root, 0), (tree.root, 1)]
    route += [(item, column) for item in (parent, child, leaf) for column in range(tree.columnCount())]
    messages = []
    handler = logger.add(lambda record: messages.append(str(record)), level='WARNING')
    try:
        for item, column in route:
            tree.scrollToItem(item)
            index = tree.indexFromItem(item, column)
            tree.scrollTo(index)
            QApplication.processEvents()
            QTest.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton,
                             pos=tree.visualRect(index).center())
            assert tree.currentItem() is item
            assert tree.currentColumn() == column
            assert QApplication.focusWidget() is tree
        if readonly:
            assert messages == []
        messages.clear()
        tree.setCurrentItem(*route[0])
        parent.setExpanded(False)
        child.setExpanded(False)
        for reverse, cells in ((False, route[1:] + [route[-1]]),
                               (True, list(reversed(route[:-1])) + [route[0]])):
            for item, column in cells:
                tab(tree, reverse=reverse)
                assert tree.currentItem() is item
                assert tree.currentColumn() == column
                assert QApplication.focusWidget() is tree
                assert not any(editor.isVisible() for editor in tree.findChildren(QLineEdit))
    finally:
        logger.remove(handler)
    assert messages == []


def test_readonly_edit_attempts_warn_but_tab_moves_silently(tree):
    item = add(tree.root, '4')
    tree.window.read_only = True
    tree.set_read_only(True)
    messages = []
    handler = logger.add(lambda record: messages.append(str(record)), level='WARNING')
    try:
        for target, column in ((tree.root, 1), (item, 1), (item, SpecFieldDef.ColumnsOrder.ALPHA)):
            tree.setFocus()
            tree.setCurrentItem(target, column)
            state = target.checkState(column)
            if column in SpecFieldDef.Checkboxes:
                QTest.keyClick(tree, Qt.Key.Key_Space)
                assert target.checkState(column) == state
            else:
                tree.editItem(target, column)
            QTest.keyClick(tree, Qt.Key.Key_Tab)
            QApplication.processEvents()
            assert QApplication.focusWidget() is tree
            route = list(tree._navigation_cells())
            assert (tree.currentItem(), tree.currentColumn()) == route[route.index((target, column)) + 1]
    finally:
        logger.remove(handler)
    assert len([text for text in messages if 'Read-only mode. Clear the checkbox at the top of the window' in text]) == 3


def test_readonly_double_click_text_warns_without_editor(tree):
    item = add(tree.root, '4')
    tree.window.read_only = True
    tree.set_read_only(True)
    tree.expandAll()
    index = tree.indexFromItem(item, 1)
    messages = []
    handler = logger.add(lambda record: messages.append(str(record)), level='WARNING')
    try:
        QTest.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton,
                         pos=tree.visualRect(index).center())
        assert messages == []
        QTest.mouseDClick(tree.viewport(), Qt.MouseButton.LeftButton,
                          pos=tree.visualRect(index).center())
        QApplication.processEvents()
    finally:
        logger.remove(handler)
    assert any('Read-only mode' in text for text in messages)
    assert not any(editor.isVisible() for editor in tree.findChildren(QLineEdit))


def test_root_name_commit_and_readonly_during_edit(tree):
    focused = start(tree, tree.root, 1)
    focused.selectAll()
    QTest.keyClicks(focused, 'Renamed specification')
    QTest.keyClick(focused, Qt.Key.Key_Return)
    QApplication.processEvents()
    assert tree.root.text(1) == 'Renamed specification'
    focused = start(tree, tree.root, 1)
    focused.selectAll()
    QTest.keyClicks(focused, 'Must not be committed')
    tree.window.read_only = True
    tree.set_read_only(True)
    tab(focused)
    assert tree.root.text(1) == 'Renamed specification'
    assert QApplication.focusWidget() is tree


def test_hidden_rows_are_skipped_and_current_sort_order_is_used(tree):
    last = add(tree.root, '20')
    hidden = add(tree.root, '10')
    first = add(tree.root, '4')
    hidden.setHidden(True)
    tree.sort_top_level_fields(0)
    focused = start(tree, first, SpecFieldDef.ColumnsOrder.SECRET)
    QTest.keyClick(focused, Qt.Key.Key_Space)
    tab(focused)
    focused = focus_at(tree, last, 0)
    tab(focused, reverse=True)
    focus_at(tree, first, SpecFieldDef.ColumnsOrder.SECRET)


@pytest.mark.parametrize('key,text', [(Qt.Key.Key_Return, None), (Qt.Key.Key_F2, None), (Qt.Key.Key_A, 'a')])
def test_explicit_text_edit_starts_tab_editing(tree, key, text):
    item = add(tree.root, '4')
    tree.expandAll()
    tree.setFocus()
    tree.setCurrentItem(item, 1)
    QTest.keyClick(tree, key)
    editor = focus_at(tree, item, 1)
    if text:
        assert editor.text() == text
    tab(editor)
    focus_at(tree, item, 2)


def test_click_and_escape_end_tab_editing(tree):
    item = add(tree.root, '4')
    editor = start(tree, item, 1)
    QTest.keyClick(editor, Qt.Key.Key_Escape)
    tab(tree)
    assert tree.currentColumn() == 2
    assert QApplication.focusWidget() is tree
    start(tree, item, 1)
    index = tree.indexFromItem(item, 3)
    tree.scrollTo(index)
    QApplication.processEvents()
    QTest.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=tree.visualRect(index).center())
    tab(tree)
    assert tree.currentColumn() == 4
    assert QApplication.focusWidget() is tree


@pytest.mark.parametrize('key', [Qt.Key.Key_Return, Qt.Key.Key_F2, Qt.Key.Key_A])
def test_readonly_keyboard_edit_intent_warns_without_changing_text(tree, key):
    item = add(tree.root, '4')
    tree.window.read_only = True
    tree.set_read_only(True)
    tree.expandAll()
    tree.setFocus()
    tree.setCurrentItem(item, 1)
    original = item.text(1)
    messages = []
    handler = logger.add(lambda record: messages.append(str(record)), level='WARNING')
    try:
        QTest.keyClick(tree, key)
        tab(tree)
    finally:
        logger.remove(handler)
    assert item.text(1) == original
    assert QApplication.focusWidget() is tree
    assert tree.currentColumn() == 2
    assert len(messages) == 1
    assert 'Read-only mode' in messages[0]


@pytest.mark.parametrize('readonly', [True, False])
def test_arrows_move_focus_without_editing(tree, readonly):
    parent = add(tree.root, '47')
    child = add(parent, '9')
    hidden = add(tree.root, '10')
    last = add(tree.root, '20')
    hidden.setHidden(True)
    tree.window.read_only = readonly
    tree.set_read_only(readonly)
    tree.expandAll()
    tree.setFocus()
    tree.setCurrentItem(parent, 1)
    parent.setExpanded(False)
    messages = []
    handler = logger.add(lambda record: messages.append(str(record)), level='WARNING')
    try:
        for key, item, column in [
            (Qt.Key.Key_Right, parent, 2),
            (Qt.Key.Key_Left, parent, 1),
            (Qt.Key.Key_Down, child, 1),
            (Qt.Key.Key_Down, last, 1),
            (Qt.Key.Key_Down, last, 1),
            (Qt.Key.Key_Up, child, 1),
            (Qt.Key.Key_Up, parent, 1),
            (Qt.Key.Key_Up, tree.root, 1),
            (Qt.Key.Key_Right, tree.root, 1),
            (Qt.Key.Key_Left, tree.root, 0),
            (Qt.Key.Key_Left, tree.root, 0),
            (Qt.Key.Key_Up, tree.root, 0),
        ]:
            QTest.keyClick(tree, key)
            assert tree.currentItem() is item
            assert tree.currentColumn() == column
            assert QApplication.focusWidget() is tree
        assert messages == []
    finally:
        logger.remove(handler)


def test_arrow_columns_follow_header_order_and_skip_hidden_columns(tree):
    item = add(tree.root, '4')
    tree.expandAll()
    tree.setColumnHidden(2, True)
    tree.header().moveSection(tree.header().visualIndex(3), tree.header().visualIndex(1))
    tree.setFocus()
    tree.setCurrentItem(item, 0)
    for key, column in [(Qt.Key.Key_Right, 3), (Qt.Key.Key_Right, 1),
                        (Qt.Key.Key_Right, 4), (Qt.Key.Key_Left, 1)]:
        QTest.keyClick(tree, key)
        assert tree.currentColumn() == column
        assert QApplication.focusWidget() is tree


def test_arrows_in_text_editor_move_caret_not_cell(tree):
    item = add(tree.root, '4')
    editor = start(tree, item, 1)
    editor.setCursorPosition(4)
    QTest.keyClick(editor, Qt.Key.Key_Left)
    assert editor.cursorPosition() == 3
    QTest.keyClick(editor, Qt.Key.Key_Right)
    assert editor.cursorPosition() == 4
    assert tree.currentItem() is item
    assert tree.currentColumn() == 1
    assert QApplication.focusWidget() is editor
    assert editor.text() == 'Description'


def test_datatype_validation_waits_for_row_departure(tree):
    item = add(tree.root, '4')
    other = add(tree.root, '5')
    item.setText(2, '1')
    item.setText(5, '0')
    tree.expandAll()
    tree.setFocus()
    tree.setCurrentItem(item, 7)
    item.setCheckState(7, Qt.CheckState.Checked)
    QApplication.processEvents()
    messages = []
    handler = logger.add(lambda record: messages.append(str(record)), level='ERROR')
    try:
        QTest.keyClick(tree, Qt.Key.Key_Space)
        QApplication.processEvents()
        QTest.keyClick(tree, Qt.Key.Key_Right)
        QApplication.processEvents()
        assert messages == []
        QTest.keyClick(tree, Qt.Key.Key_Space)
        QApplication.processEvents()
        tree.setCurrentItem(other, 8)
        QApplication.processEvents()
        assert messages == []
        tree.setCurrentItem(item, 8)
        QTest.keyClick(tree, Qt.Key.Key_Space)
        QApplication.processEvents()
        assert messages == []
        tree.setCurrentItem(other, 8)
        QApplication.processEvents()
        assert len(messages) == 1
        assert 'Missing field data type' in messages[0]
    finally:
        logger.remove(handler)


def test_incomplete_row_only_checks_departed_column(tree):
    from common.gui.tools.json_items.SpecItem import SpecItem
    item = SpecItem([])
    tree.root.addChild(item)
    editor = start(tree, item, 0)
    messages = []
    handler = logger.add(lambda record: messages.append(str(record)), level='WARNING')
    try:
        QTest.keyClicks(editor, '5')
        tab(editor)
        assert messages == []
        editor = focus_at(tree, item, 1)
        QTest.keyClicks(editor, 'New field')
        tab(editor)
        editor = focus_at(tree, item, 2)
        QTest.keyClicks(editor, 'abc')
        tab(editor)
        assert len(messages) == 1
        assert 'only numeric values allowed' in messages[0]
        assert 'Missing field data type' not in messages[0]
    finally:
        logger.remove(handler)


def test_leaving_tree_validates_last_committed_edit(tree):
    item = add(tree.root, '4')
    item.setText(2, '1')
    item.setText(5, '0')
    item.setCheckState(7, Qt.CheckState.Checked)
    editor = start(tree, item, 2)
    QApplication.processEvents()
    messages = []
    handler = logger.add(lambda record: messages.append(str(record)), level='ERROR')
    outside = QLineEdit()
    try:
        editor.selectAll()
        QTest.keyClicks(editor, '2000')
        assert messages == []
        outside.show()
        outside.activateWindow()
        outside.setFocus()
        QApplication.processEvents()
        QApplication.processEvents()
        assert item.text(2) == '2000'
        assert len(messages) == 1
        assert 'Min Length over Max Length' in messages[0]
    finally:
        logger.remove(handler)
        outside.close()


@pytest.mark.parametrize('source,keyboard', [('tree', False), ('tree', True), ('search', False)])
def test_unlock_returns_focus_only_when_arriving_from_table(runtime, config, source, keyboard):
    from common.gui.windows.spec_window import SpecWindow
    window = SpecWindow(runtime.Connector(config), config)
    window.wireless_handler.flushOnClose = True
    window.show()
    QApplication.processEvents()
    view = window.SpecView
    item = view.root.child(1)
    try:
        view.setFocus()
        view.setCurrentItem(item, 3)
        if source == 'search':
            window.SearchLine.setFocus()
        if keyboard:
            window.CheckBoxReadOnly.setFocus()
            QTest.keyClick(window.CheckBoxReadOnly, Qt.Key.Key_Space)
        else:
            click_checkbox(window.CheckBoxReadOnly)
        QApplication.processEvents()
        assert not window.read_only
        assert view.currentItem() is item
        assert view.currentColumn() == 3
        assert QApplication.focusWidget() is (view if source == 'tree' else window.CheckBoxReadOnly)
        assert not any(editor.isVisible() for editor in view.findChildren(QLineEdit))
        if source == 'tree':
            tab(view)
            assert view.currentColumn() == 4
            assert QApplication.focusWidget() is view
    finally:
        window.hide()
        window.deleteLater()


@pytest.mark.parametrize('text', ['Мама мыла раму', 'café', 'hello\u00a0world', 'abc\x00'])
@pytest.mark.parametrize('root', [False, True])
def test_non_ascii_edit_is_reported_by_validation(tree, text, root):
    item = tree.root if root else add(tree.root, '4')
    if root:
        add(tree.root, '4')
    editor = start(tree, item, 1)
    messages = []
    handler = logger.add(lambda record: messages.append(str(record)), level='WARNING')
    try:
        editor.setText(text)
        tab(editor)
        assert item.text(1) == text
        assert any('non-printable characters' in message for message in messages)
    finally:
        logger.remove(handler)


def test_ascii_description_commits_and_shared_validator_rejects_unicode(tree):
    item = add(tree.root, '4')
    editor = start(tree, item, 1)
    editor.setText('Card holder #5: test!')
    tab(editor)
    assert item.text(1) == 'Card holder #5: test!'
    item.setText(1, 'Мама мыла раму')
    with pytest.raises(ValueError, match='non-printable characters'):
        tree.validator.validate_column(item, 1)


@pytest.mark.parametrize('nested,path', [(False, '4'), (True, '47.4')])
def test_row_ascii_error_identifies_field_and_column(tree, nested, path):
    parent = add(tree.root, '47') if nested else tree.root
    item = add(parent, '4')
    other = add(tree.root, '6')
    editor = start(tree, item, 1)
    messages = []
    handler = logger.add(lambda record: messages.append(str(record)), level='ERROR')
    try:
        editor.setText('Мама мыла раму')
        QTest.keyClick(editor, Qt.Key.Key_Return)
        tree.setCurrentItem(other, 1)
        QApplication.processEvents()
        assert any(f'Field {path}' in message and 'Description' in message
                   and 'non-printable characters' in message for message in messages)
    finally:
        logger.remove(handler)


@pytest.mark.parametrize('correct', [False, True])
@pytest.mark.parametrize('column,bad,good', [(1, 'Мама мыла раму', 'Description'), (2, 'abc', '1')])
def test_cell_warning_becomes_row_error_only_if_not_corrected(tree, correct, column, bad, good):
    item = add(tree.root, '4')
    item.setText(2, '1')
    item.setText(5, '0')
    item.setCheckState(7, Qt.CheckState.Checked)
    other = add(tree.root, '6')
    editor = start(tree, item, column)
    QApplication.processEvents()
    records = []
    handler = logger.add(lambda message: records.append(message.record), level='WARNING')
    try:
        editor.setText(bad)
        tab(editor)
        assert [record['level'].name for record in records] == ['WARNING']
        if correct:
            editor = start(tree, item, column)
            editor.setText(good)
            tab(editor)
        tree.setCurrentItem(other, column)
        QApplication.processEvents()
        assert [record['level'].name for record in records] == (
            ['WARNING'] if correct else ['WARNING', 'ERROR'])
        assert all('Field 4' in record['message'] for record in records)
    finally:
        logger.remove(handler)


@pytest.mark.parametrize('number', ['Мама', 'abc', '１２', '0', '1', '129', ''])
def test_invalid_number_uses_row_location_and_collects_independent_errors(tree, number):
    from common.core.data_models.Validation import ValidationResult, ValidationTypes
    item = add(tree.root, number)
    item.setText(1, 'Мама')
    item.setText(2, 'bad')
    item.setText(3, 'wrong')
    item.setText(4, 'invalid')
    item.setText(5, '0')
    result = tree.validator.validate_spec_row(item)
    assert isinstance(result, ValidationResult)
    errors = result.errors[ValidationTypes.FIELD_SPEC_VALIDATION]
    assert len(errors) == 6
    assert all(error.startswith('Row 1') for error in errors)
    assert any('Invalid field number' in error for error in errors)
    assert sum('Missing field data type' in error for error in errors) == 1
    assert not any('Min Length over Max Length' in error for error in errors)


def test_duplicate_and_invalid_ancestor_do_not_become_field_addresses(tree):
    first = add(tree.root, '4')
    second = add(tree.root, '4')
    assert tree.validator.location(first) == 'Row 1'
    assert tree.validator.location(second) == 'Row 2'
    child = add(first, '7')
    assert tree.validator.location(child) == 'Row 1.1'
    errors = tree.validator.validate_spec_row(second).errors
    assert any('Duplicated field number' in error for group in errors.values() for error in group)


def test_row_logs_every_error_once(tree):
    item = add(tree.root, '4')
    item.setText(1, 'Мама')
    item.setText(2, 'bad')
    item.setText(3, 'wrong')
    item.setText(5, '0')
    editor = start(tree, item, 1)
    records = []
    handler = logger.add(lambda message: records.append(message.record), level='ERROR')
    try:
        QTest.keyClick(editor, Qt.Key.Key_Escape)
        tree.setCurrentItem(tree.root, 1)
        QApplication.processEvents()
        assert len(records) == 4
        assert len({record['message'] for record in records}) == 4
        assert all('Field 4' in record['message'] for record in records)
    finally:
        logger.remove(handler)


def test_disabled_toolbar_warns_and_controls_have_equal_height(runtime, config):
    from common.gui.windows.spec_window import SpecWindow
    window = SpecWindow(runtime.Connector(config), config)
    window.wireless_handler.flushOnClose = True
    window.show()
    QApplication.processEvents()
    buttons = (window.PlusButton, window.MinusButton, window.NextLevelButton,
               window.UndoButton, window.RedoButton)
    messages = []
    handler = logger.add(lambda message: messages.append(str(message)), level='WARNING')
    try:
        count = window.SpecView.root.childCount()
        for button in buttons:
            assert not button.isEnabled()
            for _ in range(3):
                QTest.mouseClick(button, Qt.MouseButton.LeftButton)
        assert len(messages) == 5
        assert all('Read-only mode' in message for message in messages)
        assert window.SpecView.root.childCount() == count
        QTest.mouseClick(buttons[0], Qt.MouseButton.LeftButton)
        assert len(messages) == 6
        assert len({control.height() for control in (*buttons, window.SearchLine)}) == 1
        click_checkbox(window.CheckBoxReadOnly)
        assert all(button.isEnabled() for button in buttons)
    finally:
        logger.remove(handler)
        window.hide()
        window.deleteLater()


def test_readonly_cell_warning_repeats_only_after_target_or_mode_changes(tree):
    item = add(tree.root, '4')
    tree.window.read_only = True
    tree.set_read_only(True)
    tree.expandAll()
    tree.setFocus()
    messages = []
    handler = logger.add(lambda message: messages.append(str(message)), level='WARNING')
    try:
        for column, expected in [(1, 1), (2, 2), (1, 3), (7, 4)]:
            tree.setCurrentItem(item, column)
            for _ in range(3):
                QTest.keyClick(tree, Qt.Key.Key_Space if column == 7 else Qt.Key.Key_Return)
            assert len(messages) == expected
        tree.window.read_only = False
        tree.set_read_only(False)
        tree.window.read_only = True
        tree.set_read_only(True)
        QTest.keyClick(tree, Qt.Key.Key_Space)
        assert len(messages) == 5
    finally:
        logger.remove(handler)


def test_readonly_checkbox_mouse_click_warns_only_on_indicator(tree):
    from PyQt6.QtCore import QPoint
    item = add(tree.root, '4')
    tree.window.read_only = True
    tree.set_read_only(True)
    tree.expandAll()
    tree.setFocus()
    messages = []
    handler = logger.add(lambda message: messages.append(str(message)), level='WARNING')
    try:
        for column, count in [(6, 1), (7, 2), (6, 3)]:
            index = tree.indexFromItem(item, column)
            tree.scrollTo(index)
            QApplication.processEvents()
            rect = tree.visualRect(index)
            state = item.checkState(column)
            # The indicator is drawn at the leading edge; the cell center is empty.
            QTest.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=rect.center())
            assert len(messages) == count - 1
            for _ in range(3):
                QTest.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton,
                                 pos=QPoint(rect.left() + 8, rect.center().y()))
                QTest.keyClick(tree, Qt.Key.Key_Space)
            assert len(messages) == count
            assert item.checkState(column) == state
        assert all('Read-only mode' in message for message in messages)
    finally:
        logger.remove(handler)


@pytest.mark.parametrize('state', [Qt.CheckState.Unchecked, Qt.CheckState.Checked, Qt.CheckState.PartiallyChecked])
def test_checkbox_focus_frame_includes_indicator(tree, state):
    from PyQt6.QtCore import QRect
    from PyQt6.QtGui import QPainter, QPixmap
    from PyQt6.QtWidgets import QStyleOptionViewItem
    item = add(tree.root, '4')
    item.setCheckState(6, state)
    tree.expandAll()
    index = tree.indexFromItem(item, 6)
    option = QStyleOptionViewItem()
    tree.initViewItemOption(option)
    option.rect = QRect(0, 0, 100, 24)
    option.state |= QStyle.StateFlag.State_HasFocus
    option.features |= QStyleOptionViewItem.ViewItemFeature.HasCheckIndicator
    option.checkState = state
    indicator = tree.style().subElementRect(QStyle.SubElement.SE_ItemViewItemCheckIndicator, option, tree)
    frames = []
    delegate = tree.itemDelegate()
    original = delegate.drawFocus
    delegate.drawFocus = lambda painter, opt, rect: frames.append(QRect(rect))
    pixmap = QPixmap(100, 24)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    try:
        delegate.paint(painter, option, index)
        assert frames[-1].contains(indicator)
        assert frames[-1].width() < option.rect.width() / 2
        assert option.rect.contains(frames[-1])
    finally:
        painter.end()
        delegate.drawFocus = original


@pytest.mark.parametrize('column,value', [(2, '1000'), (3, '1')])
def test_length_relation_warns_on_cell_exit_then_errors_on_row_exit(tree, column, value):
    item = add(tree.root, '4')
    item.setText(2, '2')
    item.setText(5, '0')
    item.setCheckState(7, Qt.CheckState.Checked)
    other = add(tree.root, '6')
    editor = start(tree, item, column)
    records = []
    handler = logger.add(lambda message: records.append(message.record), level='WARNING')
    try:
        editor.setText(value)
        tab(editor)
        assert [record['level'].name for record in records] == ['WARNING']
        assert 'Min Length over Max Length' in records[0]['message']
        tree.setCurrentItem(other, column)
        QApplication.processEvents()
        assert [record['level'].name for record in records] == ['WARNING', 'ERROR']
        assert records[0]['message'] == records[1]['message']
    finally:
        logger.remove(handler)


@pytest.mark.parametrize('checkbox', [False, True])
def test_corrected_row_loses_error_color_without_leaving_it(tree, checkbox):
    from common.gui.enums.Colors import Colors
    from PyQt6.QtGui import QColor
    item = add(tree.root, '4')
    item.setText(2, '1' if checkbox else '1000')
    item.setText(5, '0')
    item.setCheckState(7, Qt.CheckState.Unchecked if checkbox else Qt.CheckState.Checked)
    tree._validate_row(item)
    assert item.foreground(1).color() == QColor(Colors.RED)
    messages = []
    handler = logger.add(lambda message: messages.append(str(message)), level='WARNING')
    try:
        if checkbox:
            focused = start(tree, item, 7)
            QTest.keyClick(focused, Qt.Key.Key_Space)
        else:
            editor = start(tree, item, 2)
            editor.setText('1')
            QTest.keyClick(editor, Qt.Key.Key_Return)
        QApplication.processEvents()
        assert tree.currentItem() is item
        assert item.foreground(1).color() != QColor(Colors.RED)
        tree.generate_spec().validate_for_use()
        assert messages == []
    finally:
        logger.remove(handler)


def test_window_readonly_checkbox_controls_keyboard_editing(runtime, config):
    from common.gui.windows.spec_window import SpecWindow
    window = SpecWindow(runtime.Connector(config), config)
    window.wireless_handler.flushOnClose = True
    window.show()
    QApplication.processEvents()
    view = window.SpecView
    assert window.CheckBoxReadOnly.isChecked()
    assert window.read_only
    try:
        view.setCurrentItem(view.root, 1)
        view.setFocus()
        view.setCurrentItem(view.root, 1)
        view.editItem(view.root, 1)
        assert not isinstance(QApplication.focusWidget(), QLineEdit)
        click_checkbox(window.CheckBoxReadOnly)
        assert not window.read_only
        assert QApplication.focusWidget() is view
        assert view.currentItem() is view.root
        assert view.currentColumn() == 1
        focused = start(view, view.root, 1)
        tab(focused)
        first = view.root.child(0)
        while first.isHidden():
            first = view.root.child(view.root.indexOfChild(first) + 1)
        focused = focus_at(view, first, 0)
        QTest.keyClick(focused, Qt.Key.Key_Escape)
        click_checkbox(window.CheckBoxReadOnly)
        assert window.read_only
        column = SpecFieldDef.ColumnsOrder.ALPHA
        original = first.checkState(column)
        view.setFocus()
        view.setCurrentItem(first, column)
        QTest.keyClick(view, Qt.Key.Key_Space)
        assert first.checkState(column) == original
    finally:
        window.hide()
        window.deleteLater()
