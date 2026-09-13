# Signal

**An ISO 8583 tool for payment engineers.**

Signal helps you build, inspect, validate, and exchange ISO 8583 messages with a processing host over TCP. Use it to test integrations, reproduce transaction scenarios, and investigate requests and responses in a test environment.

**Version: v0.21** · [Website](https://signal.iso8583.tech/) · [User guide](common/doc/signal_user_guide.md)

![Signal graphical interface](common/data/static/main_window.png)

## What you can do

- Prepare transactions in a graphical field editor, including nested complex fields.
- Generate timestamps, trace numbers, and other supported field values.
- Validate messages against a configurable specification.
- Send transactions, inspect responses, and create reversals.
- Save and exchange transaction data as JSON, INI, or DUMP files.
- Automate scenarios through the command line or HTTP API.
- Test the message exchange locally with the bundled SmartVista emulator.

## One core, three interfaces

**GUI** is the interactive workspace: edit fields, manage transaction tabs, use inspection tools, and review the log.

**CLI** executes a job assembled from launch options and transaction files. Each run has a unique Job ID and normally exits when its work is complete.

**HTTP API** lets other tools and scripts use the same processing core. It runs within a GUI or CLI process; the GUI and API can operate alongside each other.

All three use the same transaction-processing core. The processing host receives ISO 8583 messages regardless of which interface initiated them.

## Built for engineers and AI agents

Signal is also a practical interface for AI agents testing payment workflows. Its HTTP API accepts structured transaction data and exposes configuration, validation, connection status, and transaction results. The CLI provides a way to execute file-based jobs, with Job IDs and logs that help trace each run.

For **agentic payments testing**, an agent can prepare a transaction, validate its fields, submit it to a test host, inspect the response, and request a reversal. Engineers can inspect the same message structure in the GUI and share reproducible scenarios as transaction files.

The bundled emulator supports local checks without a processing host. It generates test responses; it does not perform real authorization. Signal provides the ISO 8583 testing layer for an agent-driven workflow, while the surrounding system remains responsible for user consent, spending policies, and authorization to initiate payments.

## Getting started

With a Windows distribution, start `signal.exe`, configure the host address and port, and load or prepare a transaction. Use the specification required by your test host.

To run from source, use Python 3.12 with the project dependencies. From the repository root:

```console
python -m pip install -r requirements.txt
python Signal.py
```

To view CLI options:

```console
python Signal.py --console --help
```

The `--console` flag selects CLI mode. See the [user guide](common/doc/signal_user_guide.md) for transaction examples, API setup, configuration, validation, and troubleshooting.

## Documentation

- [Signal website](https://signal.iso8583.tech/)
- [Full user guide — Markdown](common/doc/signal_user_guide.md)
- [Standalone HTML guide](common/doc/signal_user_guide.html) — download and open in a browser; images are embedded.

To rebuild the HTML guide on the configured Windows development environment:

```console
common\scripts\make_doc.cmd
```

The launcher requires Python 3.12 at the location documented inside the script and the `grip` package. The implementation lives in `common/core/toolkit/make_doc.py`.

## License

See the [license agreement](common/data/license/agreement.txt).

Developed by Fedor Ivanov.
