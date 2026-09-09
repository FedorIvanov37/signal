from enum import StrEnum
from pathlib import Path
import sys


class ResourcePath:

    """
    Resolves resource paths for StrEnum definitions in both development and PyInstaller environments.

    Rewrites enum values to absolute paths when running from a bundled executable (using sys._MEIPASS),
    allowing direct use of enum members as file paths (e.g., QIcon, QPixmap) without additional conversion.

    Intended for read-only application resources.
    """

    @staticmethod
    def resource_path(relative_path: str) -> str:
        return str(Path(getattr(sys, "_MEIPASS", ".")) / relative_path)

    @staticmethod
    def prepare(path_enum: type[StrEnum]) -> type[StrEnum]:

        if not issubclass(path_enum, StrEnum):
            raise TypeError("Expected StrEnum subclass")

        members = {field.name: ResourcePath.resource_path(field.value) for field in path_enum}

        return StrEnum(path_enum.__name__, members)
