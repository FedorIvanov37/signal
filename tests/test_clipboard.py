import pytest
from types import SimpleNamespace

@pytest.mark.parametrize('text', ['', 'content', '  '])
def test_copy_actions_preserve_clipboard_when_empty(runtime, text):
    from common.gui.tools.SignalGui import SignalGui
    from common.gui.windows.spec_window import SpecWindow
    from common.gui.windows.complex_fields_window import ComplexFieldsParser
    from common.gui.windows.settings_window import SettingsWindow
    clipboard = runtime.app.clipboard()
    actions = [
        lambda: SignalGui.copy_log(SimpleNamespace(window=SimpleNamespace(get_log_data=lambda: text), set_clipboard_text=SignalGui.set_clipboard_text)),
        lambda: SignalGui.copy_bitmap(SimpleNamespace(window=SimpleNamespace(get_bitmap_data=lambda: text), set_clipboard_text=SignalGui.set_clipboard_text)),
        lambda: SignalGui.copy_current_field(SimpleNamespace(window=SimpleNamespace(get_current_field_data=lambda: text, tab_view=SimpleNamespace(get_current_field_data=lambda: text)), set_clipboard_text=SignalGui.set_clipboard_text)),
        lambda: SpecWindow.copy_log(SimpleNamespace(LogArea=SimpleNamespace(toPlainText=lambda: text), set_clipboard_text=SpecWindow.set_clipboard_text)),
        lambda: SettingsWindow.copy_remote_spec_url(SimpleNamespace(RemoteSpecUrl=SimpleNamespace(text=lambda: text))),
        lambda: ComplexFieldsParser.copy_string(SimpleNamespace(TextData=SimpleNamespace(toPlainText=lambda: text), set_clipboard_text=ComplexFieldsParser.set_clipboard_text)),
    ]
    for action in actions:
        clipboard.setText('previous clipboard')
        action()
        assert clipboard.text() == (text or 'previous clipboard')
