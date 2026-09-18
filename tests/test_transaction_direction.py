from unittest.mock import Mock

import pytest


@pytest.fixture
def queue(runtime, config):
    from PyQt6.QtCore import QObject, pyqtSignal
    from common.core.tools.TransactionQueue import TransactionQueue

    class Transport(QObject):
        incoming_transaction_data = pyqtSignal(bytes)
        transaction_sent = pyqtSignal(str)
        sending_error = pyqtSignal(str, str)

        def __init__(self):
            super().__init__()
            self.config = config
            self.sent = []

        def send_transaction_data(self, trans_id, data):
            self.sent.append((trans_id, data))
            self.transaction_sent.emit(trans_id)

    transport = Transport()
    result = TransactionQueue(transport)
    yield result
    for timer in result.timers.values():
        timer.stop()


def message(runtime, mti, stan='123456'):
    return runtime.Transaction(message_type=mti, data_fields={
        '2': '4000000000000002', '7': '0911210000', '11': stan,
        '12': '260911210000', '39': '00'})


def receive(runtime, queue, transaction):
    body = runtime.Parser.create_dump(transaction)
    queue.connector.incoming_transaction_data.emit(len(body).to_bytes(2, 'big') + body)


@pytest.mark.parametrize('mti', ['0100', '0110', '0200', '0210', '0800', '0810'])
def test_send_uses_transport_for_any_mti(runtime, queue, mti):
    outgoing, incoming = Mock(), Mock()
    queue.outgoing_transaction.connect(outgoing)
    queue.incoming_transaction.connect(incoming)
    transaction = message(runtime, mti)
    queue.put_transaction(transaction)
    assert queue.connector.sent == [(transaction.trans_id, runtime.Parser.create_dump(transaction))]
    outgoing.assert_called_once_with(transaction)
    incoming.assert_not_called()
    assert transaction.direction == 'outgoing'
    assert bool(queue.timers) == bool(queue.spec.get_resp_mti(mti))


@pytest.mark.parametrize('mti', ['0100', '0110', '0200', '0210', '0800', '0810'])
def test_socket_message_is_never_sent_back(runtime, queue, mti):
    incoming = Mock()
    queue.incoming_transaction.connect(incoming)
    receive(runtime, queue, message(runtime, mti))
    incoming.assert_called_once()
    transaction = incoming.call_args.args[0]
    assert transaction.message_type == mti
    assert transaction.direction == 'incoming'
    assert not transaction.matched
    assert not queue.connector.sent
    assert not queue.timers


@pytest.mark.parametrize('response_mti', ['0100', '0110'])
def test_standard_and_same_mti_response_match_outgoing(runtime, queue, response_mti):
    request = message(runtime, '0100')
    queue.put_transaction(request)
    receive(runtime, queue, message(runtime, response_mti))
    response = queue.queue[-1]
    assert response.matched and request.matched
    assert response.match_id == request.trans_id
    assert request.match_id == response.trans_id
    assert response.success is True
    assert request.trans_id not in queue.timers
    assert len(queue.connector.sent) == 1


def test_wrong_fields_and_unrelated_mti_do_not_match(runtime, queue):
    request = message(runtime, '0100')
    queue.put_transaction(request)
    receive(runtime, queue, message(runtime, '0110', stan='654321'))
    receive(runtime, queue, message(runtime, '0210'))
    assert not request.matched
    assert all(not t.matched for t in queue.queue)
    assert queue.timers[request.trans_id].isActive()


def test_incoming_messages_cannot_match_each_other(runtime, queue):
    receive(runtime, queue, message(runtime, '0100'))
    receive(runtime, queue, message(runtime, '0110'))
    assert all(not t.matched for t in queue.queue)
    assert not queue.connector.sent


def test_timeout_releases_timer_and_late_response_still_has_elapsed_time(runtime, queue):
    request = message(runtime, '0100')
    queue.put_transaction(request)
    expired = Mock()
    queue.transaction_timeout.connect(expired)
    queue.process_timeout(request)
    queue.process_timeout(request)
    expired.assert_called_once_with(request, 60)
    assert not queue.timers
    receive(runtime, queue, message(runtime, '0110'))
    assert request.matched and request.resp_time_seconds is not None


