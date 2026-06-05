#!/usr/bin/env python3
"""
check_levels.py —— 六关闯关验证主控
基于验证数据集六关体系，综合验证本体管理模块。

用法:
    python check_levels.py         # 跑全部关卡
    python check_levels.py 1       # 只跑关1
    python check_levels.py 1 2 3   # 跑关1~3
"""

import subprocess
import sys

from config import API_BASE, NEO4J_URI
from utils import GREEN, RED, RESET, YELLOW, CheckResult, LevelReport, print_banner


# ──────────────────────────────────────────
# 关1：本体边界
# ──────────────────────────────────────────
def level_1() -> LevelReport:
    """关1：验证本体空间、对象、关系、行为、规则、属性、引用边、版本记录、审计日志"""
    report = LevelReport(1, "本体边界 · 语义资产完整性")

    try:
        import psycopg
        from config import PG_DB, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER

        conn = psycopg.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB,
            user=PG_USER, password=PG_PASSWORD,
        )

        # 1.1 空间存在
        with conn.cursor() as cur:
            cur.execute("SELECT code, name FROM ontology_spaces WHERE code = 'single_contract_ontology'")
            row = cur.fetchone()
        report.add(CheckResult("空间存在", row is not None,
                               f"code={row[0] if row else 'N/A'}"))

        if not row:
            conn.close()
            return report  # 空间都不存在，后续跳过

        sid = None
        with conn.cursor() as cur:
            cur.execute("SELECT id FROM ontology_spaces LIMIT 1")
            r = cur.fetchone()
            sid = r[0] if r else None

        if not sid:
            conn.close()
            return report

        # 1.2 对象
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM ontology_elements WHERE space_id=%s AND resource_type='object'", (sid,))
            obj_cnt = cur.fetchone()[0]
        report.add(CheckResult("对象数量≥20", obj_cnt >= 20, f"实际={obj_cnt}"))

        with conn.cursor() as cur:
            cur.execute("SELECT code FROM ontology_elements WHERE space_id=%s AND resource_type='object'", (sid,))
            obj_codes = {r[0] for r in cur.fetchall()}
        expected_obj = {"Contract", "CounterParty", "Clause", "PaymentTerm", "Obligation",
                        "Deliverable", "Milestone", "RiskFinding", "Approval", "Amendment"}
        missing_obj = expected_obj - obj_codes
        report.add(CheckResult("核心对象编码", not missing_obj,
                               f"找到{len(obj_codes)}个" + (f", 缺{missing_obj}" if missing_obj else "")))

        # 1.3 关系
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM ontology_elements WHERE space_id=%s AND resource_type='relation'", (sid,))
            rel_cnt = cur.fetchone()[0]
        report.add(CheckResult("关系数量≥20", rel_cnt >= 20, f"实际={rel_cnt}"))

        # 1.4 行为
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM ontology_elements WHERE space_id=%s AND resource_type='action'", (sid,))
            act_cnt = cur.fetchone()[0]
        report.add(CheckResult("行为数量≥8", act_cnt >= 8, f"实际={act_cnt}"))

        with conn.cursor() as cur:
            cur.execute("SELECT code FROM ontology_elements WHERE space_id=%s AND resource_type='action'", (sid,))
            act_codes = {r[0] for r in cur.fetchall()}
        expected_act = {"Veto", "RaiseRiskFinding", "RequireApproval", "RequireHumanReview",
                        "BlockEffectiveness", "Notify", "RecordDecision"}
        missing_act = expected_act - act_codes
        report.add(CheckResult("核心行为编码", not missing_act,
                               f"找到{len(act_codes)}个" + (f", 缺{missing_act}" if missing_act else "")))

        # 1.5 规则
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM ontology_elements WHERE space_id=%s AND resource_type='rule'", (sid,))
            rule_cnt = cur.fetchone()[0]
        report.add(CheckResult("规则数量≥15", rule_cnt >= 15, f"实际={rule_cnt}"))

        with conn.cursor() as cur:
            cur.execute("SELECT code, payload FROM ontology_elements WHERE space_id=%s AND resource_type='rule'", (sid,))
            rules = {r[0]: r[1] for r in cur.fetchall()}
        hard_rules = [c for c, p in rules.items() if p.get("rule_type") == "硬规则" or "Veto" in str(p)]
        report.add(CheckResult("硬规则存在", len(hard_rules) >= 5, f"找到{len(hard_rules)}条硬规则"))

        # 1.6 属性
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM ontology_elements WHERE space_id=%s AND resource_type='property'", (sid,))
            prop_cnt = cur.fetchone()[0]
        report.add(CheckResult("属性数量≥40", prop_cnt >= 40, f"实际={prop_cnt}"))

        # 1.7 引用边
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM reference_edges WHERE space_id=%s", (sid,))
            edge_cnt = cur.fetchone()[0]
        report.add(CheckResult("引用边存在", edge_cnt > 0, f"数量={edge_cnt}"))

        # 1.8 版本与审计
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM version_records WHERE space_id=%s", (sid,))
            ver_cnt = cur.fetchone()[0]
        report.add(CheckResult("版本记录", ver_cnt > 0, f"数量={ver_cnt}"))

        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM audit_logs")
            audit_cnt = cur.fetchone()[0]
        report.add(CheckResult("审计日志", audit_cnt > 0, f"数量={audit_cnt}"))

        # 1.9 对象→属性的边（本体完整性）
        with conn.cursor() as cur:
            cur.execute("""
                SELECT re.edge_type, count(*)
                FROM reference_edges re
                WHERE re.space_id = %s AND re.edge_type = 'HAS_PROPERTY'
                GROUP BY re.edge_type
            """, (sid,))
            has_prop = cur.fetchone()
        has_prop_cnt = has_prop[1] if has_prop else 0
        report.add(CheckResult("对象→属性边", has_prop_cnt > 0, f"HAS_PROPERTY={has_prop_cnt}"))

        conn.close()

    except ImportError:
        report.add(CheckResult("数据库连接", False, "psycopg 未安装，请先 pip install -r requirements.txt"))
    except Exception as e:
        report.add(CheckResult("数据库查询", False, str(e)))

    return report


