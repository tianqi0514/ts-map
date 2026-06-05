// ============================================================
// queries.cypher —— 三个故事的关键查询（灌完 seed.cypher 后逐段跑）
// ============================================================

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 故事一 · 图穿透：新合同 C-2024-007 的主体，其最终受益人是否关联黑名单实体？
//   纯规则只查 S-301 自身是否黑名单 → 否 → 漏。图穿透 2~3 跳即抓到。
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

// A2 · 完整穿透路径：S-301 → 海岳控股 → 王某 → (黑名单)S-900
MATCH (c:Contract {contractNo:"C-2024-007"})-[:SIGNED_BY_COUNTERPARTY]->(p:CounterParty)
MATCH path = (p)-[:HAS_SHAREHOLDER*1..3]->(ubo:Person)<-[:HAS_SHAREHOLDER*1..3]-(bad:CounterParty {status:"黑名单"})
RETURN p.name AS 新主体, ubo.name AS 共同最终受益人, bad.name AS 关联黑名单实体, [n IN nodes(path) | coalesce(n.name,n.taxId)] AS 穿透路径;

// A1 · 对照证明：S-301 自身字段全清白（不在黑名单、经营正常、征信高）——纯规则会放行
MATCH (p:CounterParty {taxId:"S-301"})
RETURN p.name, p.status AS 主体状态, p.businessStatus AS 经营状态, p.creditScore AS 征信;

// A3 对照基线（纯规则视角）：只查主体自己是否黑名单 → 返回空 = "通过"（这就是会漏的原因）
MATCH (c:Contract {contractNo:"C-2024-007"})-[:SIGNED_BY_COUNTERPARTY]->(p:CounterParty {status:"黑名单"})
RETURN p.name AS 命中黑名单的主体;   // 期望：0 行（纯规则放行）

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 故事三 · 本体一致性 + 版本可复现
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

// C1 · 改一处全局一致：找出"按其适用政策版本，缺强制条款"的所有在审合同
//   政策的 mandatoryClauses 改一处，这条查询自动对所有合同生效（001/005/006 一起命中"缺数据合规"）
MATCH (c:Contract {status:"审核中"})-[:GOVERNED_BY_POLICY]->(pol:CompliancePolicy)
WITH c, pol, split(pol.mandatoryClauses, "; ") AS required
UNWIND required AS need
OPTIONAL MATCH (c)-[:HAS_CLAUSE]->(cl:Clause {clauseType: need})
WITH c.contractNo AS 合同, pol.version AS 政策版本, need AS 强制条款, cl
WHERE cl IS NULL
RETURN 合同, 政策版本, collect(强制条款) AS 缺失的强制条款
ORDER BY 合同;
// 期望：C-2024-001 / 005 / 006 均缺 [数据合规]；C-2024-007 不缺（条款齐全）

// C2 · 历史可复现：同一份去年合同 C-2023-088，用 v1 与 v2 两套政策分别评，结果可溯
//   —— 用 v1（它当时锁定的版本）：缺失为空 = 当时合规、通过
MATCH (c:Contract {contractNo:"C-2023-088"})
MATCH (pol:CompliancePolicy {policyId:"CP-PROC", version:"v1"})
WITH c, pol, split(pol.mandatoryClauses, "; ") AS required
UNWIND required AS need
OPTIONAL MATCH (c)-[:HAS_CLAUSE]->(cl:Clause {clauseType: need})
WITH need, cl WHERE cl IS NULL
RETURN "v1" AS 按版本, collect(need) AS 缺失条款;   // 期望：[] 空 → 通过
//   —— 用 v2 重放：缺"数据合规" → 若按今天标准则不合规（证明差异可追溯到版本）
MATCH (c:Contract {contractNo:"C-2023-088"})
MATCH (pol:CompliancePolicy {policyId:"CP-PROC", version:"v2"})
WITH c, pol, split(pol.mandatoryClauses, "; ") AS required
UNWIND required AS need
OPTIONAL MATCH (c)-[:HAS_CLAUSE]->(cl:Clause {clauseType: need})
WITH need, cl WHERE cl IS NULL
RETURN "v2" AS 按版本, collect(need) AS 缺失条款;   // 期望：[数据合规]

// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
// 故事二 · 多源事实归集（无需 LLM；确定性取证，见 README 方案①）
//   把主体的外部事实/历史在图上一次取齐，供"模板归集"生成定性提示。
//   注：ExternalFact / CoopHistory 不在图里，由程序从 seed.json 读取后与下方主体事实合并。
// ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
MATCH (c:Contract {contractNo:"C-2024-001"})-[:SIGNED_BY_COUNTERPARTY]->(p:CounterParty)
RETURN p.name AS 主体, p.paidCapital AS 实缴, c.amount AS 合同额,
       p.establishedDate AS 成立日, p.creditScore AS 征信;
// 程序再并入 seed.json 的 ExternalFact(涉诉3起) + CoopHistory(2次交付延期)，
// 套模板得："实缴50万<合同120万、成立<12月、涉诉3起、历史2次延期 → 关注履约，建议补担保"(每条带 source+fetchedAt)
