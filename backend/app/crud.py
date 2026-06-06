from typing import Any

from fastapi import HTTPException
from sqlalchemy import inspect, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.graph import GraphProjector, create_graph_task, run_graph_task
from app.models import (
    AuditLog,
    EdgeType,
    ElementStatus,
    ElementType,
    GraphSyncTask,
    OntologyElement,
    OntologySpace,
    ReferenceEdge,
    VersionRecord,
)
from app.schemas import ElementCreate, ElementUpdate, ReferenceInput, SpaceCreate, SpaceUpdate
from app.templates import CONTRACT_TEMPLATE


RESOURCE_MAP = {
    "objects": ElementType.object,
    "properties": ElementType.property,
    "relations": ElementType.relation,
    "actions": ElementType.action,
    "scenarios": ElementType.scenario,
    "rules": ElementType.rule,
    "functions": ElementType.function,
    "query-capabilities": ElementType.query_capability,
    "validation-cases": ElementType.validation_case,
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


def get_space(db: Session, space_id: str) -> OntologySpace:
    space = db.get(OntologySpace, space_id)
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")
    return space


def update_space(db: Session, space_id: str, payload: SpaceUpdate) -> OntologySpace:
    space = get_space(db, space_id)
    before = serialize_space(space)
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(space, key, value)
    db.add(
        VersionRecord(
            space_id=space.id,
            resource_type="space",
            resource_id=space.id,
            version=1,
            change_type="update",
            diff=build_diff(before, serialize_space(space)),
            snapshot=serialize_space(space),
        )
    )
    db.add(
        AuditLog(
            space_id=space.id,
            action="update",
            resource_type="space",
            resource_id=space.id,
            before=before,
            after=serialize_space(space),
        )
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Space code already exists") from exc
    db.refresh(space)
    return space


def deactivate_space(db: Session, space_id: str) -> OntologySpace:
    space = get_space(db, space_id)
    before = serialize_space(space)
    space.status = "inactive"
    after = serialize_space(space)
    db.add(
        VersionRecord(
            space_id=space.id,
            resource_type="space",
            resource_id=space.id,
            version=1,
            change_type="deactivate",
            diff=build_diff(before, after),
            snapshot=after,
        )
    )
    db.add(
        AuditLog(
            space_id=space.id,
            action="deactivate",
            resource_type="space",
            resource_id=space.id,
            before=before,
            after=after,
        )
    )
    db.commit()
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


def create_object_property(
    db: Session,
    projector: GraphProjector | None,
    space_id: str,
    object_id: str,
    payload: ElementCreate,
) -> OntologyElement:
    object_element = get_element(db, space_id, "objects", object_id)
    property_payload = dict(payload.payload or {})
    property_payload["object_code"] = object_element.code
    property_payload.setdefault("object_id", object_element.id)
    element = OntologyElement(
        space_id=space_id,
        resource_type=ElementType.property,
        code=payload.code,
        name=payload.name,
        description=payload.description,
        status=payload.status,
        payload=property_payload,
    )
    db.add(element)
    try:
        db.flush()
        db.add(
            ReferenceEdge(
                space_id=space_id,
                source_type=object_element.resource_type,
                source_id=object_element.id,
                edge_type=EdgeType.has_property,
                target_type=element.resource_type,
                target_id=element.id,
            )
        )
        if function_id := property_payload.get("calculation", {}).get("function_id"):
            function = db.get(OntologyElement, function_id)
            if not function or function.space_id != space_id or function.resource_type != ElementType.function:
                raise HTTPException(status_code=400, detail="Invalid calculation function")
            db.add(
                ReferenceEdge(
                    space_id=space_id,
                    source_type=element.resource_type,
                    source_id=element.id,
                    edge_type=EdgeType.computed_by,
                    target_type=function.resource_type,
                    target_id=function.id,
                )
            )
        task = create_graph_task(db, element)
        create_graph_task(db, object_element)
        add_version_and_audit(db, element, "create", {}, serialize_element(element))
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Element code already exists") from exc
    db.refresh(element)
    run_graph_task(db, projector, task)
    db.commit()
    return element


def create_action_rule(
    db: Session,
    projector: GraphProjector | None,
    space_id: str,
    action_id: str,
    payload: ElementCreate,
) -> OntologyElement:
    action = get_element(db, space_id, "actions", action_id)
    rule_payload = dict(payload.payload or {})
    rule_payload["action_code"] = action.code
    actions = rule_payload.get("actions")
    if not isinstance(actions, list):
        rule_payload["actions"] = [action.code]
    elif action.code not in actions:
        rule_payload["actions"] = [*actions, action.code]
    element = OntologyElement(
        space_id=space_id,
        resource_type=ElementType.rule,
        code=payload.code,
        name=payload.name,
        description=payload.description,
        status=payload.status,
        payload=rule_payload,
    )
    db.add(element)
    try:
        db.flush()
        db.add(
            ReferenceEdge(
                space_id=space_id,
                source_type=action.resource_type,
                source_id=action.id,
                edge_type=EdgeType.action_has_rule,
                target_type=element.resource_type,
                target_id=element.id,
            )
        )
        task = create_graph_task(db, element)
        create_graph_task(db, action)
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
    references = impact(db, space_id, element_id)
    if references["incoming"] and resource == "objects":
        raise HTTPException(
            status_code=409,
            detail={
                "requires_confirm": True,
                "message": "Element is referenced by other ontology assets",
                "impact": references,
            },
        )
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


def run_function_test(
    db: Session,
    space_id: str,
    function_id: str,
    input_data: Any,
    expected: Any = None,
) -> dict[str, Any]:
    function = get_element(db, space_id, "functions", function_id)
    function_type = (function.payload or {}).get("function_type", "count")
    actual = evaluate_function(function_type, input_data, function.payload or {})
    passed = expected is None or actual == expected
    return {
        "function_id": function.id,
        "function_type": function_type,
        "input_data": input_data,
        "expected": expected,
        "actual": actual,
        "passed": passed,
    }


def evaluate_function(function_type: str, input_data: Any, payload: dict[str, Any]) -> Any:
    values = extract_values(input_data, payload.get("value_field"))
    if function_type == "count":
        return len(values)
    if function_type == "sum":
        return sum(float(value) for value in values if is_number(value))
    if function_type == "max":
        numeric = [float(value) for value in values if is_number(value)]
        return max(numeric) if numeric else None
    if function_type == "min":
        numeric = [float(value) for value in values if is_number(value)]
        return min(numeric) if numeric else None
    if function_type == "last":
        return values[-1] if values else None
    if function_type == "threshold":
        threshold = payload.get("threshold", 0)
        operator = payload.get("operator", ">=")
        value = values[-1] if values else input_data
        if not is_number(value):
            return False
        number = float(value)
        threshold_number = float(threshold)
        return {
            ">": number > threshold_number,
            ">=": number >= threshold_number,
            "<": number < threshold_number,
            "<=": number <= threshold_number,
            "==": number == threshold_number,
        }.get(operator, False)
    raise HTTPException(status_code=400, detail=f"Unsupported function_type: {function_type}")


def extract_values(input_data: Any, value_field: str | None = None) -> list[Any]:
    if isinstance(input_data, list):
        if value_field:
            return [item.get(value_field) for item in input_data if isinstance(item, dict)]
        return input_data
    if isinstance(input_data, dict):
        if value_field and value_field in input_data:
            value = input_data[value_field]
        else:
            value = input_data.get("values", input_data)
        return value if isinstance(value, list) else [value]
    return [input_data]


def is_number(value: Any) -> bool:
    try:
        float(value)
        return True
    except (TypeError, ValueError):
        return False


def ontology_graph(db: Session, space_id: str) -> dict[str, Any]:
    get_space(db, space_id)
    objects = (
        db.query(OntologyElement)
        .filter(
            OntologyElement.space_id == space_id,
            OntologyElement.resource_type == ElementType.object,
            OntologyElement.deleted_at.is_(None),
        )
        .all()
    )
    relations = (
        db.query(OntologyElement)
        .filter(
            OntologyElement.space_id == space_id,
            OntologyElement.resource_type == ElementType.relation,
            OntologyElement.deleted_at.is_(None),
        )
        .all()
    )
    by_id = {item.id: item for item in objects}
    relation_edges = (
        db.query(ReferenceEdge)
        .filter(
            ReferenceEdge.space_id == space_id,
            ReferenceEdge.source_type == ElementType.relation,
            ReferenceEdge.edge_type.in_([EdgeType.relates_from, EdgeType.relates_to]),
        )
        .all()
    )
    endpoints: dict[str, dict[str, list[str]]] = {}
    for edge in relation_edges:
        endpoints.setdefault(edge.source_id, {"sources": [], "targets": []})
        if edge.edge_type == EdgeType.relates_from:
            endpoints[edge.source_id]["sources"].append(edge.target_id)
        if edge.edge_type == EdgeType.relates_to:
            endpoints[edge.source_id]["targets"].append(edge.target_id)
    edges = []
    for relation in relations:
        relation_endpoints = endpoints.get(relation.id, {"sources": [], "targets": []})
        for source_id in relation_endpoints["sources"]:
            for target_id in relation_endpoints["targets"]:
                if source_id in by_id and target_id in by_id:
                    edges.append(
                        {
                            "id": f"{relation.id}:{source_id}:{target_id}",
                            "relation_id": relation.id,
                            "relation_code": relation.code,
                            "label": relation.name,
                            "source_id": source_id,
                            "target_id": target_id,
                        }
                    )
    return {
        "nodes": [
            {
                "id": item.id,
                "code": item.code,
                "label": item.name,
                "resource_type": item.resource_type,
                "status": item.status,
            }
            for item in objects
        ],
        "edges": edges,
    }


def run_query_capability_test(
    db: Session,
    projector: GraphProjector | None,
    space_id: str,
    capability_id: str,
    inputs: dict[str, Any],
    limit: int,
) -> dict[str, Any]:
    capability = get_element(db, space_id, "query-capabilities", capability_id)
    kind = (capability.payload or {}).get("query_kind", "ontology_graph")
    if kind == "ontology_graph":
        result = ontology_graph(db, space_id)
    elif kind == "local_graph":
        start_node_id = inputs.get("start_node_id")
        if not start_node_id:
            raise HTTPException(status_code=400, detail="start_node_id is required")
        if projector and projector.is_available():
            result = projector.local_graph(start_node_id, depth=int(inputs.get("depth", 1)))
        else:
            result = {"nodes": [], "edges": [], "message": "Neo4j 不可用，查询能力已降级"}
    else:
        raise HTTPException(status_code=400, detail=f"Unsupported query_kind: {kind}")
    if "nodes" in result:
        result["nodes"] = result["nodes"][:limit]
    if "edges" in result:
        result["edges"] = result["edges"][:limit]
    return {"capability_id": capability.id, "query_kind": kind, "inputs": inputs, "result": result}


def run_validation(db: Session, space_id: str) -> dict[str, Any]:
    get_space(db, space_id)
    objects = list_elements(db, space_id, "objects", page_size=1000)["items"]
    relations = list_elements(db, space_id, "relations", page_size=1000)["items"]
    actions = list_elements(db, space_id, "actions", page_size=1000)["items"]
    functions = list_elements(db, space_id, "functions", page_size=1000)["items"]
    query_capabilities = list_elements(db, space_id, "query-capabilities", page_size=1000)["items"]
    checks = [
        {"code": "objects_exist", "name": "至少存在一个对象", "passed": bool(objects)},
        {"code": "relations_exist", "name": "至少存在一个关系", "passed": bool(relations)},
        {"code": "actions_exist", "name": "至少存在一个行为", "passed": bool(actions)},
        {
            "code": "dynamic_assets_ready",
            "name": "函数或查询能力至少存在一类",
            "passed": bool(functions or query_capabilities),
        },
    ]
    passed = all(check["passed"] for check in checks)
    result = {"space_id": space_id, "passed": passed, "checks": checks}
    db.add(
        VersionRecord(
            space_id=space_id,
            resource_type="validation",
            resource_id=space_id,
            version=1,
            change_type="run",
            diff={},
            snapshot=result,
        )
    )
    db.commit()
    return result


def publish_space(db: Session, space_id: str) -> dict[str, Any]:
    space = get_space(db, space_id)
    latest_validation = (
        db.query(VersionRecord)
        .filter(VersionRecord.space_id == space_id, VersionRecord.resource_type == "validation")
        .order_by(VersionRecord.created_at.desc())
        .first()
    )
    if not latest_validation or not latest_validation.snapshot.get("passed"):
        raise HTTPException(status_code=409, detail="Validation must pass before publish")
    package = {
        "package_id": f"{space.code}:v{latest_validation.id[:8]}",
        "space": serialize_space(space),
        "objects": list_elements(db, space_id, "objects", page_size=1000)["items"],
        "relations": list_elements(db, space_id, "relations", page_size=1000)["items"],
        "functions": list_elements(db, space_id, "functions", page_size=1000)["items"],
        "actions": list_elements(db, space_id, "actions", page_size=1000)["items"],
        "rules": list_elements(db, space_id, "rules", page_size=1000)["items"],
        "query_capabilities": list_elements(db, space_id, "query-capabilities", page_size=1000)[
            "items"
        ],
        "validation_report": latest_validation.snapshot,
    }
    db.add(
        VersionRecord(
            space_id=space_id,
            resource_type="space",
            resource_id=space_id,
            version=1,
            change_type="publish",
            diff={},
            snapshot=package,
        )
    )
    db.add(
        AuditLog(
            space_id=space_id,
            action="publish",
            resource_type="space",
            resource_id=space_id,
            before={},
            after=package,
        )
    )
    db.commit()
    return package


def sync_pending_tasks(db: Session, projector: GraphProjector | None) -> int:
    tasks = db.query(GraphSyncTask).filter(GraphSyncTask.status.in_(["pending", "failed"])).limit(100).all()
    for task in tasks:
        run_graph_task(db, projector, task)
    db.commit()
    return len(tasks)


def delete_space(db: Session, projector: GraphProjector | None, space_id: str) -> dict[str, int]:
    """级联删除单个空间及其所有关联数据"""
    space = db.get(OntologySpace, space_id)
    if not space:
        raise HTTPException(status_code=404, detail="Space not found")

    # 统计删除数量
    counts: dict[str, int] = {}
    table_names = set(inspect(db.get_bind()).get_table_names())

    def delete_optional_table(table_name: str, where_sql: str) -> None:
        if table_name not in table_names:
            return
        result = db.execute(text(f"DELETE FROM {table_name} WHERE {where_sql}"), {"space_id": space_id})
        counts[table_name] = result.rowcount or 0

    # 0. 删除智脑侧依赖数据，避免空间被外键引用时删除失败
    delete_optional_table(
        "brain_agent_executions",
        "agent_id IN (SELECT id FROM brain_agents WHERE space_id = :space_id)",
    )
    delete_optional_table(
        "brain_data_mappings",
        "connector_id IN (SELECT id FROM brain_api_connectors WHERE space_id = :space_id)",
    )
    delete_optional_table("brain_agents", "space_id = :space_id")
    delete_optional_table("brain_api_connectors", "space_id = :space_id")
    delete_optional_table("brain_rule_executions", "space_id = :space_id")

    # 1. 删除图同步任务
    counts["graph_sync_tasks"] = db.query(GraphSyncTask).filter(GraphSyncTask.space_id == space_id).delete(synchronize_session=False)

    # 2. 删除版本记录
    counts["version_records"] = db.query(VersionRecord).filter(VersionRecord.space_id == space_id).delete(synchronize_session=False)

    # 3. 删除审计日志
    counts["audit_logs"] = db.query(AuditLog).filter(AuditLog.space_id == space_id).delete(synchronize_session=False)

    # 4. 删除引用边
    counts["reference_edges"] = db.query(ReferenceEdge).filter(ReferenceEdge.space_id == space_id).delete(synchronize_session=False)

    # 5. 删除所有本体元素
    counts["elements"] = db.query(OntologyElement).filter(OntologyElement.space_id == space_id).delete(synchronize_session=False)

    # 6. 删除空间
    db.delete(space)
    db.commit()

    # 7. 清空 Neo4j 中该空间的节点
    if projector and projector.is_available():
        with projector.driver.session() as session:
            session.run("MATCH (n:OntologyNode {space_id: $space_id}) DETACH DELETE n", {"space_id": space_id})

    return counts
