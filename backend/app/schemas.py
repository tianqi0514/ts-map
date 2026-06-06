from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.models import ElementStatus, ElementType


class ApiResponse(BaseModel):
    success: bool = True
    data: Any = None
    error: str | None = None
    trace_id: str | None = None


class SpaceCreate(BaseModel):
    code: str = Field(min_length=2, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    domain: str = "contract_review"
    template_code: str | None = None
    description: str = ""


class SpaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    domain: str | None = None
    template_code: str | None = None
    description: str | None = None
    status: str | None = None


class SpaceRead(SpaceCreate):
    id: str
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ReferenceInput(BaseModel):
    edge_type: str
    target_type: ElementType
    target_id: str


class ElementCreate(BaseModel):
    code: str = Field(min_length=2, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    status: ElementStatus = ElementStatus.draft
    payload: dict[str, Any] = Field(default_factory=dict)
    references: list[ReferenceInput] = Field(default_factory=list)


class ElementUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=2, max_length=128)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    description: str | None = None
    status: ElementStatus | None = None
    payload: dict[str, Any] | None = None
    references: list[ReferenceInput] | None = None


class FunctionTestRequest(BaseModel):
    input_data: Any = Field(default_factory=dict)
    expected: Any = None


class QueryCapabilityTestRequest(BaseModel):
    inputs: dict[str, Any] = Field(default_factory=dict)
    limit: int = Field(default=50, ge=1, le=500)


class ElementRead(BaseModel):
    id: str
    space_id: str
    resource_type: str
    code: str
    name: str
    description: str
    status: str
    version: int
    payload: dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
