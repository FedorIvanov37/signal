class SignalError(Exception):
    """An expected operation failure with a user-facing explanation."""


class DataFileError(SignalError, ValueError):
    def __init__(self, path, operation, reason):
        self.path = str(path)
        self.operation = operation
        super().__init__(f"Cannot {operation} file '{self.path}': {reason}")


class MessageParseError(SignalError, ValueError):
    pass


class LicenseDataLoadingError(Exception):
    ...


class LicenceAlreadyAccepted(Exception):
    ...


class LicenseRejected(Exception):
    ...


class DataValidationError(Exception):
    ...


class DataValidationWarning(Exception):
    ...
