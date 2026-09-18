def test_auto_sort_all_levels(runtime, config):
    from PyQt6.QtWidgets import QTreeWidgetItem
    from common.gui.tools.json_views.JsonView import JsonView
    from common.gui.tools.json_items.FIeldItem import FieldItem
    assert config.fields.auto_sort is False
    tree = JsonView(config)
    tree.itemChanged.disconnect()
    def add(parent, name):
        item = FieldItem([name])
        QTreeWidgetItem.addChild(parent, item)
        return item
    a = add(tree.root, '48')
    b = add(tree.root, '3')
    c = add(tree.root, '11')
    nested = add(a, '99')
    add(nested, '10')
    add(nested, '02')
    add(a, '01')
    runtime.app.processEvents()
    assert [i.field_number for i in tree.root.get_children()] == ['48', '3', '11']
    tree.set_auto_sort(True)
    assert [i.field_number for i in tree.root.get_children()] == ['3', '11', '48']
    assert [i.field_number for i in a.get_children()] == ['01', '99']
    assert [i.field_number for i in nested.get_children()] == ['02', '10']
    c.setText(0, '2')
    runtime.app.processEvents()
    assert tree.root.child(0) is b
    add(tree.root, '1')
    runtime.app.processEvents()
    assert tree.root.child(0) is b
    tree.set_auto_sort(True)
    assert tree.root.child(0) is b
    tree.sort_top_level_fields(0)
    assert tree.root.child(0).field_number == '1'
    tree.set_auto_sort(False)
    add(tree.root, '0')
    runtime.app.processEvents()
    assert tree.root.child(tree.root.childCount()-1).field_number == '0'
    tree.deleteLater()


def test_new_field_stays_put_until_number_edit_finishes(runtime, config):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QLineEdit
    from common.gui.tools.json_views.JsonView import JsonView
    config.fields.auto_sort = True
    config.validation.validation_enabled = False
    tree = JsonView(config)
    tree.parse_fields({'3': '000000', '11': '123456', '49': '978'})
    tree.show()
    runtime.app.processEvents()
    tree.setCurrentItem(tree.root.child(0))
    tree.plus()
    runtime.app.processEvents()
    new = tree.currentItem()
    assert tree.root.indexOfChild(new) == 1
    editor = tree.findChild(QLineEdit)
    assert editor is not None
    QTest.keyClicks(editor, '41')
    runtime.app.processEvents()
    assert tree.root.indexOfChild(new) == 1
    QTest.keyClick(editor, Qt.Key.Key_Return)
    QTest.qWait(20)
    assert [item.field_number for item in tree.root.get_children()] == ['3', '11', '41', '49']
    assert tree.currentItem() is new
    tree.close()
    tree.deleteLater()


def test_auto_sort_configuration_roundtrip(runtime, config):
    from common.gui.windows.settings_window import SettingsWindow
    saved = []
    window = SettingsWindow(config, commit=lambda candidate: saved.append(candidate))
    assert not window.AutoSortFields.isChecked()
    window.AutoSortFields.setChecked(True)
    window.ok()
    assert saved[0].fields.auto_sort is True
    assert runtime.Config(**saved[0].model_dump()).fields.auto_sort is True
    window.deleteLater()


def test_successful_parsing_triggers_sorting_when_enabled(runtime, config):
    from common.gui.tools.json_views.JsonView import JsonView
    for enabled, expected in ((False, ['48', '3']), (True, ['3', '48'])):
        config.fields.auto_sort = enabled
        tree = JsonView(config)
        tree.parse_fields({'48': {'51': 'SOME ONE'}, '3': '000000'})
        runtime.app.processEvents()
        assert [item.field_number for item in tree.root.get_children()] == expected
        tree.deleteLater()


def test_unchanged_number_and_value_edits_do_not_sort(runtime, config):
    from PyQt6.QtCore import Qt
    from PyQt6.QtTest import QTest
    from PyQt6.QtWidgets import QLineEdit
    from common.gui.tools.json_views.JsonView import JsonView
    config.fields.auto_sort = True
    config.validation.validation_enabled = False
    tree = JsonView(config)
    tree.parse_fields({'49': '978', '3': '000000'})
    tree._auto_sort_timer.stop()
    tree.show()
    for column in (0, 1):
        tree.setCurrentItem(tree.root.child(0), column)
        tree.editItem(tree.root.child(0), column)
        QTest.qWait(10)
        editor = next(e for e in tree.findChildren(QLineEdit) if e.isVisible())
        if column == 1:
            QTest.keyClicks(editor, '840')
        QTest.keyClick(editor, Qt.Key.Key_Return)
        QTest.qWait(20)
        assert [i.field_number for i in tree.root.get_children()] == ['49', '3']
    tree.close()
    tree.deleteLater()
