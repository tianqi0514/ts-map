from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import inspect, text

from app.database import SessionLocal
from app.main import app
from app.models import AuditLog, EdgeType, OntologySpace, ReferenceEdge, VersionRecord


def unique_code(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex[:10]}"


def api_data(response):
    assert response.status_code < 400, response.text
    body = response.json()
    assert body["success"] is True
    return body["data"]


def create_space(client: TestClient, prefix: str = "test_space") -> dict:
    code = unique_code(prefix)
    return api_data(
        client.post(
            "/api/spaces",
            json={
                "code": code,
                "name": f"测试本体 {code}",
                "domain": "contract_review",
                "description": "pytest generated",
            },
        )
    )


def delete_space(client: TestClient, space_id: str) -> None:
    client.delete(f"/api/spaces/{space_id}")


def create_element(client: TestClient, space_id: str, resource: str, payload: dict) -> dict:
    return api_data(client.post(f"/api/ontology/{space_id}/{resource}", json=payload))


def test_space_update_deactivate_and_duplicate_create():
    with TestClient(app) as client:
        space = create_space(client, "space_crud")
        try:
            duplicate = client.post(
                "/api/spaces",
                json={"code": space["code"], "name": "重复本体", "domain": "contract_review"},
            )
            assert duplicate.status_code == 409

            updated = api_data(
                client.put(
                    f"/api/spaces/{space['id']}",
                    json={"name": "更新后的本体", "description": "已更新"},
                )
            )
            assert updated["name"] == "更新后的本体"
            assert updated["description"] == "已更新"

            deactivated = api_data(client.post(f"/api/spaces/{space['id']}/deactivate"))
            assert deactivated["status"] == "inactive"

            missing = client.put("/api/spaces/not-exists", json={"name": "missing"})
            assert missing.status_code == 404

            with SessionLocal() as db:
                audit = (
                    db.query(AuditLog)
                    .filter(AuditLog.space_id == space["id"], AuditLog.action == "deactivate")
                    .first()
                )
                assert audit is not None
        finally:
            delete_space(client, space["id"])


def test_delete_space_cleans_brain_side_references_if_tables_exist():
    with TestClient(app) as client:
        space = create_space(client, "delete_with_brain")
        connector_id = uuid4().hex
        agent_id = uuid4().hex
        execution_id = uuid4().hex
        mapping_id = uuid4().hex
        rule_execution_id = uuid4().hex
        try:
            with SessionLocal() as db:
                tables = set(inspect(db.bind).get_table_names()) if db.bind else set()
                if not {
                    "brain_api_connectors",
                    "brain_agents",
                    "brain_agent_executions",
                    "brain_data_mappings",
                    "brain_rule_executions",
                }.issubset(tables):
                    return
                db.execute(
                    text(
                        """
                        INSERT INTO brain_api_connectors (
                            id, tenant_id, code, name, description, base_url, method,
                            headers, auth_type, auth_config, request_template, space_id, status
                        )
                        VALUES (
                            :id, 'default', :code, '合同系统连接器', '', 'http://example.test',
                            'POST', '{}', 'none', '{}', '{}', :space_id, 'active'
                        )
                        """
                    ),
                    {"id": connector_id, "code": unique_code("connector"), "space_id": space["id"]},
                )
                db.execute(
                    text(
                        """
                        INSERT INTO brain_agents (
                            id, tenant_id, code, name, description, connector_id, space_id,
                            strategy_type, strategy_config, status
                        )
                        VALUES (
                            :id, 'default', :code, '合同风控Agent', '', :connector_id, :space_id,
                            'rule_first', '{}', 'active'
                        )
                        """
                    ),
                    {
                        "id": agent_id,
                        "code": unique_code("agent"),
                        "connector_id": connector_id,
                        "space_id": space["id"],
                    },
                )
                db.execute(
                    text(
                        """
                        INSERT INTO brain_agent_executions (
                            id, tenant_id, agent_id, input_data, result, status
                        )
                        VALUES (:id, 'default', :agent_id, '{}', '{}', 'success')
                        """
                    ),
                    {"id": execution_id, "agent_id": agent_id},
                )
                db.execute(
                    text(
                        """
                        INSERT INTO brain_data_mappings (
                            id, tenant_id, connector_id, source_field, target_type,
                            target_code, transform, is_key, description
                        )
                        VALUES (
                            :id, 'default', :connector_id, 'amount', 'object',
                            'Contract', 'raw', true, ''
                        )
                        """
                    ),
                    {"id": mapping_id, "connector_id": connector_id},
                )
                db.execute(
                    text(
                        """
                        INSERT INTO brain_rule_executions (
                            id, tenant_id, space_id, input_summary, status,
                            hit_count, block_count, suggest_count, trace
                        )
                        VALUES (:id, 'default', :space_id, '{}', 'success', 1, 0, 1, '{}')
                        """
                    ),
                    {"id": rule_execution_id, "space_id": space["id"]},
                )
                db.commit()

            deleted = api_data(client.delete(f"/api/spaces/{space['id']}"))["deleted"]
            assert deleted["brain_agent_executions"] == 1
            assert deleted["brain_data_mappings"] == 1
            assert deleted["brain_agents"] == 1
            assert deleted["brain_api_connectors"] == 1
            assert deleted["brain_rule_executions"] == 1

            with SessionLocal() as db:
                assert db.get(OntologySpace, space["id"]) is None
        finally:
            delete_space(client, space["id"])


