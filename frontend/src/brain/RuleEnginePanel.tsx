import React from "react";
import {
  AlertTriangle,
  Ban,
  Bot,
  CheckCircle,
  ChevronDown,
  ChevronUp,
  Clock,
  FileText,
  ListChecks,
  MessageCircle,
  Play,
  Scale,
  Send,
  Shield,
  Sparkles,
  Terminal,
  User,
  X,
  Zap,
} from "lucide-react";
import type {
  ApiConnector,
  ChatMessage,
  ExecutionContext,
  RuleEngineResult,
  Space,
} from "./types";
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
    },
    party: {
      entityId: "ENT-001",
      name: "ABC科技有限公司",
      creditScore: 75,
    },
    approval: { apId: "AP-001", approver: "张经理", decision: "待审批" },
    risk: { level: "中" },
  },
  factoring_risk: {
    receivable: {
      receivableId: "REC-001",
      amount: 2000000,
      dueDate: "2024-06-30",
      debtorCredit: "B",
    },
    party: { entityId: "ENT-002", name: "XYZ贸易公司", creditScore: 65 },
    risk: { level: "高" },
  },
  battery_scheduling: {
    order: {
      orderId: "ORD-001",
      productType: "磷酸铁锂电池",
      quantity: 5000,
      deliveryDate: "2024-03-15",
    },
    production_line: { lineId: "LINE-A", capacity: 1000, currentLoad: 900 },
  },
};

