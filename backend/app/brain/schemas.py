from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── API Connector ──

class ApiConnectorCreate(BaseModel):
    code: str = Field(min_length=2, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    base_url: str = ""
    method: str = "GET"
    headers: dict[str, str] = Field(default_factory=dict)
    auth_type: str = "none"  # none | basic | bearer | apikey
    auth_config: dict[str, Any] = Field(default_factory=dict)
    request_template: dict[str, Any] = Field(default_factory=dict)
    space_id: str | None = None
    status: str = "active"


class ApiConnectorUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    base_url: str | None = None
    method: str | None = None
    headers: dict[str, str] | None = None
    auth_type: str | None = None
    auth_config: dict[str, Any] | None = None
    request_template: dict[str, Any] | None = None
    space_id: str | None = None
    status: str | None = None


class ApiConnectorRead(BaseModel):
    id: str
    code: str
    name: str
    description: str
    base_url: str
    method: str
    headers: dict[str, str]
    auth_type: str
    auth_config: dict[str, Any]
    request_template: dict[str, Any]
    space_id: str | None
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Data Mapping ──

class DataMappingCreate(BaseModel):
    connector_id: str
    source_field: str = Field(min_length=1, max_length=256)
    target_type: str = "object"
    target_code: str = Field(min_length=1, max_length=128)
    transform: str = "string"
    is_key: bool = False
    description: str = ""


class DataMappingUpdate(BaseModel):
    source_field: str | None = None
    target_type: str | None = None
    target_code: str | None = None
    transform: str | None = None
    is_key: bool | None = None
    description: str | None = None


class DataMappingRead(BaseModel):
    id: str
    connector_id: str
    source_field: str
    target_type: str
    target_code: str
    transform: str
    is_key: bool
    description: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── 合成数据预览 ──

class SyntheticDataPreviewRequest(BaseModel):
    connector_id: str
    count: int = Field(default=3, ge=1, le=20)


class SyntheticDataPreviewResponse(BaseModel):
    connector_id: str
    connector_name: str
    records: list[dict[str, Any]]
    mapping_summary: dict[str, Any]


# ── 规则引擎 ──

class RuleEngineInput(BaseModel):
    space_id: str
    data: dict[str, Any] = Field(default_factory=dict)
    rule_ids: list[str] | None = None  # 为空则执行所有活跃规则


class RuleHitResult(BaseModel):
    rule_id: str
    rule_code: str
    rule_name: str
    rule_type: str
    priority: int
    condition: str
    matched: bool
    result: str
    severity: str  # block | warn | suggest | pass
    reasoning: list[dict[str, Any]]  # 推理步骤


class RuleEngineOutput(BaseModel):
    space_id: str
    input_data: dict[str, Any]
    total_rules: int
    hit_count: int
    block_count: int
    hits: list[RuleHitResult]
    execution_time_ms: float


# ── 规则执行记录 ──

class RuleExecutionRead(BaseModel):
    id: str
    space_id: str
    input_summary: dict[str, Any]
    status: str
    hit_count: int
    block_count: int
    suggest_count: int
    trace: list[dict[str, Any]]
    created_at: datetime

    model_config = {"from_attributes": True}


# ── Brain Agent ──

class BrainAgentCreate(BaseModel):
    code: str = Field(min_length=2, max_length=128)
    name: str = Field(min_length=1, max_length=255)
    description: str = ""
    connector_id: str | None = None
    space_id: str | None = None
    strategy_type: str = "rule_based"  # rule_based | natural_language
    strategy_config: dict[str, Any] = Field(default_factory=dict)
    status: str = "active"


class BrainAgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    connector_id: str | None = None
    space_id: str | None = None
    strategy_type: str | None = None
    strategy_config: dict[str, Any] | None = None
    status: str | None = None


class BrainAgentRead(BaseModel):
    id: str
    code: str
    name: str
    description: str
    connector_id: str | None
    space_id: str | None
    strategy_type: str
    strategy_config: dict[str, Any]
    status: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


# ── Agent 执行 ──

class AgentExecutionCreate(BaseModel):
    agent_id: str
    input_data: dict[str, Any] = Field(default_factory=dict)


class AgentExecutionRead(BaseModel):
    id: str
    agent_id: str
    input_data: dict[str, Any]
    result: dict[str, Any]
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
