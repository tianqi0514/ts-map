# -*- coding: utf-8 -*-
"""
tool_backend.py —— 8 个 function-calling 工具的参考实现（对接 Neo4j + seed.json）
配合《复现实战指南.md》闯关使用。含 3 处【关卡留白 TODO】，补全才能通关。
依赖: pip install neo4j   (可选; 未装则图工具走 seed.json 内存回退)
数据: 同目录 seed.json
"""
import json, os
from functools import lru_cache

# ---------------- 数据加载 ----------------
SEED = json.load(open(os.path.join(os.path.dirname(__file__), "seed.json"), encoding="utf-8"))

def _index(coll, key):
    return {r[key]: r for r in SEED.get(coll, [])}

CONTRACT = _index("Contract", "contractNo")
PARTY    = _index("CounterParty", "taxId")
CLAUSE_BY_CONTRACT = {}
for c in SEED["Clause"]:
    CLAUSE_BY_CONTRACT.setdefault(c["contract"], []).append(c)
POLICY = {(p["policyId"], p["version"]): p for p in SEED["CompliancePolicy"]}

# ---------------- 本体切片（关1 的边界来源）----------------
# 切片 = 该 profile 可见的对象/字段（声明式权限）。越界字段不可读。
SLICES = {
    "subject-due-diligence": {
        "objects": {
            "CounterParty": ["taxId","name","status","regCapital","paidCapital","establishedDate",
                              "businessStatus","creditScore","regAddress","bankAcctTail","registrant"],
            "Contract": ["contractNo","type","amount","counterparty"],
        },
        "links": ["HAS_SHAREHOLDER","HAS_LEGAL_REP","SIGNED_BY_COUNTERPARTY"],
        "excluded": ["PaymentTerm.*","Payment.*","Clause.text"],   # 主体审核看不到付款明细/条款原文
    },
    "legal-procurement": {
        "objects": {
            "Contract": ["contractNo","type","amount","involvesPII","fulfillmentProgress","counterpartyCoop"],
            "Clause": ["clauseId","clauseType","mandatory","text"],
            "CounterParty": ["taxId","name","paidCapital","establishedDate","status"],
        },
        "links": ["HAS_CLAUSE","SIGNED_BY_COUNTERPARTY","GOVERNED_BY_POLICY"],
        "excluded": ["CounterParty.creditScore","CounterParty.bankAcctTail"],  # 法务条款审核不看信用分/账户
    },
}

# ---------------- Neo4j（可选，未装则回退内存图）----------------
def _neo4j():
    try:
        from neo4j import GraphDatabase
        drv = GraphDatabase.driver(os.environ.get("NEO4J_URI","bolt://localhost:7687"),
                                   auth=(os.environ.get("NEO4J_USER","neo4j"), os.environ.get("NEO4J_PWD","neo4j")))
        drv.verify_connectivity(); return drv
    except Exception:
        return None
DRV = _neo4j()

# 内存图回退：邻接表（持有方向：party -[HAS_SHAREHOLDER]-> holder）
SH_OUT, SH_IN = {}, {}
for e in SEED["Shareholder"]:
    SH_OUT.setdefault(e["party"], []).append(e["holder"])
    SH_IN.setdefault(e["holder"], []).append(e["party"])

# ============================================================
# 工具实现
# ============================================================
def ontology_get_slice(profile):
    s = SLICES.get(profile)
    if not s: return {"error": f"unknown profile {profile}"}
    return {"profile": profile, "objects": s["objects"], "links": s["links"], "excluded": s["excluded"]}

def entity_get(id, fields=None, _profile="subject-due-diligence"):
    rec = PARTY.get(id) or CONTRACT.get(id)
    if not rec: return {"error": f"not found {id}"}
    slice_ = SLICES[_profile]
    label = "CounterParty" if id in PARTY else "Contract"
    allowed = set(slice_["objects"].get(label, []))
    out, forbidden = {}, []
    want = fields or list(rec.keys())
    for f in want:
        # 【关卡留白 TODO-1 · 切片权限边界】
        #   只允许返回 allowed 集合内的字段；越界字段不要返回值，应记入 forbidden。
        #   提示：if f in allowed: out[f]=rec.get(f)  else: forbidden.append(f)
        #   —— 不实现的话，Agent 能读到越界字段（如主体审核读到付款明细），故事二最小权限就崩了。
        out[f] = rec.get(f)   # ← 替换为带边界判断的实现
    return {"id": id, "fields": out, "forbidden": forbidden, "_hint": "TODO-1 未补：当前未做切片边界"}

