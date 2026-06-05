import React from "react";
import {
  AlertTriangle,
  Ban,
  CheckCircle,
  ChevronDown,
  ChevronRight,
  ChevronUp,
  Play,
  Scale,
  Shield,
  Terminal,
  X,
  Zap,
} from "lucide-react";
import type { RuleEngineResult, Space } from "./types";
import { api } from "./api";

const SCENARIOS = [
  { code: "contract_review", name: "合同审核", desc: "大额合同 + 未审批场景" },
  { code: "factoring_risk", name: "保理风控", desc: "高风险应收账款场景" },
  { code: "battery_scheduling", name: "锂电池排程", desc: "产能满载排程场景" },
];

const TEST_DATA_PRESETS: Record<string, Record<string, unknown>> = {
  contract_review: {
    contract: {
      contractNo: "CT-2024-1001",
      title: "设备采购合同",
      contractType: "采购合同",
      amount: 1500000,
      signDate: "2024-01-15",
      status: "审批中",
      effectiveCondition: "双方签字盖章",
    },
    party: {
      entityId: "ENT-001",
      name: "ABC科技有限公司",
      creditScore: 75,
      regCapital: 5000000,
      businessStatus: "存续",
    },
    approval: {
      apId: "AP-001",
      approver: "张经理",
      decision: "待审批",
      decidedAt: null,
    },
    payment_plan: {
      planAmount: 500000,
      paymentDays: 30,
      stage: "首付款",
    },
    risk: { level: "中" },
  },
  factoring_risk: {
    receivable: {
      receivableId: "REC-001",
      amount: 2000000,
      dueDate: "2024-06-30",
      debtorCredit: "B",
    },
    party: {
      entityId: "ENT-002",
      name: "XYZ贸易公司",
      creditScore: 65,
      regCapital: 2000000,
    },
    risk: { level: "高" },
  },
  battery_scheduling: {
    order: {
      orderId: "ORD-001",
      productType: "磷酸铁锂电池",
      quantity: 5000,
      deliveryDate: "2024-03-15",
    },
    production_line: {
      lineId: "LINE-A",
      capacity: 1000,
      currentLoad: 900,
    },
  },
};

