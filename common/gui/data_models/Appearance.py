from configparser import ConfigParser
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


ThemeColor = Literal["#FFFBEB", "#EFF1F5", "#282828", "#2E3440", "#282A36", "#1E1E2E", "#292D32", "#2D3742", "#2C3935", "#38323C", "#8996A3", "#24658C", "#124B70", "#012E4F", "#011627", "#243447", "#102D28", "#3B202B", "#000000", "#F0F0F0"]


# Adapted UI colors from the official Gruvbox, Nord, Dracula and Catppuccin palettes.
# Selection uses a brighter palette shade for Signal's dense transaction tables.
THEME_PRESETS = {
    '#FFFBEB': dict(text='#1F1F1F', surface='#EFEDDC', hover='#DEDDCE', selection='#644AC9'),
    '#EFF1F5': dict(text='#4C4F69', surface='#E6E9EF', hover='#CCD0DA', selection='#1E66F5'),
    '#282828': dict(text='#EBDBB2', surface='#3C3836', hover='#504945', selection='#665C54'),
    '#2E3440': dict(text='#D8DEE9', surface='#3B4252', hover='#434C5E', selection='#5E81AC'),
    '#282A36': dict(text='#F8F8F2', surface='#44475A', hover='#44475A', selection='#6272A4'),
    '#1E1E2E': dict(text='#CDD6F4', surface='#313244', hover='#45475A', selection='#585B70'),
}


class Appearance(BaseModel):
    model_config = ConfigDict(validate_assignment=True)

    consoleColor: ThemeColor = Field(default="#012E4F", exclude=True)
    windowColor: ThemeColor = Field(default="#243447", exclude=True)
    treeColor: ThemeColor = Field(default="#243447", exclude=True)
    transactionPaneRatio: float = Field(default=0.58, gt=0, lt=1)

    @model_validator(mode="before")
    @classmethod
    def migrate_tree_color(cls, values):
        if isinstance(values, dict) and 'treeColor' not in values:
            values = dict(values, treeColor=values.get('windowColor', '#243447'))
        return values

    @field_validator("consoleColor", "windowColor", "treeColor", mode="before")
    @classmethod
    def migrate_color(cls, value):
        if isinstance(value, str) and value.upper() in ('#B8C2CC', '#98A4B0'):
            return '#8996A3'
        return "#3B202B" if isinstance(value, str) and value.upper() == "#2D2038" else value

    @classmethod
    def load(cls, path: Path) -> "Appearance":
        if path.exists():
            return cls.model_validate_json(path.read_text(encoding="utf-8"))
        legacy = path.with_suffix(".ini")
        if legacy.exists():
            parser = ConfigParser(interpolation=None)
            parser.read(legacy, encoding="utf-8")
            values = {}
            for field in cls.model_fields:
                value = parser.get("appearance", field, fallback=None)
                if value is not None:
                    values[field] = "#243447" if value.upper() == "#252526" else value.upper()
            result = cls.model_validate(values)
        else:
            result = cls()
        result.save(path)
        return result

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = None
        try:
            with NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                    suffix=".tmp", delete=False) as stream:
                temporary = Path(stream.name)
                stream.write(self.model_dump_json(indent=2) + "\n")
            temporary.replace(path)
        finally:
            if temporary is not None:
                temporary.unlink(missing_ok=True)
