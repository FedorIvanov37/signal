from pydantic import BaseModel, field_validator, PrivateAttr
from typing import ClassVar, Literal
from common.core.enums.Validation import ValidationMode
from common.core.decorators.json_file_model import json_file_model
from common.core.decorators.set_default_config_file import set_default_config_file


class Theme(BaseModel):
    treeColor: Literal['#FFFBEB', '#EFF1F5', '#282828', '#2E3440', '#282A36', '#1E1E2E', '#292D32', '#2D3742', '#2C3935', '#38323C', '#8996A3', '#24658C', '#124B70', '#012E4F', '#011627', '#243447', '#102D28', '#3B202B', '#000000', '#F0F0F0'] = '#F0F0F0'
    windowColor: Literal['#FFFBEB', '#EFF1F5', '#282828', '#2E3440', '#282A36', '#1E1E2E', '#292D32', '#2D3742', '#2C3935', '#38323C', '#8996A3', '#24658C', '#124B70', '#012E4F', '#011627', '#243447', '#102D28', '#3B202B', '#000000', '#F0F0F0'] = '#F0F0F0'
    consoleColor: Literal['#FFFBEB', '#EFF1F5', '#282828', '#2E3440', '#282A36', '#1E1E2E', '#292D32', '#2D3742', '#2C3935', '#38323C', '#8996A3', '#24658C', '#124B70', '#012E4F', '#011627', '#243447', '#102D28', '#3B202B', '#000000', '#F0F0F0'] = '#012E4F'

    @field_validator('treeColor', 'windowColor', 'consoleColor', mode='before')
    @classmethod
    def migrate_grey(cls, value):
        return '#8996A3' if isinstance(value, str) and value.upper() in ('#B8C2CC', '#98A4B0') else value

    def colors(self):
        return {'Tree': self.treeColor, 'Window': self.windowColor, 'Console': self.consoleColor}


class Host(BaseModel):
    host: str = str()
    port: int = int()
    keep_alive_mode: bool = False
    keep_alive_interval: int = 300
    header_length: int = 0
    header_length_exists: bool = True


class Terminal(BaseModel):
    process_default_dump: bool = True
    connect_on_startup: bool = True
    load_remote_spec: bool = False
    show_license_dialog: bool = True
    run_api: bool = False


class Debug(BaseModel):
    level: str = "INFO"
    clear_log: bool = True
    parse_subfields: bool = False
    backup_storage_depth_exists: bool = True
    backup_storage_depth: int = 30
    reduce_keep_alive: bool = True
    print_description: bool = False

    @field_validator("level", mode="before")
    @classmethod
    def set_default_level(cls, val):
        if not val:
            return "INFO"

        return val


class Validation(BaseModel):
    validation_enabled: bool = True
    validate_window: bool = True
    validate_incoming: bool = False
    validate_outgoing: bool = True
    validation_mode: ValidationMode = ValidationMode.WARNING


class Fields(BaseModel):
    auto_sort: bool = False
    max_amount: int
    max_amount_limited: bool
    build_fld_90: bool = True
    send_internal_id: bool = True
    json_mode: bool = True
    hide_secrets: bool = True

    @field_validator("max_amount", mode='before')
    @classmethod
    def amount_should_be_digit(cls, max_amount: str):
        if not str(max_amount).isdigit():
            raise ValueError("Maximum transaction amount must contain digits only")

        return int(max_amount)


class Specification(BaseModel):
    rewrite_local_spec: bool = False
    remote_spec_url: str = str()
    backup_storage_depth: int = 100
    backup_storage: bool = True
    manual_input_mode: bool = False
    backup_on_startup: bool = False
    backup_on_shutdown: bool = False


class ApiModel(BaseModel):
    address: str | None = "0.0.0.0"
    port: int = 7777
    wait_remote_host_response: bool = True
    waiting_timeout_seconds: int = 10
    hide_secrets: bool = False
    parse_subfields: bool = False

    @field_validator("address", mode="before")
    @classmethod
    def substitute_none(cls, val):
        if val is None:
            return "0.0.0.0"

        return val


@set_default_config_file
@json_file_model
class Config(BaseModel):
    _source_file: str | None = PrivateAttr(default=None)
    describe_file_errors: ClassVar[bool] = True
    host: Host = Host()
    terminal: Terminal = Terminal()
    debug: Debug = Debug()
    validation: Validation = None
    fields: Fields | None = None
    specification: Specification = Specification()
    api: ApiModel = ApiModel()
    theme: Theme = Theme()

    @field_validator("host", "api", mode="after")
    @classmethod
    def validate_port(cls, val):
        try:
            val.port = int(val.port)

        except ValueError:
            raise ValueError("Port must contain digits only")

        except AttributeError:
            raise ValueError("Missing port in configuration")

        if val.port not in range(0, 65536):
            raise ValueError(f"Incorrect port number {val.port}. Port number must be in the range 0-65535")

        return val
