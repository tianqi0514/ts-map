# -*- coding: utf-8 -*-
"""[参考答案 SOLVED] checks_solved.py —— 六关自测。补全 tool_backend.py 的 TODO 后逐关跑：python checks.py 1"""
import sys, json
import tool_backend_solved as tb

def ok(b): return "✅ 通过" if b else "❌ 未过"

def check1():
    print("关1 · 本体切片权限边界")
    r = tb.entity_get("S-204", fields=["name","creditScore","bankAcctTail"], _profile="legal-procurement")
    # legal-procurement 切片不含 creditScore / bankAcctTail → 应进 forbidden
    pass_ = ("creditScore" in r.get("forbidden",[])) and ("bankAcctTail" in r.get("forbidden",[])) \
            and ("creditScore" not in r.get("fields",{}))
    print("  越界字段被挡:", ok(pass_), "| forbidden=", r.get("forbidden"))
    return pass_

def check2():
    print("关2 · 图穿透(多跳+方向)")
    r = tb.graph_traverse("S-301", "HAS_SHAREHOLDER", hops=3, direction="out")
    reached = {p[-1] for p in r.get("paths",[])}
    pass_ = "王某" in reached   # S-301→海岳控股(HD-CTRL)→王某
    print("  S-301 穿透到 UBO 王某:", ok(pass_), "| 终点=", sorted(reached))
    return pass_

def check3():
    print("关3 · 规则引擎按政策版本评估")
    v1 = tb.rule_evaluate("C-2023-088", policyVersion="v1")
    v2 = tb.rule_evaluate("C-2023-088", policyVersion="v2")
    pass_ = (len(v1["vetoes"])==0) and ("MissingMandatoryClauseVeto" in v2["vetoes"])
    print("  C-2023-088 v1通过 / v2缺条款:", ok(pass_), "| v1否决=",v1["vetoes"]," v2否决=",v2["vetoes"])
    return pass_

def check4():
    print("关4 · Agent 自主深挖(借壳拼图)——需接 LLM 跑 Agent，此处校验图能力支撑是否就绪")
    # 自主性靠 Agent 主循环体现；自测先确认拼图所需图能力可用：S-301 与 S-204 共同 UBO + 弱信号
    cn = tb.graph_common_neighbors("S-301", "S-204")
    # 经穿透两者最终受益人都是王某（直接共同邻居可能为空，需穿透）；这里校验弱信号已可取
    weak = tb.external_lookup("S-301","bankflow")["facts"]
    sp = tb.graph_shortest_path("S-301","S-900")
    pass_ = (len(weak)>0) and (sp.get("path") is not None)
    print("  弱信号可取 & S-301↔S-900 有关联路径:", ok(pass_), "| path=", sp.get("path"))
    print("  (A4 自主性最终由 Agent 轨迹判定：是否未经预设自行发起横向拼图)")
    return pass_

def check5():
    print("关5 · 语义可读 + 证据校验(反幻觉)")
    txt = tb.clause_read_text("C-2024-001")
    has_trap = any("直接损失" in c["text"] for c in txt["clauses"])  # 责任上限被架空的原文在
    # 【关卡留白 TODO-3 · 证据校验器】见 verify_citations；补全后下面应为 True
    good = verify_citations(["C-2024-001#03","policy:CP-PROC@v2"], txt)
    bad  = verify_citations(["C-2024-001#99(编造)"], txt)
    pass_ = has_trap and good and (not bad)
    print("  原文含语义陷阱:", ok(has_trap), "| 真id通过&假id拦截:", ok(good and not bad))
    return pass_

def verify_citations(cited_ids, clause_ctx):
    """TODO-3 · 反幻觉证据校验：cited_ids 里每个 id 必须真实存在(条款id 或 policy: 前缀)。
       全部存在返回 True，出现编造的返回 False。"""
    real = {c["clauseId"] for c in clause_ctx["clauses"]}
    # 【SOLVED · TODO-3 反幻觉证据校验】clause 类 id 必须真实存在；policy:/fact: 前缀视为合法来源
    return all(cid in real or cid.split(':')[0] in ('policy', 'fact') for cid in cited_ids)

def check6():
    print("关6 · 差异化处置(同样缺条款，处置不同)——由 Agent 出，自测校验上下文可取")
    ctx = {}
    for cid in ["C-2024-001","C-2024-005","C-2024-006"]:
        c = tb.CONTRACT[cid]
        ctx[cid] = (c.get("involvesPII"), c.get("counterpartyCoop"), c.get("fulfillmentProgress"))
    distinct = len(set(ctx.values())) == 3   # 三份上下文各不同 → 支撑差异化处置
    print("  三份合同处置上下文各异:", ok(distinct), "|", ctx)
    return distinct

CHECKS = {1:check1,2:check2,3:check3,4:check4,5:check5,6:check6}
if __name__ == "__main__":
    ns = [int(x) for x in sys.argv[1:]] or list(CHECKS)
    res = {n: CHECKS[n]() for n in ns}
    print("\n小结:", {f"关{n}": ("过" if v else "未过") for n,v in res.items()})
