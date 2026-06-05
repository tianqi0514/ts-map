"""
传神智脑 —— FastAPI 路由
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.brain import crud as brain_crud
from app.brain.rule_engine import RuleEngine
from app.brain.schemas import (
    ApiConnectorCreate,
    ApiConnectorRead,
    ApiConnectorUpdate,
    DataMappingCreate,
    DataMappingRead,
    DataMappingUpdate,
    RuleEngineInput,
    RuleExecutionRead,
    SyntheticDataPreviewRequest,
    SyntheticDataPreviewResponse,
)
from app.brain.synthetic_data import generate_preview
from app.database import get_db
from app.llm_client import LLMClient
from app.schemas import ApiResponse

router = APIRouter(prefix="/api/brain", tags=["brain"])


# ── 预设模板数据 ──

PRESET_TEMPLATES: list[dict[str, Any]] = [
    {
        "code": "contract_system",
        "name": "合同管理系统",
        "description": "对接企业合同管理系统，获取合同详情、审批状态、付款计划等业务数据",
        "base_url": "/mock/contracts/{contract_id}",
        "method": "GET",
        "auth_type": "apikey",
        "auth_config": {"key_name": "X-API-Key", "key_value": "demo-key-123"},
        "request_template": {"contract_id": "{contract_id}"},
        "mappings": [
            {"source_field": "contract.contractNo", "target_type": "object", "target_code": "contract", "transform": "string", "is_key": True, "description": "合同编号"},
            {"source_field": "contract.title", "target_type": "object", "target_code": "contract", "transform": "string", "description": "合同标题"},
            {"source_field": "contract.contractType", "target_type": "object", "target_code": "contract", "transform": "enum[采购合同,销售合同,服务合同,租赁合同]", "description": "合同类型"},
            {"source_field": "contract.amount", "target_type": "object", "target_code": "contract", "transform": "money", "description": "合同金额"},
            {"source_field": "contract.signDate", "target_type": "object", "target_code": "contract", "transform": "date", "description": "签署日期"},
            {"source_field": "contract.status", "target_type": "object", "target_code": "contract", "transform": "enum[草稿,审批中,已生效,已归档]", "description": "合同状态"},
            {"source_field": "party.entityId", "target_type": "object", "target_code": "party", "transform": "string", "is_key": True, "description": "主体编号"},
            {"source_field": "party.name", "target_type": "object", "target_code": "party", "transform": "string", "description": "主体名称"},
            {"source_field": "party.creditScore", "target_type": "object", "target_code": "party", "transform": "int", "description": "信用评分"},
            {"source_field": "approval.apId", "target_type": "object", "target_code": "approval", "transform": "string", "is_key": True, "description": "审批编号"},
            {"source_field": "approval.approver", "target_type": "object", "target_code": "approval", "transform": "string", "description": "审批人"},
            {"source_field": "approval.decision", "target_type": "object", "target_code": "approval", "transform": "enum[通过,驳回,转审]", "description": "审批结论"},
            {"source_field": "payment.planAmount", "target_type": "object", "target_code": "payment_plan", "transform": "money", "description": "计划付款金额"},
            {"source_field": "payment.paymentDays", "target_type": "object", "target_code": "payment_plan", "transform": "int", "description": "付款天数"},
            {"source_field": "risk.level", "target_type": "object", "target_code": "risk", "transform": "enum[高,中,低]", "description": "风险等级"},
        ],
    },
    {
        "code": "customer_system",
        "name": "客户管理系统",
        "description": "对接 CRM 系统，获取客户信息、工商数据、信用评级等",
        "base_url": "/mock/customers/{customer_id}",
        "method": "GET",
        "auth_type": "bearer",
        "auth_config": {"token": "Bearer demo-token-456"},
        "request_template": {"customer_id": "{customer_id}"},
        "mappings": [
            {"source_field": "customer.customerId", "target_type": "object", "target_code": "party", "transform": "string", "is_key": True, "description": "客户编号"},
            {"source_field": "customer.companyName", "target_type": "object", "target_code": "party", "transform": "string", "description": "公司名称"},
            {"source_field": "customer.taxId", "target_type": "object", "target_code": "party", "transform": "string", "description": "统一社会信用代码"},
            {"source_field": "customer.regCapital", "target_type": "object", "target_code": "party", "transform": "money", "description": "注册资本"},
            {"source_field": "customer.establishedDate", "target_type": "object", "target_code": "party", "transform": "date", "description": "成立日期"},
            {"source_field": "customer.businessStatus", "target_type": "object", "target_code": "party", "transform": "enum[存续,注销,吊销,迁出]", "description": "经营状态"},
            {"source_field": "customer.creditScore", "target_type": "object", "target_code": "party", "transform": "int", "description": "信用评分"},
            {"source_field": "customer.riskLevel", "target_type": "object", "target_code": "risk", "transform": "enum[高,中,低]", "description": "客户风险等级"},
        ],
    },
    {
        "code": "supplier_system",
        "name": "供应商管理系统",
        "description": "对接供应商管理系统，获取供应商资质、交付记录、评估得分",
        "base_url": "/mock/suppliers/{supplier_id}",
        "method": "GET",
        "auth_type": "none",
        "auth_config": {},
        "request_template": {"supplier_id": "{supplier_id}"},
        "mappings": [
            {"source_field": "supplier.supplierId", "target_type": "object", "target_code": "party", "transform": "string", "is_key": True, "description": "供应商编号"},
            {"source_field": "supplier.supplierName", "target_type": "object", "target_code": "party", "transform": "string", "description": "供应商名称"},
            {"source_field": "supplier.qualificationScore", "target_type": "object", "target_code": "party", "transform": "int", "description": "资质评分"},
            {"source_field": "supplier.deliveryScore", "target_type": "object", "target_code": "party", "transform": "int", "description": "交付评分"},
            {"source_field": "supplier.cooperationYears", "target_type": "object", "target_code": "party", "transform": "int", "description": "合作年限"},
            {"source_field": "supplier.blacklist", "target_type": "object", "target_code": "party", "transform": "bool", "description": "是否黑名单"},
        ],
    },
]


# ── 连接器 CRUD ──

@router.get("/connectors")
def list_connectors(
    keyword: str = "",
    status: str = "",
    db: Session = Depends(get_db),
) -> ApiResponse:
    connectors = brain_crud.list_connectors(db, keyword, status)
    return ApiResponse(data=[brain_crud.serialize_connector(c) for c in connectors])


@router.post("/connectors")
def create_connector(
    payload: ApiConnectorCreate,
    db: Session = Depends(get_db),
) -> ApiResponse:
    connector = brain_crud.create_connector(db, payload)
    return ApiResponse(data=brain_crud.serialize_connector(connector))


@router.get("/connectors/{connector_id}")
def get_connector(
    connector_id: str,
    db: Session = Depends(get_db),
) -> ApiResponse:
    connector = brain_crud.get_connector(db, connector_id)
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    return ApiResponse(data=brain_crud.serialize_connector(connector))


@router.put("/connectors/{connector_id}")
def update_connector(
    connector_id: str,
    payload: ApiConnectorUpdate,
    db: Session = Depends(get_db),
) -> ApiResponse:
    connector = brain_crud.update_connector(db, connector_id, payload)
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")
    return ApiResponse(data=brain_crud.serialize_connector(connector))


@router.delete("/connectors/{connector_id}")
def delete_connector(
    connector_id: str,
    db: Session = Depends(get_db),
) -> ApiResponse:
    success = brain_crud.delete_connector(db, connector_id)
    if not success:
        raise HTTPException(status_code=404, detail="Connector not found")
    return ApiResponse(data={"deleted": True})


# ── 字段映射 CRUD ──

@router.get("/connectors/{connector_id}/mappings")
def list_mappings(
    connector_id: str,
    db: Session = Depends(get_db),
) -> ApiResponse:
    mappings = brain_crud.list_mappings(db, connector_id)
    return ApiResponse(data=[brain_crud.serialize_mapping(m) for m in mappings])


@router.post("/connectors/{connector_id}/mappings")
def create_mapping(
    connector_id: str,
    payload: DataMappingCreate,
    db: Session = Depends(get_db),
) -> ApiResponse:
    # 确保 connector 存在
    connector = brain_crud.get_connector(db, connector_id)
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    # 强制绑定到该 connector
    data = payload.model_dump()
    data["connector_id"] = connector_id
    mapping = brain_crud.create_mapping(db, DataMappingCreate(**data))
    return ApiResponse(data=brain_crud.serialize_mapping(mapping))


@router.put("/mappings/{mapping_id}")
def update_mapping(
    mapping_id: str,
    payload: DataMappingUpdate,
    db: Session = Depends(get_db),
) -> ApiResponse:
    mapping = brain_crud.update_mapping(db, mapping_id, payload)
    if not mapping:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return ApiResponse(data=brain_crud.serialize_mapping(mapping))


@router.delete("/mappings/{mapping_id}")
def delete_mapping(
    mapping_id: str,
    db: Session = Depends(get_db),
) -> ApiResponse:
    success = brain_crud.delete_mapping(db, mapping_id)
    if not success:
        raise HTTPException(status_code=404, detail="Mapping not found")
    return ApiResponse(data={"deleted": True})


# ── 合成数据预览 ──

@router.post("/connectors/{connector_id}/preview")
def preview_synthetic_data(
    connector_id: str,
    payload: SyntheticDataPreviewRequest | None = None,
    db: Session = Depends(get_db),
) -> ApiResponse:
    connector = brain_crud.get_connector(db, connector_id)
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    count = payload.count if payload else 3
    result = generate_preview(db, connector_id, count)
    return ApiResponse(data=result)


# ── 预设模板 ──

@router.get("/templates")
def list_templates() -> ApiResponse:
    """列出可用的连接器预设模板"""
    templates = []
    for t in PRESET_TEMPLATES:
        templates.append({
            "code": t["code"],
            "name": t["name"],
            "description": t["description"],
            "mapping_count": len(t["mappings"]),
        })
    return ApiResponse(data=templates)


@router.post("/templates/{template_code}/apply")
def apply_template(
    template_code: str,
    space_id: str = "",
    db: Session = Depends(get_db),
) -> ApiResponse:
    """应用预设模板，创建连接器和字段映射"""
    template = next((t for t in PRESET_TEMPLATES if t["code"] == template_code), None)
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    # 创建连接器
    connector = brain_crud.create_connector(
        db,
        ApiConnectorCreate(
            code=template["code"],
            name=template["name"],
            description=template["description"],
            base_url=template["base_url"],
            method=template["method"],
            auth_type=template["auth_type"],
            auth_config=template["auth_config"],
            request_template=template["request_template"],
            space_id=space_id or None,
            status="active",
        ),
    )

    # 创建字段映射
    for m in template["mappings"]:
        brain_crud.create_mapping(
            db,
            DataMappingCreate(
                connector_id=connector.id,
                source_field=m["source_field"],
                target_type=m["target_type"],
                target_code=m["target_code"],
                transform=m["transform"],
                is_key=m.get("is_key", False),
                description=m.get("description", ""),
            ),
        )

    return ApiResponse(data={
        "connector": brain_crud.serialize_connector(connector),
        "mapping_count": len(template["mappings"]),
    })


# ── 规则引擎 ──

@router.post("/rule-engine/execute")
def execute_rule_engine(
    payload: RuleEngineInput,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """执行规则引擎，给定业务数据输出命中结果"""
    engine = RuleEngine(db)
    result = engine.execute(
        space_id=payload.space_id,
        data=payload.data,
        rule_ids=payload.rule_ids,
    )

    # 保存执行记录（推理轨迹）
    try:
        brain_crud.create_execution(
            db=db,
            space_id=payload.space_id,
            input_summary={k: str(v)[:100] for k, v in payload.data.items()},
            trace=[
                {
                    "rule_id": h["rule_id"],
                    "rule_name": h["rule_name"],
                    "matched": h["matched"],
                    "severity": h["severity"],
                    "reasoning": h["reasoning"],
                }
                for h in result["hits"]
            ],
            hit_count=result["hit_count"],
            block_count=result["block_count"],
            suggest_count=result["hit_count"] - result["block_count"],
            status="success",
        )
    except Exception:
        pass  # 执行记录失败不影响主流程

    return ApiResponse(data=result)


@router.get("/rule-engine/executions/{space_id}")
def list_executions(
    space_id: str,
    limit: int = 50,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """列出规则执行历史"""
    executions = brain_crud.list_executions(db, space_id, limit)
    return ApiResponse(data=[brain_crud.serialize_execution(e) for e in executions])


# ── 执行预设规则测试 ──

@router.post("/rule-engine/test")
def test_rule_engine(
    space_id: str,
    scenario: str = "contract_review",
    db: Session = Depends(get_db),
) -> ApiResponse:
    """
    使用预设测试场景执行规则引擎
    scenario: contract_review | factoring_risk | battery_scheduling
    """
    from app.brain.synthetic_data import SyntheticDataGenerator

    # 根据场景生成测试数据
    test_data = _generate_test_data(scenario)

    engine = RuleEngine(db)
    result = engine.execute(space_id=space_id, data=test_data)
    result["test_scenario"] = scenario
    result["test_data"] = test_data

    return ApiResponse(data=result)


def _generate_test_data(scenario: str) -> dict[str, Any]:
    """生成预设测试数据"""
    if scenario == "contract_review":
        return {
            "contract": {
                "contractNo": "CT-2024-1001",
                "title": "设备采购合同",
                "contractType": "采购合同",
                "amount": 1500000,
                "signDate": "2024-01-15",
                "status": "审批中",
                "effectiveCondition": "双方签字盖章",
            },
            "party": {
                "entityId": "ENT-001",
                "name": "ABC科技有限公司",
                "creditScore": 75,
                "regCapital": 5000000,
                "businessStatus": "存续",
            },
            "approval": {
                "apId": "AP-001",
                "approver": "张经理",
                "decision": "待审批",
                "decidedAt": None,
            },
            "payment_plan": {
                "planAmount": 500000,
                "paymentDays": 30,
                "stage": "首付款",
            },
            "risk": {
                "level": "中",
            },
        }

    if scenario == "factoring_risk":
        return {
            "receivable": {
                "receivableId": "REC-001",
                "amount": 2000000,
                "dueDate": "2024-06-30",
                "debtorCredit": "B",
            },
            "party": {
                "entityId": "ENT-002",
                "name": "XYZ贸易公司",
                "creditScore": 65,
                "regCapital": 2000000,
            },
            "risk": {
                "level": "高",
            },
        }

    if scenario == "battery_scheduling":
        return {
            "order": {
                "orderId": "ORD-001",
                "productType": "磷酸铁锂电池",
                "quantity": 5000,
                "deliveryDate": "2024-03-15",
            },
            "production_line": {
                "lineId": "LINE-A",
                "capacity": 1000,
                "currentLoad": 900,
            },
        }

    # 通用默认数据
    return {
        "contract": {
            "contractNo": "CT-2024-0001",
            "title": "测试合同",
            "amount": 100000,
            "status": "草稿",
        },
    }


# ── LLM 自然语言规则测试 ──

class NLRuleTestPayload(BaseModel):
    space_id: str
    connector_id: str
    scene_description: str


@router.post("/rule-engine/nl-test")
def nl_rule_test(
    payload: NLRuleTestPayload,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """
    自然语言规则测试：
    1. 用 LLM 根据场景描述生成测试数据
    2. 执行规则引擎
    3. 返回完整结果
    """
    client = LLMClient()
    if not client.is_available():
        return ApiResponse(data={
            "error": "LLM 未配置，请在系统配置中检查 LLM 设置",
            "llm_available": False,
        })

    # 获取连接器字段映射
    mappings = brain_crud.list_mappings(db, payload.connector_id)
    if not mappings:
        return ApiResponse(data={
            "error": "连接器没有字段映射，请先配置映射",
        })

    # 获取本体对象定义（用于提示 LLM）
    from app.models import OntologyElement
    objects = (
        db.query(OntologyElement)
        .filter(
            OntologyElement.space_id == payload.space_id,
            OntologyElement.resource_type == "object",
        )
        .all()
    )
    ontology_objects = [
        {"code": obj.code, "name": obj.name, "payload": obj.payload}
        for obj in objects
    ]

    mapping_list = [
        {
            "source_field": m.source_field,
            "transform": m.transform,
            "target_code": m.target_code,
        }
        for m in mappings
    ]

    # 调用 LLM 生成测试数据
    llm_result = client.generate_test_data(
        scene_description=payload.scene_description,
        connector_mappings=mapping_list,
        ontology_objects=ontology_objects,
    )

    if not llm_result.get("test_data"):
        return ApiResponse(data={
            "error": "LLM 未能生成有效测试数据",
            "llm_raw": llm_result.get("raw", ""),
        })

    test_data = llm_result["test_data"]

    # 执行规则引擎
    engine = RuleEngine(db)
    rule_result = engine.execute(space_id=payload.space_id, data=test_data)

    # 保存执行记录
    try:
        brain_crud.create_execution(
            db=db,
            space_id=payload.space_id,
            input_summary={k: str(v)[:100] for k, v in test_data.items()},
            trace=[
                {
                    "rule_id": h["rule_id"],
                    "rule_name": h["rule_name"],
                    "matched": h["matched"],
                    "severity": h["severity"],
                }
                for h in rule_result["hits"]
            ],
            hit_count=rule_result["hit_count"],
            block_count=rule_result["block_count"],
            suggest_count=rule_result["hit_count"] - rule_result["block_count"],
            status="success",
        )
    except Exception:
        pass

    return ApiResponse(data={
        "scene_description": payload.scene_description,
        "test_data": test_data,
        "llm_usage": llm_result.get("usage", {}),
        "llm_model": llm_result.get("model", ""),
        "rule_result": rule_result,
    })


class NLSimpleRuleTestPayload(BaseModel):
    space_id: str
    scene_description: str


@router.post("/rule-engine/nl-simple-test")
def nl_simple_rule_test(
    payload: NLSimpleRuleTestPayload,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """
    简化的自然语言规则测试（不依赖连接器）：
    LLM 直接根据场景描述和本体规则生成测试数据
    """
    client = LLMClient()
    if not client.is_available():
        return ApiResponse(data={
            "error": "LLM 未配置，请在系统配置中检查 LLM 设置",
            "llm_available": False,
        })

    # 获取本体规则
    from app.models import ElementStatus, OntologyElement
    rules = (
        db.query(OntologyElement)
        .filter(
            OntologyElement.space_id == payload.space_id,
            OntologyElement.resource_type == "rule",
            OntologyElement.status == ElementStatus.active,
        )
        .all()
    )

    rules_desc = "\n".join([
        f"- {r.name} ({r.payload.get('rule_type', '规则')}): "
        f"当 {r.payload.get('condition', '无')} 时，{r.payload.get('result', '无')}"
        for r in rules[:10]
    ])

    system_prompt = """你是一个企业业务数据生成助手。
