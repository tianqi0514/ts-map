from datetime import datetime
from enum import StrEnum
from uuid import uuid4

from sqlalchemy import DateTime, ForeignKey, Index, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

# Import brain models so they are registered with Base.metadata
from app.brain.models import AgentExecution, ApiConnector, BrainAgent, DataMapping, RuleExecution  # noqa: F401


def new_id() -> str:
    return uuid4().hex


class ElementType(StrEnum):
    object = "object"
    property = "property"
    relation = "relation"
    action = "action"
    scenario = "scenario"
    rule = "rule"
    setting = "setting"


class ElementStatus(StrEnum):
    draft = "draft"
    pending = "pending"
    active = "active"
    inactive = "inactive"
    deprecated = "deprecated"


class EdgeType(StrEnum):
    contains = "CONTAINS"
    has_property = "HAS_PROPERTY"
    relates_from = "RELATES_FROM"
    relates_to = "RELATES_TO"
    references_object = "REFERENCES_OBJECT"
    references_property = "REFERENCES_PROPERTY"
    references_relation = "REFERENCES_RELATION"
    references_action = "REFERENCES_ACTION"
    activates_object = "ACTIVATES_OBJECT"
    activates_relation = "ACTIVATES_RELATION"
    activates_action = "ACTIVATES_ACTION"
    activates_rule = "ACTIVATES_RULE"


class OntologySpace(Base):
    __tablename__ = "ontology_spaces"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    domain: Mapped[str] = mapped_column(String(128), default="contract_review")
    template_code: Mapped[str | None] = mapped_column(String(128))
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_by: Mapped[str] = mapped_column(String(128), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    elements: Mapped[list["OntologyElement"]] = relationship(back_populates="space")

    __table_args__ = (UniqueConstraint("tenant_id", "code", name="uq_space_tenant_code"),)


class OntologyElement(Base):
    __tablename__ = "ontology_elements"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    space_id: Mapped[str] = mapped_column(ForeignKey("ontology_spaces.id"), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    code: Mapped[str] = mapped_column(String(128), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default=ElementStatus.draft)
    version: Mapped[int] = mapped_column(default=1)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by: Mapped[str] = mapped_column(String(128), default="system")
    updated_by: Mapped[str] = mapped_column(String(128), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime)

    space: Mapped[OntologySpace] = relationship(back_populates="elements")

    __table_args__ = (
        UniqueConstraint("space_id", "resource_type", "code", name="uq_element_space_type_code"),
        Index("ix_elements_space_type_status", "space_id", "resource_type", "status"),
    )


class ReferenceEdge(Base):
    __tablename__ = "reference_edges"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    space_id: Mapped[str] = mapped_column(ForeignKey("ontology_spaces.id"), nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    edge_type: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    target_type: Mapped[str] = mapped_column(String(32), nullable=False)
    target_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    __table_args__ = (
        UniqueConstraint(
            "space_id",
            "source_id",
            "edge_type",
            "target_id",
            name="uq_reference_edge",
        ),
    )


class VersionRecord(Base):
    __tablename__ = "version_records"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    space_id: Mapped[str] = mapped_column(ForeignKey("ontology_spaces.id"), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    version: Mapped[int] = mapped_column(nullable=False)
    change_type: Mapped[str] = mapped_column(String(32), nullable=False)
    diff: Mapped[dict] = mapped_column(JSONB, default=dict)
    snapshot: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_by: Mapped[str] = mapped_column(String(128), default="system")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    space_id: Mapped[str] = mapped_column(ForeignKey("ontology_spaces.id"), nullable=False, index=True)
    actor_id: Mapped[str] = mapped_column(String(128), default="system")
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(32), nullable=False)
    before: Mapped[dict] = mapped_column(JSONB, default=dict)
    after: Mapped[dict] = mapped_column(JSONB, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class GraphSyncTask(Base):
    __tablename__ = "graph_sync_tasks"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    tenant_id: Mapped[str] = mapped_column(String(64), default="default", index=True)
    space_id: Mapped[str] = mapped_column(ForeignKey("ontology_spaces.id"), nullable=False, index=True)
    resource_type: Mapped[str] = mapped_column(String(32), nullable=False)
    resource_id: Mapped[str] = mapped_column(String(32), nullable=False)
    operation: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, default=dict)
    status: Mapped[str] = mapped_column(String(32), default="pending")
    retry_count: Mapped[int] = mapped_column(default=0)
    last_error: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())
