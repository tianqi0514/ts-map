#!/usr/bin/env python3
"""
check_api.py —— API 端点完整性检查
验证所有REST API是否按预期工作。
"""

import sys

from utils import (
    GREEN,
    RED,
    RESET,
    YELLOW,
    api_get,
    api_post,
    pretty,
)


def check_health() -> tuple[bool, str]:
    try:
        data = api_get("/health")
        return True, f"status={data.get('status')}, neo4j={data.get('neo4j')}"
    except Exception as e:
        return False, str(e)


def check_spaces() -> tuple[bool, str]:
    try:
        spaces = api_get("/api/spaces")
        if not spaces:
            return False, "空间列表为空，请先初始化验证本体"
        return True, f"空间数: {len(spaces)}, 首个: {spaces[0].get('name')}"
    except Exception as e:
        return False, str(e)


def check_summary() -> tuple[bool, str]:
    try:
        spaces = api_get("/api/spaces")
        if not spaces:
            return False, "无空间"
        sid = spaces[0]["id"]
        summary = api_get(f"/api/spaces/{sid}/summary")
        return True, f"总计: {summary.get('total', 0)}, 按类型: {pretty(summary.get('by_type', {}))[:80]}"
    except Exception as e:
        return False, str(e)


def check_list_resources() -> tuple[bool, str]:
    """测试对象/关系/行为的列表接口"""
    try:
        spaces = api_get("/api/spaces")
        if not spaces:
            return False, "无空间"
        sid = spaces[0]["id"]

        results = []
        for resource in ["objects", "relations", "actions", "properties", "rules"]:
            data = api_get(f"//api/ontology/{sid}/{resource}?page_size=500")
            items = data.get("items", [])
            results.append(f"{resource}={len(items)}")

        return True, ", ".join(results)
    except Exception as e:
        return False, str(e)


def check_crud_lifecycle() -> tuple[bool, str]:
    """测试元素完整的CRUD生命周期"""
    try:
        spaces = api_get("/api/spaces")
        if not spaces:
            return False, "无空间"
        sid = spaces[0]["id"]

        # 创建
        created = api_post(f"/api/ontology/{sid}/objects", {
            "code": "test_api_object",
            "name": "API测试对象",
            "description": "由check_api.py创建的测试对象",
            "status": "draft",
            "payload": {"key": "test_key", "fields": {}},
            "references": [],
        })
        eid = created["id"]

        # 读取
        fetched = api_get(f"/api/ontology/{sid}/objects/{eid}")
        if fetched["code"] != "test_api_object":
            return False, f"读取失败: {fetched}"

        # 更新
        updated = None
        import requests
        r = requests.put(
            f"http://localhost:8001/api/ontology/{sid}/objects/{eid}",
            json={"name": "API测试对象_已修改"},
            timeout=10,
        )
        r.raise_for_status()
        updated = r.json().get("data", {})
        if updated.get("name") != "API测试对象_已修改":
            return False, f"更新失败: {updated}"

        # 停用
        deactivated = api_post(f"/api/ontology/{sid}/objects/{eid}/deactivate")
        if deactivated.get("status") != "inactive":
            return False, f"停用失败: {deactivated}"

        return True, f"创建→读取→更新→停用 全部通过 (id={eid[:8]})"
    except Exception as e:
        return False, str(e)


def check_impact() -> tuple[bool, str]:
    """测试影响范围接口"""
    try:
        spaces = api_get("/api/spaces")
        if not spaces:
            return False, "无空间"
        sid = spaces[0]["id"]

        # 找一个有关系的对象
        objects = api_get(f"/api/ontology/{sid}/objects?page_size=10")
        items = objects.get("items", [])
        if not items:
            return False, "无对象"

        eid = items[0]["id"]
        impact = api_get(f"/api/ontology/{sid}/objects/{eid}/impact")
        return True, f"incoming={len(impact.get('incoming', []))}, outgoing={len(impact.get('outgoing', []))}"
    except Exception as e:
        return False, str(e)


def check_local_graph() -> tuple[bool, str]:
    """测试局部图接口"""
    try:
        spaces = api_get("/api/spaces")
        if not spaces:
            return False, "无空间"
        sid = spaces[0]["id"]

        objects = api_get(f"/api/ontology/{sid}/objects?page_size=1")
        items = objects.get("items", [])
        if not items:
            return False, "无对象"

        eid = items[0]["id"]
        graph = api_get(f"/api/ontology/{sid}/objects/{eid}/local-graph?depth=1")
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])
        return True, f"nodes={len(nodes)}, edges={len(edges)}"
    except Exception as e:
        return False, str(e)


def check_versions() -> tuple[bool, str]:
    """测试版本记录"""
    try:
        spaces = api_get("/api/spaces")
        if not spaces:
            return False, "无空间"
        sid = spaces[0]["id"]

        versions = api_get(f"/api/spaces/{sid}/versions")
        return True, f"版本记录数: {len(versions)}"
    except Exception as e:
        return False, str(e)


def main() -> None:
    print(f"\n{GREEN}╔══════════════════════════════════════════════════════════════╗")
    print(f"║              API 端点完整性检查                              ║")
    print(f"╚══════════════════════════════════════════════════════════════╝{RESET}\n")

    checks = [
        ("健康检查 /health", check_health),
        ("空间列表 /api/spaces", check_spaces),
        ("统计摘要 /api/spaces/{id}/summary", check_summary),
        ("资源列表 (对象/关系/行为/属性/规则)", check_list_resources),
        ("CRUD生命周期 (创建→读取→更新→停用)", check_crud_lifecycle),
        ("影响范围 /impact", check_impact),
        ("局部图 /local-graph", check_local_graph),
        ("版本记录 /versions", check_versions),
    ]

    all_pass = True
    for name, fn in checks:
        ok, msg = fn()
        mark = f"{GREEN}✅{RESET}" if ok else f"{RED}❌{RESET}"
        print(f"  {mark}  {name}")
        print(f"      → {msg}")
        if not ok:
            all_pass = False

    print()
    if all_pass:
        print(f"{GREEN}🎉 所有 API 端点检查通过！{RESET}\n")
        return 0
    else:
        print(f"{RED}⚠️  部分 API 检查未通过。{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
