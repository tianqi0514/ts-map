from fastapi import Depends, FastAPI
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


@app.post("/api/graph-sync/run")
def run_graph_sync(db: Session = Depends(get_db)) -> ApiResponse:
    count = crud.sync_pending_tasks(db, projector)
    return ApiResponse(data={"processed": count})
