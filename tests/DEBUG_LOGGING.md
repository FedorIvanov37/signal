# DEBUG logging

Enable DEBUG in the existing logging settings. INFO keeps its existing filtering.

Operation traces include operation, event (entered/returned/raised), call ID,
parent call ID, elapsed_ms and available request_id/trans_id. A returned event
means the Python function returned, not necessarily that the business operation
succeeded. Raised events name the exception type; detailed exception reporting
continues through ErrorReporting.

Additional events describe TCP frame assembly and writes, request/response
matching, queue timers, parsing field lengths, configuration revisions and
rollback, API dispatch and listener lifecycle, and specification backups.
GUI, CLI and library operations use the same tracing helper.

New trace records do not dump arguments, results, field values or exception
messages. Existing explicit transaction/dump logging remains unchanged and
continues to use its existing settings. Polling loops and log display handlers
are intentionally not traced to avoid repetitive output or logging recursion.

Regression checks: tests/test_debug_logging.py.