def graph_traverse(startId, rel, hops, direction="out"):
    if rel != "HAS_SHAREHOLDER":
        return {"error": "本参考实现仅示范 HAS_SHAREHOLDER 穿透；其余关系研发自行扩展"}
    # 【关卡留白 TODO-2 · 多跳穿透 + 方向 + 去重防环】
    #   实现从 startId 沿 HAS_SHAREHOLDER 走 1..hops 跳，按 direction(out/in/both) 取邻接，
    #   返回所有到达的终点及路径；必须去重、防止环路无限递归。
    #   提示：BFS/DFS，visited 集合防环；out 用 SH_OUT，in 用 SH_IN，both 取并集。
    #   —— 不实现的话，故事一查不出 S-301→海岳控股→王某→S-900 的穿透链。
    def neighbors(n):
        if direction == "out": return SH_OUT.get(n, [])
        if direction == "in":  return SH_IN.get(n, [])
        return SH_OUT.get(n, []) + SH_IN.get(n, [])
    paths = []
    # —— 下面是“只走 1 跳”的残缺版，请扩展为 1..hops 的完整遍历 ——
    for nb in neighbors(startId):
        paths.append([startId, nb])
    return {"start": startId, "rel": rel, "hops": hops, "direction": direction,
            "paths": paths, "_hint": "TODO-2 未补：当前只走了 1 跳"}

def graph_common_neighbors(a, b):
    # 共同邻居（含共同 UBO / 共同关联）。参考实现：取双方 HAS_SHAREHOLDER 出邻交集 + 弱信号里的共同点
    na = set(SH_OUT.get(a, [])); nb = set(SH_OUT.get(b, []))
    common = sorted(na & nb)
    weak = [w for w in SEED.get("WeakSignal", []) if {w.get("a"), w.get("b")} & {a} and {w.get("a"), w.get("b")} & {b}]
    return {"a": a, "b": b, "commonShareholders": common, "weakSignals": weak}

def graph_shortest_path(a, b, maxHops=4):
    # BFS 最短关联路径（沿 HAS_SHAREHOLDER 双向）
    from collections import deque
    q = deque([(a, [a])]); seen = {a}
    while q:
        node, path = q.popleft()
        if node == b: return {"a": a, "b": b, "path": path, "hops": len(path)-1}
        if len(path)-1 >= maxHops: continue
        for nb in set(SH_OUT.get(node, []) + SH_IN.get(node, [])):
            if nb not in seen:
                seen.add(nb); q.append((nb, path+[nb]))
    return {"a": a, "b": b, "path": None, "note": "maxHops 内无路径"}

def clause_read_text(contractId):
    cls = CLAUSE_BY_CONTRACT.get(contractId, [])
    return {"contractId": contractId,
            "clauses": [{"clauseId": c["clauseId"], "clauseType": c["clauseType"],
                         "mandatory": c.get("mandatory"), "text": c.get("text","(无原文)")} for c in cls]}

def external_lookup(entity, source):
    out = []
    for f in SEED.get("ExternalFact", []):
        if f["about"] == entity and (source in f["source"]):
            out.append(f)
    if source in ("bankflow","registry","gsxt"):
        out += [w for w in SEED.get("WeakSignal", []) if w.get("a")==entity or w.get("b")==entity]
    return {"entity": entity, "source": source, "facts": out}

def rule_evaluate(contractId, policyVersion=None):
    """最小规则评估器（覆盖本验证所需硬规则）。研发可替换为正式规则引擎。"""
    c = CONTRACT.get(contractId)
    if not c: return {"error": f"not found {contractId}"}
    ver = policyVersion or c.get("policyVersion","v2")
    pol = POLICY.get(("CP-PROC", ver), {})
    findings, vetoes = [], []
    # 硬规则：缺强制条款（按政策版本）—— 关3 要让它吃 policyVersion
    have = {cl["clauseType"] for cl in CLAUSE_BY_CONTRACT.get(contractId, [])}
    for need in pol.get("mandatoryClauses", []):
        if need not in have:
            findings.append({"rule":"MissingMandatoryClauseVeto","level":"高",
                             "type":f"缺强制条款:{need}","ruleType":"硬",
                             "evidence":[f"policy:CP-PROC@{ver}"]})
            vetoes.append("MissingMandatoryClauseVeto")
    # 硬规则：主体黑名单 / 非存续
    p = PARTY.get(c.get("counterparty"), {})
    if p.get("status")=="黑名单": vetoes.append("BlacklistVeto")
    if p.get("businessStatus") in ("吊销","注销"): vetoes.append("AbnormalBusinessVeto")
    # 软规则：实缴 < 合同额（信号）
    if p.get("paidCapital") is not None and p["paidCapital"] < c.get("amount",0):
        findings.append({"rule":"LowCapitalVsAmount","level":"中","type":"实缴远低于合同额",
                         "ruleType":"软","evidence":[f"fact:{p['taxId']}.paidCapital"]})
    return {"contractId": contractId, "policyVersion": ver,
            "vetoes": vetoes, "findings": findings,
            "note": "符号引擎确定性结论；语义/关系判断由 Agent 补"}

# ---------------- 分发器（供 Agent 主循环调用）----------------
DISPATCH = {
    "ontology_get_slice": ontology_get_slice, "entity_get": entity_get,
    "graph_traverse": graph_traverse, "graph_common_neighbors": graph_common_neighbors,
    "graph_shortest_path": graph_shortest_path, "clause_read_text": clause_read_text,
    "external_lookup": external_lookup, "rule_evaluate": rule_evaluate,
}
def dispatch(name, args):
    fn = DISPATCH.get(name)
    if not fn: return {"error": f"unknown tool {name}"}
    return fn(**args)

if __name__ == "__main__":
    print("自检：rule_evaluate(C-2024-001) =", json.dumps(rule_evaluate("C-2024-001"), ensure_ascii=False))