根据用户描述的场景和系统定义的规则，生成符合结构的 JSON 测试数据。
只返回 JSON 对象，不要任何解释。"""

    user_prompt = f"""场景描述：{payload.scene_description}

系统规则（供参考，生成数据应尽量触发/避开这些规则）：
{rules_desc}

请生成一段 JSON 测试数据，格式示例：
{{
  "contract": {{"contractNo": "...", "amount": ..., "status": "..."}},
  "party": {{"name": "...", "creditScore": ...}},
  "approval": {{"decision": "..."}},
  "risk": {{"level": "..."}}
}}
"""

    result = client.chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        json_mode=True,
    )

    try:
        test_data = json.loads(result["content"])
        if "test_data" in test_data and isinstance(test_data["test_data"], dict):
            test_data = test_data["test_data"]
    except json.JSONDecodeError:
        return ApiResponse(data={
            "error": "LLM 返回了非 JSON 内容",
            "raw": result["content"],
        })

    # 执行规则引擎
    engine = RuleEngine(db)
    rule_result = engine.execute(space_id=payload.space_id, data=test_data)

    return ApiResponse(data={
        "scene_description": payload.scene_description,
        "test_data": test_data,
        "llm_usage": result.get("usage", {}),
        "llm_model": result.get("model", ""),
        "rule_result": rule_result,
    })


# ── 连接器生成单条合成数据 ──

@router.post("/connectors/{connector_id}/preview-single")
def preview_single_record(
    connector_id: str,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """生成单条合成数据（用于规则引擎测试）"""
    connector = brain_crud.get_connector(db, connector_id)
    if not connector:
        raise HTTPException(status_code=404, detail="Connector not found")

    result = generate_preview(db, connector_id, count=1)
    return ApiResponse(data={
        "connector_id": connector_id,
        "connector_name": connector.name,
        "record": result["records"][0] if result["records"] else {},
    })


# ── 规则引擎对话 ──

class RuleEngineChatPayload(BaseModel):
    space_id: str
    space_name: str
    test_data: dict[str, Any]
    data_source: str
    hits: list[dict[str, Any]]
    misses: list[dict[str, Any]]
    all_rules: list[dict[str, Any]]
    execution_time_ms: float
    question: str
    history: list[dict[str, str]] = []


@router.post("/rule-engine/chat")
def rule_engine_chat(
    payload: RuleEngineChatPayload,
    db: Session = Depends(get_db),
) -> ApiResponse:
    """
    基于规则引擎执行上下文进行对话。
    大模型必须基于提供的上下文回答，不能编造信息。
    """
    client = LLMClient()
    if not client.is_available():
        return ApiResponse(data={
            "error": "LLM 未配置，请在系统配置中检查 LLM 设置",
            "llm_available": False,
        })

    # 构建命中规则摘要
    hit_summary = "\n".join([
        f"- {h['rule_name']} ({h['rule_type']}, P{h['priority']}): "
        f"条件「{h['condition']}」→ 结果「{h['result']}」"
        for h in payload.hits[:20]
    ]) if payload.hits else "无"

    # 构建未命中规则摘要
    miss_summary = "\n".join([
        f"- {m['rule_name']} ({m['rule_type']}, P{m['priority']}): "
        f"条件「{m['condition']}」→ 未命中"
        for m in payload.misses[:20]
    ]) if payload.misses else "无"

    # 构建全部规则摘要
    all_rules_summary = "\n".join([
        f"- {r['rule_name']} ({r['rule_type']}, P{r['priority']}): {r['condition']}"
        for r in payload.all_rules[:30]
    ])

    system_prompt = f"""你是一个企业规则引擎分析助手。你的回答**必须**基于以下执行上下文，**绝对不能编造**任何规则或数据。

