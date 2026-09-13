import pytest


@pytest.mark.parametrize('format', ['json', 'legacy', 'ini'])
def test_file_and_text_preserve_literal_values_without_rewriting(runtime, config, tmp_path, format):
    import json
    parser = runtime.Parser(config)
    transaction = runtime.Transaction(trans_id='literal', message_type='0200',
                                      data_fields={'43': 'Тест 100% %(name)s'})
    if format == 'legacy':
        text = json.dumps({'config': {'generate_fields': []}, 'transaction': {
            'id': transaction.trans_id, 'message_type': transaction.message_type,
            'fields': transaction.data_fields}}, ensure_ascii=False)
    elif format == 'json':
        text = transaction.model_dump_json()
    else:
        text = parser.transaction_to_ini_string(transaction)
    path = tmp_path / ('message.ini' if format == 'ini' else 'message.json')
    path.write_text(text, encoding='utf-8-sig')
    original = path.read_bytes()
    from_file = parser.parse_file(path)
    from_text = parser.parse_text('\ufeff' + text)
    assert from_file.data_fields == from_text.data_fields == transaction.data_fields
    assert from_file.generate_fields == from_text.generate_fields == []
    assert path.read_bytes() == original


@pytest.mark.parametrize('format', ['json', 'ini', 'dump'])
def test_transaction_text_formats(runtime, config, format):
    parser = runtime.Parser(config)
    transaction = runtime.Transaction(message_type='0200', data_fields={'3': '000000', '48': {'51': 'SOME ONE'}})
    text = {'json': transaction.model_dump_json,
            'ini': lambda: parser.transaction_to_ini_string(transaction),
            'dump': lambda: parser.create_sv_dump(transaction)}[format]()
    actual = parser.parse_text(text)
    assert actual.message_type == transaction.message_type
    assert actual.data_fields == transaction.data_fields


@pytest.mark.parametrize('extension', ['dump', 'txt'])
@pytest.mark.parametrize('mti', ['0200', '0210'])
def test_dump_file_and_text_share_generation_rules(runtime, config, tmp_path, monkeypatch, extension, mti):
    parser = runtime.Parser(config)
    transaction = runtime.Transaction(message_type=mti, data_fields={
        '3': '000000', '4': '000000000123', '11': '123456',
        '48': {'51': 'SOME ONE'}, '49': '978'})
    text = parser.create_sv_dump(transaction)
    from common.core.tools.FieldsGenerator import FieldsGenerator
    generated = []
    def generate(field, max_amount=100):
        generated.append(field)
        return '000000000456' if field == '4' else '654321'
    monkeypatch.setattr(FieldsGenerator, 'generate_field', staticmethod(generate))
    path = tmp_path / f'message.{extension}'
    path.write_text(text, encoding='utf-8')
    actual = parser.parse_file(path)
    expected = ([field for field in parser.spec.get_fields_to_generate()
                 if field in transaction.data_fields] if mti == '0200' else [])
    assert actual.generate_fields == expected
    assert generated == expected
    assert set(actual.data_fields) == set(transaction.data_fields)
    assert '128' not in actual.data_fields
    from_text = parser.parse_text(text)
    assert actual.data_fields == from_text.data_fields
    assert actual.generate_fields == from_text.generate_fields
    assert generated == expected + expected


def test_tree_accepts_text_drop(runtime, config):
    from PyQt6.QtCore import QMimeData, QPoint, QPointF, Qt
    from PyQt6.QtGui import QDragEnterEvent, QDropEvent
    from common.gui.tools.json_views.JsonView import JsonView
    tree = JsonView(config)
    received = []
    tree.text_dropped.connect(received.append)
    mime = QMimeData()
    mime.setText('{"message_type":"0200","data_fields":{"3":"000000"}}')
    enter = QDragEnterEvent(QPoint(5, 5), Qt.DropAction.CopyAction, mime,
                            Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    tree.dragEnterEvent(enter)
    assert enter.isAccepted()
    drop = QDropEvent(QPointF(5, 5), Qt.DropAction.CopyAction, mime,
                     Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    tree.dropEvent(drop)
    assert drop.isAccepted() and received == [mime.text()]
    tree.deleteLater()


def test_config_text_drop_updates_draft(runtime, config):
    from PyQt6.QtCore import QMimeData, QPointF, Qt
    from PyQt6.QtGui import QDropEvent
    from common.gui.windows.settings_window import SettingsWindow
    window = SettingsWindow(config)
    candidate = config.model_copy(deep=True)
    candidate.host.port = 23456
    mime = QMimeData()
    mime.setText(candidate.model_dump_json())
    event = QDropEvent(QPointF(5, 5), Qt.DropAction.CopyAction, mime,
                      Qt.MouseButton.LeftButton, Qt.KeyboardModifier.NoModifier)
    window.dropEvent(event)
    assert window.SvPort.value() == 23456
    assert config.host.port != 23456
    window.deleteLater()
