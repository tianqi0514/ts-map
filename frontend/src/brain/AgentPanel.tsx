import React from "react";
import {
  Ban,
  Bot,
  CheckCircle,
  Clock,
  Edit3,
  MessageCircle,
  Play,
  Plus,
  RefreshCw,
  Scale,
  Send,
  Sparkles,
  Terminal,
  Trash2,
  User,
  X,
  Zap,
} from "lucide-react";
import type { ApiConnector, ChatMessage, RuleEngineResult, Space } from "./types";
import { api } from "./api";

const API_BASE = import.meta.env.VITE_API_BASE ?? "";

// ── 类型 ──

type BrainAgent = {
  id: string;
  code: string;
  name: string;
  description: string;
  connector_id: string | null;
  space_id: string | null;
  strategy_type: string;
  strategy_config: Record<string, unknown>;
  status: string;
  created_at: string;
  updated_at: string;
};

type StreamEvent =
  | { type: "start"; agent_name: string; strategy: string }
  | { type: "data_generated"; data: Record<string, unknown> }
  | { type: "llm_thinking" }
  | { type: "llm_chunk"; content: string }
  | { type: "rule_executing" }
  | { type: "rule_result"; result: RuleEngineResult }
  | { type: "suggestion_generating" }
  | { type: "suggestion_chunk"; content: string }
  | { type: "complete"; final_result: AgentExecutionResult }
  | { type: "error"; message: string };

type AgentExecutionResult = {
  agent_id: string;
  agent_name: string;
  strategy: string;
  test_data: Record<string, unknown>;
  rule_result?: RuleEngineResult;
  llm_output?: {
    conclusion: string;
    summary: string;
    findings: string[];
    suggestions: string[];
  };
  llm_full_response?: string;
  llm_model?: string;
  suggestions?: string;
  error?: string;
};

// ── 预设 Agent 模板 ──

const AGENT_TEMPLATES = [
  {
    code: "contract_auditor",
    name: "合同合规审核员",
    description: "自动审核合同数据是否符合企业合规要求",
    strategy_type: "rule_based",
    strategy_config: { rule_ids: [] },
  },
  {
    code: "risk_assessor",
    name: "风险智能评估员",
    description: "基于自然语言描述自主评估业务风险",
    strategy_type: "natural_language",
    strategy_config: {
      description:
        "你是一个风控专家。请审核以下业务数据，识别潜在风险并给出建议。重点关注：金额异常、审批缺失、信用风险。",
    },
  },
];

// ── 主组件 ──

