from typing import Any

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.graph import GraphProjector, create_graph_task, run_graph_task
from app.models import (
    AuditLog,
    ElementStatus,
    ElementType,
    GraphSyncTask,
    OntologyElement,
    OntologySpace,
    ReferenceEdge,
    VersionRecord,
)
from app.schemas import ElementCreate, ElementUpdate, ReferenceInput, SpaceCreate
from app.templates import CONTRACT_TEMPLATE


RESOURCE_MAP = {
    "objects": ElementType.object,
    "properties": ElementType.property,
    "relations": ElementType.relation,
    "actions": ElementType.action,
    "scenarios": ElementType.scenario,
    "rules": ElementType.rule,
    "settings": ElementType.setting,
}


def serialize_element(element: OntologyElement) -> dict[str, Any]:
    return {
        "id": element.id,
        "space_id": element.space_id,
        "resource_type": element.resource_type,
        "code": element.code,
        "name": element.name,
        "description": element.description,
        "status": element.status,
        "version": element.version,
        "payload": element.payload or {},
        "created_at": isoformat(element.created_at),
        "updated_at": isoformat(element.updated_at),
    }


def serialize_space(space: OntologySpace) -> dict[str, Any]:
    return {
        "id": space.id,
        "tenant_id": space.tenant_id,
        "code": space.code,
        "name": space.name,
        "domain": space.domain,
        "template_code": space.template_code,
        "description": space.description,
        "status": space.status,
        "created_at": isoformat(space.created_at),
        "updated_at": isoformat(space.updated_at),
    }


def serialize_version(record: VersionRecord) -> dict[str, Any]:
    return {
        "id": record.id,
        "space_id": record.space_id,
        "resource_type": record.resource_type,
        "resource_id": record.resource_id,
        "version": record.version,
        "change_type": record.change_type,
        "diff": record.diff,
        "snapshot": record.snapshot,
        "created_by": record.created_by,
        "created_at": isoformat(record.created_at),
    }


def isoformat(value: Any) -> str:
    return value.isoformat() if hasattr(value, "isoformat") else str(value)


def create_space(db: Session, payload: SpaceCreate) -> OntologySpace:
    space = OntologySpace(**payload.model_dump())
    db.add(space)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Space code already exists") from exc
    db.refresh(space)
    return space


def get_default_space(db: Session, projector: GraphProjector | None = None) -> OntologySpace:
    ensure_demo_ontology(db, projector)
    space = db.execute(select(OntologySpace).limit(1)).scalar_one_or_none()
    if space:
        if projector and projector.is_available():
            sync_pending_tasks(db, projector)
        return space
    return initialize_contract_template(db, projector=projector)


def ensure_demo_ontology(db: Session, projector: GraphProjector | None = None) -> OntologySpace:
    existing = db.execute(
        select(OntologySpace).where(OntologySpace.code == CONTRACT_TEMPLATE["space"]["code"])
    ).scalar_one_or_none()
    if existing:
        if projector and projector.is_available():
            sync_pending_tasks(db, projector)
        return existing
    return initialize_contract_template(db, projector)


def initialize_contract_template(db: Session, projector: GraphProjector | None) -> OntologySpace:
    existing = db.execute(
        select(OntologySpace).where(OntologySpace.code == CONTRACT_TEMPLATE["space"]["code"])
    ).scalar_one_or_none()
    if existing:
        return existing

    space = OntologySpace(**CONTRACT_TEMPLATE["space"])
    db.add(space)
    db.flush()

    by_code: dict[str, OntologyElement] = {}
    for item in CONTRACT_TEMPLATE["elements"]:
        element = OntologyElement(
            space_id=space.id,
            resource_type=item["resource_type"],
            code=item["code"],
            name=item["name"],
            description=item["description"],
            status=ElementStatus.active,
            payload=item.get("payload", {}),
        )
        db.add(element)
        db.flush()
        by_code[item["code"]] = element
        add_version_and_audit(db, element, "create", {}, serialize_element(element))

    for source_code, edge_type, target_code in CONTRACT_TEMPLATE["edges"]:
        source = by_code[source_code]
        target = by_code[target_code]
        db.add(
            ReferenceEdge(
                space_id=space.id,
                source_type=source.resource_type,
                source_id=source.id,
                edge_type=edge_type,
                target_type=target.resource_type,
                target_id=target.id,
            )
        )

    for element in by_code.values():
        create_graph_task(db, element)

    db.commit()

    if projector:
        sync_pending_tasks(db, projector)
    db.refresh(space)
    return space


