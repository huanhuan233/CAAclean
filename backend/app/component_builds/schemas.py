from typing import Literal

from pydantic import BaseModel, Field


class ComponentBuildCreateFields(BaseModel):
    category_code: str = Field(min_length=1, max_length=80)
    part_type_code: str = Field(min_length=1, max_length=80)
    component_name: str = Field(min_length=1, max_length=255)
    standard_number: str | None = None
    version: str = "1.0.0"


class ComponentBuildRetryIn(BaseModel):
    role: Literal["reference_step", "drawing"]


class ComponentSpecDraftIn(BaseModel):
    data: dict


class ComponentBuildFusionIn(BaseModel):
    overwrite: bool = False
