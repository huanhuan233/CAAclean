from typing import Literal

from pydantic import BaseModel, Field


class ComponentBuildCreateFields(BaseModel):
    component_id: str = Field(min_length=1, max_length=160)
    component_name: str = Field(min_length=1, max_length=255)
    component_type: str = Field(min_length=1, max_length=80)
    component_subtype: str | None = None
    family: str | None = None
    standard_number: str | None = None
    version: str = "1.0.0"
    default_dn: int | None = None
    default_pn: int | None = None


class ComponentBuildRetryIn(BaseModel):
    role: Literal["reference_step", "drawing"]
