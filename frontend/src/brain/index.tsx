import React from "react";
import {
  Activity,
  Bot,
  Cable,
  Clock,
  Scale,
} from "lucide-react";
import type { Space } from "./types";
import AgentPanel from "./AgentPanel";
import ConnectorPanel from "./ConnectorPanel";
import RuleEnginePanel from "./RuleEnginePanel";

export type BrainTab = "agents" | "connectors" | "rule-engine" | "executions";

export default function BrainModule({
  spaces,
  activeTab,
}: {
  spaces: Space[];
  activeTab: BrainTab;
}) {
  return (
    <div style={{ height: "100%", overflow: "auto", padding: 20 }}>
      {activeTab === "agents" && <AgentPanel spaces={spaces} />}
      {activeTab === "connectors" && <ConnectorPanel />}
      {activeTab === "rule-engine" && <RuleEnginePanel spaces={spaces} />}
      {activeTab === "executions" && <BrainExecutions spaces={spaces} />}
    </div>
  );
}

function BrainExecutions({ spaces }: { spaces: Space[] }) {
  const [selectedSpaceId, setSelectedSpaceId] = React.useState(spaces[0]?.id ?? "");
  const [executions, setExecutions] = React.useState<Array<Record<string, unknown>>>([]);
  const [loading, setLoading] = React.useState(false);

  React.useEffect(() => {
    if (selectedSpaceId) loadExecutions();
  }, [selectedSpaceId]);

  async function loadExecutions() {
    setLoading(true);
    try {
      const res = await api<Array<Record<string, unknown>>>(
        `/api/brain/rule-engine/executions/${selectedSpaceId}?limit=50`
      );
      setExecutions(res.data ?? []);
    } finally {
      setLoading(false);
    }
  }

  return (
    <section className="resource-panel">
      <div className="toolbar">
        <label style={{ display: "flex", alignItems: "center", gap: 8 }}>
          空间
          <select value={selectedSpaceId} onChange={(e) => setSelectedSpaceId(e.target.value)}>
            {spaces.map((s) => (
              <option key={s.id} value={s.id}>{s.name}</option>
            ))}
          </select>
        </label>
        <button className="icon-button" onClick={loadExecutions} title="刷新">
          <Clock size={16} />
        </button>
      </div>

      {loading ? (
        <p className="muted">加载中...</p>
      ) : executions.length === 0 ? (
        <div className="ontology-empty" style={{ marginTop: 40 }}>
          <Clock size={48} />
          <p>暂无执行记录</p>
          <p className="muted">在「规则引擎」页面执行测试后将在此显示历史记录</p>
        </div>
      ) : (
        <div className="execution-list">
          {executions.map((exec: Record<string, unknown>) => (
            <div key={String(exec.id)} className="execution-card">
              <div className="execution-header">
                <span className="execution-id">{String(exec.id).slice(0, 8)}</span>
                <span className={`status-badge ${exec.status}`}>{String(exec.status)}</span>
                <span className="execution-time">{formatTime(String(exec.created_at))}</span>
              </div>
              <div className="execution-stats">
                <span>命中: {Number(exec.hit_count)}</span>
                <span>阻断: {Number(exec.block_count)}</span>
                <span>建议: {Number(exec.suggest_count)}</span>
              </div>
              <div className="execution-summary">
                {Object.entries(exec.input_summary as Record<string, unknown>).slice(0, 5).map(([k, v]) => (
                  <code key={k}>{k}: {String(v).slice(0, 30)}</code>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

async function api<T>(path: string, options: RequestInit = {}): Promise<{ success: boolean; data: T; error: string | null }> {
  const API_BASE = import.meta.env.VITE_API_BASE ?? "";
  const response = await fetch(`${API_BASE}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers ?? {}),
    },
    ...options,
  });
  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || response.statusText);
  }
  return response.json();
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
