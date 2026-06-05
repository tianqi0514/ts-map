from fastapi import Depends, FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from app import crud
from app.config import get_settings
from app.database import Base, SessionLocal, engine, get_db
from app.graph import GraphProjector
from app.models import OntologySpace, VersionRecord
from app.schemas import ApiResponse, ElementCreate, ElementUpdate, SpaceCreate

settings = get_settings()
app = FastAPI(title="传神智谱 API", version="0.1.0")
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
    from app.models import ElementStatus

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

    # 创建对象
    for code, spec in ontology.get("objects", {}).items():
        payload = ElementCreate(
            code=code,
            name=spec.get("label", code),
            description=f"{spec.get('label', code)}对象",
            status=ElementStatus.active,
            payload={
                "key": spec.get("key"),
                "fields": spec.get("fields", {}),
            },
            references=[],
        )
        crud.create_element(db, projector, space_id, "objects", payload)
        created_counts["objects"] += 1

    # 创建属性
    for code, spec in ontology.get("objects", {}).items():
        fields = spec.get("fields", {})
        for field_name, field_type in fields.items():
            prop_code = f"{code}.{field_name}"
            payload = ElementCreate(
                code=prop_code,
                name=field_name,
                description=f"{spec.get('label', code)}.{field_name}",
                status=ElementStatus.active,
                payload={"object_code": code, "data_type": str(field_type)},
                references=[],
            )
            crud.create_element(db, projector, space_id, "properties", payload)
            created_counts["properties"] += 1

    # 创建关系
    for link in ontology.get("links", []):
        rel_code = link["name"]
        to_value = link["to"]
        to_codes = to_value if isinstance(to_value, list) else [to_value]
        payload = ElementCreate(
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
        )
        crud.create_element(db, projector, space_id, "relations", payload)
        created_counts["relations"] += 1

    # 创建行为
    for behavior in ontology.get("behaviors", []):
        bcode = behavior["id"]
        payload = ElementCreate(
            code=bcode,
            name=behavior.get("label", bcode),
            description=behavior.get("effect", ""),
            status=ElementStatus.active,
            payload={"hook": behavior.get("hook"), "effect": behavior.get("effect"), "rules": []},
            references=[],
        )
        crud.create_element(db, projector, space_id, "actions", payload)
        created_counts["actions"] += 1

    # 创建规则
    for rule_type in ("hard", "soft"):
        for rule in ontology.get("rules", {}).get(rule_type, []):
            rcode = rule["id"]
            payload = ElementCreate(
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
            )
            crud.create_element(db, projector, space_id, "rules", payload)
            created_counts["rules"] += 1

    # 触发图同步
    crud.sync_pending_tasks(db, projector)

    return ApiResponse(data={"space_id": space_id, "created": created_counts})