def list_elements(
    db: Session,
    space_id: str,
    resource: str,
    keyword: str = "",
    status: str = "",
    page: int = 1,
    page_size: int = 20,
) -> dict[str, Any]:
    resource_type = resolve_resource(resource)
    query = select(OntologyElement).where(
        OntologyElement.space_id == space_id,
        OntologyElement.resource_type == resource_type,
        OntologyElement.deleted_at.is_(None),
    )
    if keyword:
        like = f"%{keyword}%"
        query = query.where(or_(OntologyElement.name.ilike(like), OntologyElement.code.ilike(like)))
    if status:
        query = query.where(OntologyElement.status == status)

    total = len(db.execute(query).scalars().all())
    rows = (
        db.execute(
            query.order_by(OntologyElement.updated_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        .scalars()
        .all()
    )
    return {
        "items": [serialize_element(row) for row in rows],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_element(db: Session, space_id: str, resource: str, element_id: str) -> OntologyElement:
    resource_type = resolve_resource(resource)
    element = db.get(OntologyElement, element_id)
    if not element or element.space_id != space_id or element.resource_type != resource_type:
        raise HTTPException(status_code=404, detail="Element not found")
    return element


def create_element(
    db: Session,
    projector: GraphProjector | None,
    space_id: str,
    resource: str,
    payload: ElementCreate,
) -> OntologyElement:
    resource_type = resolve_resource(resource)
    element = OntologyElement(
        space_id=space_id,
        resource_type=resource_type,
        code=payload.code,
        name=payload.name,
        description=payload.description,
        status=payload.status,
        payload=payload.payload,
    )
    db.add(element)
    try:
        db.flush()
        replace_references(db, element, payload.references)
        task = create_graph_task(db, element)
        add_version_and_audit(db, element, "create", {}, serialize_element(element))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Element code already exists") from exc
    db.refresh(element)
    run_graph_task(db, projector, task)
    db.commit()
    return element


def update_element(
    db: Session,
    projector: GraphProjector | None,
    space_id: str,
    resource: str,
    element_id: str,
    payload: ElementUpdate,
) -> OntologyElement:
    element = get_element(db, space_id, resource, element_id)
    before = serialize_element(element)
    data = payload.model_dump(exclude_unset=True)
    references = data.pop("references", None)
    for key, value in data.items():
        setattr(element, key, value)
    element.version += 1
    db.add(element)
    if references is not None:
        replace_references(db, element, references)
    task = create_graph_task(db, element)
    add_version_and_audit(db, element, "update", before, serialize_element(element))
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Element code already exists") from exc
    db.refresh(element)
    run_graph_task(db, projector, task)
    db.commit()
    return element


def deactivate_element(
    db: Session,
    projector: GraphProjector | None,
    space_id: str,
    resource: str,
    element_id: str,
) -> OntologyElement:
    element = get_element(db, space_id, resource, element_id)
    before = serialize_element(element)
    element.status = ElementStatus.inactive
    element.version += 1
    task = create_graph_task(db, element)
    add_version_and_audit(db, element, "deactivate", before, serialize_element(element))
    db.commit()
    db.refresh(element)
    run_graph_task(db, projector, task)
    db.commit()
    return element


def copy_element(
    db: Session,
    projector: GraphProjector | None,
    space_id: str,
    resource: str,
    element_id: str,
) -> OntologyElement:
    source = get_element(db, space_id, resource, element_id)
    copy = OntologyElement(
        space_id=space_id,
        resource_type=source.resource_type,
        code=f"{source.code}_copy",
        name=f"{source.name} 副本",
        description=source.description,
        status=ElementStatus.draft,
        payload=source.payload,
    )
    db.add(copy)
    db.flush()
    refs = db.query(ReferenceEdge).filter(ReferenceEdge.source_id == source.id).all()
    for ref in refs:
        db.add(
            ReferenceEdge(
                space_id=space_id,
                source_type=copy.resource_type,
                source_id=copy.id,
                edge_type=ref.edge_type,
                target_type=ref.target_type,
                target_id=ref.target_id,
            )
        )
    task = create_graph_task(db, copy)
    add_version_and_audit(db, copy, "copy", {}, serialize_element(copy))
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        copy.code = f"{source.code}_copy_{copy.id[:6]}"
        db.add(copy)
        db.commit()
    db.refresh(copy)
    run_graph_task(db, projector, task)
    db.commit()
    return copy


def impact(db: Session, space_id: str, element_id: str) -> dict[str, list[dict[str, Any]]]:
    incoming = (
        db.query(ReferenceEdge)
        .filter(ReferenceEdge.space_id == space_id, ReferenceEdge.target_id == element_id)
        .all()
    )
    outgoing = (
        db.query(ReferenceEdge)
        .filter(ReferenceEdge.space_id == space_id, ReferenceEdge.source_id == element_id)
        .all()
    )
    ids = {edge.source_id for edge in incoming} | {edge.target_id for edge in outgoing}
    elements = db.query(OntologyElement).filter(OntologyElement.id.in_(ids)).all() if ids else []
    by_id = {item.id: item for item in elements}
    return {
        "incoming": [
            {
                "edge_type": edge.edge_type,
                "source": compact_element(by_id.get(edge.source_id)),
            }
            for edge in incoming
        ],
        "outgoing": [
            {
                "edge_type": edge.edge_type,
                "target": compact_element(by_id.get(edge.target_id)),
            }
            for edge in outgoing
        ],
    }


def compact_element(element: OntologyElement | None) -> dict[str, Any] | None:
    if element is None:
        return None
    return {
        "id": element.id,
        "resource_type": element.resource_type,
        "code": element.code,
        "name": element.name,
        "status": element.status,
    }


def summary(db: Session, space_id: str) -> dict[str, Any]:
    elements = (
        db.query(OntologyElement)
        .filter(OntologyElement.space_id == space_id, OntologyElement.deleted_at.is_(None))
        .all()
    )
    by_type: dict[str, int] = {}
    by_status: dict[str, int] = {}
    for element in elements:
        by_type[element.resource_type] = by_type.get(element.resource_type, 0) + 1
        by_status[element.status] = by_status.get(element.status, 0) + 1
    return {"by_type": by_type, "by_status": by_status, "total": len(elements)}


def replace_references(
    db: Session,
    element: OntologyElement,
    references: list[ReferenceInput],
) -> None:
    db.query(ReferenceEdge).filter(ReferenceEdge.source_id == element.id).delete()
    for ref in references:
        target = db.get(OntologyElement, ref.target_id)
        if not target or target.space_id != element.space_id:
            raise HTTPException(status_code=400, detail=f"Invalid reference target: {ref.target_id}")
        db.add(
            ReferenceEdge(
                space_id=element.space_id,
                source_type=element.resource_type,
                source_id=element.id,
                edge_type=ref.edge_type,
                target_type=ref.target_type,
                target_id=ref.target_id,
            )
        )


def add_version_and_audit(
    db: Session,
    element: OntologyElement,
    change_type: str,
    before: dict[str, Any],
    after: dict[str, Any],
) -> None:
    diff = build_diff(before, after)
    db.add(
        VersionRecord(
            space_id=element.space_id,
            resource_type=element.resource_type,
            resource_id=element.id,
            version=element.version,
            change_type=change_type,
            diff=diff,
            snapshot=after,
        )
    )
    db.add(
        AuditLog(
            space_id=element.space_id,
            action=change_type,
            resource_type=element.resource_type,
            resource_id=element.id,
            before=before,
            after=after,
        )
    )


def build_diff(before: dict[str, Any], after: dict[str, Any]) -> dict[str, Any]:
    keys = set(before) | set(after)
    return {
        key: {"before": before.get(key), "after": after.get(key)}
        for key in keys
        if before.get(key) != after.get(key)
    }


def resolve_resource(resource: str) -> str:
    if resource not in RESOURCE_MAP:
        raise HTTPException(status_code=404, detail="Unknown resource")
    return RESOURCE_MAP[resource]


def sync_pending_tasks(db: Session, projector: GraphProjector | None) -> int:
    tasks = db.query(GraphSyncTask).filter(GraphSyncTask.status.in_(["pending", "failed"])).limit(100).all()
    for task in tasks:
        run_graph_task(db, projector, task)
    db.commit()
    return len(tasks)
