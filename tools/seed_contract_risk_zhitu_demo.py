#!/usr/bin/env python3
"""Seed a complete contract-risk Zhitu ontology demo through public APIs.

Usage:
    python tools/seed_contract_risk_zhitu_demo.py --api-base http://localhost:9010
"""

from __future__ import annotations

import argparse
import json
import sys
import urllib.error
import urllib.parse
import urllib.request
from typing import Any


class ApiClient:
    def __init__(self, api_base: str) -> None:
        self.api_base = api_base.rstrip("/")

    def request(self, method: str, path: str, body: dict[str, Any] | None = None) -> Any:
        data = None
        headers = {"Content-Type": "application/json"}
        if body is not None:
            data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            f"{self.api_base}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            message = exc.read().decode("utf-8")
            raise RuntimeError(f"{method} {path} failed: {exc.code} {message}") from exc
        except urllib.error.URLError as exc:
            raise RuntimeError(f"Cannot connect to {self.api_base}: {exc}") from exc
        if not payload.get("success", False):
            raise RuntimeError(f"{method} {path} failed: {payload}")
        return payload.get("data")

    def get(self, path: str) -> Any:
        return self.request("GET", path)

    def post(self, path: str, body: dict[str, Any] | None = None) -> Any:
        return self.request("POST", path, body or {})

    def put(self, path: str, body: dict[str, Any]) -> Any:
        return self.request("PUT", path, body)

    def delete(self, path: str) -> Any:
        return self.request("DELETE", path)


def element_payload(
    code: str,
    name: str,
    description: str,
    payload: dict[str, Any] | None = None,
    references: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "code": code,
        "name": name,
        "description": description,
        "status": "active",
        "payload": payload or {},
        "references": references or [],
    }


def clear_spaces(client: ApiClient) -> None:
    spaces = client.get("/api/spaces")
    for space in spaces:
        client.delete(f"/api/spaces/{space['id']}")
        print(f"deleted space: {space['name']} ({space['code']})")


def create_object(client: ApiClient, space_id: str, code: str, name: str, description: str, aliases: list[str]) -> dict[str, Any]:
    return client.post(
        f"/api/ontology/{space_id}/objects",
        element_payload(
            code,
            name,
            description,
            {
                "display_name": name,
                "aliases": aliases,
                "business_owner": "法务风控部",
                "lifecycle": "draft_review_publish",
            },
        ),
    )


def create_property(
    client: ApiClient,
    space_id: str,
    object_id: str,
    object_code: str,
    code: str,
    name: str,
    data_type: str,
    required: bool,
    description: str,
    enum_values: list[str] | None = None,
    calculation_function_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "object_code": object_code,
        "display_name": name,
        "data_type": data_type,
        "required": required,
        "description": description,
        "source": "contract_risk_demo",
    }
    if enum_values:
        payload["enum_values"] = enum_values
    if calculation_function_id:
        payload["calculation"] = {"function_id": calculation_function_id}
    return client.post(
        f"/api/ontology/{space_id}/objects/{object_id}/properties",
        element_payload(f"{object_code}.{code}", name, description, payload),
    )


def create_relation(
    client: ApiClient,
    space_id: str,
    code: str,
    name: str,
    source: dict[str, Any],
    target: dict[str, Any],
    description: str,
    relation_kind: str = "business",
) -> dict[str, Any]:
    return client.post(
        f"/api/ontology/{space_id}/relations",
        element_payload(
            code,
            name,
            description,
            {
                "source_code": source["code"],
                "target_codes": [target["code"]],
                "relation_kind": relation_kind,
                "cardinality": "many_to_many",
                "business_meaning": description,
            },
            [
                {"edge_type": "RELATES_FROM", "target_type": "object", "target_id": source["id"]},
                {"edge_type": "RELATES_TO", "target_type": "object", "target_id": target["id"]},
            ],
        ),
    )


def create_function(
    client: ApiClient,
    space_id: str,
    code: str,
    name: str,
    function_type: str,
    description: str,
    **payload: Any,
) -> dict[str, Any]:
    return client.post(
        f"/api/ontology/{space_id}/functions",
        element_payload(code, name, description, {"function_type": function_type, **payload}),
    )