def test_create_object_property_creates_has_property_reference():
    with TestClient(app) as client:
        space = create_space(client, "property_api")
        try:
            obj = create_element(
                client,
                space["id"],
                "objects",
                {"code": unique_code("Contract"), "name": "合同", "payload": {"aliases": ["协议"]}},
            )
            prop = api_data(
                client.post(
                    f"/api/ontology/{space['id']}/objects/{obj['id']}/properties",
                    json={
                        "code": unique_code("Contract.amount"),
                        "name": "合同金额",
                        "description": "合同总金额",
                        "payload": {"data_type": "number", "display_name": "合同金额"},
                    },
                )
            )
            assert prop["resource_type"] == "property"
            assert prop["payload"]["object_code"] == obj["code"]
            assert prop["payload"]["data_type"] == "number"

            with SessionLocal() as db:
                edge = (
                    db.query(ReferenceEdge)
                    .filter(
                        ReferenceEdge.source_id == obj["id"],
                        ReferenceEdge.target_id == prop["id"],
                        ReferenceEdge.edge_type == EdgeType.has_property,
                    )
                    .first()
                )
                assert edge is not None

            missing = client.post(
                f"/api/ontology/{space['id']}/objects/not-found/properties",
                json={"code": unique_code("missing.prop"), "name": "缺失属性"},
            )
            assert missing.status_code == 404
        finally:
            delete_space(client, space["id"])


def test_function_test_endpoint_success_and_unsupported_type():
    with TestClient(app) as client:
        space = create_space(client, "function_api")
        try:
            function = create_element(
                client,
                space["id"],
                "functions",
                {
                    "code": unique_code("sum_amount"),
                    "name": "金额求和",
                    "payload": {"function_type": "sum", "value_field": "amount"},
                },
            )
            result = api_data(
                client.post(
                    f"/api/ontology/{space['id']}/functions/{function['id']}/test",
                    json={
                        "input_data": [{"amount": 1}, {"amount": "2.5"}, {"amount": 3}],
                        "expected": 6.5,
                    },
                )
            )
            assert result["actual"] == 6.5
            assert result["passed"] is True

            bad_function = create_element(
                client,
                space["id"],
                "functions",
                {
                    "code": unique_code("bad_function"),
                    "name": "未知函数",
                    "payload": {"function_type": "does_not_exist"},
                },
            )
            failed = client.post(
                f"/api/ontology/{space['id']}/functions/{bad_function['id']}/test",
                json={"input_data": [1, 2]},
            )
            assert failed.status_code == 400
        finally:
            delete_space(client, space["id"])


def test_create_action_rule_creates_action_has_rule_reference():
    with TestClient(app) as client:
        space = create_space(client, "action_rule_api")
        try:
            action = create_element(
                client,
                space["id"],
                "actions",
                {"code": unique_code("RequireReview"), "name": "要求人工复核"},
            )
            rule = api_data(
                client.post(
                    f"/api/ontology/{space['id']}/actions/{action['id']}/rules",
                    json={
                        "code": unique_code("high_amount_rule"),
                        "name": "高金额触发复核",
                        "payload": {
                            "rule_type": "硬规则",
                            "condition": "合同金额超过阈值",
                            "result": "触发人工复核",
                        },
                    },
                )
            )
            assert rule["resource_type"] == "rule"
            assert rule["payload"]["action_code"] == action["code"]
            assert action["code"] in rule["payload"]["actions"]

            with SessionLocal() as db:
                edge = (
                    db.query(ReferenceEdge)
                    .filter(
                        ReferenceEdge.source_id == action["id"],
                        ReferenceEdge.target_id == rule["id"],
                        ReferenceEdge.edge_type == EdgeType.action_has_rule,
                    )
                    .first()
                )
                assert edge is not None

            missing = client.post(
                f"/api/ontology/{space['id']}/actions/not-found/rules",
                json={"code": unique_code("missing_action_rule"), "name": "缺失行为规则"},
            )
            assert missing.status_code == 404
        finally:
            delete_space(client, space["id"])


