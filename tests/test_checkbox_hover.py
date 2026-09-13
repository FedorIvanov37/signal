def test_checkbox_hover_does_not_move_current_row(runtime, config):
    from PyQt6.QtCore import QPoint, QPointF, Qt, QEvent
    from PyQt6.QtGui import QHoverEvent, QMouseEvent
    from PyQt6.QtTest import QTest
    from common.gui.tools.json_views.TransactionView import TransactionView
    tree = TransactionView(config)
    tree.resize(1100, 400)
    tree.parse_fields({'3': '000000', '4': '000000000100', '11': '123456'})
    tree.show()
    tree.expandAll()
    runtime.app.processEvents()
    first = tree.root.child(0)
    target = tree.root.child(1)
    target.set_checkbox(True)
    box = target.get_checkbox()
    box.setFocus()
    runtime.app.processEvents()
    tree.setCurrentItem(first)
    # First entry must not synchronize selection to a previously focused
    # persistent checkbox, even when its row differs from the current row.
    hover = QHoverEvent(QEvent.Type.HoverEnter, QPointF(40, 10), QPointF(40, 10), QPointF(-1, -1))
    runtime.app.sendEvent(tree.viewport(), hover)
    assert tree.currentItem() is first
    runtime.app.sendEvent(tree.viewport(), QEvent(QEvent.Type.Enter))
    assert tree.currentItem() is first
    point = box.mapTo(tree.viewport(), QPoint(40, box.height() // 2))
    movement = QMouseEvent(QEvent.Type.MouseMove, QPointF(point),
                          QPointF(tree.viewport().mapToGlobal(point)),
                          Qt.MouseButton.NoButton, Qt.MouseButton.NoButton,
                          Qt.KeyboardModifier.NoModifier)
    runtime.app.sendEvent(tree.viewport(), movement)
    assert tree.currentItem() is first
    QTest.mouseMove(tree.viewport(), QPoint(30, 30))
    QTest.mouseMove(box, QPoint(40, box.height() // 2))
    QTest.qWait(30)
    assert tree.currentItem() is first
    assert first.isSelected() and not target.isSelected()
    QTest.mouseClick(box, Qt.MouseButton.LeftButton, pos=QPoint(40, box.height() // 2))
    assert not box.isChecked()
    assert tree.currentItem() is target
    tree.close()
    tree.deleteLater()
