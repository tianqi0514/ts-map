from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import crud
from app.brain import api as brain_api
from app.config import get_settings
from app.config_module import api as config_api
from app.database import Base, SessionLocal, engine, get_db
from app.graph import GraphProjector
from app.models import OntologyElement, OntologySpace, VersionRecord
from app.schemas import ApiResponse, ElementCreate, ElementUpdate, SpaceCreate

settings = get_settings()
app = FastAPI(title="传神智谱 API", version="0.1.0")
app.include_router(brain_api.router)
app.include_router(config_api.router)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

projector: GraphProjector | None = None


@app.on_event("startup")
def startup() -> None:
    global projector
    Base.metadata.create_all(bind=engine)
    projector = GraphProjector()
    if projector.is_available():
        projector.ensure_constraints()
    with SessionLocal() as db:
        crud.get_default_space(db, projector)


@app.on_event("shutdown")
def shutdown() -> None:
    if projector:
        projector.close()


@app.get("/health")
def health() -> ApiResponse:
    neo4j = projector.is_available() if projector else False
    return ApiResponse(data={"status": "ok", "neo4j": neo4j})


@app.get("/api/spaces")
def list_spaces(db: Session = Depends(get_db)) -> ApiResponse:
    spaces = db.execute(select(OntologySpace).order_by(OntologySpace.created_at)).scalars().all()
    return ApiResponse(data=[crud.serialize_space(space) for space in spaces])


@app.post("/api/spaces")
def create_space(payload: SpaceCreate, db: Session = Depends(get_db)) -> ApiResponse:
    return ApiResponse(data=crud.serialize_space(crud.create_space(db, payload)))


@app.post("/api/spaces/initialize-contract-template")
def initialize_contract_template(db: Session = Depends(get_db)) -> ApiResponse:
    space = crud.initialize_contract_template(db, projector)
    return ApiResponse(data=crud.serialize_space(space))


@app.get("/api/ontology/{space_id}/{resource}")
def list_elements(
    space_id: str,
    resource: str,
    keyword: str = "",
    status: str = "",
    page: int = 1,
    page_size: int = 20,
    db: Session = Depends(get_db),
) -> ApiResponse:
    return ApiResponse(data=crud.list_elements(db, space_id, resource, keyword, status, page, page_size))


@app.get("/api/spaces/{space_id}/summary")
def get_summary(space_id: str, db: Session = Depends(get_db)) -> ApiResponse:
    return ApiResponse(data=crud.summary(db, space_id))


@app.post("/api/ontology/{space_id}/{resource}")
def create_element(
    space_id: str,
    resource: str,
    payload: ElementCreate,
    db: Session = Depends(get_db),
) -> ApiResponse:
    element = crud.create_element(db, projector, space_id, resource, payload)
    return ApiResponse(data=crud.serialize_element(element))


@app.get("/api/ontology/{space_id}/{resource}/{element_id}")
def get_element(space_id: str, resource: str, element_id: str, db: Session = Depends(get_db)) -> ApiResponse:
    element = crud.get_element(db, space_id, resource, element_id)
    return ApiResponse(data=crud.serialize_element(element))


@app.put("/api/ontology/{space_id}/{resource}/{element_id}")
def update_element(
    space_id: str,
    resource: str,
    element_id: str,
    payload: ElementUpdate,
    db: Session = Depends(get_db),
) -> ApiResponse:
    element = crud.update_element(db, projector, space_id, resource, element_id, payload)
    return ApiResponse(data=crud.serialize_element(element))


@app.post("/api/ontology/{space_id}/{resource}/{element_id}/deactivate")
def deactivate_element(
    space_id: str,
    resource: str,
    element_id: str,
    db: Session = Depends(get_db),
) -> ApiResponse:
    element = crud.deactivate_element(db, projector, space_id, resource, element_id)
    return ApiResponse(data=crud.serialize_element(element))


@app.post("/api/ontology/{space_id}/{resource}/{element_id}/copy")
def copy_element(space_id: str, resource: str, element_id: str, db: Session = Depends(get_db)) -> ApiResponse:
    element = crud.copy_element(db, projector, space_id, resource, element_id)
    return ApiResponse(data=crud.serialize_element(element))


@app.get("/api/ontology/{space_id}/{resource}/{element_id}/impact")
def get_impact(space_id: str, resource: str, element_id: str, db: Session = Depends(get_db)) -> ApiResponse:
    crud.get_element(db, space_id, resource, element_id)
    return ApiResponse(data=crud.impact(db, space_id, element_id))


