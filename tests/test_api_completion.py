import asyncio
from http import HTTPStatus
from threading import Lock
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


@pytest.fixture
def backend(runtime, config):
    from PyQt6.QtCore import QObject
    from common.api.tools.SignalApi import SignalApi
    backend = SignalApi.__new__(SignalApi)
    QObject.__init__(backend)
    backend.config = config
    backend.config.api.wait_remote_host_response = False
    backend.lock = Lock()
    backend.api_tasks = {}
    backend.terminal = SimpleNamespace(
        trans_validator=Mock(), connector=Mock(), spec=Mock(), trans_queue=Mock())
    backend.terminal.connector.connection_in_progress.return_value = False
    return backend


@pytest.mark.parametrize("failure", ["connecting", "validation", "missing_reversal", "socket"])
def test_failed_dispatch_is_not_acknowledged_or_sent_twice(runtime, backend, failure):
    from common.api.data_models.ApiRequests import ApiTransactionRequest, ReversalRequest
    from common.core.exceptions.exceptions import DataValidationError
    request = ApiTransactionRequest(request_id="failed", transaction=runtime.Transaction(message_type="0200", data_fields={"3": "000000"}))
    emitted = []
    responses = []
    backend.send_transaction.connect(emitted.append)
    backend.terminal_response.connect(lambda response: responses.append((response.http_status, response.error)))
    expected = HTTPStatus.SERVICE_UNAVAILABLE
    if failure == "connecting":
        backend.terminal.connector.connection_in_progress.return_value = True
    elif failure == "validation":
        backend.terminal.trans_validator.validate_transaction.side_effect = DataValidationError("invalid field")
        expected = HTTPStatus.UNPROCESSABLE_ENTITY
    elif failure == "missing_reversal":
        request = ReversalRequest(request_id="failed", original_trans_id="missing")
        backend.terminal.trans_queue.get_transaction.return_value = None
        expected = HTTPStatus.NOT_FOUND
    else:
        backend.send_transaction.connect(lambda transaction: backend.send_response(
            request, HTTPStatus.BAD_GATEWAY, error="socket failure"))
        expected = HTTPStatus.BAD_GATEWAY
    backend.process_api_call(request)
    assert len(emitted) == (1 if failure == "socket" else 0)
    assert len(responses) == 1
    assert responses[0][0] == expected and responses[0][1]
    assert not backend.api_tasks


def test_accepted_request_releases_backend_tracking(runtime, backend):
    from common.api.data_models.ApiRequests import ApiTransactionRequest
    from common.api.data_models.TransactionResp import TransactionResp
    request = ApiTransactionRequest(request_id="accepted", transaction=runtime.Transaction(message_type="0200", data_fields={"3": "000000"}))
    responses = []
    backend.terminal_response.connect(responses.append)
    backend.process_api_call(request)
    assert len(responses) == 1 and responses[0].http_status == HTTPStatus.OK
    assert isinstance(responses[0].response_data, TransactionResp)
    assert "accepted" in responses[0].response_data.status
    assert not backend.api_tasks


def test_api_spec_update_uses_single_validating_persistence_path(runtime, backend, monkeypatch):
    from common.api.data_models.ApiRequests import SpecAction
    from common.api.enums.ApiRequestType import ApiRequestType
    from common.core.tools.SpecFilesRotator import SpecFilesRotator
    backup = Mock(return_value=True)
    monkeypatch.setattr(SpecFilesRotator, 'backup_spec', backup)
    backend.terminal.spec = runtime.Parser(backend.config).spec
    candidate = backend.terminal.spec.spec.model_copy(deep=True)
    request = SpecAction(request_id='spec', request_type=ApiRequestType.UPDATE_SPEC, spec=candidate)
    backend.process_api_call(request)
    assert request.http_status == HTTPStatus.OK
    assert backup.call_count == 1
    assert backup.call_args.kwargs['required'] is True


@pytest.mark.parametrize("cancel", [False, True])
def test_http_timeout_or_cancellation_releases_both_trackers(runtime, backend, cancel):
    from PyQt6.QtCore import QObject
    from common.api.tools.Api import Api
    from common.api.data_models.ApiRequests import ApiTransactionRequest
    from common.api.exceptions.TerminalApiError import TerminalApiError
    backend.config.api.wait_remote_host_response = True
    backend.config.api.waiting_timeout_seconds = 0
    api = Api.__new__(Api)
    QObject.__init__(api)
    api.backend = backend
    api.pending_jobs = {}
    api.api_request.connect(backend.process_api_call)
    api.request_finished.connect(backend.discard_request)
    async def scenario():
        request = ApiTransactionRequest(request_id="pending", transaction=runtime.Transaction(message_type="0200", data_fields={"3": "000000"}))
        if cancel:
            backend.config.api.waiting_timeout_seconds = 30
            task = asyncio.create_task(api.backend_request(request))
            await asyncio.sleep(0)
            assert backend.api_tasks
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            with pytest.raises(TerminalApiError) as caught:
                await api.backend_request(request)
            assert caught.value.http_status == HTTPStatus.GATEWAY_TIMEOUT
        assert not api.pending_jobs and not backend.api_tasks
    asyncio.run(scenario())


@pytest.mark.parametrize("path", ["/api/transactions/predefined/echo-test", "/api/transactions/original/reverse"])
@pytest.mark.parametrize("accepted", [False, True])
def test_send_routes_accept_both_response_modes(runtime, config, monkeypatch, tmp_path, path, accepted):
    from fastapi.testclient import TestClient
    from common.api.tools.Api import Api
    from common.api.data_models.TransactionResp import TransactionResp
    from common.core.tools.ResourcePath import ResourcePath
    monkeypatch.setattr(ResourcePath, "resource_path", staticmethod(lambda path: str(tmp_path)))
    transaction = runtime.Transaction(message_type="0210", data_fields={"39": "00"})
    api = Api(SimpleNamespace(config=config, terminal_response=Mock(),
                              get_predefined_transaction=Mock(return_value=transaction)))
    response = TransactionResp(status="accepted") if accepted else transaction
    monkeypatch.setattr(api, "backend_request", AsyncMock(return_value=response))
    with TestClient(api.app) as client:
        result = client.post(path)
    assert result.status_code == 200
    assert result.json()["status" if accepted else "message_type"] == ("accepted" if accepted else "0210")
