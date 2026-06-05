import React from "react";
import {
  AlertTriangle,
  Ban,
  BookOpen,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Clock,
  FileText,
  ListChecks,
  Play,
  Scale,
  Shield,
  Sparkles,
  Terminal,
  X,
  Zap,
} from "lucide-react";
import type { RuleEngineResult, RuleHitResult, Space } from "./types";
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

// ── 执行日志类型 ──
type ExecutionLog = {
  timestamp: string;
  mode: "manual" | "nl";
  spaceName: string;
  inputData: Record<string, unknown>;
  llmInfo?: {
    sceneDescription: string;
    model: string;
    usage: Record<string, number>;
  };
  ruleResult: RuleEngineResult;
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
  const [expandedReasoning, setExpandedReasoning] = React.useState<Set<string>>(new Set());

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

  // 执行日志
  const [executionLog, setExecutionLog] = React.useState<ExecutionLog | null>(null);
  const [showLogDrawer, setShowLogDrawer] = React.useState(false);

  // Tab 切换
  const [activeTab, setActiveTab] = React.useState<"nl" | "manual">("nl");

  React.useEffect(() => {
    setTestData(JSON.stringify(TEST_DATA_PRESETS[scenario], null, 2));
  }, [scenario]);

  const selectedSpace = spaces.find((s) => s.id === selectedSpaceId);

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
      setExecutionLog({
        timestamp: new Date().toISOString(),
        mode: "manual",
        spaceName: selectedSpace?.name ?? selectedSpaceId,
        inputData: data,
        ruleResult: res.data,
      });
      const newExpanded = new Set<string>();
      res.data.hits.forEach((h) => newExpanded.add(h.rule_id));
      setExpandedReasoning(newExpanded);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
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
        llm_usage: Record<string, number>;
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
        setResult(res.data.rule_result);
        setTestData(JSON.stringify(res.data.test_data, null, 2));
        setExecutionLog({
          timestamp: new Date().toISOString(),
          mode: "nl",
          spaceName: selectedSpace?.name ?? selectedSpaceId,
          inputData: res.data.test_data,
          llmInfo: {
            sceneDescription: res.data.scene_description,
            model: res.data.llm_model,
            usage: res.data.llm_usage,
          },
          ruleResult: res.data.rule_result,
        });
        const newExpanded = new Set<string>();
        res.data.rule_result.hits.forEach((h) => newExpanded.add(h.rule_id));
        setExpandedReasoning(newExpanded);
      }
    } catch (e) {
      setNlError(String(e));
    } finally {
      setNlLoading(false);
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

  return (
    <section className="resource-panel">
      <div className="re-layout">
        {/* ── 左侧输入区 ── */}
        <div className="re-input-panel">
          {/* 头部 */}
          <div className="re-input-header">
            <Scale size={20} />
            <h3>规则引擎测试</h3>
          </div>

          {/* 空间选择 */}
          <div className="re-form-group">
            <label className="re-label">
              <ListChecks size={14} />
              选择本体空间
            </label>
            <select
              className="re-select"
              value={selectedSpaceId}
              onChange={(e) => setSelectedSpaceId(e.target.value)}
            >
              <option value="">请选择本体空间...</option>
              {spaces.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
            {selectedSpace && (
              <span className="re-space-meta">
                {selectedSpace.code} · {selectedSpace.domain}
              </span>
            )}
          </div>

          {/* Tab 切换 */}
          <div className="re-tabs">
            <button
              className={activeTab === "nl" ? "re-tab active" : "re-tab"}
              onClick={() => setActiveTab("nl")}
            >
              <Sparkles size={14} />
              自然语言
            </button>
            <button
              className={activeTab === "manual" ? "re-tab active" : "re-tab"}
              onClick={() => setActiveTab("manual")}
            >
              <Terminal size={14} />
              手动配置
            </button>
          </div>

          {/* 自然语言面板 */}
          {activeTab === "nl" && (
            <div className="re-nl-panel">
              <label className="re-label">
                <BookOpen size={14} />
                描述测试场景
              </label>
              <textarea
                className="re-textarea"
                value={nlScene}
                onChange={(e) => setNlScene(e.target.value)}
                rows={4}
                placeholder="例如：一份200万的采购合同，还没有经过法务审批，合作方信用评分只有60分"
              />
              <p className="re-hint">
                LLM 会根据描述自动生成测试数据并执行规则引擎
              </p>
              {nlError && <p className="form-error">{nlError}</p>}
              <button
                className="re-nl-btn"
                onClick={nlExecute}
                disabled={nlLoading || !selectedSpaceId}
              >
                {nlLoading ? (
                  <>
                    <span className="re-spinner" />
                    LLM 思考中...
                  </>
                ) : (
                  <>
                    <Sparkles size={16} />
                    生成数据并执行
                  </>
                )}
              </button>
              {nlResult && (
                <div className="re-nl-success">
                  <CheckCircle size={14} />
                  <span>
                    {nlResult.llm_model} 已生成数据，命中{" "}
                    <strong>{nlResult.rule_result.hit_count}</strong> 条规则
                  </span>
                </div>
              )}
            </div>
          )}

          {/* 手动配置面板 */}
          {activeTab === "manual" && (
            <div className="re-manual-panel">
              <div className="re-form-group">
                <label className="re-label">
                  <ListChecks size={14} />
                  测试场景
                </label>
                <select
                  className="re-select"
                  value={scenario}
                  onChange={(e) => setScenario(e.target.value)}
                >
                  {SCENARIOS.map((s) => (
                    <option key={s.code} value={s.code}>
                      {s.name}
                    </option>
                  ))}
                </select>
              </div>

              <div className="re-form-group">
                <label className="re-label">
                  <Terminal size={14} />
                  测试数据 JSON
                </label>
                <textarea
                  className="re-textarea code"
                  value={testData}
                  onChange={(e) => setTestData(e.target.value)}
                  rows={12}
                />
              </div>

              {error && <p className="form-error">{error}</p>}
              <button
                className="re-execute-btn"
                onClick={execute}
                disabled={loading || !selectedSpaceId}
              >
                {loading ? (
                  <>
                    <span className="re-spinner" />
                    执行中...
                  </>
                ) : (
                  <>
                    <Play size={16} />
                    执行规则引擎
                  </>
                )}
              </button>
            </div>
          )}
        </div>

        {/* ── 右侧结果区 ── */}
        <div className="re-output-panel">
          {!result && !loading && (
            <div className="re-empty">
              <Scale size={56} />
              <h4>等待执行</h4>
              <p>
                选择本体空间，配置测试数据后
                <br />
                点击「执行」查看规则命中结果
              </p>
            </div>
          )}

          {loading && (
            <div className="re-empty">
              <span className="re-spinner large" />
              <h4>规则引擎执行中...</h4>
              <p>正在遍历规则、评估条件、生成推理轨迹</p>
            </div>
          )}

          {result && !loading && (
            <>
              {/* 统计栏 */}
              <div className="re-stats-bar">
                <div className={`re-stat ${result.block_count > 0 ? "danger" : result.hit_count > 0 ? "warn" : "success"}`}>
                  <div className="re-stat-icon">
                    {result.block_count > 0 ? <Ban size={18} /> : result.hit_count > 0 ? <AlertTriangle size={18} /> : <CheckCircle size={18} />}
                  </div>
                  <div className="re-stat-body">
                    <strong>{result.hit_count}</strong>
                    <span>命中规则</span>
                  </div>
                </div>
                <div className="re-stat">
                  <div className="re-stat-body">
                    <strong>{result.total_rules}</strong>
                    <span>总规则</span>
                  </div>
                </div>
                <div className="re-stat">
                  <div className="re-stat-body">
                    <strong>{result.execution_time_ms}ms</strong>
                    <span>执行耗时</span>
                  </div>
                </div>
                {result.block_count > 0 && (
                  <div className="re-stat danger">
                    <div className="re-stat-body">
                      <strong>{result.block_count}</strong>
                      <span>阻断</span>
                    </div>
                  </div>
                )}
              </div>

              {/* 查看日志按钮 */}
              {executionLog && (
                <div className="re-log-bar">
                  <button className="re-log-btn" onClick={() => setShowLogDrawer(true)}>
                    <FileText size={14} />
                    查看执行日志
                  </button>
                  <span className="re-log-hint">
                    <Clock size={12} />
                    {formatTime(executionLog.timestamp)}
                  </span>
                </div>
              )}

              {/* 命中规则列表 */}
              {result.hits.length === 0 ? (
                <div className="re-no-hits">
                  <div className="re-no-hits-icon">
                    <CheckCircle size={40} />
                  </div>
                  <h4>数据合规</h4>
                  <p>未命中任何规则，当前测试数据符合所有约束</p>
                </div>
              ) : (
                <div className="re-hits">
                  <h4 className="re-hits-title">
                    <Shield size={16} />
                    命中规则 ({result.hits.length})
                  </h4>
                  {result.hits.map((hit) => (
                    <HitCard
                      key={hit.rule_id}
                      hit={hit}
                      expanded={expandedReasoning.has(hit.rule_id)}
                      onToggle={() => toggleReasoning(hit.rule_id)}
                    />
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      </div>

      {/* ── 执行日志抽屉 ── */}
      {showLogDrawer && executionLog && (
        <ExecutionLogDrawer
          log={executionLog}
          onClose={() => setShowLogDrawer(false)}
        />
      )}
    </section>
  );
}

// ── 规则命中卡片 ──

function HitCard({
  hit,
  expanded,
  onToggle,
}: {
  hit: RuleHitResult;
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div className={`re-hit ${hit.severity}`}>
      <div className="re-hit-main" onClick={onToggle}>
        <div className="re-hit-severity">
          {hit.severity === "block" ? <Ban size={16} /> : <AlertTriangle size={16} />}
        </div>
        <div className="re-hit-info">
          <div className="re-hit-name">
            {hit.rule_name}
            <span className="re-hit-type">{hit.rule_type}</span>
            <span className={`re-hit-badge ${hit.severity}`}>
              {hit.severity === "block" ? "阻断" : "建议"}
            </span>
          </div>
          <div className="re-hit-desc">{hit.result}</div>
        </div>
        <div className="re-hit-meta">
          <span className="re-hit-priority">P{hit.priority}</span>
          {expanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
        </div>
      </div>

      <div className="re-hit-condition">
        <code>{hit.condition}</code>
      </div>

      {expanded && (
        <div className="re-hit-reasoning">
          <h5>
            <Terminal size={13} />
            推理轨迹
          </h5>
          {hit.reasoning.map((step, i) => (
            <div key={i} className={`re-step ${step.result ? "pass" : "fail"}`}>
              <span className="re-step-num">{i + 1}</span>
              <div className="re-step-body">
                <div className="re-step-action">{String(step.step)}</div>
                {step.field != null && (
                  <code className="re-step-field">{String(step.field)}</code>
                )}
                {step.actual !== undefined && (
                  <span className="re-step-value">
                    实际: {JSON.stringify(step.actual)}
                  </span>
                )}
                {step.expected !== undefined && (
                  <span className="re-step-value">
                    期望: {JSON.stringify(step.expected)}
                  </span>
                )}
              </div>
              <span className="re-step-result">{step.result ? "✓" : "✗"}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── 执行日志抽屉 ──

function ExecutionLogDrawer({
  log,
  onClose,
}: {
  log: ExecutionLog;
  onClose: () => void;
}) {
  return (
    <aside className="drawer wide">
      <div className="drawer-header">
        <div>
          <p className="crumb">执行日志</p>
          <h2>规则引擎执行详情</h2>
        </div>
        <button onClick={onClose}>
          <X size={18} />
        </button>
      </div>
      <div className="re-log-content">
        {/* 基本信息 */}
        <div className="re-log-section">
          <h4>
            <Clock size={14} />
            执行信息
          </h4>
          <div className="re-log-info-grid">
            <div className="re-log-info-item">
              <span>执行时间</span>
              <strong>{new Date(log.timestamp).toLocaleString("zh-CN")}</strong>
            </div>
            <div className="re-log-info-item">
              <span>执行模式</span>
              <strong>{log.mode === "nl" ? "自然语言（LLM）" : "手动配置"}</strong>
            </div>
            <div className="re-log-info-item">
              <span>本体空间</span>
              <strong>{log.spaceName}</strong>
            </div>
            <div className="re-log-info-item">
              <span>总规则数</span>
              <strong>{log.ruleResult.total_rules}</strong>
            </div>
            <div className="re-log-info-item">
              <span>命中规则</span>
              <strong>{log.ruleResult.hit_count}</strong>
            </div>
            <div className="re-log-info-item">
              <span>执行耗时</span>
              <strong>{log.ruleResult.execution_time_ms}ms</strong>
            </div>
          </div>
        </div>

        {/* LLM 信息 */}
        {log.llmInfo && (
          <div className="re-log-section">
            <h4>
              <Sparkles size={14} />
              LLM 生成信息
            </h4>
            <div className="re-log-info-grid">
              <div className="re-log-info-item">
                <span>场景描述</span>
                <strong>{log.llmInfo.sceneDescription}</strong>
              </div>
              <div className="re-log-info-item">
                <span>模型</span>
                <strong>{log.llmInfo.model}</strong>
              </div>
              <div className="re-log-info-item">
                <span>Prompt Tokens</span>
                <strong>{log.llmInfo.usage?.prompt_tokens ?? "-"}</strong>
              </div>
              <div className="re-log-info-item">
                <span>Completion Tokens</span>
                <strong>{log.llmInfo.usage?.completion_tokens ?? "-"}</strong>
              </div>
            </div>
          </div>
        )}

        {/* 输入数据 */}
        <div className="re-log-section">
          <h4>
            <Terminal size={14} />
            输入数据
          </h4>
          <pre className="re-log-code">{JSON.stringify(log.inputData, null, 2)}</pre>
        </div>

        {/* 规则执行过程 */}
        <div className="re-log-section">
          <h4>
            <ListChecks size={14} />
            规则执行过程
          </h4>
          <div className="re-log-process">
            {log.ruleResult.hits.length === 0 ? (
              <div className="re-log-process-item success">
                <CheckCircle size={14} />
                <span>未命中任何规则，数据合规通过</span>
              </div>
            ) : (
              log.ruleResult.hits.map((hit, i) => (
                <div key={hit.rule_id} className={`re-log-process-item ${hit.severity}`}>
                  <span className="re-log-process-num">{i + 1}</span>
                  <div className="re-log-process-body">
                    <strong>{hit.rule_name}</strong>
                    <code>{hit.condition}</code>
                    <span className="re-log-process-result">
                      {hit.severity === "block" ? "🚫 阻断" : "⚠️ 建议"} · {hit.result}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* 输出结果 */}
        <div className="re-log-section">
          <h4>
            <Shield size={14} />
            执行结果摘要
          </h4>
          <div className="re-log-result">
            {log.ruleResult.block_count > 0 ? (
              <div className="re-log-result-item danger">
                <Ban size={16} />
                <span>
                  发现 <strong>{log.ruleResult.block_count}</strong> 条阻断规则，
                  <strong>{log.ruleResult.hit_count - log.ruleResult.block_count}</strong> 条建议
                </span>
              </div>
            ) : log.ruleResult.hit_count > 0 ? (
              <div className="re-log-result-item warn">
                <AlertTriangle size={16} />
                <span>
                  发现 <strong>{log.ruleResult.hit_count}</strong> 条建议，无阻断
                </span>
              </div>
            ) : (
              <div className="re-log-result-item success">
                <CheckCircle size={16} />
                <span>数据合规，未命中任何规则</span>
              </div>
            )}
          </div>
        </div>
      </div>
    </aside>
  );
}

function formatTime(value: string) {
  return new Intl.DateTimeFormat("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}
