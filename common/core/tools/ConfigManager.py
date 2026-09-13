"""One configuration owner per application, with stable read-only views."""
from common.core.tools.DebugTrace import trace_operation
from copy import deepcopy
from pathlib import Path
from threading import RLock, get_ident

from pydantic import BaseModel
from loguru import logger

from common.core.data_models.Config import Config
from common.core.enums.TermFilesPath import TermFilesPath
from common.core.exceptions.exceptions import SignalError
from common.core.tools.ConfigStore import save_config


class ConfigConflictError(SignalError):
    pass


class ConfigView:
    """A retained view (including a retained section) always reads the current version."""
    __slots__ = ("_manager", "_path")

    def __init__(self, manager, path=()):
        object.__setattr__(self, "_manager", manager)
        object.__setattr__(self, "_path", path)

    def __setattr__(self, name, value):
        raise AttributeError("Active configuration is read-only; edit a snapshot and call update_config()")

    def __getattr__(self, name):
        with self._manager._lock:
            value = self._manager._current
            for part in self._path:
                value = getattr(value, part)
            value = getattr(value, name)
            if isinstance(value, BaseModel):
                return ConfigView(self._manager, self._path + (name,))
            if callable(value):
                raise AttributeError(name)
            return deepcopy(value)

    def snapshot(self):
        with self._manager._lock:
            value = self._manager._current
            for part in self._path:
                value = getattr(value, part)
            return value.model_copy(deep=True)

    def model_copy(self, *, deep=False, update=None):
        return self.snapshot().model_copy(deep=True, update=update)

    def model_dump(self, **kwargs):
        return self.snapshot().model_dump(**kwargs)

    def model_dump_json(self, **kwargs):
        return self.snapshot().model_dump_json(**kwargs)

    @property
    def manager(self):
        return self._manager


class ConfigManager:
    def __init__(self, config: Config, filename=None):
        self._lock = RLock()
        self._owner = get_ident()
        self._current = Config.model_validate_json(config.model_dump_json())
        self.filename = Path(filename or getattr(config, "_source_file", None) or TermFilesPath.CONFIG).resolve()
        self._revision = 0
        self._applying = False
        self._listeners = []
        self._validators = []
        self.view = ConfigView(self)

    def read(self):
        """A coherent mutable snapshot and its optimistic concurrency version."""
        with self._lock:
            return self._current.model_copy(deep=True), self._revision

    def subscribe(self, listener):
        """Called synchronously in the writer thread with old and new snapshots.

        Listeners apply behavior only; consumers never need to register for reads.
        On failure, invoked listeners also receive the reverse change for recovery.
        """
        self._listeners.append(listener)

    def add_validator(self, validator):
        """Reject an unsupported runtime change before saving or publishing it."""
        self._validators.append(validator)

    @trace_operation
    def replace(self, candidate: Config, *, persist=True, expected_revision=None):
        logger.debug("Config update requested: expected_revision={} persist={}", expected_revision, persist)
        if get_ident() != self._owner:
            raise SignalError("Configuration changes must be dispatched to the application thread")
        with self._lock:
            if self._applying:
                raise SignalError("A configuration change is already being applied")
            if expected_revision is not None and expected_revision != self._revision:
                logger.debug("Config update rejected: stale_revision={} current_revision={}", expected_revision, self._revision)
                raise ConfigConflictError("Settings changed while this editor was open. Reopen settings before saving.")
            new = Config.model_validate_json(candidate.model_dump_json())
            old = self._current
            logger.opt(lazy=True).debug("Config candidate validated: current_revision={} changed_sections={}",
                lambda: self._revision,
                lambda: [name for name in type(new).model_fields if getattr(new, name) != getattr(old, name)])
            for validator in self._validators:
                validator(old.model_copy(deep=True), new.model_copy(deep=True))
            if new == old:
                logger.debug("Config unchanged: revision={} persist={}", self._revision, persist)
                if persist:
                    save_config(new, self.filename)
                return self.read()[0]
            if persist:
                save_config(new, self.filename)
            self._applying = True
            self._current = new
            invoked = []
            logger.debug("Config applying callbacks: count={}", len(self._listeners))
            try:
                for listener in self._listeners:
                    invoked.append(listener)
                    listener(old.model_copy(deep=True), new.model_copy(deep=True))
            except Exception as error:
                logger.debug("Config rollback started: revision={} invoked_callbacks={} error_type={}",
                             self._revision, len(invoked), type(error).__name__)
                self._current = old
                recovery_errors = []
                if persist:
                    try:
                        save_config(old, self.filename)
                    except Exception as recovery_error:
                        recovery_errors.append(recovery_error)
                for listener in reversed(invoked):
                    try:
                        listener(new.model_copy(deep=True), old.model_copy(deep=True))
                    except Exception as recovery_error:
                        recovery_errors.append(recovery_error)
                if recovery_errors:
                    logger.debug("Config rollback incomplete: recovery_errors={}", len(recovery_errors))
                    raise SignalError("Configuration update failed. The previous values are active, but recovery was incomplete; restart after checking settings.") from recovery_errors[0]
                logger.debug("Config rollback completed: revision={}", self._revision)
                raise SignalError("Configuration update failed; the previous settings were restored.") from error
            finally:
                self._applying = False
            self._revision += 1
            logger.debug("Config update committed: revision={} persisted={}", self._revision, persist)
            return self.read()[0]
