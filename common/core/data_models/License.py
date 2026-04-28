from pydantic import BaseModel
from datetime import datetime
from uuid import uuid1
from common.core.decorators.json_file_model import json_file_model


@json_file_model
class LicenseInfo(BaseModel):
    accepted: bool = False
    last_acceptance_date: datetime | str | None = None
    show_agreement: bool = True
    license_id: str = str(uuid1())
