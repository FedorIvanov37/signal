# Live configuration

Each Terminal owns a ConfigManager (not a process-global singleton). The manager
owns one validated configuration and one stable, read-only ConfigView. GUI, API,
CLI, connectors, parsers, tabs and validators receive that view at construction.
Replacing settings never replaces those references. A previously retained section,
such as `host = terminal.config.host`, also reads the current version.

Consumers do not register for configuration updates. Subscriptions are needed only
for behavior such as adjusting a timer or refreshing widgets. Terminal subscribes
its runtime change handler; SignalGui extends it for presentation in all tabs.

## Making changes

```python
candidate, revision = terminal.config_manager.read()
candidate.host.port = 16678
terminal.update_config(candidate, expected_revision=revision)
```

For temporary CLI/library overrides use `persist=False`. To obtain a detached
Config model for serialization or editing, use `terminal.config.model_copy(deep=True)`
or `terminal.config_manager.read()`. Direct mutation of the active view raises an
error; changes must go through update_config. HTTP GET and PUT keep their existing
Config JSON schema and return detached snapshots, never the view object.

The file selected at startup (including --config-file) remains the save destination.
Reloading another file imports its values without changing that destination.
The running transaction queue supplies its current settings explicitly to the
parser; it no longer reloads the default config file for each incoming message.
Static Parser.parse_raw_data calls without config retain their standalone fallback.

## Consistency and failure behavior

The manager validates and saves before making the candidate visible. Failed writes
leave every reader on the old version. A lock makes snapshot reads coherent across
threads and prevents readers observing intermediate state during change callbacks.
Use a snapshot when one operation needs several mutually consistent values.
Configuration writes belong to the application thread; API writes are dispatched
there through the existing Qt bridge. Unrelated Terminal instances remain isolated.

On a callback failure, the manager restores the old configuration, restores the
file if persistence was requested, and invokes the applied callbacks in reverse
order with the reverse change. Failed recovery is reported explicitly. Callbacks
should implement reversible local behavior and must not wait for another thread
that reads configuration. Already-triggered external effects cannot be rolled back.

An open settings dialog is an edit snapshot, not a second active configuration.
If an API update commits while the dialog is open, saving that old snapshot is
rejected; the user must reopen settings. This prevents silently overwriting newer
changes. Existing main-window tabs continue reading the live version immediately.

## Listening ports and connections

API request behavior uses current settings immediately. A new API address/port
can be saved through PUT /config or GUI while the API is running. The current
listener keeps its existing address/port until the user restarts the API using
the restart control. Starting the API honors the latest configured address and
port. Saving configuration does not stop or restart the API automatically.
Startup-only settings do not replay startup.
Changing the processing host settings does not move an already-open TCP connection;
the next connection uses the new destination.

## Tests

Run `python -m pytest tests -q`. Tests cover real HTTP GET/PUT routing through the
Qt API bridge, GUI settings commits, inactive tabs and nested validators, stale
edit conflicts, write denial, rollback, custom paths, CLI/library consumers and
timer updates. GUI tests use offscreen widgets and omit startup actions and the
background connection thread; existing TCP tests separately exercise real sockets.
