"""
传神智脑 —— CRUD 操作
"""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.brain.models import ApiConnector, BrainAgent, DataMapping, RuleExecution
from app.brain.schemas import (
    ApiConnectorCreate,
    ApiConnectorUpdate,
    BrainAgentCreate,
    BrainAgentUpdate,
    DataMappingCreate,
    DataMappingUpdate,
)


# ── API Connector ──

def create_connector(db: Session, payload: ApiConnectorCreate) -> ApiConnector:
    connector = ApiConnector(
        code=payload.code,
        name=payload.name,
        description=payload.description,
        base_url=payload.base_url,
        method=payload.method,
        headers=payload.headers,
        auth_type=payload.auth_type,
        auth_config=payload.auth_config,
        request_template=payload.request_template,
        space_id=payload.space_id,
        status=payload.status,
    )
    db.add(connector)
    db.commit()
    db.refresh(connector)
    return connector


def get_connector(db: Session, connector_id: str) -> ApiConnector | None:
    return db.get(ApiConnector, connector_id)


def list_connectors(db: Session, keyword: str = "", status: str = "") -> list[ApiConnector]:
    query = db.query(ApiConnector)
    if keyword:
        query = query.filter(
            (ApiConnector.name.ilike(f"%{keyword}%"))
            | (ApiConnector.code.ilike(f"%{keyword}%"))
        )
    if status:
        query = query.filter(ApiConnector.status == status)
    return query.order_by(ApiConnector.created_at.desc()).all()


def update_connector(
    db: Session, connector_id: str, payload: ApiConnectorUpdate
) -> ApiConnector | None:
    connector = db.get(ApiConnector, connector_id)
    if not connector:
        return None

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(connector, field, value)

    db.commit()
    db.refresh(connector)
    return connector


def delete_connector(db: Session, connector_id: str) -> bool:
    connector = db.get(ApiConnector, connector_id)
    if not connector:
        return False

    # 级联删除映射
    db.query(DataMapping).filter(DataMapping.connector_id == connector_id).delete()
    db.delete(connector)
    db.commit()
    return True


def serialize_connector(connector: ApiConnector) -> dict[str, Any]:
    return {
        "id": connector.id,
        "code": connector.code,
        "name": connector.name,
        "description": connector.description,
        "base_url": connector.base_url,
        "method": connector.method,
        "headers": connector.headers,
        "auth_type": connector.auth_type,
        "auth_config": connector.auth_config,
        "request_template": connector.request_template,
        "space_id": connector.space_id,
        "status": connector.status,
        "created_at": connector.created_at.isoformat() if connector.created_at else None,
        "updated_at": connector.updated_at.isoformat() if connector.updated_at else None,
    }


# ── Data Mapping ──

def create_mapping(db: Session, payload: DataMappingCreate) -> DataMapping:
    mapping = DataMapping(
        connector_id=payload.connector_id,
        source_field=payload.source_field,
        target_type=payload.target_type,
        target_code=payload.target_code,
        transform=payload.transform,
        is_key=payload.is_key,
        description=payload.description,
    )
    db.add(mapping)
    db.commit()
    db.refresh(mapping)
    return mapping


def get_mapping(db: Session, mapping_id: str) -> DataMapping | None:
    return db.get(DataMapping, mapping_id)


def list_mappings(db: Session, connector_id: str) -> list[DataMapping]:
    return (
        db.query(DataMapping)
        .filter(DataMapping.connector_id == connector_id)
        .order_by(DataMapping.created_at)
        .all()
    )


def update_mapping(
    db: Session, mapping_id: str, payload: DataMappingUpdate
) -> DataMapping | None:
    mapping = db.get(DataMapping, mapping_id)
    if not mapping:
        return None

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(mapping, field, value)

    db.commit()
    db.refresh(mapping)
    return mapping


def delete_mapping(db: Session, mapping_id: str) -> bool:
    mapping = db.get(DataMapping, mapping_id)
    if not mapping:
        return False
    db.delete(mapping)
    db.commit()
    return True


def serialize_mapping(mapping: DataMapping) -> dict[str, Any]:
    return {
        "id": mapping.id,
        "connector_id": mapping.connector_id,
        "source_field": mapping.source_field,
        "target_type": mapping.target_type,
        "target_code": mapping.target_code,
        "transform": mapping.transform,
        "is_key": mapping.is_key,
        "description": mapping.description,
        "created_at": mapping.created_at.isoformat() if mapping.created_at else None,
        "updated_at": mapping.updated_at.isoformat() if mapping.updated_at else None,
    }


# ── Rule Execution ──

def create_execution(
    db: Session,
    space_id: str,
    input_summary: dict[str, Any],
    trace: list[dict[str, Any]],
    hit_count: int,
    block_count: int,
    suggest_count: int,
    status: str = "success",
) -> RuleExecution:
    execution = RuleExecution(
        space_id=space_id,
        input_summary=input_summary,
        trace=trace,
        hit_count=hit_count,
        block_count=block_count,
        suggest_count=suggest_count,
        status=status,
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


def list_executions(db: Session, space_id: str, limit: int = 50) -> list[RuleExecution]:
    return (
        db.query(RuleExecution)
        .filter(RuleExecution.space_id == space_id)
        .order_by(RuleExecution.created_at.desc())
        .limit(limit)
        .all()
    )


def serialize_execution(execution: RuleExecution) -> dict[str, Any]:
    return {
        "id": execution.id,
        "space_id": execution.space_id,
        "input_summary": execution.input_summary,
        "status": execution.status,
        "hit_count": execution.hit_count,
        "block_count": execution.block_count,
        "suggest_count": execution.suggest_count,
        "trace": execution.trace,
        "created_at": execution.created_at.isoformat() if execution.created_at else None,
    }


# ── Brain Agent ──

def create_agent(db: Session, payload: BrainAgentCreate) -> BrainAgent:
    agent = BrainAgent(
        code=payload.code,
        name=payload.name,
        description=payload.description,
        connector_id=payload.connector_id,
        space_id=payload.space_id,
        strategy_type=payload.strategy_type,
        strategy_config=payload.strategy_config,
        status=payload.status,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


def get_agent(db: Session, agent_id: str) -> BrainAgent | None:
    return db.get(BrainAgent, agent_id)


def list_agents(db: Session, keyword: str = "", status: str = "") -> list[BrainAgent]:
    query = db.query(BrainAgent)
    if keyword:
        query = query.filter(
            (BrainAgent.name.ilike(f"%{keyword}%"))
            | (BrainAgent.code.ilike(f"%{keyword}%"))
        )
    if status:
        query = query.filter(BrainAgent.status == status)
    return query.order_by(BrainAgent.created_at.desc()).all()


def update_agent(
    db: Session, agent_id: str, payload: BrainAgentUpdate
) -> BrainAgent | None:
    agent = db.get(BrainAgent, agent_id)
    if not agent:
        return None

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(agent, field, value)

    db.commit()
    db.refresh(agent)
    return agent


def delete_agent(db: Session, agent_id: str) -> bool:
    agent = db.get(BrainAgent, agent_id)
    if not agent:
        return False
    db.delete(agent)
    db.commit()
    return True


def serialize_agent(agent: BrainAgent) -> dict[str, Any]:
    return {
        "id": agent.id,
        "code": agent.code,
        "name": agent.name,
        "description": agent.description,
        "connector_id": agent.connector_id,
        "space_id": agent.space_id,
        "strategy_type": agent.strategy_type,
        "strategy_config": agent.strategy_config,
        "status": agent.status,
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
        "updated_at": agent.updated_at.isoformat() if agent.updated_at else None,
    }
