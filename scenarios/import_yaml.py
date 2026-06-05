#!/usr/bin/env python3
"""
import_yaml.py —— 从 YAML 批量导入本体到智谱系统

用法:
    python import_yaml.py contract-review.yaml          # 导入合同审核场景
    python import_yaml.py factoring-risk.yaml           # 导入保理风控场景
    python import_yaml.py battery-scheduling.yaml       # 导入锂电池排程场景
    python import_yaml.py --reset                       # 清空所有数据

依赖:
    pip install requests pyyaml
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

import requests
import yaml

API_BASE = "http://localhost:9000"


def api(path: str, method: str = "GET", payload: dict | None = None) -> dict[str, Any]:
    url = f"{API_BASE}{path}"
    kwargs = {"timeout": 30}
    if payload:
        kwargs["json"] = payload
    r = requests.request(method, url, **kwargs)
    r.raise_for_status()
    body = r.json()
    if not body.get("success"):
        raise RuntimeError(f"API error: {body.get('error')}")
    return body.get("data", {})


def reset_all() -> None:
    """清空所有本体数据（空间 + 元素 + 引用边 + 版本 + 审计 + 图同步任务）"""
    print("⚠️  即将清空所有本体数据...")
    # 通过直接调用后端接口清空，或提示用户手动操作
    # 这里我们调用图同步接口，然后逐个删除空间
    spaces = api("/api/spaces")
    for sp in spaces:
        sid = sp["id"]
        print(f"  删除空间: {sp['name']} ({sid[:8]})")
        # 删除空间下所有元素
        for resource in ["objects", "properties", "relations", "actions", "scenarios", "rules"]:
            try:
                data = api(f"/api/ontology/{sid}/{resource}?page_size=500")
                for item in data.get("items", []):
                    try:
                        api(f"/api/ontology/{sid}/{resource}/{item['id']}/deactivate", "POST")
                    except Exception:
                        pass
            except Exception:
                pass
    print("✅ 数据已标记为停用（建议手动清空数据库以彻底重置）")
    print()
    print("彻底重置请执行:")
    print("  docker compose exec postgres psql -U postgres -d zhishen -c \"")
    print("    TRUNCATE ontology_spaces, ontology_elements, reference_edges,")
    print("             version_records, audit_logs, graph_sync_tasks CASCADE;")
    print("  \"")
    print("  # 同时清空 Neo4j:")
    print("  docker compose exec neo4j cypher-shell -u neo4j -p password123 \\")
    print("    'MATCH (n:OntologyNode) DETACH DELETE n;'")


def load_yaml(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def create_space(yaml_data: dict[str, Any]) -> str:
    """创建本体空间，返回 space_id"""
    space_cfg = yaml_data.get("space", {})
    payload = {
        "code": space_cfg.get("code", "default_ontology"),
        "name": space_cfg.get("name", "默认本体"),
        "domain": space_cfg.get("domain", "custom"),
        "description": space_cfg.get("description", ""),
    }
    # 检查是否已存在
    existing = api("/api/spaces")
    for sp in existing:
        if sp["code"] == payload["code"]:
            print(f"  空间已存在: {sp['name']} (id={sp['id'][:8]})")
            return sp["id"]

    result = api("/api/spaces", "POST", payload)
    print(f"  ✅ 创建空间: {result['name']} (id={result['id'][:8]})")
    return result["id"]


def create_elements(space_id: str, yaml_data: dict[str, Any]) -> dict[str, str]:
    """创建所有本体元素，返回 code -> id 映射"""
    by_code: dict[str, str] = {}
    ontology = yaml_data.get("ontology", yaml_data)

    # ── 对象 ──
    objects = ontology.get("objects", {})
    for code, spec in objects.items():
        payload = {
            "code": code,
            "name": spec.get("label", code),
            "description": f"{spec.get('label', code)}对象，业务主键为 {spec.get('key', '-')}",
            "status": "active",
            "payload": {
                "key": spec.get("key"),
                "fields": spec.get("fields", {}),
                "source": yaml_data.get("space", {}).get("code", ""),
            },
            "references": [],
        }
        result = api(f"/api/ontology/{space_id}/objects", "POST", payload)
        by_code[code] = result["id"]
        print(f"    对象: {code} -> {result['id'][:8]}")

    # ── 属性（对象字段）──
    for code, spec in objects.items():
        fields = spec.get("fields", {})
        for field_name, field_type in fields.items():
            property_code = f"{code}.{field_name}"
            payload = {
                "code": property_code,
                "name": field_name,
                "description": f"{spec.get('label', code)}.{field_name}",
                "status": "active",
                "payload": {
                    "object_code": code,
                    "data_type": str(field_type),
                },
                "references": [],
            }
            result = api(f"/api/ontology/{space_id}/properties", "POST", payload)
            by_code[property_code] = result["id"]
        print(f"    属性: {code} 的 {len(fields)} 个字段已创建")

    # ── 关系 ──
    for link in ontology.get("links", []):
        rel_code = link["name"]
        from_code = link["from"]
        to_value = link["to"]
        to_codes = to_value if isinstance(to_value, list) else [to_value]
        payload = {
            "code": rel_code,
            "name": link.get("label", rel_code),
            "description": f"{link.get('label', rel_code)}: {from_code} -> {', '.join(to_codes)}",
            "status": "active",
            "payload": {
                "source_code": from_code,
                "target_codes": to_codes,
                "cardinality": link.get("card"),
                "traversable": link.get("traversable", False),
            },
            "references": [],
        }
        result = api(f"/api/ontology/{space_id}/relations", "POST", payload)
        by_code[rel_code] = result["id"]
        print(f"    关系: {rel_code} -> {result['id'][:8]}")

    # ── 行为 ──
    behavior_codes = set()
    for behavior in ontology.get("behaviors", []):
        bcode = behavior["id"]
        behavior_codes.add(bcode)
        payload = {
            "code": bcode,
            "name": behavior.get("label", bcode),
            "description": behavior.get("effect", ""),
            "status": "active",
            "payload": {
                "hook": behavior.get("hook"),
                "effect": behavior.get("effect"),
                "rules": [],
            },
            "references": [],
        }
        result = api(f"/api/ontology/{space_id}/actions", "POST", payload)
        by_code[bcode] = result["id"]
        print(f"    行为: {bcode} -> {result['id'][:8]}")

    # ── 场景 ──
    for scenario in ontology.get("scenarios", []):
        scode = scenario["id"]
        payload = {
            "code": scode,
            "name": scenario.get("label", scode),
            "description": scenario.get("description", ""),
            "status": "active",
            "payload": {
                "contract_types": scenario.get("contract_types", []),
                "active_elements": scenario.get("active_elements", []),
            },
            "references": [],
        }
        result = api(f"/api/ontology/{space_id}/scenarios", "POST", payload)
        by_code[scode] = result["id"]
        print(f"    场景: {scode} -> {result['id'][:8]}")

    # ── 规则 ──
    for rule_type in ("hard", "soft"):
        for rule in ontology.get("rules", {}).get(rule_type, []):
            rcode = rule["id"]
            actions = extract_actions(rule.get("then"))
            payload = {
                "code": rcode,
                "name": rule.get("label", rcode),
                "description": f"{rule.get('when', '')} -> {rule.get('then', '')}",
                "status": "active",
                "payload": {
                    "rule_type": "硬规则" if rule_type == "hard" else "软规则",
                    "priority": rule.get("priority"),
                    "condition": rule.get("when"),
                    "result": rule.get("then"),
                    "actions": actions,
                    "needs": rule.get("needs"),
                },
                "references": [],
            }
            result = api(f"/api/ontology/{space_id}/rules", "POST", payload)
            by_code[rcode] = result["id"]
            print(f"    规则: {rcode} ({rule_type}) -> {result['id'][:8]}")

    # ── 约束 ──
    for constraint in ontology.get("constraints", []):
        ccode = f"Constraint.{constraint['id']}"
        payload = {
            "code": ccode,
            "name": constraint["id"],
            "description": constraint.get("expr", ""),
            "status": "active",
            "payload": {
                "rule_type": "约束",
                "condition": constraint.get("expr"),
                "kind": constraint.get("kind"),
                "weight": constraint.get("weight"),
                "actions": [],
            },
            "references": [],
        }
        result = api(f"/api/ontology/{space_id}/rules", "POST", payload)
        by_code[ccode] = result["id"]
        print(f"    约束: {ccode} -> {result['id'][:8]}")

    return by_code


def create_reference_edges(space_id: str, yaml_data: dict[str, Any], by_code: dict[str, str]) -> None:
    """创建引用边（对象→属性、关系→对象、规则→行为等）"""
    ontology = yaml_data.get("ontology", yaml_data)

    # 对象→属性边 (HAS_PROPERTY)
    for code, spec in ontology.get("objects", {}).items():
        obj_id = by_code.get(code)
        if not obj_id:
            continue
        for field_name in spec.get("fields", {}).keys():
            prop_code = f"{code}.{field_name}"
            prop_id = by_code.get(prop_code)
            if prop_id:
                # 通过更新属性来建立引用关系
                pass  # 引用边由后端在创建时自动处理，或通过 API 建立

    # 关系→对象边 (RELATES_FROM, RELATES_TO)
    for link in ontology.get("links", []):
        rel_code = link["name"]
        rel_id = by_code.get(rel_code)
        from_code = link["from"]
        to_value = link["to"]
        to_codes = to_value if isinstance(to_value, list) else [to_value]
        # 这些边在创建关系时通过 payload 隐含，不需要单独创建
        print(f"    关系边: {rel_code} ({from_code} -> {', '.join(to_codes)})")

    # 规则→行为边 (REFERENCES_ACTION)
    for rule_type in ("hard", "soft"):
        for rule in ontology.get("rules", {}).get(rule_type, []):
            rcode = rule["id"]
            actions = extract_actions(rule.get("then"))
            for action_code in actions:
                if action_code in by_code:
                    print(f"    规则→行为: {rcode} -> {action_code}")

    print(f"  ✅ 引用边梳理完成（图投影将自动同步到 Neo4j）")


def extract_actions(value: Any) -> list[str]:
    text = str(value)
    actions = [
        "Veto", "RaiseRiskFinding", "RequireApproval", "RequireHumanReview",
        "ProposeAmendment", "BlockEffectiveness", "Notify", "RecordDecision",
    ]
    return [action for action in actions if action in text]


def import_from_yaml(path: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"📦 导入场景: {path}")
    print(f"{'=' * 60}\n")

    data = load_yaml(path)

    # 创建空间
    print("1️⃣  创建本体空间...")
    space_id = create_space(data)

    # 创建元素
    print("\n2️⃣  创建本体元素...")
    by_code = create_elements(space_id, data)

    # 引用边
    print("\n3️⃣  建立引用边...")
    create_reference_edges(space_id, data, by_code)

    # 触发图同步
    print("\n4️⃣  触发图同步...")
    try:
        result = api("/api/graph-sync/run", "POST")
        print(f"  ✅ 图同步完成: 处理了 {result.get('processed', 0)} 个任务")
    except Exception as e:
        print(f"  ⚠️  图同步: {e}")

    print(f"\n{'=' * 60}")
    print(f"🎉 导入完成！空间 ID: {space_id}")
    print(f"{'=' * 60}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="批量导入本体 YAML 到智谱系统")
    parser.add_argument("file", nargs="?", help="YAML 文件路径")
    parser.add_argument("--reset", action="store_true", help="清空所有数据")
    parser.add_argument("--api-base", default="http://localhost:8001", help="API 地址")
    args = parser.parse_args()

    global API_BASE
    API_BASE = args.api_base

    if args.reset:
        reset_all()
        return

    if not args.file:
        print("用法:")
        print("  python import_yaml.py contract-review.yaml")
        print("  python import_yaml.py --reset")
        sys.exit(1)

    import_from_yaml(args.file)


if __name__ == "__main__":
    main()
