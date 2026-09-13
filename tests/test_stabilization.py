import socket
import threading
import time

import pytest


def frame(body, width=2):
    return len(body).to_bytes(width, "big") + body


@pytest.fixture
def connector(runtime, config):
    class MemoryConnector(runtime.Connector):
        chunk = b""
        aborted = False

        def readAll(self):
            from PyQt6.QtCore import QByteArray
            chunk, self.chunk = self.chunk, b""
            return QByteArray(chunk)

        def abort(self):
            self.aborted = True

        def feed(self, data):
            self.chunk = data
            self.read_transaction_data()

    value = MemoryConnector(config)
    yield value
    value.close()


@pytest.mark.parametrize("width", [2, 4])
def test_fragmented_and_coalesced_frames(connector, config, width):
    config.host.header_length = width
    messages = []
    connector.incoming_transaction_data.connect(messages.append)
    first, second = frame(b"first", width), frame(b"second", width)
    connector.feed(first[:1])
    connector.feed(first[1:-1])
    assert messages == []
    connector.feed(first[-1:] + second)
    assert messages == [first, second]
    assert connector._recv_buffer == b""


@pytest.mark.parametrize("enabled,width", [(False, 2), (True, 0), (True, -1)])
def test_invalid_framing_does_not_loop(connector, config, enabled, width):
    config.host.header_length_exists = enabled
    config.host.header_length = width
    # Abort the old infinite loop deterministically, even before the fix.
    class UnexpectedEmission(Exception):
        pass
    class Guard:
        def emit(self, data):
            raise UnexpectedEmission("Invalid configuration emitted a message")
    # Use the actual method on a lightweight receiver so exceptions propagate.
    from types import SimpleNamespace
    receiver = SimpleNamespace(config=config, _recv_buffer=b"",
                               readAll=connector.readAll,
                               incoming_transaction_data=Guard(),
                               abort=connector.abort)
    receiver._clear_recv_buffer = lambda: setattr(receiver, "_recv_buffer", b"")
    connector.chunk = frame(b"abc")
    type(connector).read_transaction_data(receiver)
    assert connector.aborted
    assert receiver._recv_buffer == b""


def test_empty_frame_is_rejected(connector):
    connector.feed(b"\x00\x00")
    assert connector.aborted
    assert connector._recv_buffer == b""


def test_disconnect_discards_partial_frame(connector):
    messages = []
    connector.incoming_transaction_data.connect(messages.append)
    connector.feed(b"\x00\x10old")
    connector.disconnected.emit()
    connector.feed(frame(b"new"))
    assert messages == [frame(b"new")]


@pytest.mark.parametrize("written", [-1, 0, 2])
def test_failed_or_partial_write_is_not_reported_as_sent(runtime, config, written):
    class Writer(runtime.Connector):
        aborted = False
        def state(self):
            return self.SocketState.ConnectedState
        def write(self, data):
            return written
        def abort(self):
            self.aborted = True
    writer = Writer(config)
    sent, errors = [], []
    writer.transaction_sent.connect(sent.append)
    writer.sending_error.connect(lambda *args: errors.append(args))
    writer.send_transaction_data("id", b"abc")
    assert not sent
    assert errors and errors[0][0] == "id"
    assert writer.aborted


@pytest.mark.parametrize("size", [65535, 65536])
def test_outgoing_frame_length_limit(runtime, config, size):
    class Writer(runtime.Connector):
        payload = None
        def state(self):
            return self.SocketState.ConnectedState
        def write(self, data):
            self.payload = data
            return len(data)
        def flush(self):
            return True
    writer = Writer(config)
    sent, errors = [], []
    writer.transaction_sent.connect(sent.append)
    writer.sending_error.connect(lambda *args: errors.append(args))
    writer.send_transaction_data("id", b"a" * size)
    if size == 65535:
        assert writer.payload == b"\xff\xff" + b"a" * size
        assert sent == ["id"] and not errors
    else:
        assert writer.payload is None
        assert not sent and errors[0][0] == "id"


@pytest.mark.parametrize("fields", [
    {"3": "000000", "11": "123456"},
    {"2": "4111111111111111", "3": "000000"},
    {"7": "0909123456", "11": "123456", "70": "301"},
])
def test_parser_round_trip(runtime, config, fields):
    transaction = runtime.Transaction(message_type="0800", data_fields=fields)
    body = runtime.Parser.create_dump(transaction)
    parsed = runtime.Parser.parse_raw_data(frame(body), flat=True)[0]
    assert parsed.message_type == transaction.message_type
    assert parsed.data_fields == fields