@app.get("/api/ontology/{space_id}/{resource}/{element_id}/local-graph")
def get_local_graph(
    space_id: str,
    resource: str,
    element_id: str,
    depth: int = 1,
    db: Session = Depends(get_db),
) -> ApiResponse:
    crud.get_element(db, space_id, resource, element_id)
    if projector and projector.is_available():
        return ApiResponse(data=projector.local_graph(element_id, depth))
    return ApiResponse(data={"nodes": [], "edges": [], "message": "图视图同步中或 Neo4j 不可用"})


class GraphTraversePayload(BaseModel):
    start_node_id: str
    direction: str = "both"
    max_depth: int = 2
    edge_types: list[str] | None = None
    node_types: list[str] | None = None
    limit: int = 100


@app.post("/api/graph/traverse")
def graph_traverse(payload: GraphTraversePayload, db: Session = Depends(get_db)) -> ApiResponse:
    """图遍历：从指定节点出发按条件遍历图"""
    if not projector or not projector.is_available():
        return ApiResponse(data={"nodes": [], "edges": [], "paths": [], "message": "Neo4j 不可用"})

    # 验证起始节点存在
    element = db.get(OntologyElement, payload.start_node_id)
    if not element:
        raise HTTPException(status_code=404, detail="Start node not found")

    result = projector.traverse(
        space_id=element.space_id,
        start_node_id=payload.start_node_id,
        direction=payload.direction,
        max_depth=payload.max_depth,
        edge_types=payload.edge_types,
        node_types=payload.node_types,
        limit=payload.limit,
    )
    return ApiResponse(data=result)


@app.get("/api/spaces/{space_id}/versions")
def list_versions(space_id: str, db: Session = Depends(get_db)) -> ApiResponse:
    rows = (
        db.execute(
            select(VersionRecord)
            .where(VersionRecord.space_id == space_id)
            .order_by(VersionRecord.created_at.desc())
            .limit(200)
    )
    .scalars()
    .all()
    )
    return ApiResponse(data=[crud.serialize_version(row) for row in rows])


@app.delete("/api/spaces/{space_id}")
def delete_space(space_id: str, db: Session = Depends(get_db)) -> ApiResponse:
    """级联删除单个空间及其所有关联数据"""
    counts = crud.delete_space(db, projector, space_id)
    return ApiResponse(data={"deleted": counts})


@app.post("/api/graph-sync/run")
def run_graph_sync(db: Session = Depends(get_db)) -> ApiResponse:
    count = crud.sync_pending_tasks(db, projector)
    return ApiResponse(data={"processed": count})


