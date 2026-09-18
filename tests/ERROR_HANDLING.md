# Error handling contract

This first pass covers configuration persistence and startup, the Qt API dispatch
boundary, HTTP requests, transaction preparation and incoming parser errors.
It does not claim that every existing GUI action or background worker has been
converted to this contract.

## Expected failures

`SignalError` describes an operation that could not complete.
`DataFileError` adds a file path and operation (read/load/save); the original
exception is preserved as `__cause__`. Config file errors omit input values.
`MessageParseError` preserves the parser's explanation, including field numbers.
They remain compatible with existing `ValueError` handlers where appropriate.

Only Config opts into JSON file error translation. Other models retain their
original exceptions, including the ValidationError used to detect legacy messages.

## Configuration

The settings dialog edits a copy. Failed validation or saving keeps the dialog
open and does not mutate the active configuration. ConfigStore validates a
serialized candidate, writes a temporary file in the destination directory,
flushes it and replaces the target. An unsuccessful write never truncates the
target file. No automatic fallback to default settings is performed.

Terminal.read_config raises on failure and keeps its previous configuration.
Terminal.update_config delegates to ConfigManager, which saves before publishing
a candidate. If applying settings fails, the shared view returns to the old
configuration, the manager attempts to restore the file and invokes reverse callbacks.
A failed rollback is reported explicitly. This does not undo external effects
already triggered by application callbacks, such as a remote specification fetch.
Concurrent writers and atomic multi-file changes are outside this contract.

## Presentation and request completion

Startup loads configuration before importing the GUI/CLI implementation. Startup
failures show a GUI dialog or a CLI stderr message and return code 100.
The settings dialog reports errors through ErrorReporting. Application error
messages use the existing English UI language.

The Qt API dispatcher converts exceptions to a terminal response, completing the
waiting Future instead of leaving the HTTP caller waiting for a timeout. File
access failures and unexpected errors produce 500; rejected input produces 422.
Unexpected HTTP exceptions receive a generic 500 response with X-Request-ID.

Outgoing preparation failures mark the transaction unsuccessful and emit the
existing socket_error channel. Incoming malformed messages emit parsing_error;
GUI displays a status message and the queue logs the cause. A malformed response
cannot safely be matched to a particular request; pending requests keep their
normal timeout behavior.

An uncaught Qt callback exception reaches the installed sys.excepthook: it reports
the failure and requests event-loop exit with code 100. This is a last resort,
not a recovery mechanism. Python worker threads and independent asyncio tasks
require their own operation boundaries. The previous hook is restored on exit.

## Extending the contract

1. Raise a descriptive domain error at the failing operation, using `from error`.
2. Decide whether the operation can be retried and what state must be restored.
3. Catch at the user action/request boundary, not indiscriminately in helpers.
4. Notify the caller exactly once and preserve diagnostic context.
5. Add an injected-failure test that checks both the message and resulting state.

Next candidates are specification saving/backups, transaction file exports,
logging initialization, background worker failures and orderly shutdown.

Run `python -m pytest tests -q` from the repository root. Tests use temporary
settings, offscreen Qt widgets and mocked permission failures; they do not alter
Windows ACLs. The packaged executable and an interactive GUI session are not
covered by this test suite.
