from PyQt6.QtCore import QRect
from PyQt6.QtGui import QImage, QPainter
from PyQt6.QtWidgets import QStyle, QStyleOptionViewItem, QTreeWidgetItem


def test_json_delegate_focus_does_not_change_rendering(runtime, config):
    from common.gui.tools.json_views.JsonView import JsonView
    tree = JsonView(config)
    item = QTreeWidgetItem(['4', '000000004256'])
    QTreeWidgetItem.addChild(tree.root, item)
    index = tree.indexFromItem(item, 1)
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 250, 25)
    option.palette = tree.palette()
    option.font = tree.font()
    option.state = QStyle.StateFlag.State_Enabled | QStyle.StateFlag.State_Active | QStyle.StateFlag.State_Selected

    def render(focused):
        current = QStyleOptionViewItem(option)
        if focused:
            current.state |= QStyle.StateFlag.State_HasFocus
        image = QImage(250, 25, QImage.Format.Format_ARGB32)
        image.fill(0)
        painter = QPainter(image)
        tree.delegate.paint(painter, current, index)
        painter.end()
        return image

    assert render(True) == render(False)
    assert not tree.allColumnsShowFocus()
    assert tree.styleSheet() == ''
    tree.close()


def test_checkbox_selection_color_and_click(runtime, config):
    from PyQt6.QtCore import Qt, QPoint
    from PyQt6.QtGui import QPalette
    from PyQt6.QtTest import QTest
    from common.gui.tools.json_views.JsonView import JsonView
    from common.gui.tools.json_items.FIeldItem import FieldItem
    tree = JsonView(config)
    item = FieldItem(['4', '000000000100'])
    QTreeWidgetItem.addChild(tree.root, item)
    item.set_checkbox(True)
    checkbox = item.get_checkbox()
    original = checkbox.palette().color(QPalette.ColorRole.ButtonText)
    tree.expandAll()
    tree.resize(1000, 250)
    tree.show()
    runtime.app.processEvents()
    tree.setCurrentItem(item)
    assert checkbox.palette().color(QPalette.ColorRole.ButtonText).name() == '#ffffff'
    from PyQt6.QtWidgets import QStyleOptionButton

    def rendered_label():
        option = QStyleOptionButton()
        option.initFrom(checkbox)
        option.rect = QRect(0, 0, 160, 30)
        option.text = checkbox.text()
        image = QImage(160, 30, QImage.Format.Format_ARGB32)
        image.fill(0xff0078d7)
        painter = QPainter(image)
        painter.setFont(checkbox.font())
        checkbox.style().drawControl(QStyle.ControlElement.CE_CheckBoxLabel, option, painter, checkbox)
        painter.end()
        return image

    selected_label = rendered_label()
    assert any(selected_label.pixelColor(x, y).name() == '#ffffff'
               for x in range(160) for y in range(30))
    QTest.mouseClick(checkbox, Qt.MouseButton.LeftButton, pos=QPoint(6, checkbox.height() // 2))
    assert not checkbox.isChecked()
    QTest.mouseClick(checkbox, Qt.MouseButton.LeftButton, pos=QPoint(6, checkbox.height() // 2))
    assert checkbox.isChecked()
    tree.clearSelection()
    assert checkbox.palette().color(QPalette.ColorRole.ButtonText) == original
    assert rendered_label() != selected_label
    assert checkbox.font().family() == 'Calibri'
    assert checkbox.font().pointSize() == 12
    tree.close()

def test_checkbox_indicator_geometry_matches(runtime, config):
    from PyQt6.QtWidgets import QCheckBox, QStyle, QStyleOptionButton
    from common.gui.windows.main_window import MainWindow
    window = MainWindow(config)
    checkbox = QCheckBox('Generate', window)
    checkbox.resize(140, 24)
    results = []
    for checked in (False, True, False):
        checkbox.setChecked(checked)
        checkbox.ensurePolished()
        option = QStyleOptionButton()
        checkbox.initStyleOption(option)
        results.append((checkbox.style().subElementRect(QStyle.SubElement.SE_CheckBoxIndicator, option, checkbox),
                        checkbox.style().subElementRect(QStyle.SubElement.SE_CheckBoxContents, option, checkbox)))
    assert results[0] == results[1] == results[2]
    window.deleteLater()

def test_hotkeys_table_tracks_window_theme(runtime, config):
    from PyQt6.QtGui import QColor, QPalette
    from common.gui.windows.main_window import MainWindow
    from common.gui.windows.hotkeys_hint_window import HotKeysHintWindow
    main = MainWindow(config)
    hotkeys = HotKeysHintWindow()
    hotkeys.show()
    for color in [action.data() for action in main.window_colors.actions() if action.data() not in ('#F0F0F0', '#000000')]:
        main._apply_dark_theme(color)
        runtime.app.processEvents()
        palette = hotkeys.HintTable.palette()
        assert palette.color(QPalette.ColorRole.Base) == QColor(color)
        assert palette.color(QPalette.ColorRole.AlternateBase).name() == QColor(color).lighter(115).name()
    hotkeys.deleteLater()
    main.deleteLater()



def test_selection_is_preserved_by_window_and_console_themes(runtime, config):
    from common.gui.windows.main_window import MainWindow
    main = MainWindow(config)
    colors = [a.data() for a in main.window_colors.actions() if a.data() not in ('#F0F0F0', '#000000')]
    selected = []
    for color in colors:
        main._apply_dark_theme(color)
        selected.append(runtime.app.property('signalSelectionColor'))
        for console in ('#012E4F', '#F0F0F0'):
            main._set_console_color(console)
            assert runtime.app.property('signalSelectionColor') == selected[-1]
    assert len(set(selected)) == 1
    main.deleteLater()

def test_second_tab_does_not_shift_tree(runtime, config):
    from PyQt6.QtCore import QPoint
    from common.gui.windows.main_window import MainWindow
    window = MainWindow(config)
    window.show()
    runtime.app.processEvents()
    tabs = window._tab_view
    before = tabs.json_view.mapTo(window, QPoint(0, 0)).y()
    tabs.add_tab()
    runtime.app.processEvents()
    after = tabs.json_view.mapTo(window, QPoint(0, 0)).y()
    assert after == before
    window.deleteLater()


def test_control_fonts_match_across_windows(runtime, config):
    from PyQt6.QtWidgets import QPushButton, QToolButton, QTabBar, QCheckBox
    from common.gui.windows.main_window import MainWindow
    from common.gui.windows.settings_window import SettingsWindow
    main = MainWindow(config)
    settings = SettingsWindow(config)
    for color in ('#012E4F', '#F0F0F0'):
        main._apply_dark_theme(color)
        for window in (main, settings):
            for widget in window.findChildren((QPushButton, QToolButton, QTabBar, QCheckBox)):
                widget.ensurePolished()
                if widget.property('signalHistoryArrow'):
                    continue
                is_button = isinstance(widget, (QPushButton, QToolButton))
                assert widget.font().family() == ('Arial' if is_button else 'Calibri')
                assert widget.font().pointSize() == (11 if is_button else 12)
                assert not widget.font().bold()
    settings.deleteLater()
    main.deleteLater()

def test_mti_editor_selection_tracks_theme(runtime, config):
    from PyQt6.QtWidgets import QLineEdit
    from PyQt6.QtGui import QPalette
    from common.gui.windows.main_window import MainWindow
    from common.gui.windows.mti_spec_window import MtiSpecWindow
    main = MainWindow(config)
    dialog = MtiSpecWindow()
    dialog.show()
    dialog.MtiTable.editItem(dialog.MtiTable.item(0, 0))
    runtime.app.processEvents()
    editor = dialog.MtiTable.findChild(QLineEdit)
    assert editor is not None
    for action in main.window_colors.actions():
        main._apply_dark_theme(action.data())
        runtime.app.processEvents()
        assert editor.palette().color(QPalette.ColorRole.Highlight) == dialog.MtiTable.palette().color(QPalette.ColorRole.Highlight)
    dialog.deleteLater()
    main.deleteLater()

def test_dropdown_fonts_match_controls(runtime, config):
    from PyQt6.QtWidgets import QMenu, QComboBox
    from common.gui.windows.main_window import MainWindow
    main = MainWindow(config)
    for color in ('#012E4F', '#F0F0F0'):
        main._apply_dark_theme(color)
        widgets = main.findChildren((QMenu, QComboBox))
        assert widgets
        for widget in widgets:
            widget.ensurePolished()
            assert widget.font().family() == 'Calibri'
            assert widget.font().pointSize() == 12
            if isinstance(widget, QComboBox):
                widget.view().ensurePolished()
                assert widget.view().font().family() == 'Calibri'
                assert widget.view().font().pointSize() == 12
    main.deleteLater()


def test_field_header_sorts_recursively(runtime, config):
    from common.gui.tools.json_views.JsonView import JsonView
    from common.gui.tools.json_items.FIeldItem import FieldItem
    from common.gui.enums import MainFieldSpec as FieldsSpec
    from PyQt6.QtWidgets import QTreeWidgetItem

    tree = JsonView(config)
    fields = [FieldItem([number, value]) for number, value in (("14", "a"), ("2", "b"), ("7", "c"))]
    for field in fields:
        QTreeWidgetItem.addChild(tree.root, field)
        field.set_checkbox(True)
    child = FieldItem(["01", "nested"])
    QTreeWidgetItem.addChild(fields[0], child)
    nested = [FieldItem([number, 'nested']) for number in ('12', '02')]
    for item in nested:
        QTreeWidgetItem.addChild(fields[0], item)
    for number in ('10', '3', '01'):
        QTreeWidgetItem.addChild(nested[0], FieldItem([number, 'deep']))
    nested[0].setExpanded(True)
    tree.root.setExpanded(True)
    fields[0].setExpanded(True)
    tree.setCurrentItem(child)
    checkbox = fields[2].get_checkbox()
    collapsed = []
    tree.itemCollapsed.connect(collapsed.append)

    tree.sort_fields_button.click()

    assert [item.field_number for item in tree.root.get_children()] == ["2", "7", "14"]
    assert fields[0].child(0) is child
    assert [item.field_number for item in fields[0].get_children()] == ['01', '02', '12']
    assert [item.field_number for item in nested[0].get_children()] == ['01', '3', '10']
    assert nested[0].isExpanded()
    assert fields[2].get_checkbox() is not None
    runtime.app.processEvents()
    assert fields[0].isExpanded()
    assert tree.currentItem() is child
    assert fields[2].get_checkbox() is checkbox
    assert not collapsed
    tree.close()


def test_spec_header_sorts_recursively_including_hidden_fields(runtime, monkeypatch):
    from types import SimpleNamespace
    from PyQt6.QtCore import Qt
    from common.gui.tools.json_views.SpecView import SpecView
    from common.gui.tools.json_items.SpecItem import SpecItem
    from common.gui.enums import SpecFieldDef

    monkeypatch.setattr(SpecView, 'parse_spec', lambda self: None)
    tree = SpecView(SimpleNamespace(read_only=True))
    fields = [SpecItem([number]) for number in ('14', '2', '7')]
    for item in fields:
        tree.root.addChild(item)
    nested = [SpecItem([number]) for number in ('12', '02', '01')]
    for item in nested:
        fields[0].addChild(item)
    for number in ('10', '3', '01'):
        nested[0].addChild(SpecItem([number]))
    fields[2].setHidden(True)
    fields[0].setExpanded(True)
    nested[0].setExpanded(True)
    tree.setCurrentItem(nested[1])
    fields[0].set_checkbox(SpecFieldDef.ColumnsOrder.SECRET, True)
    items = fields + nested + list(nested[0].get_children())
    states = [[item.checkState(col) for col in SpecFieldDef.Checkboxes] for item in items]
    collapsed = []
    changed = []
    tree.itemCollapsed.connect(collapsed.append)
    tree.itemChanged.connect(lambda *args: changed.append(args))

    for _ in range(2):
        tree.sort_fields_button.click()
        runtime.app.processEvents()
        assert [item.field_number for item in tree.root.get_children()] == ['2', '7', '14']
        assert [item.field_number for item in fields[0].get_children()] == ['01', '02', '12']
        assert [item.field_number for item in nested[0].get_children()] == ['01', '3', '10']
        assert fields[2].isHidden()
        assert fields[0].isExpanded() and nested[0].isExpanded()
        assert tree.currentItem() is nested[1]
        assert states == [[item.checkState(col) for col in SpecFieldDef.Checkboxes] for item in items]
    fields[2].setHidden(False)
    assert tree.root.child(1) is fields[2]
    assert not collapsed
    assert not changed
    tree.close()


def test_constructor_conversion_buttons_accept_clicked_signal(runtime, config, monkeypatch):
    from types import SimpleNamespace
    from common.gui.windows.complex_fields_window import ComplexFieldsParser
    from common.core.tools.Parser import Parser
    import sys

    errors = []
    monkeypatch.setattr(sys, 'excepthook', lambda *error: errors.append(error))
    monkeypatch.setattr(ComplexFieldsParser, 'set_field_data', lambda self: None)
    dialog = ComplexFieldsParser(config, SimpleNamespace())
    monkeypatch.setattr(dialog, 'get_field_number', lambda: '47')
    parsed = []
    monkeypatch.setattr(Parser, 'split_complex_field', lambda field, data: parsed.append((field, data)) or {'01': 'test'})
    monkeypatch.setattr(dialog.parser, 'join_complex_item', lambda item: 'converted')
    dialog.TextData.setPlainText('input')
    dialog.UpButton.click()
    runtime.app.processEvents()
    assert not errors, [(str(error[1])) for error in errors]
    assert parsed == [('47', 'input')]
    dialog.DownButton.click()
    runtime.app.processEvents()
    assert not errors, [(str(error[1])) for error in errors]
    assert dialog.TextData.toPlainText() == 'converted'
    dialog.close()
