from datetime import datetime
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


def new_id() -> str:
    return uuid4().hex


class ApiConnector(Base):
    """API 数据源连接器配置"""

    __tablename__ = "brain_api_connectors"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")

    # 连接配置
    base_url: Mapped[str] = mapped_column(String(512), default="")
    method: Mapped[str] = mapped_column(String(16), default="GET")
    headers: Mapped[dict] = mapped_column(JSONB, default=dict)
    auth_type: Mapped[str] = mapped_column(String(32), default="none")
    auth_config: Mapped[dict] = mapped_column(JSONB, default=dict)

    # 请求模板（含变量占位，如 {contract_id}）
    request_template: Mapped[dict] = mapped_column(JSONB, default=dict)

    # 关联本体空间
    space_id: Mapped[str | None] = mapped_column(ForeignKey("ontology_spaces.id"), nullable=True)

    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_connector_tenant_code"),)


class DataMapping(Base):
    """字段映射：API 返回字段 → 本体属性"""

    __tablename__ = "brain_data_mappings"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    connector_id: Mapped[str] = mapped_column(ForeignKey("brain_api_connectors.id"), nullable=False, index=True)

    # 源字段路径（支持点号路径，如 data.contract.amount）
    source_field: Mapped[str] = mapped_column(String(256), nullable=False)

    # 目标本体信息
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_code: Mapped[str] = mapped_column(String(128), nullable=False)

    # 数据类型转换：string | int | float | date | datetime | bool | enum | money
    transform: Mapped[str] = mapped_column(String(32), default="string")

    # 是否主键字段
    is_key: Mapped[bool] = mapped_column(default=False)

    # 字段描述
    description: Mapped[str] = mapped_column(Text, default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    __table_args__ = (
        UniqueConstraint(
            "connector_id", "source_field", "target_code",
            name="uq_mapping_connector_source_target",
        ),
    )


class RuleExecution(Base):
    """规则执行记录（推理轨迹）"""

    __tablename__ = "brain_rule_executions"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    space_id: Mapped[str] = mapped_column(ForeignKey("ontology_spaces.id"), nullable=False, index=True)

    # 输入数据摘要
    input_summary: Mapped[dict] = mapped_column(JSONB, default=dict)

    # 执行结果
    status: Mapped[str] = mapped_column(String(32), default="success")
    hit_count: Mapped[int] = mapped_column(default=0)
    block_count: Mapped[int] = mapped_column(default=0)
    suggest_count: Mapped[int] = mapped_column(default=0)

    # 完整推理轨迹
    trace: Mapped[list] = mapped_column(JSONB, default=list)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