# ──────────────────────────────────────────
# 关2：图穿透
# ──────────────────────────────────────────
def level_2() -> LevelReport:
    """关2：验证Neo4j图数据库中节点、边、穿透路径"""
    report = LevelReport(2, "图穿透 · Neo4j语义网络")

    try:
        from neo4j import GraphDatabase
        from config import NEO4J_PASSWORD, NEO4J_URI, NEO4J_USER

        driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        driver.verify_connectivity()

        # 2.1 节点存在
        with driver.session() as s:
            result = s.run("MATCH (n:OntologyNode) RETURN count(n) AS cnt").single()
            node_cnt = result["cnt"] if result else 0
        report.add(CheckResult("图中有节点", node_cnt > 0, f"节点数={node_cnt}"))

        # 2.2 核心节点标签
        with driver.session() as s:
            result = s.run("""
                MATCH (n:OntologyNode)
                RETURN n.resource_type AS type, count(*) AS cnt
                ORDER BY cnt DESC
            """).data()
        types = {r["type"]: r["cnt"] for r in result}
        report.add(CheckResult("节点类型分布", "object" in types,
                               f"object={types.get('object',0)}, relation={types.get('relation',0)}, "
                               f"action={types.get('action',0)}, rule={types.get('rule',0)}"))

        # 2.3 关系边
        with driver.session() as s:
            result = s.run("""
                MATCH ()-[r]->()
                RETURN type(r) AS t, count(*) AS cnt
                ORDER BY cnt DESC
            """).data()
        edge_types = {r["t"]: r["cnt"] for r in result}
        report.add(CheckResult("图中有边", len(edge_types) > 0,
                               f"{len(edge_types)} 种边: {', '.join(f'{k}={v}' for k,v in list(edge_types.items())[:4])}"))

        # 2.4 HAS_PROPERTY 边
        has_prop = edge_types.get("HAS_PROPERTY", 0)
        report.add(CheckResult("HAS_PROPERTY边", has_prop > 0, f"数量={has_prop}"))

        # 2.5 图穿透深度（核心断言）
        with driver.session() as s:
            result = s.run("""
                MATCH path = (a:OntologyNode)-[*1..3]-(b:OntologyNode)
                WHERE a <> b
                RETURN length(path) AS len, [n IN nodes(path) | n.code] AS codes
                LIMIT 5
            """).data()
        deep_paths = [r for r in result if r["len"] >= 2]
        report.add(CheckResult("深度≥2的路径存在", len(deep_paths) > 0,
                               f"找到{len(deep_paths)}条≥2跳路径" + (f", 示例: {'->'.join(deep_paths[0]['codes'][:4])}" if deep_paths else "")))

        # 2.6 local-graph API
        try:
            import requests
            r = requests.get(f"{API_BASE}/api/spaces", timeout=10)
            spaces = r.json().get("data", [])
            if spaces:
                sid = spaces[0]["id"]
                r2 = requests.get(f"{API_BASE}/api/ontology/{sid}/objects?page_size=1", timeout=10)
                items = r2.json().get("data", {}).get("items", [])
                if items:
                    eid = items[0]["id"]
                    r3 = requests.get(f"{API_BASE}/api/ontology/{sid}/objects/{eid}/local-graph?depth=1", timeout=10)
                    graph = r3.json().get("data", {})
                    nodes = graph.get("nodes", [])
                    edges = graph.get("edges", [])
                    report.add(CheckResult("local-graph API", len(nodes) > 0,
                                           f"nodes={len(nodes)}, edges={len(edges)}"))
                else:
                    report.add(CheckResult("local-graph API", False, "无对象可测试"))
            else:
                report.add(CheckResult("local-graph API", False, "无空间"))
        except Exception as e:
            report.add(CheckResult("local-graph API", False, str(e)))

        driver.close()

    except ImportError:
        report.add(CheckResult("Neo4j连接", False, "neo4j 未安装"))
    except Exception as e:
        report.add(CheckResult("Neo4j查询", False, str(e)))

    return report