export default function AgentPanel({ spaces }: { spaces: Space[] }) {
  const [agents, setAgents] = React.useState<BrainAgent[]>([]);
  const [connectors, setConnectors] = React.useState<ApiConnector[]>([]);
  const [loading, setLoading] = React.useState(false);
  const [editing, setEditing] = React.useState<BrainAgent | "new" | null>(null);
  const [executing, setExecuting] = React.useState<BrainAgent | null>(null);
  const [execResult, setExecResult] = React.useState<AgentExecutionResult | null>(null);
  const [streamSteps, setStreamSteps] = React.useState<StreamEvent[]>([]);
  const [streamLoading, setStreamLoading] = React.useState(false);
  const [streamError, setStreamError] = React.useState("");
  // 流式内容累积（用于打字机效果）
  const [llmContent, setLlmContent] = React.useState("");
  const [suggestionContent, setSuggestionContent] = React.useState("");

  React.useEffect(() => {
    loadData();
  }, []);

  async function loadData() {
    setLoading(true);
    try {
      const [agentRes, connRes] = await Promise.all([
        api<BrainAgent[]>("/api/brain/agents"),
        api<ApiConnector[]>("/api/brain/connectors"),
      ]);
      setAgents(agentRes.data ?? []);
      setConnectors(connRes.data ?? []);
    } finally {
      setLoading(false);
    }
  }

  async function deleteAgent(id: string) {
    if (!confirm("确定删除此 Agent？")) return;
    await api(`/api/brain/agents/${id}`, { method: "DELETE" });
    await loadData();
  }

  // ── SSE 流式执行 ──
  function executeAgent(agent: BrainAgent) {
    setExecuting(agent);
    setExecResult(null);
    setStreamSteps([]);
    setStreamLoading(true);
    setStreamError("");
    setLlmContent("");
    setSuggestionContent("");

    const evtSource = new EventSource(
      `${API_BASE}/api/brain/agents/${agent.id}/execute-stream`,
      { withCredentials: false }
    );

    evtSource.onmessage = (event) => {
      try {
        const data: StreamEvent = JSON.parse(event.data);
        setStreamSteps((prev) => [...prev, data]);

        switch (data.type) {
          case "llm_chunk":
            setLlmContent((prev) => prev + data.content);
            break;
          case "suggestion_chunk":
            setSuggestionContent((prev) => prev + data.content);
            break;
          case "complete":
            setExecResult(data.final_result);
            setStreamLoading(false);
            evtSource.close();
            break;
          case "error":
            setStreamError(data.message);
            setStreamLoading(false);
            evtSource.close();
            break;
        }
      } catch {
        // 忽略解析失败的行
      }
    };

    evtSource.onerror = () => {
      setStreamError("连接中断");
      setStreamLoading(false);
      evtSource.close();
    };
  }

  return (
    <div>
      {/* 工具栏 */}
      <div className="toolbar" style={{ marginBottom: 16 }}>
        <h2 style={{ margin: 0, fontSize: 16 }}>Agent 列表</h2>
        <div style={{ display: "flex", gap: 8 }}>
          <button className="icon-button" onClick={loadData} title="刷新">
            <RefreshCw size={16} />
          </button>
          <button className="primary-button" onClick={() => setEditing("new")}>
            <Plus size={16} />
            新建 Agent
          </button>
        </div>
      </div>

      {/* Agent 列表 */}
      {agents.length === 0 && !loading ? (
        <div className="ontology-empty" style={{ marginTop: 40 }}>
          <Bot size={48} />
          <p>暂无 Agent</p>
          <p className="muted">创建 Agent 来构建自动化审核工作流</p>
          <div className="ontology-empty-actions">
            <button className="primary-button" onClick={() => setEditing("new")}>
              <Plus size={16} />
              创建第一个 Agent
            </button>
          </div>
        </div>
      ) : (
        <div className="agent-grid">
          {agents.map((agent) => {
            const connector = connectors.find((c) => c.id === agent.connector_id);
            const space = spaces.find((s) => s.id === agent.space_id);
            return (
              <div key={agent.id} className="agent-card">
                <div className="agent-card-header">
                  <div className="agent-icon">
                    <Bot size={20} />
                  </div>
                  <div className="agent-info">
                    <strong>{agent.name}</strong>
                    <code>{agent.code}</code>
                  </div>
                  <span className={`status-badge ${agent.status}`}>
                    {agent.status === "active" ? "已启用" : agent.status}
                  </span>
                </div>
                <p className="agent-desc">{agent.description || "暂无描述"}</p>
                <div className="agent-meta">
                  <span className="agent-meta-tag">
                    <Terminal size={12} />
                    {agent.strategy_type === "rule_based" ? "规则策略" : "自然语言"}
                  </span>
                  <span className="agent-meta-tag">
                    <Zap size={12} />
                    {connector?.name ?? "未配置数据源"}
                  </span>
                  <span className="agent-meta-tag">
                    <Scale size={12} />
                    {space?.name ?? "未配置本体"}
                  </span>
                </div>
                <div className="agent-actions">
                  <button className="primary-button small" onClick={() => executeAgent(agent)}>
                    <Play size={14} />
                    执行审核
                  </button>
                  <button className="ghost-button small" onClick={() => setEditing(agent)}>
                    <Edit3 size={14} />
                    编辑
                  </button>
                  <button
                    className="ghost-button small danger"
                    onClick={() => deleteAgent(agent.id)}
                  >
                    <Trash2 size={14} />
                    删除
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* 新建/编辑抽屉 */}
      {editing && (
        <AgentEditor
          agent={editing === "new" ? null : editing}
          spaces={spaces}
          connectors={connectors}
          onClose={() => setEditing(null)}
          onSave={loadData}
        />
      )}

      {/* 执行结果抽屉 */}
      {executing && (
        <AgentExecutionDrawer
          agent={executing}
          result={execResult}
          streamSteps={streamSteps}
          streamLoading={streamLoading}
          streamError={streamError}
          llmContent={llmContent}
          suggestionContent={suggestionContent}
          onClose={() => {
            setExecuting(null);
            setExecResult(null);
            setStreamSteps([]);
            setStreamLoading(false);
            setStreamError("");
            setLlmContent("");
            setSuggestionContent("");
          }}
        />
      )}
    </div>
  );
}

// ── Agent 编辑器 ──

function AgentEditor({
  agent,
  spaces,
  connectors,
  onClose,
  onSave,
}: {
  agent: BrainAgent | null;
  spaces: Space[];
  connectors: ApiConnector[];
  onClose: () => void;
  onSave: () => void;
}) {
  const [code, setCode] = React.useState(agent?.code ?? "");
  const [name, setName] = React.useState(agent?.name ?? "");
  const [description, setDescription] = React.useState(agent?.description ?? "");
  const [connectorId, setConnectorId] = React.useState(agent?.connector_id ?? "");
  const [spaceId, setSpaceId] = React.useState(agent?.space_id ?? "");
  const [strategyType, setStrategyType] = React.useState(agent?.strategy_type ?? "rule_based");
  const [strategyConfig, setStrategyConfig] = React.useState(
    JSON.stringify(agent?.strategy_config ?? { rule_ids: [] }, null, 2)
  );
  const [error, setError] = React.useState("");

  function autoCode(n: string): string {
    return n
      .trim()
      .toLowerCase()
      .replace(/[^\w\s]/g, "")
      .replace(/\s+/g, "_")
      .slice(0, 50) || "agent_" + Date.now();
  }

  async function save() {
    if (!name.trim()) { setError("名称不能为空"); return; }
    let finalCode = code.trim();
    if (!finalCode) { finalCode = autoCode(name); setCode(finalCode); }
    if (finalCode.length < 2) { setError("编码至少 2 个字符"); return; }
    if (!connectorId) { setError("请选择数据源连接器"); return; }
    if (!spaceId) { setError("请选择本体空间"); return; }

    let cfg: Record<string, unknown>;
    try { cfg = JSON.parse(strategyConfig); }
    catch { setError("策略配置必须是合法 JSON"); return; }

    const payload = {
      code: finalCode,
      name: name.trim(),
      description: description.trim(),
      connector_id: connectorId,
      space_id: spaceId,
      strategy_type: strategyType,
      strategy_config: cfg,
    };

    try {
      if (agent) {
        await api(`/api/brain/agents/${agent.id}`, { method: "PUT", body: JSON.stringify(payload) });
      } else {
        await api("/api/brain/agents", { method: "POST", body: JSON.stringify(payload) });
      }
      setError("");
      onSave();
      onClose();
    } catch (e) { setError(String(e)); }
  }

  return (
    <aside className="drawer wide">
      <div className="drawer-header">
        <div>
          <p className="crumb">Agent 管理</p>
          <h2>{agent ? "编辑 Agent" : "新建 Agent"}</h2>
        </div>
        <button onClick={onClose}><X size={18} /></button>
      </div>
      <div className="form">
        <label>
          名称
          <input
            value={name}
            onChange={(e) => {
              const v = e.target.value;
              setName(v);
              if (!agent && !code.trim()) setCode(autoCode(v));
            }}
            placeholder="如：合同合规审核员"
          />
        </label>
        <label>
          编码
          <input value={code} onChange={(e) => setCode(e.target.value)} placeholder="如：contract_auditor" />
        </label>
        <label>
          描述
          <textarea value={description} onChange={(e) => setDescription(e.target.value)} />
        </label>
        <div className="form-row">
          <label style={{ flex: 1 }}>
            数据源连接器
            <select value={connectorId} onChange={(e) => setConnectorId(e.target.value)}>
              <option value="">请选择...</option>
              {connectors.map((c) => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </label>
          <label style={{ flex: 1 }}>
            本体空间（规则来源）
            <select value={spaceId} onChange={(e) => setSpaceId(e.target.value)}>
              <option value="">请选择...</option>
              {spaces.map((s) => (
                <option key={s.id} value={s.id}>{s.name}</option>
              ))}
            </select>
          </label>
        </div>
        <label>
          审核策略
          <select value={strategyType} onChange={(e) => setStrategyType(e.target.value)}>
            <option value="rule_based">基于规则（引用本体规则）</option>
            <option value="natural_language">自然语言（LLM 自主判断）</option>
          </select>
        </label>
        {strategyType === "rule_based" && (
          <div className="re-nl-panel">
            <p className="re-hint">策略配置 JSON：可指定引用的规则 ID 列表，空数组表示执行全部规则</p>
            <textarea className="re-textarea code" value={strategyConfig} onChange={(e) => setStrategyConfig(e.target.value)} rows={6} />
          </div>
        )}
        {strategyType === "natural_language" && (
          <div className="re-nl-panel">
            <p className="re-hint">用自然语言描述审核要求，LLM 将据此自主判断</p>
            <textarea className="re-textarea" value={strategyConfig} onChange={(e) => setStrategyConfig(e.target.value)} rows={6} placeholder='{"description": "你是一个风控专家。请审核以下业务数据..."}' />
          </div>
        )}
        {!agent && (
          <div className="template-list" style={{ marginTop: 12 }}>
            <p className="re-hint">或从模板创建：</p>
            {AGENT_TEMPLATES.map((tmpl) => (
              <button
                key={tmpl.code}
                className="template-card"
                style={{ textAlign: "left", width: "100%" }}
                onClick={() => {
                  setCode(tmpl.code);
                  setName(tmpl.name);
                  setDescription(tmpl.description);
                  setStrategyType(tmpl.strategy_type);
                  setStrategyConfig(JSON.stringify(tmpl.strategy_config, null, 2));
                }}
              >
                <strong>{tmpl.name}</strong>
                <p>{tmpl.description}</p>
                <span className="template-meta">{tmpl.strategy_type === "rule_based" ? "规则策略" : "自然语言"}</span>
              </button>
            ))}
          </div>
        )}
        {error && <p className="form-error">{error}</p>}
        <button className="primary-button" onClick={save}>
          {agent ? "保存修改" : "创建 Agent"}
        </button>
      </div>
    </aside>
  );
}

// ── Agent 执行结果抽屉 ──

function AgentExecutionDrawer({
  agent,
  result,
  streamSteps,
  streamLoading,
  streamError,
  llmContent,
  suggestionContent,
  onClose,
}: {
  agent: BrainAgent;
  result: AgentExecutionResult | null;
  streamSteps: StreamEvent[];
  streamLoading: boolean;
  streamError: string;
  llmContent: string;
  suggestionContent: string;
  onClose: () => void;
}) {
  const [showChat, setShowChat] = React.useState(false);
  const [chatMessages, setChatMessages] = React.useState<ChatMessage[]>([]);
  const [chatInput, setChatInput] = React.useState("");
  const [chatLoading, setChatLoading] = React.useState(false);
  const [chatStreamContent, setChatStreamContent] = React.useState("");
  const [chatStreaming, setChatStreaming] = React.useState(false);

  // 从 result 构建规则引擎结果上下文（用于对话）
  const ruleResult = result?.rule_result;

  // 发送对话消息（流式）
  async function sendChatMessage() {
    if (!chatInput.trim() || !result) return;

    const userMsg: ChatMessage = {
      role: "user",
      content: chatInput.trim(),
      timestamp: new Date().toISOString(),
    };
    const newMessages = [...chatMessages, userMsg];
    setChatMessages(newMessages);
    setChatInput("");
    setChatLoading(true);
    setChatStreamContent("");
    setChatStreaming(true);

    const history = newMessages.slice(-6).map((m) => ({
      role: m.role,
      content: m.content,
    }));

    const space = agent.space_id
      ? { id: agent.space_id, name: "Agent 空间" }
      : { id: "", name: "" };

    try {
      const response = await fetch(`${API_BASE}/api/brain/rule-engine/chat-stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          space_id: space.id,
          space_name: space.name,
          test_data: result.test_data,
          data_source: "Agent 执行",
          hits: ruleResult?.hits ?? [],
          misses: ruleResult?.misses ?? [],
          all_rules: ruleResult?.all_rules ?? [],
          execution_time_ms: ruleResult?.execution_time_ms ?? 0,
          question: userMsg.content,
          history,
        }),
      });

      if (!response.ok || !response.body) {
        throw new Error("请求失败");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      let fullContent = "";

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split("\n\n");
        buffer = lines.pop() ?? "";

        for (const line of lines) {
          const dataMatch = line.match(/^data: (.+)$/m);
          if (dataMatch) {
            try {
              const evt = JSON.parse(dataMatch[1]);
              if (evt.type === "chunk" && evt.content) {
                fullContent += evt.content;
                setChatStreamContent(fullContent);
              } else if (evt.type === "complete") {
                fullContent = evt.full_content || fullContent;
              } else if (evt.type === "error") {
                throw new Error(evt.message);
              }
            } catch {
              // 忽略解析失败
            }
          }
        }
      }

      setChatMessages((prev) => [
        ...prev,
        { role: "assistant", content: fullContent, timestamp: new Date().toISOString() },
      ]);
    } catch (e) {
      setChatMessages((prev) => [
        ...prev,
        { role: "assistant", content: `❌ 请求失败: ${String(e)}`, timestamp: new Date().toISOString() },
      ]);
    } finally {
      setChatLoading(false);
      setChatStreaming(false);
      setChatStreamContent("");
    }
  }

  // 判断当前处于哪个阶段
  const hasStarted = streamSteps.some((s) => s.type === "start");
  const hasDataGenerated = streamSteps.some((s) => s.type === "data_generated");
  const hasRuleResult = streamSteps.some((s) => s.type === "rule_result");
  const isLlmThinking = streamSteps.some((s) => s.type === "llm_thinking") && !result;
  const isSuggestionGenerating = streamSteps.some((s) => s.type === "suggestion_generating") && !result;

  return (
    <aside className="drawer wide">
      <div className="drawer-header">
        <div>
          <p className="crumb">Agent 执行</p>
          <h2>
            {agent.name}
            {result && !streamLoading && (
              <span style={{ fontSize: 13, color: "var(--muted)", marginLeft: 12 }}>
                {result.strategy === "natural_language"
                  ? result.llm_output?.conclusion ?? "完成"
                  : `命中 ${result.rule_result?.hit_count ?? 0} 条规则`}
              </span>
            )}
          </h2>
        </div>
        <button onClick={onClose}><X size={18} /></button>
      </div>

      <div className="form" style={{ maxHeight: "calc(100vh - 80px)", overflow: "auto" }}>
        {/* 流式过程展示 */}
        {streamLoading && (
          <div className="re-log-section">
            <h4><Clock size={14} /> 执行进度</h4>
            <div className="re-log-process">
              <StreamStepItem
                done={hasStarted}
                active={!hasStarted}
                label="开始执行"
                icon={<Play size={14} />}
              />
              <StreamStepItem
                done={hasDataGenerated}
                active={hasStarted && !hasDataGenerated}
                label="生成合成数据"
                icon={<Zap size={14} />}
              />
              {agent.strategy_type === "natural_language" ? (
                <StreamStepItem
                  done={!!result}
                  active={isLlmThinking}
                  label="LLM 分析中..."
                  icon={<Sparkles size={14} />}
                  spinner={isLlmThinking}
                />
              ) : (
                <>
                  <StreamStepItem
                    done={hasRuleResult}
                    active={hasDataGenerated && !hasRuleResult}
                    label="规则引擎执行"
                    icon={<Scale size={14} />}
                    spinner={hasDataGenerated && !hasRuleResult}
                  />
                  {(hasRuleResult || isSuggestionGenerating) && (
                    <StreamStepItem
                      done={!!result}
                      active={isSuggestionGenerating}
                      label="生成修改建议..."
                      icon={<Sparkles size={14} />}
                      spinner={isSuggestionGenerating}
                    />
                  )}
                </>
              )}
            </div>

            {/* 流式内容实时展示 */}
            {isLlmThinking && llmContent && (
              <div className="re-log-section" style={{ marginTop: 12 }}>
                <h4><Sparkles size={14} /> LLM 正在分析</h4>
                <div className="re-log-code" style={{ whiteSpace: "pre-wrap", lineHeight: 1.7 }}>
                  {llmContent}
                  <span className="cursor-blink">▌</span>
                </div>
              </div>
            )}
            {isSuggestionGenerating && suggestionContent && (
              <div className="re-log-section" style={{ marginTop: 12 }}>
                <h4><Sparkles size={14} /> 正在生成修改建议</h4>
                <div className="re-log-code" style={{ whiteSpace: "pre-wrap", lineHeight: 1.7 }}>
                  {suggestionContent}
                  <span className="cursor-blink">▌</span>
                </div>
              </div>
            )}
          </div>
        )}

        {streamError && (
          <div className="re-log-result-item danger">
            <Ban size={16} />
            <span>执行失败: {streamError}</span>
          </div>
        )}

        {/* 最终结果 */}
        {result && !streamLoading && !streamError && (
          <>
            {/* 输入数据 */}
            <div className="re-log-section">
              <h4><Terminal size={14} /> 输入数据</h4>
              <pre className="re-log-code">{JSON.stringify(result.test_data, null, 2)}</pre>
            </div>

            {/* LLM 自然语言策略结果 */}
            {result.llm_output && (
              <div className="re-log-section">
                <h4><Sparkles size={14} /> LLM 审核结论 {result.llm_model && `(${result.llm_model})`}</h4>
                <div className={`re-log-result-item ${result.llm_output.conclusion === "阻断" ? "danger" : result.llm_output.conclusion === "通过" ? "success" : "warn"}`}>
                  <strong>{result.llm_output.conclusion}</strong>
                  <span>{result.llm_output.summary}</span>
                </div>
                {result.llm_output.findings.length > 0 && (
                  <div style={{ marginTop: 10 }}>
                    <p style={{ fontSize: 13, fontWeight: 500 }}>发现：</p>
                    <ul style={{ fontSize: 13, color: "var(--text)", lineHeight: 1.8 }}>
                      {result.llm_output.findings.map((f, i) => (
                        <li key={i}>{f}</li>
                      ))}
                    </ul>
                  </div>
                )}
                {result.llm_output.suggestions.length > 0 && (
                  <div style={{ marginTop: 10 }}>
                    <p style={{ fontSize: 13, fontWeight: 500 }}>建议：</p>
                    <ul style={{ fontSize: 13, color: "var(--text)", lineHeight: 1.8 }}>
                      {result.llm_output.suggestions.map((s, i) => (
                        <li key={i}>{s}</li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            )}

            {/* 规则引擎策略结果 */}
            {result.rule_result && (
              <div className="re-log-section">
                <h4><Scale size={14} /> 规则引擎结果</h4>
                <div className="re-log-info-grid">
                  <div className="re-log-info-item">
                    <span>命中规则</span>
                    <strong>{result.rule_result.hit_count}</strong>
                  </div>
                  <div className="re-log-info-item">
                    <span>阻断</span>
                    <strong>{result.rule_result.block_count}</strong>
                  </div>
                  <div className="re-log-info-item">
                    <span>总规则</span>
                    <strong>{result.rule_result.total_rules}</strong>
                  </div>
                  <div className="re-log-info-item">
                    <span>耗时</span>
                    <strong>{result.rule_result.execution_time_ms}ms</strong>
                  </div>
                </div>
                {result.rule_result.hits.length > 0 && (
                  <div className="re-log-process" style={{ marginTop: 12 }}>
                    {result.rule_result.hits.map((hit: any, i: number) => (
                      <div key={i} className={`re-log-process-item ${hit.severity}`}>
                        <span className="re-log-process-num">{i + 1}</span>
                        <div className="re-log-process-body">
                          <strong>{hit.rule_name}</strong>
                          <code>{hit.condition}</code>
                          <span className="re-log-process-result">
                            {hit.severity === "block" ? "🚫 阻断" : "⚠️ 建议"} · {hit.result}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* 修改建议 */}
            {result.suggestions && (
              <div className="re-log-section">
                <h4><Sparkles size={14} /> LLM 修改建议</h4>
                <div className="re-log-code" style={{ whiteSpace: "pre-wrap", lineHeight: 1.7 }}>
                  {result.suggestions}
                </div>
              </div>
            )}

            {/* 对话按钮 */}
            <div className="re-log-bar" style={{ marginTop: 16 }}>
              <button className="re-log-btn" onClick={() => setShowChat(true)}>
                <MessageCircle size={14} />
                执行对话
                {chatMessages.length > 0 && (
                  <span className="re-chat-badge">{chatMessages.length}</span>
                )}
              </button>
            </div>
          </>
        )}
      </div>

      {/* 对话面板 */}
      {showChat && result && (
        <AgentChatPanel
          messages={chatMessages}
          input={chatInput}
          onInputChange={setChatInput}
          onSend={sendChatMessage}
          loading={chatLoading}
          streaming={chatStreaming}
          streamContent={chatStreamContent}
          onClose={() => setShowChat(false)}
          result={result}
        />
      )}

      {/* 光标闪烁动画 */}
      <style>{`
        .cursor-blink {
          animation: blink 1s step-end infinite;
          color: var(--tech-blue);
        }
        @keyframes blink {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
      `}</style>
    </aside>
  );
}

// ── 流式步骤项 ──

function StreamStepItem({
  done,
  active,
  label,
  icon,
  spinner,
}: {
  done: boolean;
  active: boolean;
  label: string;
  icon: React.ReactNode;
  spinner?: boolean;
}) {
  return (
    <div
      className={`re-log-process-item ${done ? "success" : active ? "warn" : ""}`}
      style={{ opacity: done || active ? 1 : 0.5 }}
    >
      <span className="re-log-process-num">
        {done ? <CheckCircle size={12} /> : spinner ? <span className="re-spinner" /> : icon}
      </span>
      <div className="re-log-process-body">
        <strong>{label}</strong>
      </div>
    </div>
  );
}

// ── Agent 对话面板 ──

function AgentChatPanel({
  messages,
  input,
  onInputChange,
  onSend,
  loading,
  streaming,
  streamContent,
  onClose,
  result,
}: {
  messages: ChatMessage[];
  input: string;
  onInputChange: (v: string) => void;
  onSend: () => void;
  loading: boolean;
  streaming: boolean;
  streamContent: string;
  onClose: () => void;
  result: AgentExecutionResult;
}) {
  const scrollRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, streaming, streamContent]);

  const hitCount = result.rule_result?.hit_count ?? 0;
  const totalRules = result.rule_result?.total_rules ?? 0;

  return (
    <div className="re-chat-overlay" onClick={onClose}>
      <div className="re-chat-panel" onClick={(e) => e.stopPropagation()}>
        <div className="re-chat-header">
          <div>
            <h4><Bot size={18} /> 执行对话</h4>
            <p>基于本次执行上下文（{hitCount} 命中 / {totalRules} 规则）</p>
          </div>
          <button onClick={onClose}><X size={18} /></button>
        </div>

        {messages.length === 0 && (
          <div className="re-chat-suggestions">
            <p className="re-chat-suggestions-title">你可以问：</p>
            <div className="re-chat-suggestion-list">
              <button onClick={() => onInputChange("为什么这条规则命中了？")}>
                为什么这条规则命中了？
              </button>
              <button onClick={() => onInputChange("如果我修改金额为50万，结果会怎样？")}>
                如果我修改金额为50万，结果会怎样？
              </button>
              <button onClick={() => onInputChange("还有哪些规则没被命中，为什么？")}>
                还有哪些规则没被命中，为什么？
              </button>
              <button onClick={() => onInputChange("总结一下本次审核的结论和建议")}>
                总结一下本次审核的结论和建议
              </button>
            </div>
          </div>
        )}

        <div className="re-chat-messages" ref={scrollRef}>
          {messages.map((msg, i) => (
            <div key={i} className={`re-chat-msg ${msg.role}`}>
              <div className="re-chat-msg-avatar">
                {msg.role === "user" ? <User size={14} /> : <Bot size={14} />}
              </div>
              <div className="re-chat-msg-body">
                <div className="re-chat-msg-content">{msg.content}</div>
                <span className="re-chat-msg-time">{formatTime(msg.timestamp)}</span>
              </div>
            </div>
          ))}
          {streaming && streamContent && (
            <div className="re-chat-msg assistant">
              <div className="re-chat-msg-avatar"><Bot size={14} /></div>
              <div className="re-chat-msg-body">
                <div className="re-chat-msg-content">
                  {streamContent}
                  <span className="cursor-blink">▌</span>
                </div>
              </div>
            </div>
          )}
          {loading && !streaming && (
            <div className="re-chat-msg assistant">
              <div className="re-chat-msg-avatar"><Bot size={14} /></div>
              <div className="re-chat-msg-body">
                <div className="re-chat-msg-loading"><span className="re-spinner" />思考中...</div>
              </div>
            </div>
          )}
        </div>

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