@pytest.mark.parametrize('operation', ['remove', 'replace', 'evict'])
def test_queue_removal_or_replacement_stops_obsolete_timer(runtime, queue, operation):
    from collections import deque
    if operation == 'evict':
        queue.queue = deque(maxlen=1)
    request = message(runtime, '0100')
    queue.put_transaction(request)
    old_timer = queue.timers[request.trans_id]
    if operation == 'remove':
        queue.remove_from_queue(request)
        assert not queue.timers
    else:
        new = message(runtime, '0100', stan='654321')
        if operation == 'replace':
            new.trans_id = request.trans_id
        queue.put_transaction(new)
        assert len(queue.timers) == 1
        assert queue.timers[new.trans_id] is not old_timer
    assert not old_timer.isActive()


def test_duplicate_response_does_not_rematch(runtime, queue):
    request = message(runtime, '0100')
    queue.put_transaction(request)
    receive(runtime, queue, message(runtime, '0110'))
    first_match = request.match_id
    receive(runtime, queue, message(runtime, '0110'))
    assert request.match_id == first_match
    assert not queue.queue[-1].matched
    assert len(queue.connector.sent) == 1


def test_real_socket_sends_response_mti_and_receives_request_mti(runtime, config):
    import socket
    from time import monotonic
    from common.core.tools.TransactionQueue import TransactionQueue
    server = socket.socket()
    server.bind(('127.0.0.1', 0))
    server.listen(1)
    server.settimeout(2)
    connector = runtime.Connector(config)
    queue = TransactionQueue(connector)
    incoming, outgoing = [], []
    queue.incoming_transaction.connect(incoming.append)
    queue.outgoing_transaction.connect(outgoing.append)
    peer = None
    try:
        connector.connectToHost('127.0.0.1', server.getsockname()[1])
        assert connector.waitForConnected(2000)
        peer, _ = server.accept()
        peer.settimeout(2)
        sent = message(runtime, '0110')
        queue.put_transaction(sent)
        body = runtime.Parser.create_dump(sent)
        expected = len(body).to_bytes(2, 'big') + body
        wire = b''
        while len(wire) < len(expected):
            wire += peer.recv(len(expected) - len(wire))
        assert wire == expected
        assert outgoing == [sent] and not incoming
        body = runtime.Parser.create_dump(message(runtime, '0100'))
        peer.sendall(len(body).to_bytes(2, 'big') + body)
        deadline = monotonic() + 2
        while not incoming and monotonic() < deadline:
            runtime.app.processEvents()
        assert len(incoming) == 1
        assert incoming[0].message_type == '0100'
        assert incoming[0].direction == 'incoming'
        assert outgoing == [sent]
        peer.settimeout(0.1)
        with pytest.raises(socket.timeout):
            peer.recv(1)
    finally:
        connector.abort()
        if peer is not None:
            peer.close()
        server.close()
        for timer in queue.timers.values():
            timer.stop()


@pytest.mark.parametrize('mti', ['0110', '0210', '0810'])
def test_emulator_ignores_response_and_handles_next_request(runtime, monkeypatch, mti):
    import importlib
    emulator = runtime.SvEmulator(runtime.IsoConfig())
    frames = []
    for transaction in (message(runtime, mti), runtime.Transaction(message_type='0800', data_fields={'70': '301'})):
        body = runtime.Parser.create_dump(transaction)
        frames.append(len(body).to_bytes(2, 'big') + body)
    connection = Mock()
    def recv(size):
        if frames:
            return frames.pop(0)
        emulator.stop = True
        return b''
    connection.recv.side_effect = recv
    connect = Mock(return_value=connection)
    monkeypatch.setattr(emulator, 'get_connector', connect)
    module = importlib.import_module('common.core.toolkit.sv_emulator')
    monkeypatch.setattr(module, 'logger', Mock())
    generate = Mock(wraps=emulator.generate_resp)
    monkeypatch.setattr(emulator, 'generate_resp', generate)
    emulator.run(sleep_time=0)
    connect.assert_called_once()
    generate.assert_called_once()
    assert generate.call_args.args[0].message_type == '0800'
    connection.sendall.assert_called_once()
    assert connection.sendall.call_args.args[0][2:6] == b'0810'
    module.logger.error.assert_not_called()


def test_cli_does_not_wait_for_reply_to_response(runtime):
    from types import SimpleNamespace
    from common.cli.tools.SignalCli import SignalCli
    from common.core.tools.EpaySpecification import EpaySpecification
    cli = SimpleNamespace(spec=EpaySpecification(), wait=Mock())
    SignalCli.wait_response(cli, message(runtime, '0110'))
    cli.wait.assert_not_called()