# ──────────────────────────────────────────
# 关3：规则引擎
# ──────────────────────────────────────────
def level_3() -> LevelReport:
    """关3：验证规则、行为、约束的完整性和关联关系"""
    report = LevelReport(3, "规则引擎 · 条件→结果→行为链")

    try:
        import psycopg
        from config import PG_DB, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER

        conn = psycopg.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB,
            user=PG_USER, password=PG_PASSWORD,
        )

        with conn.cursor() as cur:
            cur.execute("SELECT id FROM ontology_spaces LIMIT 1")
            row = cur.fetchone()
        sid = row[0] if row else None

        if not sid:
            report.add(CheckResult("空间存在", False, "无空间"))
            conn.close()
            return report

        # 3.1 硬规则
        with conn.cursor() as cur:
            cur.execute("""
                SELECT code, name, payload FROM ontology_elements
                WHERE space_id=%s AND resource_type='rule'
                  AND (payload->>'rule_type' = '硬规则' OR payload->>'rule_type' LIKE '%%硬%%')
            """, (sid,))
            hard = cur.fetchall()
        report.add(CheckResult("硬规则存在", len(hard) >= 5, f"找到{len(hard)}条"))

        # 3.2 软规则
        with conn.cursor() as cur:
            cur.execute("""
                SELECT code, name, payload FROM ontology_elements
                WHERE space_id=%s AND resource_type='rule'
                  AND (payload->>'rule_type' = '软规则' OR payload->>'rule_type' LIKE '%%软%%')
            """, (sid,))
            soft = cur.fetchall()
        report.add(CheckResult("软规则存在", len(soft) >= 5, f"找到{len(soft)}条"))

        # 3.3 核心硬规则
        with conn.cursor() as cur:
            cur.execute("SELECT code FROM ontology_elements WHERE space_id=%s AND resource_type='rule'", (sid,))
            rule_codes = {r[0] for r in cur.fetchall()}
        core_rules = {"BlacklistVeto", "InvalidAuthorizationVeto", "AbnormalBusinessVeto",
                      "MissingMandatoryClauseVeto", "ApprovalGate"}
        missing = core_rules - rule_codes
        report.add(CheckResult("核心硬规则", not missing,
                               f"命中{len(core_rules & rule_codes)}/{len(core_rules)}" + (f", 缺{missing}" if missing else "")))

        # 3.4 核心软规则
        core_soft = {"LowCapitalVsAmount", "WeakLiabilityCap", "LongPaymentTerm"}
        missing_soft = core_soft - rule_codes
        report.add(CheckResult("核心软规则", not missing_soft,
                               f"命中{len(core_soft & rule_codes)}/{len(core_soft)}" + (f", 缺{missing_soft}" if missing_soft else "")))

        # 3.5 行为
        with conn.cursor() as cur:
            cur.execute("SELECT code, payload FROM ontology_elements WHERE space_id=%s AND resource_type='action'", (sid,))
            actions = {r[0]: r[1] for r in cur.fetchall()}
        expected_act = {"Veto", "RaiseRiskFinding", "RequireApproval", "BlockEffectiveness"}
        missing_act = expected_act - set(actions.keys())
        report.add(CheckResult("核心行为", not missing_act,
                               f"找到{len(actions)}个行为" + (f", 缺{missing_act}" if missing_act else "")))

        # 3.6 规则→行为的引用边
        with conn.cursor() as cur:
            cur.execute("""
                SELECT count(*) FROM reference_edges
                WHERE space_id=%s AND edge_type='REFERENCES_ACTION'
            """, (sid,))
            ref_cnt = cur.fetchone()[0]
        report.add(CheckResult("规则→行为引用边", ref_cnt > 0, f"REFERENCES_ACTION={ref_cnt}"))

        # 3.7 规则 payload 结构
        with conn.cursor() as cur:
            cur.execute("""
                SELECT code, payload FROM ontology_elements
                WHERE space_id=%s AND resource_type='rule' AND code='BlacklistVeto'
            """, (sid,))
            row = cur.fetchone()
        if row:
            payload = row[1]
            has_condition = "condition" in payload or "when" in str(payload)
            has_result = "result" in payload or "then" in str(payload)
            report.add(CheckResult("规则有条件和结果", has_condition and has_result,
                                   f"condition={has_condition}, result={has_result}"))
        else:
            report.add(CheckResult("BlacklistVeto规则", False, "未找到"))

        conn.close()

    except ImportError:
        report.add(CheckResult("数据库连接", False, "psycopg 未安装"))
    except Exception as e:
        report.add(CheckResult("数据库查询", False, str(e)))

    return report


