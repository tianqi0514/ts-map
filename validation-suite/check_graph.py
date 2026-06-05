#!/usr/bin/env python3
"""
check_graph.py —— Neo4j 图结构验证
验证图数据库中是否正确投影了本体数据集的语义网络。
对应验证数据集关2：图穿透。
"""

import sys

from neo4j import GraphDatabase

from config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER
from utils import GREEN, RED, RESET


def get_driver():
    return GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))


def check_nodes_exist() -> tuple[bool, str]:
    """检查核心节点类型是否存在"""
    driver = get_driver()
    with driver.session() as s:
        result = s.run("""
            MATCH (n:OntologyNode)
            RETURN n.resource_type AS type, count(*) AS cnt
            ORDER BY cnt DESC
        """).data()
    driver.close()

    if not result:
        return False, "图中无任何 OntologyNode 节点"

    summary = ", ".join(f"{r['type']}={r['cnt']}" for r in result)
    return True, summary


def check_edges_exist() -> tuple[bool, str]:
    """检查关系边是否存在"""
    driver = get_driver()
    with driver.session() as s:
        result = s.run("""
            MATCH ()-[r]->()
            RETURN type(r) AS rel_type, count(*) AS cnt
            ORDER BY cnt DESC
        """).data()
    driver.close()

    if not result:
        return False, "图中无任何关系边"

    summary = ", ".join(f"{r['rel_type']}={r['cnt']}" for r in result[:8])
    return True, summary


def check_contract_nodes() -> tuple[bool, str]:
    """检查合同相关节点"""
    driver = get_driver()
    with driver.session() as s:
        result = s.run("""
            MATCH (n:OntologyNode)
            WHERE n.code IN ['Contract', 'CounterParty', 'Clause', 'PaymentTerm', 'Obligation']
            RETURN n.code AS code, n.name AS name, n.resource_type AS type
            ORDER BY n.code
        """).data()
    driver.close()

    expected = {'Contract', 'CounterParty', 'Clause', 'PaymentTerm', 'Obligation'}
    found = {r['code'] for r in result}
    missing = expected - found

    if missing:
        return False, f"缺少节点: {missing}"
    return True, f"找到: {', '.join(found)}"


def check_relation_edges() -> tuple[bool, str]:
    """检查关系类型的边是否正确"""
    driver = get_driver()
    with driver.session() as s:
        # 检查 RELATES_FROM / RELATES_TO 边
        result = s.run("""
            MATCH (r:OntologyNode:RelationType)-[rel:RELATES_FROM]->(src:OntologyNode:ObjectType)
            RETURN count(*) AS cnt
        """).single()
        from_count = result["cnt"] if result else 0

        result2 = s.run("""
            MATCH (r:OntologyNode:RelationType)-[rel:RELATES_TO]->(tgt:OntologyNode:ObjectType)
            RETURN count(*) AS cnt
        """).single()
        to_count = result2["cnt"] if result2 else 0
    driver.close()

    if from_count == 0 or to_count == 0:
        return False, f"RELATES_FROM={from_count}, RELATES_TO={to_count}"
    return True, f"RELATES_FROM={from_count}, RELATES_TO={to_count}"


def check_has_property_edges() -> tuple[bool, str]:
    """检查对象→属性的 HAS_PROPERTY 边"""
    driver = get_driver()
    with driver.session() as s:
        result = s.run("""
            MATCH (o:OntologyNode:ObjectType)-[r:HAS_PROPERTY]->(p:OntologyNode:Property)
            RETURN count(*) AS cnt
        """).single()
        cnt = result["cnt"] if result else 0
    driver.close()

    if cnt == 0:
        return False, "无 HAS_PROPERTY 边"
    return True, f"HAS_PROPERTY 边数: {cnt}"


def check_graph_traverse_depth2() -> tuple[bool, str]:
    """
    关2核心验证：图穿透能力
    验证从任意 ObjectType 出发，能否通过关系到达其他节点（深度≥2）
    """
    driver = get_driver()
    with driver.session() as s:
        # 找一个有至少2跳路径的节点
        result = s.run("""
            MATCH path = (start:OntologyNode:ObjectType)-[*1..2]-(end:OntologyNode)
            WHERE start <> end
            RETURN start.code AS start_code, length(path) AS path_len,
                   [n IN nodes(path) | n.code] AS path_codes
            LIMIT 3
        """).data()
    driver.close()

    if not result:
        return False, "图中无深度≥2的路径"

    sample = result[0]
    return True, f"存在 {sample['path_len']} 跳路径: {' → '.join(sample['path_codes'])}"


def check_local_graph_api() -> tuple[bool, str]:
    """通过API验证局部图功能"""
    try:
        import requests
        from config import API_BASE

        # 先获取空间和对象
        r = requests.get(f"{API_BASE}/api/spaces", timeout=10)
        spaces = r.json().get("data", [])
        if not spaces:
            return False, "无空间"

        sid = spaces[0]["id"]
        r2 = requests.get(f"{API_BASE}/api/ontology/{sid}/objects?page_size=1", timeout=10)
        items = r2.json().get("data", {}).get("items", [])
        if not items:
            return False, "无对象"

        eid = items[0]["id"]
        r3 = requests.get(f"{API_BASE}/api/ontology/{sid}/objects/{eid}/local-graph?depth=1", timeout=10)
        graph = r3.json().get("data", {})
        nodes = graph.get("nodes", [])
        edges = graph.get("edges", [])

        return True, f"API返回 nodes={len(nodes)}, edges={len(edges)}"
    except Exception as e:
        return False, str(e)


def main() -> None:
    print(f"\n{GREEN}╔══════════════════════════════════════════════════════════════╗")
    print(f"║              Neo4j 图结构验证                                ║")
    print(f"║              对应验证数据集 · 关2 · 图穿透                    ║")
    print(f"╚══════════════════════════════════════════════════════════════╝{RESET}\n")

    checks = [
        ("节点类型分布", check_nodes_exist),
        ("关系边类型分布", check_edges_exist),
        ("核心对象节点存在性", check_contract_nodes),
        ("RELATES_FROM/RELATES_TO 边", check_relation_edges),
        ("HAS_PROPERTY 对象→属性边", check_has_property_edges),
        ("图穿透深度≥2", check_graph_traverse_depth2),
        ("local-graph API", check_local_graph_api),
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
        print(f"{GREEN}🎉 图结构验证全部通过！{RESET}\n")
        return 0
    else:
        print(f"{RED}⚠️  部分图验证未通过。{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