@app.post("/api/admin/import-yaml")
def admin_import_yaml(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ApiResponse:
    """从上传的 YAML 文件批量导入本体"""
    import yaml
    from app.models import ElementStatus, OntologyElement, ReferenceEdge
    from app.graph import create_graph_task

    content = file.file.read().decode("utf-8")
    data = yaml.safe_load(content)

    # 创建空间
    space_cfg = data.get("space", {})
    from app.models import OntologySpace

    existing = db.execute(
        select(OntologySpace).where(OntologySpace.code == space_cfg.get("code"))
    ).scalar_one_or_none()
    if existing:
        space = existing
    else:
        space = crud.create_space(
            db,
            SpaceCreate(
                code=space_cfg.get("code", "imported_ontology"),
                name=space_cfg.get("name", "导入的本体"),
                domain=space_cfg.get("domain", "custom"),
                description=space_cfg.get("description", ""),
            ),
        )
    space_id = space.id

    ontology = data.get("ontology", data)
    created_counts: dict[str, int] = {"objects": 0, "properties": 0, "relations": 0, "actions": 0, "rules": 0}

    # 维护 code -> element 映射，用于后续创建引用边
    by_code: dict[str, OntologyElement] = {}

    def _create(resource: str, code: str, payload_data: ElementCreate) -> OntologyElement:
        element = crud.create_element(db, projector, space_id, resource, payload_data)
        by_code[code] = element
        created_counts[resource] += 1
        return element

    # 创建对象
    for code, spec in ontology.get("objects", {}).items():
        _create(
            "objects",
            code,
            ElementCreate(
                code=code,
                name=spec.get("label", code),
                description=f"{spec.get('label', code)}对象",
                status=ElementStatus.active,
                payload={"key": spec.get("key"), "fields": spec.get("fields", {})},
                references=[],
            ),
        )

    # 创建属性
    for code, spec in ontology.get("objects", {}).items():
        fields = spec.get("fields", {})
        for field_name, field_type in fields.items():
            prop_code = f"{code}.{field_name}"
            _create(
                "properties",
                prop_code,
                ElementCreate(
                    code=prop_code,
                    name=field_name,
                    description=f"{spec.get('label', code)}.{field_name}",
                    status=ElementStatus.active,
                    payload={"object_code": code, "data_type": str(field_type)},
                    references=[],
                ),
            )

    # 创建关系
    for link in ontology.get("links", []):
        rel_code = link["name"]
        to_value = link["to"]
        to_codes = to_value if isinstance(to_value, list) else [to_value]
        _create(
            "relations",
            rel_code,
            ElementCreate(
                code=rel_code,
                name=link.get("label", rel_code),
                description=f"{link.get('label', rel_code)}: {link['from']} -> {', '.join(to_codes)}",
                status=ElementStatus.active,
                payload={
                    "source_code": link["from"],
                    "target_codes": to_codes,
                    "cardinality": link.get("card"),
                    "traversable": link.get("traversable", False),
                },
                references=[],
            ),
        )

    # 创建行为
    for behavior in ontology.get("behaviors", []):
        bcode = behavior["id"]
        _create(
            "actions",
            bcode,
            ElementCreate(
                code=bcode,
                name=behavior.get("label", bcode),
                description=behavior.get("effect", ""),
                status=ElementStatus.active,
                payload={"hook": behavior.get("hook"), "effect": behavior.get("effect"), "rules": []},
                references=[],
            ),
        )

    # 创建规则
    for rule_type in ("hard", "soft"):
        for rule in ontology.get("rules", {}).get(rule_type, []):
            rcode = rule["id"]
            _create(
                "rules",
                rcode,
                ElementCreate(
                    code=rcode,
                    name=rule.get("label", rcode),
                    description=f"{rule.get('when', '')} -> {rule.get('then', '')}",
                    status=ElementStatus.active,
                    payload={
                        "rule_type": "硬规则" if rule_type == "hard" else "软规则",
                        "priority": rule.get("priority"),
                        "condition": rule.get("when"),
                        "result": rule.get("then"),
                    },
                    references=[],
                ),
            )

    # ── 创建引用边（ReferenceEdge）──
    # 1. 属性 -> 对象 (HAS_PROPERTY)
    for code, spec in ontology.get("objects", {}).items():
        obj = by_code.get(code)
        if not obj:
            continue
        for field_name in spec.get("fields", {}).keys():
            prop = by_code.get(f"{code}.{field_name}")
            if prop:
                db.add(
                    ReferenceEdge(
                        space_id=space_id,
                        source_type=obj.resource_type,
                        source_id=obj.id,
                        edge_type="HAS_PROPERTY",
                        target_type=prop.resource_type,
                        target_id=prop.id,
                    )
                )

    # 2. 关系 -> 源对象 / 目标对象
    for link in ontology.get("links", []):
        rel = by_code.get(link["name"])
        if not rel:
            continue
        src = by_code.get(link["from"])
        if src:
            db.add(
                ReferenceEdge(
                    space_id=space_id,
                    source_type=rel.resource_type,
                    source_id=rel.id,
                    edge_type="SOURCE",
                    target_type=src.resource_type,
                    target_id=src.id,
                )
            )
        to_value = link["to"]
        to_codes = to_value if isinstance(to_value, list) else [to_value]
        for tc in to_codes:
            tgt = by_code.get(tc)
            if tgt:
                db.add(
                    ReferenceEdge(
                        space_id=space_id,
                        source_type=rel.resource_type,
                        source_id=rel.id,
                        edge_type="TARGET",
                        target_type=tgt.resource_type,
                        target_id=tgt.id,
                    )
                )

    # 3. 行为 -> 规则（反向：规则引用行为）
    # 从规则 payload 中提取引用的行为
    behavior_codes = {b["id"] for b in ontology.get("behaviors", [])}
    for rule_type in ("hard", "soft"):
        for rule in ontology.get("rules", {}).get(rule_type, []):
            rule_elem = by_code.get(rule["id"])
            if not rule_elem:
                continue
            then_text = str(rule.get("then", ""))
            for bcode in behavior_codes:
                if bcode in then_text:
                    beh = by_code.get(bcode)
                    if beh:
                        db.add(
                            ReferenceEdge(
                                space_id=space_id,
                                source_type=rule_elem.resource_type,
                                source_id=rule_elem.id,
                                edge_type="TRIGGERS",
                                target_type=beh.resource_type,
                                target_id=beh.id,
                            )
                        )

    db.commit()

    # ── 同步所有元素到 Neo4j（含新引用边）──
    for element in by_code.values():
        edges = (
            db.query(ReferenceEdge)
            .filter(ReferenceEdge.source_id == element.id, ReferenceEdge.status == "active")
            .all()
        )
        if projector and projector.is_available():
            projector.upsert_element(element, edges)

    return ApiResponse(data={"space_id": space_id, "created": created_counts})