# ──────────────────────────────────────────
# 关4：Agent 自主（框架预留）
# ──────────────────────────────────────────
def level_4() -> LevelReport:
    """关4：Agent 自主调查能力验证（后续阶段）"""
    report = LevelReport(4, "Agent自主 · 目标驱动调查（后续阶段）")

    report.add(CheckResult("本体切片API", True,
                           "框架预留：需提供 /api/ontology/{space}/slice?profile=xxx 接口"))
    report.add(CheckResult("图穿透工具", True,
                           "框架预留：图穿透能力已验证（关2）"))
    report.add(CheckResult("function-calling工具集", False,
                           "待实现：需要提供 tools.json 中8个工具的正式后端"))
    report.add(CheckResult("manus式自主调查", False,
                           "待实现：需要接入LLM + 自主规划循环"))

    return report


# ──────────────────────────────────────────
# 关5：语义 + 反幻觉（框架预留）
# ──────────────────────────────────────────
def level_5() -> LevelReport:
    """关5：条款原文读取 + 证据ID校验（后续阶段）"""
    report = LevelReport(5, "语义+反幻觉 · 条款原文与证据校验（后续阶段）")

    try:
        import psycopg
        from config import PG_DB, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER

        conn = psycopg.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB,
            user=PG_USER, password=PG_PASSWORD,
        )

        with conn.cursor() as cur:
            cur.execute("SELECT id FROM ontology_spaces LIMIT 1")
            row = cur.fetchone()
        sid = row[0] if row else None

        if sid:
            # 检查 Clause 对象是否存在
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT count(*) FROM ontology_elements
                    WHERE space_id=%s AND resource_type='object' AND code='Clause'
                """, (sid,))
                clause_obj = cur.fetchone()[0]
            report.add(CheckResult("Clause对象存在", clause_obj > 0,
                                   "条款语义验证的基础对象"))

            # 检查条款属性（text字段）
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT count(*) FROM ontology_elements
                    WHERE space_id=%s AND resource_type='property' AND code LIKE 'Clause.%'
                """, (sid,))
                clause_props = cur.fetchone()[0]
            report.add(CheckResult("Clause属性", clause_props > 0, f"数量={clause_props}"))
        else:
            report.add(CheckResult("空间存在", False, "无空间"))

        conn.close()
    except Exception as e:
        report.add(CheckResult("数据库查询", False, str(e)))

    report.add(CheckResult("条款原文读取API", False,
                           "待实现：/api/ontology/{space}/clauses/{id}/text"))
    report.add(CheckResult("反幻觉校验器", False,
                           "待实现：证据ID校验机制"))

    return report