def test_query_validation_publish_and_graph_contract():
    with TestClient(app) as client:
        space = create_space(client, "publish_api")
        try:
            contract = create_element(
                client,
                space["id"],
                "objects",
                {"code": unique_code("Contract"), "name": "合同"},
            )
            party = create_element(
                client,
                space["id"],
                "objects",
                {"code": unique_code("Party"), "name": "合同主体"},
            )
            relation = create_element(
                client,
                space["id"],
                "relations",
                {
                    "code": unique_code("binds"),
                    "name": "约束",
                    "payload": {
                        "source_code": contract["code"],
                        "target_codes": [party["code"]],
                    },
                    "references": [
                        {
                            "edge_type": EdgeType.relates_from,
                            "target_type": "object",
                            "target_id": contract["id"],
                        },
                        {
                            "edge_type": EdgeType.relates_to,
                            "target_type": "object",
                            "target_id": party["id"],
                        },
                    ],
                },
            )
            action = create_element(
                client,
                space["id"],
                "actions",
                {"code": unique_code("Review"), "name": "触发复核"},
            )
            function = create_element(
                client,
                space["id"],
                "functions",
                {
                    "code": unique_code("count_items"),
                    "name": "计数",
                    "payload": {"function_type": "count"},
                },
            )
            capability = create_element(
                client,
                space["id"],
                "query-capabilities",
                {
                    "code": unique_code("ontology_graph"),
                    "name": "本体图谱读取",
                    "payload": {"query_kind": "ontology_graph"},
                },
            )

            graph = api_data(client.get(f"/api/ontology/{space['id']}/graph"))
            assert {node["id"] for node in graph["nodes"]} == {contract["id"], party["id"]}
            assert graph["edges"][0]["relation_id"] == relation["id"]
            assert set(graph["nodes"][0]) == {"id", "code", "label", "resource_type", "status"}

            query_result = api_data(
                client.post(
                    f"/api/ontology/{space['id']}/query-capabilities/{capability['id']}/test",
                    json={"inputs": {}, "limit": 10},
                )
            )
            assert query_result["result"]["nodes"]
            assert query_result["query_kind"] == "ontology_graph"

            validation = api_data(client.post(f"/api/ontology/{space['id']}/validation/run"))
            assert validation["passed"] is True

            package = api_data(client.post(f"/api/ontology/{space['id']}/publish"))
            assert package["space"]["id"] == space["id"]
            assert package["objects"]
            assert package["functions"][0]["id"] == function["id"]
            assert package["actions"][0]["id"] == action["id"]
            assert package["query_capabilities"][0]["id"] == capability["id"]

            with SessionLocal() as db:
                publish_record = (
                    db.query(VersionRecord)
                    .filter(
                        VersionRecord.space_id == space["id"],
                        VersionRecord.change_type == "publish",
                    )
                    .first()
                )
                assert publish_record is not None
        finally:
            delete_space(client, space["id"])


def test_publish_requires_validation_and_deactivate_referenced_object_returns_409():
    with TestClient(app) as client:
        space = create_space(client, "guard_api")
        try:
            source = create_element(
                client,
                space["id"],
                "objects",
                {"code": unique_code("Source"), "name": "源对象"},
            )
            target = create_element(
                client,
                space["id"],
                "objects",
                {"code": unique_code("Target"), "name": "目标对象"},
            )
            create_element(
                client,
                space["id"],
                "relations",
                {
                    "code": unique_code("references_target"),
                    "name": "引用目标",
                    "references": [
                        {
                            "edge_type": EdgeType.relates_from,
                            "target_type": "object",
                            "target_id": source["id"],
                        },
                        {
                            "edge_type": EdgeType.relates_to,
                            "target_type": "object",
                            "target_id": target["id"],
                        },
                    ],
                },
            )

            publish = client.post(f"/api/ontology/{space['id']}/publish")
            assert publish.status_code == 409

            deactivated = client.post(
                f"/api/ontology/{space['id']}/objects/{target['id']}/deactivate"
            )
            assert deactivated.status_code == 409
            detail = deactivated.json()["detail"]
            assert detail["requires_confirm"] is True
            assert detail["impact"]["incoming"]
        finally:
            delete_space(client, space["id"])
