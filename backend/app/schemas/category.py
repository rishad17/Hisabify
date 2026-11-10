import uuid
from typing import Literal

from pydantic import BaseModel, ConfigDict


class CategoryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    name_bn: str | None
    kind: Literal["expense", "income"]
    is_essential: bool
    icon: str | None
