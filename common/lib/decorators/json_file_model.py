from pathlib import Path
from functools import wraps
from typing import Any, TypeVar
from pydantic import BaseModel


"""
Decorator for convenient JSON file initialization of Pydantic models

By default, Pydantic expects JSON content as a string and uses model_validate_json() for parsing:

 config = Config.model_validate_json(Path("config.json").read_text(encoding="utf-8"))

This is the official native approach, described here:

 • https://docs.pydantic.dev/latest/concepts/models/
 • https://docs.pydantic.dev/latest/concepts/json/

The decorator adds a simpler and more readable shortcut:

 @json_file_model
 class Config(BaseModel):
     host: str
     port: int

 config = Config("config.json")

This improves readability and removes repetitive boilerplate for common configuration loading scenarios

Important:
 • Native Pydantic initialization remains fully supported
 • Standard field-based initialization still works
 • model_validate_json() can still be used as before
 • Backward compatibility is preserved

This decorator adds convenience without replacing or restricting standard Pydantic behavior
"""


T = TypeVar("T", bound=type[BaseModel])


def json_file_model(cls: T):
    original_init = cls.__init__

    @wraps(original_init)
    def __init__(self, json_path: str | Path | None = None, **fields_data: Any) -> None:

        if json_path is not None and fields_data:
            raise ValueError("Use argument json_path or model fields, not both")

        if json_path is not None:
            raw_data = Path(json_path).read_text(encoding="utf-8")
            parsed_data = cls.model_validate_json(raw_data)
            fields_data = parsed_data.model_dump()

        original_init(self, **fields_data)

    cls.__init__ = __init__

    return cls
