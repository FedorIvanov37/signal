import pytest
from PyQt6.QtWidgets import QTreeWidgetItem

@pytest.mark.parametrize('number,old,new', [('2','4111111111111111','5555555555554444'), ('14','2912','3011')])
def test_secret_history(runtime, config, number, old, new):
    from common.gui.tools.json_views.JsonView import JsonView
    from common.gui.tools.json_items.FIeldItem import FieldItem
    from common.gui.undo_commands.EditItemTextCommand import EditItemTextCommand
    from common.gui.enums.MainFieldSpec import ColumnsOrder
    from common.core.toolkit.toolkit import mask_pan, mask_secret
    config.fields.hide_secrets = True
    config.validation.validation_enabled = False
    tree = JsonView(config)
    item = FieldItem([number, old])
    QTreeWidgetItem.addChild(tree.root, item)
    tree.setCurrentItem(item)
    item.hide_secret()
    mask = mask_pan if number == '2' else mask_secret
    tree.undo_stack.push(EditItemTextCommand(tree, item, ColumnsOrder.VALUE, old, new))
    for action, expected in [(lambda: None,new),(tree.undo,old),(tree.redo,new),(tree.undo,old),(tree.redo,new)]:
        action()
        assert item.field_data == expected
        assert item.text(ColumnsOrder.VALUE) == mask(expected)
        assert tree.undo_stack.count() == 1
    tree.close()

@pytest.mark.parametrize('number,old,new', [('2','4111111111111111','378282246310005'), ('14','2912','301101')])
def test_history_length_uses_edited_item_not_selection(runtime, config, number, old, new):
    from common.gui.tools.json_views.JsonView import JsonView
    from common.gui.tools.json_items.FIeldItem import FieldItem
    from common.gui.undo_commands.EditItemTextCommand import EditItemTextCommand
    from common.gui.enums.MainFieldSpec import ColumnsOrder
    config.validation.validation_enabled = False
    tree = JsonView(config)
    item = FieldItem([number, old])
    other = FieldItem(['3', '000000', '006'])
    for child in (item, other):
        QTreeWidgetItem.addChild(tree.root, child)
    tree.setCurrentItem(item)
    item.hide_secret()
    tree.undo_stack.push(EditItemTextCommand(tree, item, ColumnsOrder.VALUE, old, new, tree.delegate.text_edited))
    tree.setCurrentItem(other)
    for action, expected in [(tree.undo, old), (tree.redo, new), (tree.undo, old)]:
        action()
        assert tree.currentItem() is other
        assert other.field_data == '000000'
        assert other.field_length == '006'
        assert item.field_data == expected
        assert int(item.field_length) == len(expected)
    tree.close()

@pytest.mark.parametrize('redo', [False, True])
@pytest.mark.parametrize('number,checked,skip', [('7', True, True), ('7', False, False), ('48', True, False)])
def test_history_skips_only_generate(runtime, config, redo, number, checked, skip):
    from PyQt6.QtGui import QUndoCommand
    from common.gui.tools.json_views.JsonView import JsonView
    from common.gui.tools.json_items.FIeldItem import FieldItem
    tree = JsonView(config)
    item = FieldItem([number, 'value'])
    QTreeWidgetItem.addChild(tree.root, item)
    item.set_checkbox(False)
    calls = []
    class Command(QUndoCommand):
        def __init__(self, target, label):
            super().__init__()
            self.item = target
            self.label = label
        def undo(self): calls.append(('undo', self.label))
        def redo(self): calls.append(('redo', self.label))
    normal = FieldItem(['3', '000000'])
    QTreeWidgetItem.addChild(tree.root, normal)
    for target, label in ([(item, 'target'), (normal, 'normal')] if redo else [(normal, 'normal'), (item, 'target')]):
        tree.undo_stack.push(Command(target, label))
    if redo:
        tree.undo_stack.undo()
        tree.undo_stack.undo()
    item.get_checkbox().setChecked(checked)
    calls.clear()
    (tree.redo if redo else tree.undo)()
    assert calls == [('redo' if redo else 'undo', 'normal' if skip else 'target')]
    tree.close()