export default function RuleEnginePanel({ spaces }: { spaces: Space[] }) {
  const [selectedSpaceId, setSelectedSpaceId] = React.useState("");
  const [scenario, setScenario] = React.useState("contract_review");
  const [testData, setTestData] = React.useState(
    JSON.stringify(TEST_DATA_PRESETS.contract_review, null, 2)
  );
  const [result, setResult] = React.useState<RuleEngineResult | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const [expandedReasoning, setExpandedReasoning] = React.useState<Set<string>>(
    new Set()
  );
  // 自然语言测试
  const [nlScene, setNlScene] = React.useState("");
  const [nlLoading, setNlLoading] = React.useState(false);
  const [nlResult, setNlResult] = React.useState<{
    scene_description: string;
    test_data: Record<string, unknown>;
    rule_result: RuleEngineResult;
    llm_model: string;
  } | null>(null);
  const [nlError, setNlError] = React.useState("");

  React.useEffect(() => {
    setTestData(JSON.stringify(TEST_DATA_PRESETS[scenario], null, 2));
  }, [scenario]);

  async function execute() {
    if (!selectedSpaceId) {
      setError("请先选择本体空间");
      return;
    }
    let data: Record<string, unknown>;
    try {
      data = JSON.parse(testData);
    } catch {
      setError("测试数据必须是合法 JSON");
      return;
    }
    setError("");
    setLoading(true);
    try {
      const res = await api<RuleEngineResult>("/api/brain/rule-engine/execute", {
        method: "POST",
        body: JSON.stringify({ space_id: selectedSpaceId, data }),
      });
      setResult(res.data);
      // 默认展开所有命中规则的推理
      const newExpanded = new Set<string>();
      res.data.hits.forEach((h) => newExpanded.add(h.rule_id));
      setExpandedReasoning(newExpanded);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  function toggleReasoning(ruleId: string) {
    setExpandedReasoning((prev) => {
      const next = new Set(prev);
      if (next.has(ruleId)) {
        next.delete(ruleId);
      } else {
        next.add(ruleId);
      }
      return next;
    });
  }

  async function nlExecute() {
    if (!selectedSpaceId) {
      setNlError("请先选择本体空间");
      return;
    }
    if (!nlScene.trim()) {
      setNlError("请输入场景描述");
      return;
    }
    setNlError("");
    setNlLoading(true);
    try {
      const res = await api<{
        scene_description: string;
        test_data: Record<string, unknown>;
        rule_result: RuleEngineResult;
        llm_model: string;
        error?: string;
      }>("/api/brain/rule-engine/nl-simple-test", {
        method: "POST",
        body: JSON.stringify({
          space_id: selectedSpaceId,
          scene_description: nlScene,
        }),
      });
      if (res.data?.error) {
        setNlError(res.data.error);
        setNlResult(null);
      } else {
        setNlResult(res.data);
        // 同时更新传统结果区域
        setResult(res.data.rule_result);
        // 把生成的数据填入 textarea
        setTestData(JSON.stringify(res.data.test_data, null, 2));
      }
    } catch (e) {
      setNlError(String(e));
    } finally {
      setNlLoading(false);
    }
  }

  return (
    <section className="resource-panel">
      <div className="rule-engine-layout">
        <div className="rule-engine-input">
          <h3>
            <Zap size={18} />
            规则引擎测试
          </h3>

          <label>
            选择本体空间
            <select
              value={selectedSpaceId}
              onChange={(e) => setSelectedSpaceId(e.target.value)}
            >
              <option value="">选择空间...</option>
              {spaces.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name} ({s.code})
                </option>
              ))}
            </select>
          </label>

          {/* ── 自然语言测试 ── */}
          <div
            style={{
              background: "#fafafa",
              border: "1px solid #e4e8ef",
              borderRadius: 10,
              padding: 14,
              marginBottom: 16,
            }}
          >
            <h4 style={{ margin: "0 0 10px", fontSize: 14, display: "flex", alignItems: "center", gap: 6 }}>
              <Zap size={14} />
              自然语言测试（LLM 生成数据）
            </h4>
            <label style={{ marginBottom: 8 }}>
              用中文描述测试场景
              <textarea
                value={nlScene}
                onChange={(e) => setNlScene(e.target.value)}
                rows={3}
                placeholder="如：一份200万的采购合同，还没有经过法务审批，合作方信用评分只有60分"
                style={{ fontSize: 13 }}
              />
            </label>
            {nlError && <p className="form-error">{nlError}</p>}
            <button
              className="primary-button"
              onClick={nlExecute}
              disabled={nlLoading || !selectedSpaceId}
              style={{ width: "100%" }}
            >
              {nlLoading ? "LLM 生成数据中..." : "🤖 LLM 生成数据并执行规则"}
            </button>
            {nlResult && (
              <div
                style={{
                  marginTop: 10,
                  padding: 10,
                  background: "#f6ffed",
                  borderRadius: 6,
                  fontSize: 12,
                  color: "#389e0d",
                }}
              >
                ✅ LLM ({nlResult.llm_model}) 已生成数据并执行规则，命中{" "}
                {nlResult.rule_result.hit_count} 条
              </div>
            )}
          </div>

          <div style={{ borderTop: "1px solid var(--line)", paddingTop: 16 }}>
            <h4 style={{ margin: "0 0 10px", fontSize: 14, color: "var(--muted)" }}>
              或手动选择场景
            </h4>
          </div>

          <label>
            测试场景
            <select
              value={scenario}
              onChange={(e) => setScenario(e.target.value)}
            >
              {SCENARIOS.map((s) => (
                <option key={s.code} value={s.code}>
                  {s.name} — {s.desc}
                </option>
              ))}
            </select>
          </label>

          <label>
            测试数据 JSON
            <textarea
              className="json-input"
              value={testData}
              onChange={(e) => setTestData(e.target.value)}
              rows={14}
            />
          </label>

          {error && <p className="form-error">{error}</p>}
          <button
            className="primary-button"
            onClick={execute}
            disabled={loading || !selectedSpaceId}
          >
            <Play size={16} />
            {loading ? "执行中..." : "执行规则引擎"}
          </button>
        </div>

        <div className="rule-engine-output">
          {!result && !loading && (
            <div className="traverse-empty">
              <Scale size={48} />
              <p>选择空间并点击「执行规则引擎」</p>
            </div>
          )}

          {result && (
            <>
              <div className="rule-engine-stats">
                <div
                  className={`rule-stat ${
                    result.block_count > 0 ? "danger" : "success"
                  }`}
                >
                  <strong>{result.hit_count}</strong>
                  <span>
                    命中规则
                    {result.block_count > 0 && ` (${result.block_count} 阻断)`}
                  </span>
                </div>
                <div className="rule-stat">
                  <strong>{result.total_rules}</strong>
                  <span>总规则数</span>
                </div>
                <div className="rule-stat">
                  <strong>{result.execution_time_ms}ms</strong>
                  <span>执行耗时</span>
                </div>
              </div>

              {result.hits.length === 0 && (
                <div className="rule-empty-hits">
                  <CheckCircle size={32} />
                  <p>未命中任何规则，数据合规</p>
                </div>
              )}

              <div className="rule-hits-list">
                {result.hits.map((hit) => (
                  <div
                    key={hit.rule_id}
                    className={`rule-hit-card ${hit.severity}`}
                  >
                    <div
                      className="rule-hit-header"
                      onClick={() => toggleReasoning(hit.rule_id)}
                    >
                      {hit.severity === "block" ? (
                        <Ban size={16} />
                      ) : (
                        <AlertTriangle size={16} />
                      )}
                      <div className="rule-hit-title">
                        <strong>{hit.rule_name}</strong>
                        <span className="rule-type">{hit.rule_type}</span>
                        <span className={`severity-badge ${hit.severity}`}>
                          {hit.severity === "block" ? "阻断" : "建议"}
                        </span>
                      </div>
                      <div className="rule-hit-priority">
                        P{hit.priority}
                      </div>
                      {expandedReasoning.has(hit.rule_id) ? (
                        <ChevronUp size={16} />
                      ) : (
                        <ChevronDown size={16} />
                      )}
                    </div>

                    <div className="rule-hit-condition">
                      <code>条件: {hit.condition}</code>
                    </div>

                    <div className="rule-hit-result">
                      <Shield size={14} />
                      <span>{hit.result}</span>
                    </div>

                    {expandedReasoning.has(hit.rule_id) && (
                      <div className="rule-reasoning">
                        <h5>
                          <Terminal size={14} /> 推理轨迹
                        </h5>
                        {hit.reasoning.map((step, i) => (
                          <div key={i} className="reasoning-step">
                            <span className="step-number">#{i + 1}</span>
                            <span className="step-action">
                              {String(step.step)}
                            </span>
                            {step.field != null && (
                              <code className="step-field">
                                {String(step.field)}
                              </code>
                            )}
                            {step.actual !== undefined && (
                              <span className="step-value">
                                实际值: {JSON.stringify(step.actual)}
                              </span>
                            )}
                            {step.expected !== undefined && (
                              <span className="step-value">
                                期望值: {JSON.stringify(step.expected)}
                              </span>
                            )}
                            <span
                              className={`step-result ${
                                step.result ? "pass" : "fail"
                              }`}
                            >
                              {step.result ? "✓" : "✗"}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </>
          )}
        </div>
      </div>
    </section>
  );
}
