from contextlib import suppress
from typing import Any

from neo4j import GraphDatabase
from neo4j.exceptions import Neo4jError, ServiceUnavailable
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import GraphSyncTask, OntologyElement, ReferenceEdge


LABELS = {
    "object": "ObjectType",
    "property": "Property",
    "relation": "RelationType",
    "action": "ActionType",
    "scenario": "Scenario",
    "rule": "Rule",
    "setting": "Setting",
}


class GraphProjector:
    def __init__(self) -> None:
        settings = get_settings()
        self.driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )

    def close(self) -> None:
        with suppress(Exception):
            self.driver.close()

    def is_available(self) -> bool:
        try:
            self.driver.verify_connectivity()
            return True
        except (Neo4jError, ServiceUnavailable, OSError):
            return False

    def ensure_constraints(self) -> None:
        with self.driver.session() as session:
            session.run(
                "CREATE CONSTRAINT ontology_node_id IF NOT EXISTS "
                "FOR (n:OntologyNode) REQUIRE n.id IS UNIQUE"
            )

    def upsert_element(self, element: OntologyElement, edges: list[ReferenceEdge]) -> None:
        self.upsert_node(element)
        with self.driver.session() as session:
            session.run(
                "MATCH (n:OntologyNode {id: $id})-[r]->() DELETE r",
                {"id": element.id},
            )
            for edge in edges:
                edge_type = safe_edge_type(edge.edge_type)
                session.run(
                    f"""
                    MATCH (source:OntologyNode {{id: $source_id}})
                    MATCH (target:OntologyNode {{id: $target_id}})
                    MERGE (source)-[r:{edge_type}]->(target)
                    SET r.status = $status
                    """,
                    {
                        "source_id": edge.source_id,
                        "target_id": edge.target_id,
                        "status": edge.status,
                    },
                )

    def upsert_node(self, element: OntologyElement) -> None:
        label = LABELS.get(element.resource_type, "OntologyNode")
        with self.driver.session() as session:
            session.run(
                f"""
                MERGE (n:OntologyNode:{label} {{id: $id}})
                SET n.tenant_id = $tenant_id,
                    n.space_id = $space_id,
                    n.resource_type = $resource_type,
                    n.code = $code,
                    n.name = $name,
                    n.status = $status,
                    n.version = $version,
                    n.description = $description
                """,
                {
                    "id": element.id,
                    "tenant_id": element.tenant_id,
                    "space_id": element.space_id,
                    "resource_type": element.resource_type,
                    "code": element.code,
                    "name": element.name,
                    "status": element.status,
                    "version": element.version,
                    "description": element.description,
                },
            )

    def deactivate_element(self, element: OntologyElement) -> None:
        with self.driver.session() as session:
            session.run(
                "MATCH (n:OntologyNode {id: $id}) SET n.status = $status",
                {"id": element.id, "status": element.status},
            )

    def local_graph(self, element_id: str, depth: int = 1) -> dict[str, list[dict[str, Any]]]:
        safe_depth = min(max(depth, 1), 2)
        with self.driver.session() as session:
            result = session.run(
                f"""
                MATCH path = (n:OntologyNode {{id: $id}})-[*0..{safe_depth}]-(m)
                WITH collect(path) AS paths
                CALL (paths) {{
                  UNWIND paths AS p
                  UNWIND nodes(p) AS node
                  RETURN collect(DISTINCT node) AS nodes
                }}
                CALL (paths) {{
                  UNWIND paths AS p
                  UNWIND relationships(p) AS rel
                  RETURN collect(DISTINCT rel) AS rels
                }}
                RETURN nodes, rels
                """,
                {"id": element_id},
            ).single()
        if not result:
            return {"nodes": [], "edges": []}
        nodes = [
            {
                "id": node["id"],
                "name": node.get("name", ""),
                "code": node.get("code", ""),
                "type": node.get("resource_type", ""),
                "status": node.get("status", ""),
            }
            for node in result["nodes"]
        ]
        edges = [
            {
                "source": rel.start_node["id"],
                "target": rel.end_node["id"],
                "type": rel.type,
                "status": rel.get("status", ""),
            }
            for rel in result["rels"]
        ]
        return {"nodes": nodes, "edges": edges}


def safe_edge_type(edge_type: str) -> str:
    return "".join(ch for ch in edge_type.upper() if ch.isalnum() or ch == "_")


def create_graph_task(
    db: Session,
    element: OntologyElement,
    operation: str = "upsert_node",
) -> GraphSyncTask:
    task = GraphSyncTask(
        tenant_id=element.tenant_id,
        space_id=element.space_id,
        resource_type=element.resource_type,
        resource_id=element.id,
        operation=operation,
        payload={},
    )
    db.add(task)
    return task


def run_graph_task(db: Session, projector: GraphProjector | None, task: GraphSyncTask) -> None:
    if projector is None or not projector.is_available():
        task.status = "failed"
        task.retry_count += 1
        task.last_error = "Neo4j is unavailable"
        db.add(task)
        return

    element = db.get(OntologyElement, task.resource_id)
    if element is None:
        task.status = "failed"
        task.last_error = "Element not found"
        db.add(task)
        return

    edges = (
        db.query(ReferenceEdge)
        .filter(ReferenceEdge.source_id == element.id, ReferenceEdge.status == "active")
        .all()
    )
    try:
        target_ids = [edge.target_id for edge in edges]
        if target_ids:
            targets = db.query(OntologyElement).filter(OntologyElement.id.in_(target_ids)).all()
            for target in targets:
                projector.upsert_node(target)
        projector.upsert_element(element, edges)
        task.status = "success"
        task.last_error = ""
    except Exception as exc:  # noqa: BLE001
        task.status = "failed"
        task.retry_count += 1
        task.last_error = str(exc)
    db.add(task)