def test_golden_message_and_multiple_frames(runtime, config):
    body = b"0200" + bytes.fromhex("2020000000000000") + b"000000123456"
    transaction = runtime.Transaction(message_type="0200", data_fields={
        "3": "000000", "11": "123456"})
    assert runtime.Parser.create_dump(transaction) == body
    parsed = runtime.Parser.parse_raw_data(frame(body) * 2, flat=True)
    assert len(parsed) == 2
    assert all(item.data_fields == transaction.data_fields for item in parsed)


@pytest.mark.parametrize("body", [
    b"0800" + bytes.fromhex("2000000000000000") + b"123",
    b"0800" + bytes.fromhex("4000000000000000") + b"1",
    b"0800" + bytes.fromhex("4000000000000000") + b"16" + b"4111",
    b"0800" + bytes.fromhex("8000000000000000"),
])
def test_parser_rejects_truncated_fields_and_bitmap(runtime, config, body):
    with pytest.raises(ValueError):
        runtime.Parser.parse_dump(body, flat=True)


@pytest.mark.parametrize("data", [b"\x00", b"\x00\x05abc", b"\x00\x00"])
def test_parser_rejects_invalid_frames(runtime, config, data):
    with pytest.raises(ValueError):
        runtime.Parser.parse_raw_data(data)


@pytest.mark.parametrize("enabled,width", [(False, 2), (True, 0), (True, -1)])
def test_parser_rejects_invalid_framing(runtime, config, enabled, width):
    config.host.header_length_exists = enabled
    config.host.header_length = width
    with pytest.raises(ValueError):
        runtime.Parser.parse_raw_data(frame(b"abc"))


@pytest.mark.parametrize("request_mti,response_mti", [
    ("0800", "0810"), ("0200", "0210"), ("0400", "0410")])
def test_local_tcp_exchange_with_emulator_response(runtime, config, request_mti, response_mti):
    """Real Qt socket and ISO parser, using the existing emulator response logic."""
    emulator = runtime.SvEmulator(runtime.IsoConfig(ADDRESS="127.0.0.1"))
    errors = []
    with socket.socket() as server:
        server.bind(("127.0.0.1", 0))
        server.listen(1)
        server.settimeout(3)
        config.host.host, config.host.port = server.getsockname()

        def serve():
            try:
                peer, _ = server.accept()
                with peer:
                    peer.settimeout(3)
                    def read_exact(length):
                        data = b""
                        while len(data) < length:
                            chunk = peer.recv(length - len(data))
                            if not chunk:
                                raise EOFError("Peer closed before the frame was complete")
                            data += chunk
                        return data
                    size = int.from_bytes(read_exact(2), "big")
                    request = runtime.Parser.parse_dump(read_exact(size), flat=True)
                    response = emulator.generate_resp(request)
                    response.message_type = emulator.spec.get_resp_mti(request.message_type)
                    payload = frame(runtime.Parser.create_dump(response))
                    peer.sendall(payload[:1])
                    peer.sendall(payload[1:])
            except Exception as error:
                errors.append(error)

        thread = threading.Thread(target=serve, daemon=True)
        thread.start()
        client = runtime.Connector(config)
        received = []
        client.incoming_transaction_data.connect(received.append)
        try:
            client.connect_sv()
            assert client.is_connected()
            request = runtime.Transaction(message_type=request_mti, data_fields={
                "7": "0909123456", "11": "123456", "70": "301"})
            client.send_transaction_data(request.trans_id, runtime.Parser.create_dump(request))
            deadline = time.monotonic() + 3
            while not received and time.monotonic() < deadline:
                runtime.app.processEvents()
                time.sleep(0.001)
            assert received, errors
            response = runtime.Parser.parse_raw_data(received[0], flat=True)[0]
            assert response.message_type == response_mti
            assert response.data_fields["39"] == "00"
            assert response.data_fields["11"] == "123456"
        finally:
            client.abort()
            thread.join(4)
        assert not thread.is_alive()
        assert not errors


@pytest.mark.parametrize('mti,expected', [('0800', False), ('0200', True)])
def test_emulator_auth_code_only_for_non_0810_response(runtime, mti, expected):
    emulator = runtime.SvEmulator(runtime.IsoConfig())
    request = runtime.Transaction(message_type=mti, data_fields={'38': 'ABC123'})
    response = emulator.generate_resp(request)
    assert ('38' in response.data_fields) is expected
    assert response.data_fields['39'] == '00'
    assert request.data_fields['38'] == 'ABC123'