def create_action(client: ApiClient, space_id: str, code: str, name: str, description: str, payload: dict[str, Any]) -> dict[str, Any]:
    return client.post(f"/api/ontology/{space_id}/actions", element_payload(code, name, description, payload))


def create_rule(
    client: ApiClient,
    space_id: str,
    action_id: str,
    code: str,
    name: str,
    condition: str,
    result: str,
    severity: str,
    referenced_objects: list[str],
    referenced_relations: list[str],
) -> dict[str, Any]:
    return client.post(
        f"/api/ontology/{space_id}/actions/{action_id}/rules",
        element_payload(
            code,
            name,
            result,
            {
                "rule_type": "contract_risk_control",
                "severity": severity,
                "condition": condition,
                "result": result,
                "referenced_objects": referenced_objects,
                "referenced_relations": referenced_relations,
                "decision_hint": "供智脑进行合同风控推理、阻断、补证或升级审批。",
            },
        ),
    )


def seed_demo(client: ApiClient, skip_clear: bool = False) -> dict[str, Any]:
    if not skip_clear:
        clear_spaces(client)

    space = client.post(
        "/api/spaces",
        {
            "code": "contract_risk_decision_demo",
            "name": "合同风控决策本体",
            "domain": "合同风控",
            "template_code": "zhitu_contract_risk_v1",
            "description": "用于手工测试智谱模块的完整演示本体。覆盖对象、属性、关系、函数、行为、规则、查询能力、图谱、验证与发布。",
        },
    )
    space_id = space["id"]
    print(f"created space: {space['name']} ({space_id})")

    functions = {
        "high_amount": create_function(
            client,
            space_id,
            "fn_high_amount_threshold",
            "高金额阈值判断",
            "threshold",
            "合同金额大于等于 500 万时触发升级审批。",
            value_field="amount",
            threshold=5_000_000,
            operator=">=",
        ),
        "sum_payment": create_function(
            client,
            space_id,
            "fn_sum_payment_amount",
            "付款计划金额求和",
            "sum",
            "汇总付款计划金额，用于核对合同金额与付款安排是否一致。",
            value_field="amount",
        ),
        "max_risk": create_function(
            client,
            space_id,
            "fn_max_risk_score",
            "最高风险分提取",
            "max",
            "提取风险项中的最高风险分，辅助智脑判断是否需要阻断或升级。",
            value_field="score",
        ),
        "risk_count": create_function(
            client,
            space_id,
            "fn_count_risk_findings",
            "风险项计数",
            "count",
            "统计合同命中的风险项数量。",
        ),
    }

    objects = {
        "Contract": create_object(client, space_id, "Contract", "合同", "合同主对象，承载交易金额、期限、类型、签署状态等核心信息。", ["协议", "订单合同"]),
        "Party": create_object(client, space_id, "Party", "合同主体", "合同相对方或我方主体，承载资信、关联关系、签署权限。", ["签约方", "相对方"]),
        "Clause": create_object(client, space_id, "Clause", "条款", "合同条款对象，承载付款、违约、续约、争议解决等条款内容。", ["合同条款"]),
        "PaymentSchedule": create_object(client, space_id, "PaymentSchedule", "付款计划", "分期付款节点与付款条件。", ["付款节点"]),
        "Obligation": create_object(client, space_id, "Obligation", "履约义务", "交付、验收、开票、付款、保密等义务。", ["义务"]),
        "RiskFinding": create_object(client, space_id, "RiskFinding", "风险项", "规则、函数或人工审核识别出的合同风险。", ["风险发现"]),
        "Approval": create_object(client, space_id, "Approval", "审批记录", "法务、财务、业务等审批意见。", ["审批"]),
        "Attachment": create_object(client, space_id, "Attachment", "附件证据", "合同附件、授权书、报价单、招投标文件等证据。", ["附件"]),
        "Regulation": create_object(client, space_id, "Regulation", "法规政策", "法律法规、公司制度或合规政策。", ["政策"]),
        "SealAuthorization": create_object(client, space_id, "SealAuthorization", "签署授权", "签署人、印章、授权期限和额度。", ["授权", "印章授权"]),
    }

    properties: list[dict[str, Any]] = []
    property_specs = {
        "Contract": [
            ("contract_no", "合同编号", "string", True, "合同唯一编号。", None, None),
            ("title", "合同标题", "string", True, "合同名称或项目名称。", None, None),
            ("contract_type", "合同类型", "enum", True, "采购、销售、服务、NDA、框架等类型。", ["采购", "销售", "服务", "NDA", "框架"], None),
            ("amount", "合同金额", "money", True, "合同含税总金额。", None, functions["high_amount"]["id"]),
            ("currency", "币种", "enum", True, "合同计价币种。", ["CNY", "USD", "EUR"], None),
            ("sign_date", "签署日期", "date", False, "合同计划或实际签署日期。", None, None),
            ("expiry_date", "到期日期", "date", False, "合同到期日。", None, None),
            ("auto_renewal", "自动续约", "boolean", False, "是否存在自动续约条款。", None, None),
        ],
        "Party": [
            ("name", "主体名称", "string", True, "签约主体名称。", None, None),
            ("role", "主体角色", "enum", True, "我方、相对方、担保方、代理方。", ["我方", "相对方", "担保方", "代理方"], None),
            ("credit_rating", "信用等级", "enum", False, "外部或内部信用等级。", ["A", "B", "C", "D"], None),
            ("is_related_party", "关联方", "boolean", False, "是否为关联交易主体。", None, None),
        ],
        "Clause": [
            ("clause_type", "条款类型", "enum", True, "付款、违约、保密、争议、续约等。", ["付款", "违约", "保密", "争议", "续约"], None),
            ("content", "条款内容", "text", True, "条款原文或结构化摘要。", None, None),
            ("risk_level", "条款风险等级", "enum", False, "条款级风险。", ["低", "中", "高"], None),
        ],
        "PaymentSchedule": [
            ("due_date", "付款到期日", "date", True, "付款节点到期日。", None, None),
            ("amount", "付款金额", "money", True, "单个付款节点金额。", None, functions["sum_payment"]["id"]),
            ("condition", "付款条件", "text", False, "付款前置条件。", None, None),
        ],
        "Obligation": [
            ("obligation_type", "义务类型", "enum", True, "交付、验收、开票、付款、保密。", ["交付", "验收", "开票", "付款", "保密"], None),
            ("deadline", "履约期限", "date", False, "义务完成期限。", None, None),
            ("penalty", "违约责任", "text", False, "未履约时的违约责任。", None, None),
        ],
        "RiskFinding": [
            ("risk_type", "风险类型", "enum", True, "金额、主体、条款、授权、付款、附件。", ["金额", "主体", "条款", "授权", "付款", "附件"], None),
            ("severity", "严重程度", "enum", True, "低、中、高、阻断。", ["低", "中", "高", "阻断"], None),
            ("score", "风险分", "number", True, "0-100 风险评分。", None, functions["max_risk"]["id"]),
            ("recommendation", "处置建议", "text", False, "推荐的处置动作。", None, None),
        ],
        "Approval": [
            ("approver", "审批人", "string", True, "审批人或审批角色。", None, None),
            ("decision", "审批结论", "enum", True, "通过、驳回、补充材料。", ["通过", "驳回", "补充材料"], None),
            ("approved_at", "审批时间", "datetime", False, "审批发生时间。", None, None),
        ],
        "Attachment": [
            ("file_name", "文件名", "string", True, "附件文件名。", None, None),
            ("attachment_type", "附件类型", "enum", True, "授权书、报价单、营业执照、招标文件。", ["授权书", "报价单", "营业执照", "招标文件"], None),
            ("verified", "已核验", "boolean", False, "附件是否已核验。", None, None),
        ],
        "Regulation": [
            ("name", "制度名称", "string", True, "法规或制度名称。", None, None),
            ("article", "条款编号", "string", False, "法规制度条款编号。", None, None),
            ("requirement", "合规要求", "text", True, "合规要求摘要。", None, None),
        ],
        "SealAuthorization": [
            ("authorized_person", "授权签署人", "string", True, "被授权签署合同的人。", None, None),
            ("authorization_expiry", "授权到期日", "date", False, "授权有效期。", None, None),
            ("limit_amount", "授权额度", "money", False, "签署授权金额上限。", None, None),
        ],
    }
    for object_code, specs in property_specs.items():
        obj = objects[object_code]
        for spec in specs:
            properties.append(create_property(client, space_id, obj["id"], object_code, *spec))

    relations = {
        "signed_by": create_relation(client, space_id, "signed_by", "签约主体", objects["Contract"], objects["Party"], "合同由一个或多个主体签署。"),
        "contains_clause": create_relation(client, space_id, "contains_clause", "包含条款", objects["Contract"], objects["Clause"], "合同包含付款、违约、续约等条款。"),
        "has_payment_schedule": create_relation(client, space_id, "has_payment_schedule", "付款安排", objects["Contract"], objects["PaymentSchedule"], "合同金额通过付款计划拆分履行。"),
        "creates_obligation": create_relation(client, space_id, "creates_obligation", "产生义务", objects["Contract"], objects["Obligation"], "合同条款产生具体履约义务。"),
        "has_risk_finding": create_relation(client, space_id, "has_risk_finding", "识别风险", objects["Contract"], objects["RiskFinding"], "合同审核过程中识别风险项。"),
        "requires_approval": create_relation(client, space_id, "requires_approval", "需要审批", objects["Contract"], objects["Approval"], "高风险合同需要触发法务、财务或业务审批。"),
        "has_attachment": create_relation(client, space_id, "has_attachment", "关联附件", objects["Contract"], objects["Attachment"], "合同关联授权书、报价单等附件。"),
        "governed_by": create_relation(client, space_id, "governed_by", "受制度约束", objects["Clause"], objects["Regulation"], "条款需要满足法规或公司制度要求。"),
        "has_authorization": create_relation(client, space_id, "has_authorization", "具备签署授权", objects["Party"], objects["SealAuthorization"], "签约主体或签署人应具备有效授权。"),
        "risk_from_clause": create_relation(client, space_id, "risk_from_clause", "风险来源条款", objects["RiskFinding"], objects["Clause"], "风险项来源于具体条款。"),
    }

    actions = {
        "BlockSigning": create_action(
            client,
            space_id,
            "BlockSigning",
            "阻断签署",
            "命中阻断类风险时禁止进入签署。",
            {"action_type": "block", "owner_role": "法务负责人", "sla": "即时"},
        ),
        "RequireLegalReview": create_action(
            client,
            space_id,
            "RequireLegalReview",
            "升级法务复核",
            "中高风险条款或主体风险需要法务复核。",
            {"action_type": "review", "owner_role": "法务", "sla": "4小时"},
        ),
        "RequireFinanceApproval": create_action(
            client,
            space_id,
            "RequireFinanceApproval",
            "触发财务审批",
            "金额、付款计划或开票风险触发财务审批。",
            {"action_type": "approval", "owner_role": "财务", "sla": "8小时"},
        ),
        "RequestSupplement": create_action(
            client,
            space_id,
            "RequestSupplement",
            "要求补充材料",
            "附件、授权、资质证照缺失时要求业务补证。",
            {"action_type": "supplement", "owner_role": "业务经办人", "sla": "1工作日"},
        ),
        "PublishToBrain": create_action(
            client,
            space_id,
            "PublishToBrain",
            "发布给智脑",
            "验证通过后作为智脑推理与执行的本体包。",
            {"action_type": "publish", "owner_role": "本体管理员", "sla": "手动触发"},
        ),
    }

    rules = [
        create_rule(
            client,
            space_id,
            actions["RequireFinanceApproval"]["id"],
            "rule_high_amount_requires_finance",
            "高金额合同触发财务审批",
            "Contract.amount >= 5000000",
            "触发财务审批，并要求核对付款计划金额合计。",
            "高",
            ["Contract", "PaymentSchedule", "Approval"],
            ["has_payment_schedule", "requires_approval"],
        ),
        create_rule(
            client,
            space_id,
            actions["RequireLegalReview"]["id"],
            "rule_low_credit_party_requires_legal",
            "低信用主体触发法务复核",
            "Party.credit_rating in ['C', 'D']",
            "升级法务复核，检查担保、预付款和违约责任。",
            "高",
            ["Party", "Contract", "RiskFinding"],
            ["signed_by", "has_risk_finding"],
        ),
        create_rule(
            client,
            space_id,
            actions["BlockSigning"]["id"],
            "rule_missing_authorization_blocks_signing",
            "缺失签署授权阻断签署",
            "Party.role == '相对方' and SealAuthorization.authorized_person is null",
            "阻断签署，要求补充授权书或更换签署人。",
            "阻断",
            ["Party", "SealAuthorization", "Attachment"],
            ["has_authorization", "has_attachment"],
        ),
        create_rule(
            client,
            space_id,
            actions["RequestSupplement"]["id"],
            "rule_attachment_not_verified_requires_supplement",
            "附件未核验要求补充材料",
            "Attachment.verified == false",
            "要求业务补充或核验附件证据。",
            "中",
            ["Attachment", "Contract"],
            ["has_attachment"],
        ),
        create_rule(
            client,
            space_id,
            actions["RequireLegalReview"]["id"],
            "rule_high_risk_score_requires_legal",
            "高风险分触发法务复核",
            "RiskFinding.score >= 80",
            "升级法务复核，并输出风险处置建议。",
            "高",
            ["RiskFinding", "Clause"],
            ["risk_from_clause"],
        ),
        create_rule(
            client,
            space_id,
            actions["RequireLegalReview"]["id"],
            "rule_auto_renewal_without_notice",
            "自动续约缺少通知期触发复核",
            "Contract.auto_renewal == true and Clause.clause_type == '续约'",
            "检查是否设置提前通知期、退出机制和价格调整机制。",
            "中",
            ["Contract", "Clause"],
            ["contains_clause"],
        ),
    ]

    capabilities = {
        "ontology_graph": client.post(
            f"/api/ontology/{space_id}/query-capabilities",
            element_payload(
                "cap_contract_risk_graph",
                "合同风控本体图谱查询",
                "返回对象与关系构成的本体图谱，供智脑构建语义网络。",
                {"query_kind": "ontology_graph", "inputs": {}, "output_schema": {"nodes": "object[]", "edges": "relation[]"}},
            ),
        ),
        "local_graph": client.post(
            f"/api/ontology/{space_id}/query-capabilities",
            element_payload(
                "cap_contract_local_reasoning_context",
                "合同局部推理上下文查询",
                "围绕某个对象读取局部图谱上下文，供智脑生成风控解释。",
                {"query_kind": "local_graph", "inputs": {"depth": 2}, "output_schema": {"nodes": "object[]", "edges": "edge[]"}},
            ),
        ),
    }

    smoke = {
        "function_high_amount": client.post(
            f"/api/ontology/{space_id}/functions/{functions['high_amount']['id']}/test",
            {"input_data": {"amount": 8_800_000}, "expected": True},
        ),
        "function_sum_payment": client.post(
            f"/api/ontology/{space_id}/functions/{functions['sum_payment']['id']}/test",
            {"input_data": [{"amount": 3_000_000}, {"amount": 5_800_000}], "expected": 8_800_000},
        ),
        "query_graph": client.post(
            f"/api/ontology/{space_id}/query-capabilities/{capabilities['ontology_graph']['id']}/test",
            {"inputs": {}, "limit": 100},
        ),
        "validation": client.post(f"/api/ontology/{space_id}/validation/run"),
    }
    if not smoke["validation"]["passed"]:
        raise RuntimeError(f"validation failed: {json.dumps(smoke['validation'], ensure_ascii=False)}")
    smoke["publish"] = client.post(f"/api/ontology/{space_id}/publish")

    return {
        "space": space,
        "counts": {
            "objects": len(objects),
            "properties": len(properties),
            "relations": len(relations),
            "functions": len(functions),
            "actions": len(actions),
            "rules": len(rules),
            "query_capabilities": len(capabilities),
        },
        "ids": {
            "contract_object_id": objects["Contract"]["id"],
            "legal_action_id": actions["RequireLegalReview"]["id"],
            "graph_capability_id": capabilities["ontology_graph"]["id"],
        },
        "smoke": smoke,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed contract-risk Zhitu demo ontology.")
    parser.add_argument("--api-base", default="http://localhost:9010", help="Backend API base URL.")
    parser.add_argument("--skip-clear", action="store_true", help="Do not delete existing ontology spaces first.")
    args = parser.parse_args()

    client = ApiClient(args.api_base)
    result = seed_demo(client, skip_clear=args.skip_clear)
    print("\nDemo ontology is ready.")
    print(json.dumps(result["counts"], ensure_ascii=False, indent=2))
    print(f"\nOpen frontend: http://localhost:9005/")
    print(f"Space: {result['space']['name']} / {result['space']['id']}")
    print("Smoke checks: function tests, graph query, validation and publish passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
