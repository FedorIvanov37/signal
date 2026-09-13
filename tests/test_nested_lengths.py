from types import SimpleNamespace


def test_container_lengths_include_each_encoding_prefix(runtime, config):
    from PyQt6.QtWidgets import QTreeWidgetItem
    from common.gui.tools.json_views.JsonView import JsonView
    from common.gui.tools.json_items.FIeldItem import FieldItem

    tree = JsonView(config)
    tree.itemChanged.disconnect()
    tree.root.set_spec = lambda: None
    def add(parent, number, value, prefix, tag):
        item = FieldItem([number, value], spec=SimpleNamespace(var_length=prefix, tag_length=tag, is_secret=False))
        QTreeWidgetItem.addChild(parent, item)
        return item
    field = add(tree.root, '48', '', 3, 2)
    leaf = add(field, '51', 'SOME ONE', 2, 0)
    leaf.set_length()
    assert int(leaf.field_length) == 8
    assert int(field.field_length) == 12
    assert int(tree.root.field_length) == 15
    # Another nested TLV contributes its own header at every level.
    nested = add(field, '60', '', 2, 3)
    inner = add(nested, '001', 'abc', 1, 0)
    inner.set_length()
    assert int(nested.field_length) == 7
    assert int(field.field_length) == 23
    assert int(tree.root.field_length) == 26
    # Preview length follows the same rules without committing the value.
    tree.set_item_length('abcde', 1, item=inner)
    assert inner.field_data == 'abc'
    assert int(tree.root.field_length) == 28
    # Flat ISO fields contribute no field-number tag, just their prefix.
    flat = add(tree.root, '2', '12345', 2, 0)
    flat.set_length()
    assert int(flat.field_length) == 5
    assert int(tree.root.field_length) == 33
    nested.set_disabled(True)
    assert int(field.field_length) == 12
    assert int(tree.root.field_length) == 22
    tree.close()
    tree.deleteLater()
