# Stabilization tests

Run from the repository root with Python 3.12 or later:

```powershell
python -m pip install -r requirements-test.txt
python -m pytest tests -q
```

The tests copy settings and dictionaries to a temporary directory and load
the default configuration there. They do not start the GUI, use the configured
remote host, or modify the project's settings. TCP integration tests bind only
to `127.0.0.1` on an automatically selected port.

Coverage includes fragmented and coalesced TCP frames, invalid framing settings,
empty frames, disconnect cleanup, failed/partial writes, the outgoing two-byte
length limit, a golden ISO message, primary/secondary bitmaps, variable-length
fields, and truncated messages. Three local socket exchanges exercise the
existing emulator's response generator for 0800/0810, 0200/0210 and 0400/0410.
These check message transport and response parsing, not payment business rules
or a complete reversal workflow. The emulator's standalone accept/recv loop is
not used by these tests.

TCP reception requires `header_length_exists=true` and `header_length > 0`.
Unsupported settings and empty frames now log an error and close the connection
instead of looping or emitting invalid messages. The parser rejects the same
invalid framing and truncated field data. Sending retains the existing two-byte
length prefix; a body larger than 65535 bytes reports a sending error.

The initial verification environment was Windows, Python 3.14.3, PyQt6 6.11.0,
Qt 6.11.2, Pydantic 2.13.5 and pytest 9.1.1. Python 3.12 and the packaged executable
have not been verified by this test run.