# ──────────────────────────────────────────
# 关6：融合判断（框架预留）
# ──────────────────────────────────────────
def level_6() -> LevelReport:
    """关6：差异化处置 + 版本可复现（后续阶段）"""
    report = LevelReport(6, "融合判断 · 差异化处置与版本可复现（后续阶段）")

    try:
        import psycopg
        from config import PG_DB, PG_HOST, PG_PASSWORD, PG_PORT, PG_USER

        conn = psycopg.connect(
            host=PG_HOST, port=PG_PORT, dbname=PG_DB,
            user=PG_USER, password=PG_PASSWORD,
        )

        # 版本记录检查
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM version_records")
            ver_cnt = cur.fetchone()[0]
        report.add(CheckResult("版本记录机制", ver_cnt > 0,
                               f"已有{ver_cnt}条版本记录，支持历史可复现"))

        # 审计日志检查
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM audit_logs")
            audit_cnt = cur.fetchone()[0]
        report.add(CheckResult("审计日志机制", audit_cnt > 0,
                               f"已有{audit_cnt}条审计记录，支持决策回溯"))

        conn.close()
    except Exception as e:
        report.add(CheckResult("数据库查询", False, str(e)))

    report.add(CheckResult("差异化处置API", False,
                           "待实现：需要Agent综合判断层"))
    report.add(CheckResult("版本对比功能", False,
                           "待实现：/api/spaces/{id}/versions/compare"))

    return report


# ──────────────────────────────────────────
# 主控
# ──────────────────────────────────────────
LEVELS = {
    1: level_1,
    2: level_2,
    3: level_3,
    4: level_4,
    5: level_5,
    6: level_6,
}


def run_level(n: int) -> LevelReport:
    fn = LEVELS.get(n)
    if not fn:
        print(f"{RED}未知关卡: {n}{RESET}")
        sys.exit(1)
    return fn()


def main() -> int:
    print_banner()

    # 解析参数
    if len(sys.argv) > 1:
        try:
            targets = [int(a) for a in sys.argv[1:] if a.isdigit() and 1 <= int(a) <= 6]
        except ValueError:
            print(f"{RED}用法: python check_levels.py [1] [2] ... [6]{RESET}")
            return 1
    else:
        targets = list(range(1, 7))

    if not targets:
        targets = list(range(1, 7))

    results: dict[int, LevelReport] = {}
    for n in targets:
        results[n] = run_level(n)
        results[n].print()

    # 总结
    print(f"\n{GREEN}{'━' * 60}{RESET}")
    print(f"{GREEN}                    验证总结{RESET}")
    print(f"{GREEN}{'━' * 60}{RESET}")

    passed = 0
    for n in sorted(results):
        r = results[n]
        status = f"{GREEN}✅通过{RESET}" if r.passed() else f"{RED}❌未通过{RESET}"
        print(f"  关{n}: {status}  ({r.title})")
        if r.passed():
            passed += 1

    print()
    if passed == len(results):
        print(f"{GREEN}🎉🎉🎉 全部 {len(results)} 关通过！本体管理模块验证完成！{RESET}\n")
        return 0
    else:
        print(f"{YELLOW}⚠️  {passed}/{len(results)} 关通过，部分关卡需优化。{RESET}\n")
        return 1


if __name__ == "__main__":
    sys.exit(main())
