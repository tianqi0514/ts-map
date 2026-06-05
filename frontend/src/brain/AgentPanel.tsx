import React from "react";
import {
  Ban,
  Bot,
  CheckCircle,
  ChevronRight,
  Copy,
  Edit3,
  Eye,
  FileText,
  ListChecks,
  Play,
  Plus,
  RefreshCw,
  Scale,
  Settings,
  Sparkles,
  Terminal,
  Trash2,
  X,
  Zap,
} from "lucide-react";
import type { ApiConnector, Space } from "./types";
import { api } from "./api";

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

type AgentExecutionResult = {
  agent_id: string;
  agent_name: string;
  strategy: string;
  test_data: Record<string, unknown>;
  rule_result?: {
    hit_count: number;
    block_count: number;
    total_rules: number;
    hits: Array<Record<string, unknown>>;
    misses: Array<Record<string, unknown>>;
    execution_time_ms: number;
  };
  llm_output?: {
    conclusion: string;
    summary: string;
    findings: string[];
    suggestions: string[];
  };
  llm_model?: string;
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
  const [execLoading, setExecLoading] = React.useState(false);

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

  async function executeAgent(agent: BrainAgent) {
    setExecuting(agent);
    setExecLoading(true);
    setExecResult(null);
    try {
      const res = await api<AgentExecutionResult>(`/api/brain/agents/${agent.id}/execute`, {
        method: "POST",
      });
      setExecResult(res.data);
    } catch (e) {
      setExecResult({
        agent_id: agent.id,
        agent_name: agent.name,
        strategy: agent.strategy_type,
        test_data: {},
        error: String(e),
      } as AgentExecutionResult);
    } finally {
      setExecLoading(false);
    }
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
          loading={execLoading}
          onClose={() => {
            setExecuting(null);
            setExecResult(null);
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

  // 从名称自动生成编码
  function autoCode(n: string): string {
    return n
      .trim()
      .toLowerCase()
      .replace(/[^\w\s]/g, "")
      .replace(/\s+/g, "_")
      .slice(0, 50) || "agent_" + Date.now();
  }

  async function save() {
    if (!name.trim()) {
      setError("名称不能为空");
      return;
    }
    let finalCode = code.trim();
    if (!finalCode) {
      finalCode = autoCode(name);
      setCode(finalCode);
    }
    if (finalCode.length < 2) {
      setError("编码至少 2 个字符");
      return;
    }
    if (!connectorId) {
      setError("请选择数据源连接器");
      return;
    }
    if (!spaceId) {
      setError("请选择本体空间");
      return;
    }

    let cfg: Record<string, unknown>;
    try {
      cfg = JSON.parse(strategyConfig);
    } catch {
      setError("策略配置必须是合法 JSON");
      return;
    }

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
        await api(`/api/brain/agents/${agent.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        await api("/api/brain/agents", {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }
      setError("");
      onSave();
      onClose();
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <aside className="drawer wide">
      <div className="drawer-header">
        <div>
          <p className="crumb">Agent 管理</p>
          <h2>{agent ? "编辑 Agent" : "新建 Agent"}</h2>
        </div>
        <button onClick={onClose}>
          <X size={18} />
        </button>
      </div>
      <div className="form">
        <label>
          名称
          <input
            value={name}
            onChange={(e) => {
              const v = e.target.value;
              setName(v);
              // 如果是新建且 code 为空，自动根据 name 生成 code
              if (!agent && !code.trim()) {
                setCode(autoCode(v));
              }
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
                <option key={c.id} value={c.id}>
                  {c.name}
                </option>
              ))}
            </select>
          </label>
          <label style={{ flex: 1 }}>
            本体空间（规则来源）
            <select value={spaceId} onChange={(e) => setSpaceId(e.target.value)}>
              <option value="">请选择...</option>
              {spaces.map((s) => (
                <option key={s.id} value={s.id}>
                  {s.name}
                </option>
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
            <textarea
              className="re-textarea code"
              value={strategyConfig}
              onChange={(e) => setStrategyConfig(e.target.value)}
              rows={6}
            />
          </div>
        )}

        {strategyType === "natural_language" && (
          <div className="re-nl-panel">
            <p className="re-hint">用自然语言描述审核要求，LLM 将据此自主判断</p>
            <textarea
              className="re-textarea"
              value={strategyConfig}
              onChange={(e) => setStrategyConfig(e.target.value)}
              rows={6}
              placeholder='{"description": "你是一个风控专家。请审核以下业务数据..."}'
            />
          </div>
        )}

        {/* 预设模板 */}
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
                <span className="template-meta">
                  {tmpl.strategy_type === "rule_based" ? "规则策略" : "自然语言"}
                </span>
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
  loading,
  onClose,
}: {
  agent: BrainAgent;
  result: AgentExecutionResult | null;
  loading: boolean;
  onClose: () => void;
}) {
  return (
    <aside className="drawer wide">
      <div className="drawer-header">
        <div>
          <p className="crumb">Agent 执行</p>
          <h2>
            {agent.name}
            {result && !loading && (
              <span style={{ fontSize: 13, color: "var(--muted)", marginLeft: 12 }}>
                {result.strategy === "natural_language"
                  ? result.llm_output?.conclusion ?? "完成"
                  : `命中 ${result.rule_result?.hit_count ?? 0} 条规则`}
              </span>
            )}
          </h2>
        </div>
        <button onClick={onClose}>
          <X size={18} />
        </button>
      </div>
      <div className="form">
        {loading && (
          <div className="re-empty">
            <span className="re-spinner large" />
            <p>Agent 正在审核数据...</p>
          </div>
        )}

        {result?.error && (
          <div className="re-log-result-item danger">
            <Ban size={16} />
            <span>执行失败: {result.error}</span>
          </div>
        )}

        {result && !loading && !result.error && (
          <>
            {/* 输入数据 */}
            <div className="re-log-section">
              <h4>
                <Terminal size={14} />
                输入数据（来自连接器合成数据）
              </h4>
              <pre className="re-log-code">{JSON.stringify(result.test_data, null, 2)}</pre>
            </div>

            {/* LLM 自然语言策略结果 */}
            {result.llm_output && (
              <div className="re-log-section">
                <h4>
                  <Sparkles size={14} />
                  LLM 审核结论 {result.llm_model && `(${result.llm_model})`}
                </h4>
                <div
                  className={`re-log-result-item ${
                    result.llm_output.conclusion === "阻断" ? "danger" : "warn"
                  }`}
                >
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
                <h4>
                  <Scale size={14} />
                  规则引擎结果
                </h4>
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
          </>
        )}
      </div>
    </aside>
  );
}
