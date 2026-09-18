import pytest
from PyQt6.QtWidgets import QTreeWidget
from PyQt6.QtGui import QFontDatabase


@pytest.mark.parametrize('color', ['#012E4F', '#F0F0F0'])
def test_specification_columns_fit_without_changing_font(runtime, config, monkeypatch, tmp_path, color):
    import importlib
    from common.gui.windows.spec_window import SpecWindow
    from common.gui.enums import SpecFieldDef

    # The offscreen platform does not discover Windows fonts automatically.
    font_id = QFontDatabase.addApplicationFont('C:/Windows/Fonts/calibri.ttf')
    if font_id < 0:
        pytest.skip('Calibri is required for the Windows layout measurement')
    module = importlib.import_module('common.gui.windows.main_window')
    monkeypatch.setattr(module, 'APPEARANCE_SETTINGS_PATH', tmp_path / 'appearance.json')
    main = module.MainWindow(config)
    main._apply_dark_theme(color)
    window = SpecWindow(runtime.Connector(config), config)
    window.wireless_handler.flushOnClose = True
    window.show()
    runtime.app.processEvents()
    tree = window.SpecView
    reference = QTreeWidget()
    reference.setHeaderLabels(SpecFieldDef.Columns)
    reference.header().setFont(tree.header().font())
    reference.ensurePolished()
    try:
        controls = (window.SearchLine, window.PlusButton, window.MinusButton,
                    window.NextLevelButton, window.UndoButton, window.RedoButton)
        assert len({control.height() for control in controls}) == 1
        assert tree.header().font().pointSize() == 12
        assert tree.font().pointSize() == 12
        assert tree.header().length() <= tree.viewport().width()
        assert tree.horizontalScrollBar().maximum() == 0
        for column in range(1, tree.columnCount()):
            assert tree.header().sectionSizeHint(column) == reference.header().sectionSizeHint(column)
        assert tree.header().sectionSizeHint(0) > reference.header().sectionSizeHint(0)
        assert tree.sort_fields_button.isVisible()
        assert tree.sort_fields_button.geometry().right() < tree.header().label_inset
    finally:
        window.hide()
        window.deleteLater()
        main.hide()
        main.deleteLater()
        reference.deleteLater()
        QFontDatabase.removeApplicationFont(font_id)
