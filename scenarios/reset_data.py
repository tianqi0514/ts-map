#!/usr/bin/env python3
"""
reset_data.py —— 清空智谱系统所有本体数据

用法:
    python reset_data.py              # 交互式确认后清空
    python reset_data.py --force      # 跳过确认直接清空
    python reset_data.py --soft       # 仅停用，不物理删除

⚠️  危险操作！会删除所有本体空间、元素、引用边、版本记录、审计日志、图同步任务！
"""

import argparse
import sys

import psycopg
import requests
from neo4j import GraphDatabase

# ── 配置 ──
API_BASE = "http://localhost:9000"
PG_HOST, PG_PORT, PG_DB = "localhost", "9002", "zhishen"
PG_USER, PG_PASSWORD = "postgres", "postgres"
NEO4J_URI = "bolt://localhost:9004"
NEO4J_USER, NEO4J_PASSWORD = "neo4j", "password123"


def pg_execute(sql: str) -> None:
    conn = psycopg.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASSWORD,
    )
    with conn.cursor() as cur:
        cur.execute(sql)
    conn.commit()
    conn.close()


def reset_postgres(soft: bool = False) -> None:
    """清空 PostgreSQL 数据"""
    print("\n📦 清空 PostgreSQL...")

    if soft:
        # 仅停用所有元素和空间
        pg_execute("""
            UPDATE ontology_elements SET status = 'inactive', deleted_at = NOW()
            WHERE deleted_at IS NULL;
        """)
        pg_execute("""
            UPDATE ontology_spaces SET status = 'inactive' WHERE status != 'inactive';
        """)
        print("  ✅ 所有元素已标记为停用（软删除）")
        return

    # 物理清空
    tables = [
        "reference_edges",
        "graph_sync_tasks",
        "version_records",
        "audit_logs",
        "ontology_elements",
        "ontology_spaces",
    ]
    for table in tables:
        pg_execute(f"TRUNCATE TABLE {table} CASCADE")
        print(f"  ✅ 已清空: {table}")


def reset_neo4j() -> None:
    """清空 Neo4j 图数据"""
    print("\n🕸️  清空 Neo4j...")
    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        with driver.session() as s:
            s.run("MATCH (n:OntologyNode) DETACH DELETE n")
            result = s.run("MATCH (n) RETURN count(n) AS cnt").single()
            cnt = result["cnt"] if result else 0
        driver.close()
        print(f"  ✅ Neo4j 已清空（剩余 {cnt} 个非 OntologyNode 节点）")
    except Exception as e:
        print(f"  ⚠️  Neo4j 清空失败: {e}")


def show_summary() -> None:
    """显示当前数据量"""
    print("\n📊 当前数据概况:")
    try:
        conn = psycopg.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB,
            user=PG_USER, password=PG_PASSWORD,
        )
        with conn.cursor() as cur:
            for table in ["ontology_spaces", "ontology_elements", "reference_edges", "version_records", "audit_logs"]:
                cur.execute(f"SELECT count(*) FROM {table}")
                cnt = cur.fetchone()[0]
                print(f"  {table}: {cnt}")
        conn.close()
    except Exception as e:
        print(f"  无法查询: {e}")

    try:
        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        with driver.session() as s:
            result = s.run("MATCH (n:OntologyNode) RETURN count(n) AS cnt").single()
            cnt = result["cnt"] if result else 0
        driver.close()
        print(f"  Neo4j OntologyNode: {cnt}")
    except Exception as e:
        print(f"  Neo4j 无法查询: {e}")


def main() -> int:
    parser = argparse.ArgumentParser(description="清空智谱系统所有本体数据")
    parser.add_argument("--force", action="store_true", help="跳过确认直接执行")
    parser.add_argument("--soft", action="store_true", help="仅停用（软删除），不物理删除")
    args = parser.parse_args()

    print("=" * 60)
    print("⚠️  智谱系统数据清空工具")
    print("=" * 60)

    show_summary()

    mode = "软删除（停用）" if args.soft else "物理清空（不可恢复）"
    print(f"\n操作模式: {mode}")

    if not args.force:
        print("\n此操作将删除所有本体数据！")
        confirm = input("输入 'DELETE' 确认清空: ")
        if confirm.strip() != "DELETE":
            print("❌ 操作已取消")
            return 1

    reset_postgres(soft=args.soft)
    if not args.soft:
        reset_neo4j()

    print("\n" + "=" * 60)
    print("✅ 清空完成")
    print("=" * 60)

    show_summary()
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
