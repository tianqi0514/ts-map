#!/usr/bin/env python3
"""
check_ontology.py —— 本体数据完整性验证
验证 PostgreSQL 中的本体数据是否与验证数据集 ontology.yaml 一致。
对应验证数据集关1：本体边界。
"""

import sys

import psycopg

from config import (
    EXPECTED_ACTION_COUNT,
    EXPECTED_OBJECT_COUNT,
    EXPECTED_PROPERTY_COUNT,
    EXPECTED_RELATION_COUNT,
    EXPECTED_RULE_COUNT,
    PG_DB,
    PG_HOST,
    PG_PASSWORD,
    PG_PORT,
    PG_USER,
)
from utils import GREEN, RED, RESET, YELLOW, CheckResult, LevelReport, load_yaml, pretty


def get_db():
    return psycopg.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB,
        user=PG_USER, password=PG_PASSWORD,
    )


def get_space_id() -> str | None:
    """获取第一个本体空间的ID"""
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT id, code, name FROM ontology_spaces LIMIT 1")
        row = cur.fetchone()
    conn.close()
    return row[0] if row else None


def check_space_exists() -> CheckResult:
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT code, name, domain FROM ontology_spaces WHERE code = 'single_contract_ontology'")
        row = cur.fetchone()
    conn.close()

    if row:
        return CheckResult("本体空间存在", True, f"code={row[0]}, name={row[1]}")
    return CheckResult("本体空间存在", False, "未找到 single_contract_ontology 空间")


def check_object_count() -> CheckResult:
    sid = get_space_id()
    if not sid:
        return CheckResult("对象数量", False, "无空间")

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM ontology_elements WHERE space_id = %s AND resource_type = 'object'",
            (sid,)
        )
        cnt = cur.fetchone()[0]
    conn.close()

    if cnt >= EXPECTED_OBJECT_COUNT:
        return CheckResult("对象数量", True, f"实际={cnt}, 期望≥{EXPECTED_OBJECT_COUNT}")
    return CheckResult("对象数量", False, f"实际={cnt}, 期望≥{EXPECTED_OBJECT_COUNT}")


def check_object_codes() -> CheckResult:
    """验证核心对象编码是否存在"""
    sid = get_space_id()
    if not sid:
        return CheckResult("核心对象编码", False, "无空间")

    expected = {
        "Contract", "CounterParty", "OwnEntity", "Clause", "PaymentTerm",
        "Obligation", "Deliverable", "Milestone", "RiskFinding", "Approval"
    }

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT code FROM ontology_elements WHERE space_id = %s AND resource_type = 'object'",
            (sid,)
        )
        found = {r[0] for r in cur.fetchall()}
    conn.close()

    missing = expected - found
    if not missing:
        return CheckResult("核心对象编码", True, f"找到 {len(found)} 个对象")
    return CheckResult("核心对象编码", False, f"缺少: {missing}", detail=list(missing))


def check_relation_count() -> CheckResult:
    sid = get_space_id()
    if not sid:
        return CheckResult("关系数量", False, "无空间")

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM ontology_elements WHERE space_id = %s AND resource_type = 'relation'",
            (sid,)
        )
        cnt = cur.fetchone()[0]
    conn.close()

    if cnt >= EXPECTED_RELATION_COUNT:
        return CheckResult("关系数量", True, f"实际={cnt}, 期望≥{EXPECTED_RELATION_COUNT}")
    return CheckResult("关系数量", False, f"实际={cnt}, 期望≥{EXPECTED_RELATION_COUNT}")


def check_relation_codes() -> CheckResult:
    """验证核心关系编码"""
    sid = get_space_id()
    if not sid:
        return CheckResult("核心关系编码", False, "无空间")

    expected = {
        "signedByCounterparty", "hasClause", "hasPaymentTerm",
        "hasObligation", "hasRisk", "governedByPolicy"
    }

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT code FROM ontology_elements WHERE space_id = %s AND resource_type = 'relation'",
            (sid,)
        )
        found = {r[0] for r in cur.fetchall()}
    conn.close()

    missing = expected - found
    if not missing:
        return CheckResult("核心关系编码", True, f"找到 {len(found)} 个关系")
    return CheckResult("核心关系编码", False, f"缺少: {missing}")