【执行上下文】
- 本体空间：{payload.space_name}
- 数据来源：{payload.data_source}
- 执行耗时：{payload.execution_time_ms}ms

【输入测试数据】
```json
{json.dumps(payload.test_data, ensure_ascii=False, indent=2)}
```

【全部规则（共 {len(payload.all_rules)} 条）】
{all_rules_summary}

【命中规则（共 {len(payload.hits)} 条）】
{hit_summary}

【未命中规则（共 {len(payload.misses)} 条）】
{miss_summary}

【回答要求】
1. **只基于以上上下文回答**，不要编造不存在的规则或数据
2. 如果用户问的是上下文中**没有**的信息，明确说"根据当前执行上下文，我无法回答这个问题"
3. 解释规则命中原因时，**引用具体的条件表达式和实际数据值**
4. 如果用户问"修改某字段会怎样"，基于规则条件做逻辑推理，但不要假设规则不存在
5. 用中文回答，简洁专业"""

    messages = [{"role": "system", "content": system_prompt}]

    # 添加历史对话
    for msg in payload.history[-6:]:  # 只保留最近 6 轮
        messages.append({"role": msg["role"], "content": msg["content"]})

    messages.append({"role": "user", "content": payload.question})

    try:
        result = client.chat(messages=messages)
        return ApiResponse(data={
            "answer": result["content"],
            "model": result["model"],
            "usage": result["usage"],
        })
    except Exception as e:
        return ApiResponse(data={
            "error": f"LLM 调用失败: {str(e)}",
        })