export default function RuleEnginePanel({
  spaces,
}: {
  spaces: Space[];
}) {
  // ── 基础状态 ──
  const [selectedSpaceId, setSelectedSpaceId] = React.useState("");
  const [scenario, setScenario] = React.useState("contract_review");
  const [testData, setTestData] = React.useState(
    JSON.stringify(TEST_DATA_PRESETS.contract_review, null, 2)
  );
  const [dataSourceTag, setDataSourceTag] = React.useState("预设场景: 合同审核");
  const [result, setResult] = React.useState<RuleEngineResult | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState("");
  const [expandedReasoning, setExpandedReasoning] = React.useState<
    Set<string>
  >(new Set());

  // ── Tab ──
  const [activeTab, setActiveTab] = React.useState<"connector" | "nl" | "manual">("connector");

  // ── 连接器 ──
  const [connectors, setConnectors] = React.useState<ApiConnector[]>([]);
  const [selectedConnectorId, setSelectedConnectorId] = React.useState("");
  const [connectorLoading, setConnectorLoading] = React.useState(false);

  // ── 自然语言 ──
  const [nlScene, setNlScene] = React.useState("");
  const [nlLoading, setNlLoading] = React.useState(false);
  const [nlError, setNlError] = React.useState("");

  // ── 执行上下文 + 对话 ──
  const [executionContext, setExecutionContext] =
    React.useState<ExecutionContext | null>(null);
  const [showChat, setShowChat] = React.useState(false);
  const [chatMessages, setChatMessages] = React.useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = React.useState("");
  const [chatLoading, setChatLoading] = React.useState(false);

  const selectedSpace = spaces.find((s) => s.id === selectedSpaceId);

  // 加载连接器列表
  React.useEffect(() => {
    loadConnectors();
  }, []);

  React.useEffect(() => {
    setTestData(JSON.stringify(TEST_DATA_PRESETS[scenario], null, 2));
    setDataSourceTag(`预设场景: ${SCENARIOS.find((s) => s.code === scenario)?.name ?? scenario}`);
  }, [scenario]);

  async function loadConnectors() {
    try {
      const res = await api<ApiConnector[]>("/api/brain/connectors");
      setConnectors(res.data ?? []);
    } catch {
      // ignore
    }
  }

  // ── 连接器: 生成合成数据 ──
  async function generateFromConnector() {
    if (!selectedConnectorId) {
      setError("请选择连接器");
      return;
    }
    setConnectorLoading(true);
    setError("");
    try {
      const res = await api<{
        record: Record<string, unknown>;
        connector_name: string;
      }>(`/api/brain/connectors/${selectedConnectorId}/preview-single`, {
        method: "POST",
      });
      setTestData(JSON.stringify(res.data.record, null, 2));
      setDataSourceTag(`连接器: ${res.data.connector_name}`);
    } catch (e) {
      setError(String(e));
    } finally {
      setConnectorLoading(false);
    }
  }

  // ── 执行规则引擎 ──
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
      setExecutionContext({
        execution: {
          timestamp: new Date().toISOString(),
          mode: activeTab,
          spaceId: selectedSpaceId,
          spaceName: selectedSpace?.name ?? "",
          executionTimeMs: res.data.execution_time_ms,
        },
        input: { testData: data, source: dataSourceTag },
        result: res.data,
      });
      const expanded = new Set<string>();
      res.data.hits.forEach((h) => expanded.add(h.rule_id));
      setExpandedReasoning(expanded);
      // 重置对话
      setChatMessages([]);
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  // ── 自然语言执行 ──
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
        return;
      }
      setTestData(JSON.stringify(res.data.test_data, null, 2));
      setDataSourceTag(`LLM: ${res.data.llm_model}`);
      setResult(res.data.rule_result);
      setExecutionContext({
        execution: {
          timestamp: new Date().toISOString(),
          mode: "nl",
          spaceId: selectedSpaceId,
          spaceName: selectedSpace?.name ?? "",
          executionTimeMs: res.data.rule_result.execution_time_ms,
        },
        input: {
          testData: res.data.test_data,
          source: `LLM: ${res.data.llm_model}`,
          sourceDetail: res.data.scene_description,
        },
        result: res.data.rule_result,
      });
      const expanded = new Set<string>();
      res.data.rule_result.hits.forEach((h) => expanded.add(h.rule_id));
      setExpandedReasoning(expanded);
      setChatMessages([]);
    } catch (e) {
      setNlError(String(e));
    } finally {
      setNlLoading(false);
    }
  }

  // ── 发送对话消息 ──
  async function sendChatMessage() {
    if (!chatInput.trim() || !executionContext) return;

    const userMsg: ChatMessage = {
      role: "user",
      content: chatInput.trim(),
      timestamp: new Date().toISOString(),
    };
    const newMessages = [...chatMessages, userMsg];
    setChatMessages(newMessages);
    setChatInput("");
    setChatLoading(true);

    try {
      const history = newMessages.slice(-6).map((m) => ({
        role: m.role,
        content: m.content,
      }));

      const res = await api<{
        answer: string;
        model: string;
        usage?: Record<string, number>;
        error?: string;
      }>("/api/brain/rule-engine/chat", {
        method: "POST",
        body: JSON.stringify({
          space_id: executionContext.execution.spaceId,
          space_name: executionContext.execution.spaceName,
          test_data: executionContext.input.testData,
          data_source: executionContext.input.source,
          hits: executionContext.result.hits,
          misses: executionContext.result.misses,
          all_rules: executionContext.result.all_rules,
          execution_time_ms: executionContext.execution.executionTimeMs,
          question: userMsg.content,
          history,
        }),
      });

      if (res.data?.error) {
        setChatMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: `❌ ${res.data.error}`,
            timestamp: new Date().toISOString(),
          },
        ]);
      } else {
        setChatMessages((prev) => [
          ...prev,
          {
            role: "assistant",
            content: res.data.answer,
            timestamp: new Date().toISOString(),
          },
        ]);
      }
    } catch (e) {
      setChatMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: `❌ 请求失败: ${String(e)}`,
          timestamp: new Date().toISOString(),
        },
      ]);
    } finally {
      setChatLoading(false);
    }
  }

  function toggleReasoning(ruleId: string) {
    setExpandedReasoning((prev) => {
      const next = new Set(prev);
      if (next.has(ruleId)) next.delete(ruleId);
      else next.add(ruleId);
      return next;
    });
  }

  return (
    <section className="resource-panel">
      <div className="re-layout">
        {/* ═══════ 左侧输入区 ═══════ */}
        <div className="re-input-panel">
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
              <option value="">请选择...</option>
              {spaces.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
              ))}
            </select>
          </div>

          {/* Tab */}
          <div className="re-tabs">
            <button
              className={activeTab === "connector" ? "re-tab active" : "re-tab"}
              onClick={() => setActiveTab("connector")}
            >
              <Terminal size={14} />
              连接器数据
            </button>
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
              <FileText size={14} />
              手动配置
            </button>
          </div>

          {/* ── 连接器面板 ── */}
          {activeTab === "connector" && (
            <div className="re-nl-panel">
              <label className="re-label">
                <Terminal size={14} />
                选择数据源连接器
              </label>
              <select
                className="re-select"
                value={selectedConnectorId}
                onChange={(e) => setSelectedConnectorId(e.target.value)}
              >
                <option value="">请选择连接器...</option>
                {connectors.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name} ({c.code})
                  </option>
                ))}
              </select>
              {connectors.length === 0 && (
                <p className="re-hint">
                  暂无连接器，请先应用预设模板或创建连接器
                </p>
              )}
              <button
                className="re-nl-btn"
                onClick={generateFromConnector}
                disabled={connectorLoading || !selectedConnectorId}
              >
                {connectorLoading ? (
                  <>
                    <span className="re-spinner" />
                    生成中...
                  </>
                ) : (
                  <>
                    <Zap size={16} />
                    生成合成数据
                  </>
                )}
              </button>
            </div>
          )}

          {/* ── 自然语言面板 ── */}
          {activeTab === "nl" && (
            <div className="re-nl-panel">
              <label className="re-label">
                <Sparkles size={14} />
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
            </div>
          )}

          {/* ── 手动配置面板 ── */}
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
            </div>
          )}

          {/* ── 统一的 JSON 编辑区 ── */}
          <div className="re-form-group" style={{ marginTop: 8 }}>
            <div className="re-data-source-bar">
              <label className="re-label">
                <Terminal size={14} />
                测试数据 JSON
              </label>
              <span className="re-data-source-tag">
                <Clock size={11} />
                {dataSourceTag}
              </span>
            </div>
            <textarea
              className="re-textarea code"
              value={testData}
              onChange={(e) => {
                setTestData(e.target.value);
                setDataSourceTag("手动编辑");
              }}
              rows={activeTab === "manual" ? 16 : 10}
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

        {/* ═══════ 右侧结果区 ═══════ */}
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
                <div
                  className={`re-stat ${
                    result.block_count > 0
                      ? "danger"
                      : result.hit_count > 0
                        ? "warn"
                        : "success"
                  }`}
                >
                  <div className="re-stat-icon">
                    {result.block_count > 0 ? (
                      <Ban size={18} />
                    ) : result.hit_count > 0 ? (
                      <AlertTriangle size={18} />
                    ) : (
                      <CheckCircle size={18} />
                    )}
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

              {/* 日志 + 对话按钮 */}
              {executionContext && (
                <div className="re-log-bar">
                  <button
                    className="re-log-btn"
                    onClick={() => setShowChat(true)}
                  >
                    <MessageCircle size={14} />
                    执行对话
                    {chatMessages.length > 0 && (
                      <span className="re-chat-badge">
                        {chatMessages.length}
                      </span>
                    )}
                  </button>
                  <span className="re-log-hint">
                    <Clock size={12} />
                    {formatTime(executionContext.execution.timestamp)}
                    {executionContext.input.sourceDetail && (
                      <span style={{ marginLeft: 8 }}>
                        · {executionContext.input.sourceDetail.slice(0, 30)}
                      </span>
                    )}
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

              {/* 未命中规则（可折叠） */}
              {result.misses.length > 0 && (
                <MissedRules misses={result.misses} />
              )}
            </>
          )}
        </div>
      </div>

      {/* ═══════ 执行对话面板 ═══════ */}
      {showChat && executionContext && (
        <ExecutionChatPanel
          messages={chatMessages}
          input={chatInput}
          onInputChange={setChatInput}
          onSend={sendChatMessage}
          loading={chatLoading}
          onClose={() => setShowChat(false)}
          context={executionContext}
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
  hit: {
    rule_id: string;
    rule_name: string;
    rule_type: string;
    severity: string;
    priority: number;
    condition: string;
    result: string;
    reasoning: Array<Record<string, unknown>>;
  };
  expanded: boolean;
  onToggle: () => void;
}) {
  return (
    <div className={`re-hit ${hit.severity}`}>
      <div className="re-hit-main" onClick={onToggle}>
        <div className="re-hit-severity">
          {hit.severity === "block" ? (
            <Ban size={16} />
          ) : (
            <AlertTriangle size={16} />
          )}
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
        <code>条件: {hit.condition}</code>
      </div>

      {expanded && (
        <div className="re-hit-reasoning">
          <h5>
            <Terminal size={13} /> 推理轨迹
          </h5>
          {hit.reasoning.map((step, i) => (
            <div key={i} className={`re-step ${step.result ? "pass" : "fail"}`}>
              <span className="re-step-num">{i + 1}</span>
              <div className="re-step-body">
                <span className="re-step-action">{String(step.step)}</span>
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
              <span className="re-step-result">
                {step.result ? "✓" : "✗"}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── 未命中规则（可折叠） ──

function MissedRules({
  misses,
}: {
  misses: Array<{
    rule_id: string;
    rule_name: string;
    rule_type: string;
    condition: string;
    priority: number;
  }>;
}) {
  const [expanded, setExpanded] = React.useState(false);
  return (
    <div className="re-misses">
      <button className="re-misses-toggle" onClick={() => setExpanded(!expanded)}>
        {expanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
        <span>未命中规则 ({misses.length})</span>
      </button>
      {expanded && (
        <div className="re-misses-list">
          {misses.map((m) => (
            <div key={m.rule_id} className="re-miss-item">
              <span className="re-miss-name">{m.rule_name}</span>
              <span className="re-miss-type">{m.rule_type}</span>
              <code className="re-miss-condition">{m.condition}</code>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── 执行对话面板 ──

function ExecutionChatPanel({
  messages,
  input,
  onInputChange,
  onSend,
  loading,
  onClose,
  context,
}: {
  messages: ChatMessage[];
  input: string;
  onInputChange: (v: string) => void;
  onSend: () => void;
  loading: boolean;
  onClose: () => void;
  context: ExecutionContext;
}) {
  const scrollRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, loading]);

  return (
    <div className="re-chat-overlay" onClick={onClose}>
      <div className="re-chat-panel" onClick={(e) => e.stopPropagation()}>
        {/* 头部 */}
        <div className="re-chat-header">
          <div>
            <h4>
              <Bot size={18} />
              执行对话
            </h4>
            <p>
              基于本次执行上下文（{context.result.hit_count} 命中 /{" "}
              {context.result.total_rules} 规则）
            </p>
          </div>
          <button onClick={onClose}>
            <X size={18} />
          </button>
        </div>

        {/* 建议问题 */}
        {messages.length === 0 && (
          <div className="re-chat-suggestions">
            <p className="re-chat-suggestions-title">你可以问：</p>
            <div className="re-chat-suggestion-list">
              <button
                onClick={() => {
                  onInputChange("为什么这条规则命中了？");
                }}
              >
                为什么这条规则命中了？
              </button>
              <button
                onClick={() => {
                  onInputChange(
                    "如果我修改金额为50万，结果会怎样？"
                  );
                }}
              >
                如果我修改金额为50万，结果会怎样？
              </button>
              <button
                onClick={() => {
                  onInputChange("还有哪些规则没被命中，为什么？");
                }}
              >
                还有哪些规则没被命中，为什么？
              </button>
              <button
                onClick={() => {
                  onInputChange("总结一下本次审核的结论和建议");
                }}
              >
                总结一下本次审核的结论和建议
              </button>
            </div>
          </div>
        )}

        {/* 消息列表 */}
        <div className="re-chat-messages" ref={scrollRef}>
          {messages.map((msg, i) => (
            <div
              key={i}
              className={`re-chat-msg ${msg.role}`}
            >
              <div className="re-chat-msg-avatar">
                {msg.role === "user" ? <User size={14} /> : <Bot size={14} />}
              </div>
              <div className="re-chat-msg-body">
                <div className="re-chat-msg-content">{msg.content}</div>
                <span className="re-chat-msg-time">
                  {formatTime(msg.timestamp)}
                </span>
              </div>
            </div>
          ))}
          {loading && (
            <div className="re-chat-msg assistant">
              <div className="re-chat-msg-avatar">
                <Bot size={14} />
              </div>
              <div className="re-chat-msg-body">
                <div className="re-chat-msg-loading">
                  <span className="re-spinner" />
                  思考中...
                </div>
              </div>
            </div>
          )}
        </div>

        {/* 输入区 */}
        <div className="re-chat-input-bar">
          <input
            type="text"
            value={input}
            onChange={(e) => onInputChange(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && !loading && onSend()}
            placeholder="基于执行上下文提问..."
            disabled={loading}
          />
          <button onClick={onSend} disabled={loading || !input.trim()}>
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
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