def check_action_count() -> CheckResult:
    sid = get_space_id()
    if not sid:
        return CheckResult("行为数量", False, "无空间")

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM ontology_elements WHERE space_id = %s AND resource_type = 'action'",
            (sid,)
        )
        cnt = cur.fetchone()[0]
    conn.close()

    if cnt >= EXPECTED_ACTION_COUNT:
        return CheckResult("行为数量", True, f"实际={cnt}, 期望≥{EXPECTED_ACTION_COUNT}")
    return CheckResult("行为数量", False, f"实际={cnt}, 期望≥{EXPECTED_ACTION_COUNT}")


def check_action_codes() -> CheckResult:
    """验证核心行为编码"""
    sid = get_space_id()
    if not sid:
        return CheckResult("核心行为编码", False, "无空间")

    expected = {"Veto", "RaiseRiskFinding", "RequireApproval", "RequireHumanReview",
                "ProposeAmendment", "BlockEffectiveness", "Notify", "RecordDecision"}

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT code FROM ontology_elements WHERE space_id = %s AND resource_type = 'action'",
            (sid,)
        )
        found = {r[0] for r in cur.fetchall()}
    conn.close()

    missing = expected - found
    if not missing:
        return CheckResult("核心行为编码", True, f"找到 {len(found)} 个行为")
    return CheckResult("核心行为编码", False, f"缺少: {missing}")


def check_rule_count() -> CheckResult:
    sid = get_space_id()
    if not sid:
        return CheckResult("规则数量", False, "无空间")

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM ontology_elements WHERE space_id = %s AND resource_type = 'rule'",
            (sid,)
        )
        cnt = cur.fetchone()[0]
    conn.close()

    if cnt >= EXPECTED_RULE_COUNT:
        return CheckResult("规则数量", True, f"实际={cnt}, 期望≥{EXPECTED_RULE_COUNT}")
    return CheckResult("规则数量", False, f"实际={cnt}, 期望≥{EXPECTED_RULE_COUNT}")


def check_rule_codes() -> CheckResult:
    """验证核心规则编码"""
    sid = get_space_id()
    if not sid:
        return CheckResult("核心规则编码", False, "无空间")

    expected_hard = {"BlacklistVeto", "InvalidAuthorizationVeto", "AbnormalBusinessVeto",
                     "MissingMandatoryClauseVeto", "MissingQualificationVeto",
                     "PaymentExceedsAmountVeto", "ApprovalGate"}
    expected_soft = {"LowCapitalVsAmount", "WeakLiabilityCap", "LongPaymentTerm"}

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT code, payload FROM ontology_elements WHERE space_id = %s AND resource_type = 'rule'",
            (sid,)
        )
        rows = cur.fetchall()
    conn.close()

    found = {r[0] for r in rows}
    missing_hard = expected_hard - found
    missing_soft = expected_soft - found

    if not missing_hard and not missing_soft:
        return CheckResult("核心规则编码", True,
                          f"硬规则={len(expected_hard & found)}, 软规则={len(expected_soft & found)}")

    msg_parts = []
    if missing_hard:
        msg_parts.append(f"缺硬规则: {missing_hard}")
    if missing_soft:
        msg_parts.append(f"缺软规则: {missing_soft}")
    return CheckResult("核心规则编码", False, "; ".join(msg_parts))


def check_property_count() -> CheckResult:
    sid = get_space_id()
    if not sid:
        return CheckResult("属性数量", False, "无空间")

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM ontology_elements WHERE space_id = %s AND resource_type = 'property'",
            (sid,)
        )
        cnt = cur.fetchone()[0]
    conn.close()

    if cnt >= EXPECTED_PROPERTY_COUNT:
        return CheckResult("属性数量", True, f"实际={cnt}, 期望≥{EXPECTED_PROPERTY_COUNT}")
    return CheckResult("属性数量", False, f"实际={cnt}, 期望≥{EXPECTED_PROPERTY_COUNT}")


