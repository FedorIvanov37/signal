import asyncio
import re
from inspect import iscoroutinefunction
from types import SimpleNamespace

import pytest
from loguru import logger

from common.core.tools.DebugTrace import trace_operation


@pytest.fixture
def debug_messages():
    messages = []
    sink = logger.add(lambda message: messages.append(message.record['message']), level='DEBUG')
    yield messages
    logger.remove(sink)


def test_trace_preserves_results_and_hides_payload(debug_messages):
    secret = '4111111111111111'
    @trace_operation
    def operation(transaction):
        return transaction.payload
    transaction = SimpleNamespace(trans_id='test-id', payload=secret)
    assert operation(transaction) == secret
    assert len(debug_messages) == 2
    assert 'event=entered' in debug_messages[0]
    assert 'event=returned' in debug_messages[1]
    assert 'trans_id=test-id' in debug_messages[1]
    assert secret not in '\n'.join(debug_messages)


def test_trace_preserves_exception_and_resets_parent(debug_messages):
    error = ValueError('private payload')
    @trace_operation
    def failing():
        raise error
    with pytest.raises(ValueError) as caught:
        failing()
    assert caught.value is error
    assert 'event=raised' in debug_messages[-1]
    assert 'error_type=ValueError' in debug_messages[-1]
    assert 'private payload' not in '\n'.join(debug_messages)
    @trace_operation
    def next_operation():
        pass
    next_operation()
    assert 'parent=0 ' in debug_messages[-2]


def test_nested_calls_are_correlated(debug_messages):
    @trace_operation
    def inner():
        return 42
    @trace_operation
    def outer():
        return inner()
    assert outer() == 42
    call = re.search(r' call=(\d+)', debug_messages[0]).group(1)
    assert f'parent={call} ' in debug_messages[1]


def test_async_trace_preserves_coroutine_semantics(debug_messages):
    @trace_operation
    async def operation():
        await asyncio.sleep(0)
        return 42
    assert iscoroutinefunction(operation)
    assert asyncio.run(operation()) == 42
    assert 'event=returned' in debug_messages[-1]


def test_debug_records_do_not_reach_info_sink():
    messages = []
    sink = logger.add(lambda message: messages.append(message.record['message']), level='INFO')
    try:
        @trace_operation
        def operation():
            return 42
        assert operation() == 42
        assert messages == []
    finally:
        logger.remove(sink)


def test_parser_debug_describes_processing_without_field_values(runtime, config, debug_messages):
    secret = '4111111111111111'
    transaction = runtime.Transaction(message_type='0200', data_fields={'2': secret})
    body = runtime.Parser.create_dump(transaction)
    parsed = runtime.Parser.parse_dump(body)
    assert parsed.data_fields['2'] == secret
    output = '\n'.join(debug_messages)
    assert 'event=returned' in output
    assert 'Parser' in output
    assert secret not in output


def test_startup_does_not_install_console_handler(monkeypatch):
    import ast
    from io import StringIO
    from pathlib import Path
    from unittest.mock import Mock
    import loguru

    source = Path(__file__).resolve().parents[1] / 'common/signal.py'
    tree = ast.parse(source.read_text(encoding='utf-8'))
    runtime_class = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == 'SignalRuntime')
    namespace = {'stderr': StringIO()}
    exec(compile(ast.Module(body=[runtime_class], type_ignores=[]), str(source), 'exec'), namespace)
    isolated_logger = Mock()
    monkeypatch.setattr(loguru, 'logger', isolated_logger)
    config = SimpleNamespace(debug=SimpleNamespace(level='DEBUG'))
    namespace['SignalRuntime'].prepare_logging()
    isolated_logger.remove.assert_called_once_with()
    isolated_logger.add.assert_not_called()


@pytest.mark.parametrize('configured,override,expected', [
    ('DEBUG', None, 'DEBUG'),
    ('INFO', None, 'INFO'),
    ('INFO', 'DEBUG', 'DEBUG'),
    ('DEBUG', 'INFO', 'INFO'),
    ('DEBUG', 'NOTSET', 'NOTSET'),
])
def test_cli_log_level_preserves_config_unless_explicit(runtime, config, monkeypatch, configured, override, expected):
    import sys
    from common.cli.tools.CliArgsParser import CliArgsParser
    from common.cli.tools.SignalCli import SignalCli
    config.debug.level = configured
    args = ['Signal.py', '-c']
    if override is not None:
        args += ['--log-level', override]
    monkeypatch.setattr(sys, 'argv', args)
    parsed = CliArgsParser(config).parse_arguments()
    applied = []
    target = SimpleNamespace(config=config, update_config=lambda candidate, persist: applied.append(candidate))
    SignalCli.parse_cli_config(target, parsed)
    assert applied[0].debug.level == expected
    assert config.debug.level == configured


@pytest.mark.parametrize('level', ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'])
def test_console_source_location_is_debug_only(level):
    from io import StringIO
    from common.core.constants.LogDefinition import console_format
    output = StringIO()
    sink = logger.add(output, format=console_format, colorize=True, level='DEBUG')
    try:
        logger.log(level, 'console-format-probe')
    finally:
        logger.remove(sink)
    rendered = output.getvalue()
    assert 'console-format-probe' in rendered
    assert '\x1b[' in rendered
    assert ('test_console_source_location_is_debug_only' in rendered) == (level == 'DEBUG')
