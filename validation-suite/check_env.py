#!/usr/bin/env python3
"""
check_env.py —— 环境基线检查
验证后端API、Neo4j、PostgreSQL是否全部就绪。
"""

import sys

import psycopg
import requests
from neo4j import GraphDatabase

from config import (
    API_BASE,
    NEO4J_PASSWORD,
    NEO4J_URI,
    NEO4J_USER,
    PG_DB,
    PG_HOST,
    PG_PASSWORD,
    PG_PORT,
    PG_USER,
)
from utils import GREEN, RED, RESET, YELLOW


def check_backend() -> tuple[bool, str]:
    """检查后端API是否可达"""
    try:
        r = requests.get(f"{API_BASE}/health", timeout=5)
        r.raise_for_status()
        data = r.json().get("data", {})
        neo4j_status = data.get("neo4j", False)
        return True, f"后端OK，Neo4j连接: {'✅' if neo4j_status else '❌'}"
    except Exception as e:
        return False, f"后端不可达: {e}"


def check_neo4j() -> tuple[bool, str]:
    """检查Neo4j是否可连接"""
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()
        with driver.session() as s:
            result = s.run("MATCH (n) RETURN count(n) AS cnt").single()
            cnt = result["cnt"] if result else 0
        driver.close()
        return True, f"Neo4j OK，当前节点数: {cnt}"
    except Exception as e:
        return False, f"Neo4j不可达: {e}"


def check_postgres() -> tuple[bool, str]:
    """检查PostgreSQL是否可连接"""
    try:
        conn = psycopg.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB,
            user=PG_USER, password=PG_PASSWORD, connect_timeout=5,
        )
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM ontology_spaces")
            space_count = cur.fetchone()[0]
            cur.execute("SELECT count(*) FROM ontology_elements")
            element_count = cur.fetchone()[0]
        conn.close()
        return True, f"PostgreSQL OK，空间: {space_count}，元素: {element_count}"
    except Exception as e:
        return False, f"PostgreSQL不可达: {e}"


def main() -> None:
    print(f"\n{GREEN}╔══════════════════════════════════════════════════════════════╗")
    print(f"║              环境基线检查                                    ║")
    print(f"╚══════════════════════════════════════════════════════════════╝{RESET}\n")

    all_pass = True

    checks = [
        ("后端 API", check_backend),
        ("Neo4j 图数据库", check_neo4j),
        ("PostgreSQL 关系库", check_postgres),
    ]

    for name, fn in checks:
        ok, msg = fn()
        mark = f"{GREEN}✅{RESET}" if ok else f"{RED}❌{RESET}"
        print(f"  {mark}  {name}: {msg}")
        if not ok:
            all_pass = False

    print()
    if all_pass:
        print(f"{GREEN}🎉 环境全部就绪，可以开始验证！{RESET}\n")
        sys.exit(0)
    else:
        print(f"{RED}⚠️  环境未完全就绪，请先启动缺失的服务。{RESET}\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