def check_reference_edges() -> CheckResult:
    """验证引用边是否正确建立"""
    sid = get_space_id()
    if not sid:
        return CheckResult("引用边", False, "无空间")

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT edge_type, count(*) FROM reference_edges WHERE space_id = %s GROUP BY edge_type",
            (sid,)
        )
        edges = {r[0]: r[1] for r in cur.fetchall()}
    conn.close()

    if not edges:
        return CheckResult("引用边", False, "无任何引用边")

    summary = ", ".join(f"{k}={v}" for k, v in list(edges.items())[:6])
    return CheckResult("引用边", True, f"{len(edges)} 种边类型, {summary}")


def check_version_records() -> CheckResult:
    """验证版本记录是否存在"""
    sid = get_space_id()
    if not sid:
        return CheckResult("版本记录", False, "无空间")

    conn = get_db()
    with conn.cursor() as cur:
        cur.execute(
            "SELECT count(*) FROM version_records WHERE space_id = %s",
            (sid,)
        )
        cnt = cur.fetchone()[0]
    conn.close()

    if cnt > 0:
        return CheckResult("版本记录", True, f"版本记录数: {cnt}")
    return CheckResult("版本记录", False, "无版本记录（模板初始化时应已生成）")


def check_audit_logs() -> CheckResult:
    """验证审计日志"""
    conn = get_db()
    with conn.cursor() as cur:
        cur.execute("SELECT count(*) FROM audit_logs")
        cnt = cur.fetchone()[0]
    conn.close()

    if cnt > 0:
        return CheckResult("审计日志", True, f"审计日志数: {cnt}")
    return CheckResult("审计日志", False, "无审计日志")


def check_against_yaml() -> CheckResult:
    """将数据库数据与 ontology.yaml 对照"""
    try:
        yaml_data = load_yaml("ontology.yaml")
        ontology = yaml_data.get("ontology", {})

        sid = get_space_id()
        if not sid:
            return CheckResult("YAML对照", False, "无空间")

        conn = get_db()
        with conn.cursor() as cur:
            # 对象对照
            cur.execute(
                "SELECT code, name FROM ontology_elements WHERE space_id = %s AND resource_type = 'object'",
                (sid,)
            )
            db_objects = {r[0]: r[1] for r in cur.fetchall()}

            # 关系对照
            cur.execute(
                "SELECT code, name FROM ontology_elements WHERE space_id = %s AND resource_type = 'relation'",
                (sid,)
            )
            db_relations = {r[0]: r[1] for r in cur.fetchall()}
        conn.close()

        yaml_objects = set(ontology.get("objects", {}).keys())
        yaml_links = {link["name"] for link in ontology.get("links", [])}

        obj_match = yaml_objects & set(db_objects.keys())
        rel_match = yaml_links & set(db_relations.keys())

        msg = f"对象匹配: {len(obj_match)}/{len(yaml_objects)}, 关系匹配: {len(rel_match)}/{len(yaml_links)}"
        if len(obj_match) >= EXPECTED_OBJECT_COUNT and len(rel_match) >= 15:
            return CheckResult("YAML对照", True, msg)
        return CheckResult("YAML对照", False, msg)

    except Exception as e:
        return CheckResult("YAML对照", False, f"YAML读取失败: {e}")


def main() -> None:
    print(f"\n{GREEN}╔══════════════════════════════════════════════════════════════╗")
    print(f"║              本体数据完整性验证                              ║")
    print(f"║              对应验证数据集 · 关1 · 本体边界                  ║")
    print(f"╚══════════════════════════════════════════════════════════════╝{RESET}\n")

    report = LevelReport(1, "本体边界")

    report.add(check_space_exists())
    report.add(check_object_count())
    report.add(check_object_codes())
    report.add(check_relation_count())
    report.add(check_relation_codes())
    report.add(check_action_count())
    report.add(check_action_codes())
    report.add(check_rule_count())
    report.add(check_rule_codes())
    report.add(check_property_count())
    report.add(check_reference_edges())
    report.add(check_version_records())
    report.add(check_audit_logs())
    report.add(check_against_yaml())

    report.print()
    return 0 if report.passed() else 1


if __name__ == "__main__":
    sys.exit(main())
