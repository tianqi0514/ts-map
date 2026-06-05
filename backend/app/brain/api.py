"""
传神智脑 —— FastAPI 路由
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException
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
